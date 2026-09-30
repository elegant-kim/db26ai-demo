"""답변 피드백 — DBMS_CLOUD_AI.FEEDBACK + AI_FEEDBACK_LOG 를 한 서비스로 (고객사 PoC 확장 1-B, 2026-09-30).

2026-09-30 실측(docs/verified-signatures.md §6):
- FEEDBACK 은 프로필에 **`embedding_model` 속성**이 있어야 한다 — OpenAI 호환(Gemini) 프로필은 없으면 ORA-20048.
  이 DB 는 `gemini-embedding-001` 로 설정했다(51번 §2 참조). 첫 호출이 `<PROFILE>_FEEDBACK_VECINDEX`(+ `$VECTAB`, IVF 테이블)를 만든다.
- 피드백은 **실행된 `SELECT AI …` 문장**(V$MAPPED_SQL)에만 붙는다 — GENERATE 호출은 매핑이 없어 ORA-20000.
  그래서 여기서는 같은 커넥션에서 `SET_PROFILE` → `SELECT AI showsql <질문>` 을 한 번 돌려(LLM 1회, 이미 매핑돼 있으면 생략) 문장을 만든 뒤
  `sql_text` 오버로드로 FEEDBACK 한다. 다른 커넥션에서도 sql_text 로 찾는다.
- 저장 단위는 **질문 텍스트**(`$VECTAB.CONTENT`) — 같은 질문에 다시 add 하면 한 행이 갱신된다. 수정 API 는 없으니 수정 = delete 후 add.
- 프롬프트 주입: showprompt 끝에 "Here are examples of previous successful queries for similar questions" + [{user_prompt, sql_query}] 로 붙는다(2-C 의 diff 앵커).
"""
from __future__ import annotations

import logging
import time

from app.ai_log import _rows
from app.select_ai import _lob_to_str

logger = logging.getLogger(__name__)

FEEDBACK_TYPES = ("positive", "negative")
SOURCES = ("INLINE", "HISTORY", "FEWSHOT", "SCENARIO")


def statement_for(question: str) -> str:
    """피드백이 붙을 SELECT AI 문장 — 질문 한 줄로 정규화(개행·세미콜론은 문장을 끊는다)."""
    q = " ".join((question or "").split()).rstrip(";")
    return f"SELECT AI showsql {q}"


async def feedback_status(pool, profile_name: str) -> dict:
    """환경 탭 배지용 — embedding_model 유무 · 벡터 인덱스 존재 · 인덱스 안 피드백 행 수 · 앱 기록 수."""
    out = {"profile_name": profile_name, "embedding_model": None, "index_name": None, "index_status": None, "index_rows": None, "app_rows": 0, "ready": False}
    if not profile_name:
        return out
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT attribute_value FROM user_cloud_ai_profile_attributes WHERE profile_name = :p AND attribute_name = 'embedding_model'", {"p": profile_name})
            row = await cur.fetchone()
            if row:
                out["embedding_model"] = str(await _lob_to_str(row[0]) or "") or None
            await cur.execute("SELECT index_name, status FROM user_cloud_vector_indexes WHERE index_name = :n", {"n": f"{profile_name.upper()}_FEEDBACK_VECINDEX"})
            row = await cur.fetchone()
            if row:
                out["index_name"], out["index_status"] = row[0], row[1]
                try:
                    await cur.execute(f'SELECT COUNT(*) FROM "{row[0]}$VECTAB"')
                    out["index_rows"] = int((await cur.fetchone())[0])
                except Exception as e:
                    logger.warning("[feedback] VECTAB 행 수 조회 실패 (%s): %s", row[0], e)
            await cur.execute("SELECT COUNT(*) FROM ai_feedback_log WHERE profile_name = :p", {"p": profile_name})
            out["app_rows"] = int((await cur.fetchone())[0])
    out["ready"] = bool(out["embedding_model"])
    return out


async def _ensure_mapped(cur, statement: str) -> str:
    """문장이 V$MAPPED_SQL 에 있으면 sql_id, 없으면 지금 한 번 실행(LLM 1회)해 만든다."""
    await cur.execute("SELECT sql_id FROM v$mapped_sql WHERE sql_text = :t FETCH FIRST 1 ROWS ONLY", {"t": statement})
    row = await cur.fetchone()
    if row:
        return row[0]
    await cur.execute(statement)
    await cur.fetchall()
    await cur.execute("SELECT sql_id FROM v$mapped_sql WHERE sql_text = :t FETCH FIRST 1 ROWS ONLY", {"t": statement})
    row = await cur.fetchone()
    return row[0] if row else ""


async def submit_feedback(pool, log_id: int, feedback_type: str, feedback_content: str = "", corrected_sql: str = "",
                          source: str = "INLINE") -> dict:
    """한 트랜잭션: (기존 피드백 있으면 Oracle delete + 앱 행 삭제) → SELECT AI 문장 확보 → FEEDBACK add → AI_FEEDBACK_LOG INSERT.
    Oracle 호출이 실패하면 앱 행도 남기지 않고 오류를 그대로 올린다(원칙 1-B)."""
    if feedback_type not in FEEDBACK_TYPES:
        raise ValueError("feedback_type 은 positive/negative 만 됩니다.")
    if source not in SOURCES:
        source = "INLINE"
    t0 = time.time()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id, profile_name, question, generated_sql, conversation_id FROM ai_query_log WHERE id = :id", {"id": int(log_id)})
            rows = await _rows(cur)
            if not rows:
                raise LookupError(f"이력이 없습니다: {log_id}")
            log = rows[0]
            profile = log["PROFILE_NAME"] or ""
            question = log["QUESTION"] or ""
            if not profile or not question.strip():
                raise ValueError("프로필 또는 질문이 없는 이력에는 피드백을 붙일 수 없습니다.")
            statement = statement_for(question)
            try:
                await cur.execute("BEGIN DBMS_CLOUD_AI.SET_PROFILE(:p); END;", {"p": profile})
                # 같은 이력에 이미 피드백이 있으면 지우고 다시 넣는다(수정 API 없음)
                await cur.execute("SELECT COUNT(*) FROM ai_feedback_log WHERE log_id = :id", {"id": int(log_id)})
                had = int((await cur.fetchone())[0])
                if had:
                    await cur.execute("BEGIN DBMS_CLOUD_AI.FEEDBACK(profile_name => :p, sql_text => :t, operation => 'delete'); END;", {"p": profile, "t": statement})
                    await cur.execute("DELETE FROM ai_feedback_log WHERE log_id = :id", {"id": int(log_id)})
                sql_id = await _ensure_mapped(cur, statement)
                await cur.execute("""BEGIN DBMS_CLOUD_AI.FEEDBACK(profile_name => :p, sql_text => :t, feedback_type => :ft,
                                     response => :resp, feedback_content => :fc, operation => 'add'); END;""",
                                  {"p": profile, "t": statement, "ft": feedback_type, "resp": corrected_sql or None, "fc": feedback_content or None})
                out = cur.var(int)
                await cur.execute("""INSERT INTO ai_feedback_log (log_id, profile_name, conversation_id, question, generated_sql, sql_id, feedback_type,
                                     feedback_content, corrected_sql, source, updated_at)
                                     VALUES (:log_id, :p, :cid, :q, :gs, :sid, :ft, :fc, :cs, :src, CASE WHEN :had > 0 THEN SYSTIMESTAMP END)
                                     RETURNING id INTO :out""",
                                  {"log_id": int(log_id), "p": profile, "cid": log["CONVERSATION_ID"], "q": question, "gs": log["GENERATED_SQL"],
                                   "sid": sql_id or None, "ft": feedback_type, "fc": (feedback_content or "")[:4000] or None, "cs": corrected_sql or None,
                                   "src": source, "had": had, "out": out})
                await conn.commit()
                v = out.getvalue()
                fid = int(v[0] if isinstance(v, list) else v)
            except Exception:
                await conn.rollback()
                raise
    return {"feedback_id": fid, "log_id": int(log_id), "profile_name": profile, "feedback_type": feedback_type, "statement": statement,
            "sql_id": sql_id, "replaced": bool(had), "elapsed_ms": int((time.time() - t0) * 1000)}


async def delete_feedback(pool, feedback_id: int) -> dict:
    """Oracle FEEDBACK(delete) + 앱 행 삭제. 같은 질문의 다른 앱 행이 남아 있어도 Oracle 쪽은 질문 단위라 같이 지워진다(그 사실을 응답에)."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id, log_id, profile_name, question FROM ai_feedback_log WHERE id = :id", {"id": int(feedback_id)})
            rows = await _rows(cur)
            if not rows:
                raise LookupError(f"피드백이 없습니다: {feedback_id}")
            f = rows[0]
            statement = statement_for(f["QUESTION"] or "")
            try:
                await cur.execute("BEGIN DBMS_CLOUD_AI.SET_PROFILE(:p); END;", {"p": f["PROFILE_NAME"]})
                await cur.execute("BEGIN DBMS_CLOUD_AI.FEEDBACK(profile_name => :p, sql_text => :t, operation => 'delete'); END;", {"p": f["PROFILE_NAME"], "t": statement})
                await cur.execute("DELETE FROM ai_feedback_log WHERE id = :id", {"id": int(feedback_id)})
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise
    return {"deleted": int(feedback_id), "log_id": f["LOG_ID"]}


async def list_feedback(pool, profile_name: str = "", limit: int = 200) -> list[dict]:
    """등록된 피드백 목록(2-A 의 목록 카드에서도 쓴다)."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            where = "WHERE profile_name = :p" if profile_name else ""
            binds = {"p": profile_name} if profile_name else {}
            await cur.execute(f"""SELECT id, log_id, profile_name, feedback_type, DBMS_LOB.SUBSTR(question, 300, 1) AS question, feedback_content,
                                         CASE WHEN corrected_sql IS NOT NULL THEN 1 ELSE 0 END AS has_corrected, source, created_at, updated_at
                                  FROM ai_feedback_log {where} ORDER BY id DESC FETCH FIRST {int(limit)} ROWS ONLY""", binds)
            return await _rows(cur)
