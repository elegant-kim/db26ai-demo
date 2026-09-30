"""Few-shot 일괄 등록 — 고객이 만든 (질문, SQL, 설명) 파일을 positive 피드백으로 한꺼번에 (고객사 PoC 확장 2-A, 2026-09-30).

흐름: 파일(CSV/JSON/XLSX) 파싱 → 각 SQL 문법 검증(EXPLAIN PLAN) → 행마다 FEEDBACK(positive, response => SQL, feedback_content => 설명).
FEEDBACK 은 실행된 `SELECT AI` 문장에만 붙으므로(app/feedback.py 참조) 행마다 `SELECT AI showsql <질문>` 이 한 번 돈다 — **행당 LLM 1회, 수 초**.
그래서 등록은 SSE 로 행 단위 진행을 흘려보내고, 실패 행만 다시 보낼 수 있다.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import time
import uuid

from app.feedback import _ensure_mapped, statement_for
from app.select_ai import _insert_query_log, profile_model

logger = logging.getLogger(__name__)

# 헤더 이름은 느슨하게 받는다 — 고객 파일은 우리가 정한 이름을 안 쓴다
_Q_KEYS = ("question", "질문", "prompt", "user_prompt", "자연어")
_S_KEYS = ("sql", "query", "sql_query", "정답sql", "정답 sql", "answer")
_N_KEYS = ("note", "설명", "feedback_content", "comment", "사유", "memo")

TEMPLATE_CSV = "question,sql,note\n면수별 전시상태별 매출 금액은?,\"SELECT d.face_count, d.display_state, SUM(s.amount) FROM sales s JOIN displays d ON d.display_id = s.display_id GROUP BY d.face_count, d.display_state\",진열 면수와 전시상태 기준 집계\n"


def _pick(row: dict, keys: tuple[str, ...]) -> str:
    low = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
    for k in keys:
        if k in low and low[k] is not None:
            return str(low[k]).strip()
    return ""


def _normalize(records: list[dict]) -> list[dict]:
    out = []
    for i, r in enumerate(records, start=1):
        q, s, n = _pick(r, _Q_KEYS), _pick(r, _S_KEYS), _pick(r, _N_KEYS)
        err = None
        if not q:
            err = "질문(question) 이 비었습니다"
        elif not s:
            err = "SQL 이 비었습니다"
        out.append({"row": i, "question": q, "sql": s.rstrip(";").strip(), "note": n, "error": err, "valid": None})
    return out


def parse_file(filename: str, content: bytes) -> tuple[list[dict], list[str]]:
    """(행 목록, 감지한 헤더). CSV 는 BOM 허용, JSON 은 배열 또는 {rows:[…]}, XLSX 는 첫 시트 첫 행이 헤더."""
    name = (filename or "").lower()
    if name.endswith(".json"):
        data = json.loads(content.decode("utf-8-sig"))
        records = data.get("rows") if isinstance(data, dict) else data
        if not isinstance(records, list):
            raise ValueError("JSON 은 객체 배열이거나 {\"rows\": [...]} 여야 합니다")
        headers = sorted({str(k) for r in records if isinstance(r, dict) for k in r})
        return _normalize([r for r in records if isinstance(r, dict)]), headers
    if name.endswith(".xlsx"):
        import openpyxl  # noqa: PLC0415 — 선택 의존성, 이 경로에서만
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return [], []
        headers = [str(h).strip() if h is not None else f"col{i}" for i, h in enumerate(rows[0], start=1)]
        records = [dict(zip(headers, r, strict=False)) for r in rows[1:] if any(v not in (None, "") for v in r)]
        return _normalize(records), headers
    # CSV (기본)
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    records = [r for r in reader if any((v or "").strip() for v in r.values() if isinstance(v, str))]
    return _normalize(records), list(reader.fieldnames or [])


async def validate_rows(pool, rows: list[dict]) -> list[dict]:
    """각 SQL 을 EXPLAIN PLAN 으로 문법·객체 검증 — 실행하지 않는다. SELECT/WITH 만 허용."""
    out = []
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for r in rows:
                r = dict(r)
                if r.get("error"):
                    r["valid"] = False
                    out.append(r)
                    continue
                sql = r["sql"].strip().rstrip(";")
                up = sql.upper()
                if not (up.startswith("SELECT") or up.startswith("WITH")):
                    r["valid"], r["error"] = False, "SELECT/WITH 문만 등록할 수 있습니다"
                    out.append(r)
                    continue
                sid = f"FS_{uuid.uuid4().hex[:12]}"
                try:
                    await cur.execute(f"EXPLAIN PLAN SET STATEMENT_ID = '{sid}' FOR {sql}")
                    r["valid"], r["error"] = True, None
                except Exception as e:
                    r["valid"], r["error"] = False, str(e).splitlines()[0][:300]
                finally:
                    try:
                        await cur.execute("DELETE FROM plan_table WHERE statement_id = :s", {"s": sid})
                        await conn.commit()
                    except Exception as e:
                        logger.warning("[fewshot] plan_table 정리 실패: %s", e)
                out.append(r)
    return out


async def register_rows(pool, profile_name: str, rows: list[dict], on_progress) -> dict:
    """행마다: SELECT AI 문장 확보(매핑 없으면 LLM 1회) → FEEDBACK positive(response=SQL) → AI_FEEDBACK_LOG(source FEWSHOT).
    on_progress(event, data): 'row' 마다 결과, 끝에 'done'."""
    t_all = time.time()
    ok = failed = 0
    model = await profile_model(pool, profile_name)
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("BEGIN DBMS_CLOUD_AI.SET_PROFILE(:p); END;", {"p": profile_name})
            for r in rows:
                t0 = time.time()
                q, sql, note = (r.get("question") or "").strip(), (r.get("sql") or "").strip().rstrip(";"), (r.get("note") or "").strip()
                res = {"row": r.get("row"), "question": q[:120]}
                if not q or not sql:
                    failed += 1
                    res.update({"ok": False, "error": "질문 또는 SQL 이 비었습니다", "elapsed_ms": 0})
                    await on_progress("row", res)
                    continue
                statement = statement_for(q)
                try:
                    sql_id = await _ensure_mapped(cur, statement)
                    gen_ms = int((time.time() - t0) * 1000)
                    # 같은 질문의 옛 앱 행은 정리(Oracle 쪽은 add 가 덮어쓴다)
                    await cur.execute("DELETE FROM ai_feedback_log WHERE profile_name = :p AND source = 'FEWSHOT' AND DBMS_LOB.SUBSTR(question, 4000, 1) = :q", {"p": profile_name, "q": q})
                    await cur.execute("""BEGIN DBMS_CLOUD_AI.FEEDBACK(profile_name => :p, sql_text => :t, feedback_type => 'positive',
                                         response => :resp, feedback_content => :fc, operation => 'add'); END;""",
                                      {"p": profile_name, "t": statement, "resp": sql, "fc": note or None})
                    out = cur.var(int)
                    await cur.execute("""INSERT INTO ai_feedback_log (log_id, profile_name, question, generated_sql, sql_id, feedback_type, feedback_content, corrected_sql, source)
                                         VALUES (NULL, :p, :q, :gs, :sid, 'positive', :fc, :cs, 'FEWSHOT') RETURNING id INTO :out""",
                                      {"p": profile_name, "q": q, "gs": sql, "sid": sql_id or None, "fc": note or None, "cs": sql, "out": out})
                    await conn.commit()
                    v = out.getvalue()
                    fid = int(v[0] if isinstance(v, list) else v)
                    ok += 1
                    res.update({"ok": True, "feedback_id": fid, "elapsed_ms": int((time.time() - t0) * 1000), "generate_ms": gen_ms})
                except Exception as e:
                    await conn.rollback()
                    failed += 1
                    res.update({"ok": False, "error": str(e).splitlines()[0][:300], "elapsed_ms": int((time.time() - t0) * 1000)})
                    logger.warning("[fewshot] 등록 실패 row=%s: %s", r.get("row"), e)
                await _insert_query_log(conn, source="FEWSHOT", profile_name=profile_name, action="showsql", question=q,
                                        generated_sql=sql if res.get("ok") else None, status="SUCCEEDED" if res.get("ok") else "FAILED",
                                        error_msg=res.get("error"), elapsed_ms=res["elapsed_ms"], model=model)
                await on_progress("row", res)
    summary = {"ok": ok, "failed": failed, "total": len(rows), "elapsed_ms": int((time.time() - t_all) * 1000)}
    await on_progress("done", summary)
    return summary


async def purge_profile_feedback(pool, profile_name: str) -> dict:
    """프로필의 피드백 전부 삭제 — 벡터 인덱스($VECTAB 의 질문마다 FEEDBACK delete) + 앱 행. 앱 밖에서 넣은 것도 지운다."""
    idx = f"{profile_name.upper()}_FEEDBACK_VECINDEX"
    removed_oracle = 0
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("BEGIN DBMS_CLOUD_AI.SET_PROFILE(:p); END;", {"p": profile_name})
            questions: list[str] = []
            try:
                await cur.execute(f'SELECT content FROM "{idx}$VECTAB"')
                for (c,) in await cur.fetchall():
                    questions.append(str(await c.read() if hasattr(c, "read") else c))
            except Exception as e:
                logger.warning("[fewshot] %s$VECTAB 조회 실패(인덱스 없음?): %s", idx, e)
            for q in questions:
                try:
                    await cur.execute("BEGIN DBMS_CLOUD_AI.FEEDBACK(profile_name => :p, sql_text => :t, operation => 'delete'); END;",
                                      {"p": profile_name, "t": statement_for(q)})
                    removed_oracle += 1
                except Exception as e:
                    logger.warning("[fewshot] FEEDBACK delete 실패 (%s): %s", q[:40], e)
            await cur.execute("DELETE FROM ai_feedback_log WHERE profile_name = :p", {"p": profile_name})
            removed_app = cur.rowcount
            await conn.commit()
    return {"profile_name": profile_name, "removed_oracle": removed_oracle, "removed_app": removed_app, "index_questions": len(questions)}
