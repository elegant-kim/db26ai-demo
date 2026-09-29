"""저장 질문 프리셋(AI_PROMPT_PRESET) — 예시 질문 드롭다운의 DB 판 (고객사 PoC 확장 1-D, 2026-09-29).

옛 하드코딩(`web/src/lib/nl2sql.ts` EXAMPLE_QUESTIONS)은 `sql/setup/72_poc_prompt_preset_seed.sql` 로 이관했다.
`profile_name` 은 NULL(모든 프로필) 또는 LIKE 패턴(`%SH%`) — 조회 시 `:profile LIKE profile_name` 으로 맞춘다.
"""
from __future__ import annotations

import logging

from app.select_ai import SELECT_AI_ACTIONS, _lob_to_str

logger = logging.getLogger(__name__)

TITLE_MAX = 200
QUESTION_MAX = 2000


def validate(title: str, question: str, action: str) -> str | None:
    if not title or not title.strip():
        return "제목이 비었습니다."
    if len(title) > TITLE_MAX:
        return f"제목은 {TITLE_MAX}자까지입니다."
    if not question or not question.strip():
        return "질문이 비었습니다."
    if len(question) > QUESTION_MAX:
        return f"질문은 {QUESTION_MAX}자까지입니다."
    if action and action not in SELECT_AI_ACTIONS:
        return f"유효하지 않은 action입니다: {action}"
    return None


async def _rows(cur) -> list[dict]:
    cols = [c[0] for c in cur.description]
    out = []
    for row in await cur.fetchall():
        d = {}
        for c, v in zip(cols, row, strict=True):
            if hasattr(v, "read"):
                v = await _lob_to_str(v)
            elif hasattr(v, "isoformat"):
                v = v.isoformat(timespec="seconds") + ("Z" if v.tzinfo is None else "")
            d[c] = v
        out.append(d)
    return out


async def list_presets(pool, profile: str = "") -> list[dict]:
    """프로필에 맞는 프리셋(NULL = 전체 + LIKE 패턴 일치), sort_order · id 순."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            if profile:
                await cur.execute("""SELECT id, profile_name, title, question, action, sort_order, created_at FROM ai_prompt_preset
                                     WHERE profile_name IS NULL OR UPPER(:p) LIKE UPPER(profile_name) ORDER BY sort_order, id""", {"p": profile})
            else:
                await cur.execute("SELECT id, profile_name, title, question, action, sort_order, created_at FROM ai_prompt_preset ORDER BY sort_order, id")
            return await _rows(cur)


async def create_preset(pool, title: str, question: str, action: str = "runsql", profile_name: str | None = None, sort_order: int = 100) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            out = cur.var(int)
            await cur.execute("""INSERT INTO ai_prompt_preset (profile_name, title, question, action, sort_order)
                                 VALUES (:pn, :t, :q, :a, :so) RETURNING id INTO :out""",
                              {"pn": profile_name or None, "t": title.strip(), "q": question.strip(), "a": action or "runsql", "so": sort_order, "out": out})
            await conn.commit()
            v = out.getvalue()
            return int(v[0] if isinstance(v, list) else v)


async def update_preset(pool, preset_id: int, title: str, question: str, action: str = "runsql", profile_name: str | None = None) -> bool:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""UPDATE ai_prompt_preset SET title = :t, question = :q, action = :a, profile_name = :pn WHERE id = :id""",
                              {"t": title.strip(), "q": question.strip(), "a": action or "runsql", "pn": profile_name or None, "id": int(preset_id)})
            n = cur.rowcount
            await conn.commit()
            return n > 0


async def delete_preset(pool, preset_id: int) -> bool:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM ai_prompt_preset WHERE id = :id", {"id": int(preset_id)})
            n = cur.rowcount
            await conn.commit()
            return n > 0
