"""Select AI 호출 이력(AI_QUERY_LOG) 조회 — 「이력」 서브탭(고객사 PoC 확장 1-C, 2026-09-29).

기록은 app/select_ai.py 의 run_select_ai() / execute_raw_sql() 이 하고, 여기는 **읽기만** 한다.
필터는 전부 바인드 변수 — 질문 LIKE 는 대소문자 무시(UPPER), 기간은 datetime-local 문자열(YYYY-MM-DDTHH:MI) 그대로 받는다.
피드백은 AI_FEEDBACK_LOG 의 **가장 최근 한 건**을 조인해 👍/👎 로 보여준다(1-B 가 쓰기를 맡는다).
"""
from __future__ import annotations

import logging

from app.select_ai import _lob_to_str

logger = logging.getLogger(__name__)

PAGE_SIZE_MAX = 100
VALID_STATUS = {"", "SUCCEEDED", "FAILED"}
VALID_FEEDBACK = {"", "positive", "negative", "any", "none"}

# 최근 피드백 한 건 — 같은 log_id 에 여러 건이면 created_at 이 가장 늦은 것
_FEEDBACK_JOIN = """
LEFT JOIN (
  SELECT f.log_id, f.id AS feedback_id, f.feedback_type, f.feedback_content,
         ROW_NUMBER() OVER (PARTITION BY f.log_id ORDER BY f.created_at DESC, f.id DESC) rn
  FROM   ai_feedback_log f
) fb ON fb.log_id = l.id AND fb.rn = 1"""


def _where(q: str, date_from: str, date_to: str, profile: str, action: str, status: str, feedback: str) -> tuple[str, dict]:
    conds, binds = [], {}
    if q:
        conds.append("UPPER(DBMS_LOB.SUBSTR(l.question, 4000, 1)) LIKE '%' || UPPER(:q) || '%'")
        binds["q"] = q
    if date_from:
        conds.append("l.started_at >= TO_TIMESTAMP(:date_from, 'YYYY-MM-DD\"T\"HH24:MI')")
        binds["date_from"] = date_from[:16]
    if date_to:
        conds.append("l.started_at < TO_TIMESTAMP(:date_to, 'YYYY-MM-DD\"T\"HH24:MI') + INTERVAL '1' MINUTE")
        binds["date_to"] = date_to[:16]
    if profile:
        conds.append("l.profile_name = :profile")
        binds["profile"] = profile
    if action:
        conds.append("l.action = :action")
        binds["action"] = action
    if status:
        conds.append("l.status = :status")
        binds["status"] = status
    if feedback == "any":
        conds.append("fb.feedback_id IS NOT NULL")
    elif feedback == "none":
        conds.append("fb.feedback_id IS NULL")
    elif feedback in ("positive", "negative"):
        conds.append("fb.feedback_type = :feedback")
        binds["feedback"] = feedback
    return (" WHERE " + " AND ".join(conds)) if conds else "", binds


async def _rows(cur) -> list[dict]:
    cols = [c[0] for c in cur.description]
    out = []
    for row in await cur.fetchall():
        d = {}
        for c, v in zip(cols, row, strict=True):
            if hasattr(v, "read"):
                v = await _lob_to_str(v)
            elif hasattr(v, "isoformat"):
                v = v.isoformat(sep=" ", timespec="seconds")
            d[c] = v
        out.append(d)
    return out


async def list_query_log(pool, q: str = "", date_from: str = "", date_to: str = "", profile: str = "", action: str = "",
                         status: str = "", feedback: str = "", page: int = 1, size: int = 20) -> dict:
    """이력 표 한 쪽. 최신순. 반환: rows · total · page · size · sql(화면의 「조회 SQL」)."""
    size = max(1, min(int(size), PAGE_SIZE_MAX))
    page = max(1, int(page))
    where, binds = _where(q, date_from, date_to, profile, action, status, feedback)
    base = f"FROM ai_query_log l{_FEEDBACK_JOIN}{where}"
    sql_rows = f"""SELECT l.id, l.started_at, l.source, l.profile_name, l.action,
       DBMS_LOB.SUBSTR(l.question, 300, 1) AS question, l.status, l.elapsed_ms, l.conversation_id,
       l.row_count, l.model, fb.feedback_type, fb.feedback_id
{base}
ORDER BY l.id DESC
OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(f"SELECT COUNT(*) {base}", binds)
            total = int((await cur.fetchone())[0])
            await cur.execute(sql_rows, {**binds, "off": (page - 1) * size, "lim": size})
            rows = await _rows(cur)
    shown = sql_rows
    for k, v in binds.items():
        shown = shown.replace(f":{k}", f"'{str(v).replace(chr(39), chr(39) * 2)}'")
    return {"rows": rows, "total": total, "page": page, "size": size, "sql": shown}


async def get_query_log(pool, log_id: int) -> dict | None:
    """한 건 상세 — 질문·생성 SQL·답변 앞부분·오류 전문 + 그 건의 피드백 전부(최신순)."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""SELECT id, started_at, source, profile_name, action, question, generated_sql, response_text, status,
                                        error_msg, elapsed_ms, conversation_id, row_count, model, sql_id, created_by
                                 FROM ai_query_log WHERE id = :id""", {"id": int(log_id)})
            rows = await _rows(cur)
            if not rows:
                return None
            await cur.execute("""SELECT id, feedback_type, feedback_content, corrected_sql, source, created_at, updated_at
                                 FROM ai_feedback_log WHERE log_id = :id ORDER BY created_at DESC, id DESC""", {"id": int(log_id)})
            feedback = await _rows(cur)
    return {**rows[0], "feedback": feedback}


async def query_log_summary(pool, profile: str = "") -> dict:
    """상단 요약 카드 + 프로필(모델)별 평균 elapsed (3-C 의 절반). 프로필을 주면 그 프로필만."""
    where = " WHERE l.profile_name = :profile" if profile else ""
    binds = {"profile": profile} if profile else {}
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(f"""SELECT COUNT(*) total,
                                         SUM(CASE WHEN l.status = 'SUCCEEDED' THEN 1 ELSE 0 END) succeeded,
                                         ROUND(AVG(CASE WHEN l.status = 'SUCCEEDED' THEN l.elapsed_ms END)) avg_ms,
                                         MAX(l.elapsed_ms) max_ms,
                                         COUNT(DISTINCT fb.log_id) feedback_logs,
                                         SUM(CASE WHEN fb.feedback_type = 'positive' THEN 1 ELSE 0 END) positive,
                                         SUM(CASE WHEN fb.feedback_type = 'negative' THEN 1 ELSE 0 END) negative,
                                         MIN(l.started_at) first_at, MAX(l.started_at) last_at
                                  FROM ai_query_log l{_FEEDBACK_JOIN}{where}""", binds)
            s = (await _rows(cur))[0]
            await cur.execute(f"""SELECT l.profile_name, MAX(l.model) AS model, COUNT(*) n,
                                         SUM(CASE WHEN l.status = 'SUCCEEDED' THEN 1 ELSE 0 END) succeeded,
                                         ROUND(AVG(CASE WHEN l.status = 'SUCCEEDED' THEN l.elapsed_ms END)) avg_ms,
                                         MAX(l.elapsed_ms) max_ms
                                  FROM ai_query_log l{where}
                                  GROUP BY l.profile_name ORDER BY n DESC""", binds)
            by_profile = await _rows(cur)
            await cur.execute(f"""SELECT l.action, COUNT(*) n, ROUND(AVG(CASE WHEN l.status = 'SUCCEEDED' THEN l.elapsed_ms END)) avg_ms
                                  FROM ai_query_log l{where} GROUP BY l.action ORDER BY n DESC""", binds)
            by_action = await _rows(cur)
    total = int(s["TOTAL"] or 0)
    succeeded = int(s["SUCCEEDED"] or 0)
    return {
        "total": total, "succeeded": succeeded, "failed": total - succeeded,
        "success_rate": round(succeeded / total * 100, 1) if total else None,
        "avg_ms": s["AVG_MS"], "max_ms": s["MAX_MS"],
        "feedback_logs": int(s["FEEDBACK_LOGS"] or 0), "positive": int(s["POSITIVE"] or 0), "negative": int(s["NEGATIVE"] or 0),
        "feedback_rate": round(int(s["FEEDBACK_LOGS"] or 0) / total * 100, 1) if total else None,
        "first_at": s["FIRST_AT"], "last_at": s["LAST_AT"],
        "by_profile": by_profile, "by_action": by_action,
    }
