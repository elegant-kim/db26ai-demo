"""정확도 개선 시나리오 — 같은 질문을 ① Annotation 끔 → ② Annotation 켬 → ③ 피드백 반영 순으로 풀어 나란히 (고객사 PoC 확장 2-B·2-C, 2026-09-30).

방식: Annotation 을 DDL 로 뗐다 붙이지 않고 **프로필 속성 `annotations`·`comments` 를 `SET_ATTRIBUTE` 로 잠시 끄고 켠다**
(요청서 2-B 의 권고 — 복원이 확실하고 다른 테이블을 건드리지 않는다). 끝나면(실패해도) 원래 값으로 되돌린다.
③ 은 ②의 SQL(또는 사용자가 준 정답 SQL)을 positive 피드백으로 넣고 같은 질문을 다시 푼다 — 프롬프트 끝에 예시가 주입되고
(2-C: ②·③ 의 showprompt 를 화면이 diff 로 보여준다) LLM 이 그 예시를 그대로 돌려주는 것이 보인다. keep_feedback 이 아니면 피드백은 지운다.
행마다 LLM 이 여러 번 돌아(showsql·showprompt ×2·피드백 매핑) 1분 안팎 → SSE.
"""
from __future__ import annotations

import logging
import time

from app.feedback import delete_feedback, submit_feedback
from app.select_ai import _lob_to_str, execute_raw_sql, run_select_ai

logger = logging.getLogger(__name__)

STEPS = (
    (1, "① Annotation 없이", "annotations=false · comments=false — LLM 이 컬럼 이름만 보고 SQL 을 만든다"),
    (2, "② Annotation 적용", "annotations=true · comments=true — 컬럼의 한국어 설명이 프롬프트에 실린다"),
    (3, "③ 피드백 반영", "②의 SQL 을 positive 피드백으로 등록한 뒤 같은 질문 — 프롬프트 끝에 예시가 주입된다"),
)


async def _get_attr(pool, profile: str, name: str) -> str | None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT attribute_value FROM user_cloud_ai_profile_attributes WHERE profile_name = :p AND attribute_name = :a", {"p": profile, "a": name})
            row = await cur.fetchone()
            return str(await _lob_to_str(row[0])) if row else None


async def _set_attr(pool, profile: str, name: str, value: str) -> None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("BEGIN DBMS_CLOUD_AI.SET_ATTRIBUTE(profile_name => :p, attribute_name => :a, attribute_value => :v); END;",
                              {"p": profile, "a": name, "v": value})


async def _solve(pool, profile: str, question: str, with_prompt: bool, source: str = "SCENARIO") -> dict:
    """showsql → (showprompt) → 생성 SQL 실행(SELECT 만). 한 단계의 결과."""
    out: dict = {"sql": None, "prompt": None, "rows": None, "row_count": None, "elapsed_ms": 0, "run_error": None, "log_id": None}
    t0 = time.time()
    r = await run_select_ai(pool, question, "showsql", profile, source=source)
    out["log_id"] = r.get("log_id")
    if r.get("error"):
        out["error"] = r["error"]
        out["elapsed_ms"] = int((time.time() - t0) * 1000)
        return out
    out["sql"] = str(r["result"] or "").strip()
    out["generate_ms"] = r["elapsed_ms"]
    if with_prompt:
        p = await run_select_ai(pool, question, "showprompt", profile, source=source)
        out["prompt"] = None if p.get("error") else str(p["result"] or "")
    if out["sql"]:
        res = await execute_raw_sql(pool, out["sql"])
        if res.get("error"):
            out["run_error"] = res["error"]
        else:
            out["row_count"] = res.get("row_count")
            out["rows"] = {"columns": res.get("columns", []), "rows": res.get("data", [])[:5]}
    out["elapsed_ms"] = int((time.time() - t0) * 1000)
    return out


async def run_scenario(pool, profile: str, question: str, corrected_sql: str = "", keep_feedback: bool = False, on_progress=None) -> dict:
    async def emit(ev, data):
        if on_progress:
            await on_progress(ev, data)

    orig = {k: await _get_attr(pool, profile, k) for k in ("annotations", "comments")}
    await emit("start", {"profile": profile, "question": question, "original": orig, "steps": [{"n": n, "title": t, "desc": d} for n, t, d in STEPS]})
    results: dict[int, dict] = {}
    feedback_id = None
    t_all = time.time()
    try:
        # ① 끄고
        await _set_attr(pool, profile, "annotations", "false")
        await _set_attr(pool, profile, "comments", "false")
        await emit("step", {"n": 1, "status": "running"})
        results[1] = await _solve(pool, profile, question, with_prompt=False)
        await emit("step", {"n": 1, "status": "done", **results[1]})
        # ② 켜고
        await _set_attr(pool, profile, "annotations", "true")
        await _set_attr(pool, profile, "comments", "true")
        await emit("step", {"n": 2, "status": "running"})
        results[2] = await _solve(pool, profile, question, with_prompt=True)
        await emit("step", {"n": 2, "status": "done", **results[2]})
        # ③ 피드백 → 다시
        await emit("step", {"n": 3, "status": "running", "note": "피드백 등록 중 (SELECT AI 매핑 + FEEDBACK)"})
        base_sql = (corrected_sql or results[2].get("sql") or "").strip()
        if results[2].get("log_id") and base_sql:
            fb = await submit_feedback(pool, results[2]["log_id"], "positive", "정확도 시나리오 ③", base_sql, source="SCENARIO")
            feedback_id = fb["feedback_id"]
            results[3] = await _solve(pool, profile, question, with_prompt=True)
            results[3]["feedback_id"] = feedback_id
        else:
            results[3] = {"error": "②에서 SQL 을 얻지 못해 피드백을 등록할 수 없습니다", "elapsed_ms": 0}
        await emit("step", {"n": 3, "status": "done", **results[3]})
    finally:
        restored = {}
        for k, v in orig.items():
            try:
                await _set_attr(pool, profile, k, v if v is not None else "true")
                restored[k] = v
            except Exception as e:
                logger.warning("[accuracy] 속성 복원 실패 %s: %s", k, e)
                restored[k] = f"복원 실패: {e}"
        kept = keep_feedback
        if feedback_id and not keep_feedback:
            try:
                await delete_feedback(pool, feedback_id)
            except Exception as e:
                logger.warning("[accuracy] 시나리오 피드백 삭제 실패: %s", e)
                kept = True
        summary = {"restored": restored, "feedback_id": feedback_id, "feedback_kept": kept, "elapsed_ms": int((time.time() - t_all) * 1000),
                   "same_2_3": bool(results.get(2, {}).get("sql")) and _norm(results.get(2, {}).get("sql")) == _norm(results.get(3, {}).get("sql"))}
        await emit("done", summary)
    return {"steps": results, **summary}


def _norm(sql: str | None) -> str:
    return " ".join((sql or "").split()).rstrip(";").lower()
