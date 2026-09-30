"""프로필(모델) 비교 실행 — 같은 질문을 2~3개 프로필로 순차 실행해 SQL·결과·elapsed 를 나란히 (PoC 3-C, 2026-09-30).

같은 테이블을 보는 프로필끼리 비교해야 뜻이 있다(GEMINI_SH vs GROQ_SH). 다른 데이터셋 프로필(RETAIL_DEMO)은 SQL 이 당연히 다르다 — 화면이 object_list 가 다르면 경고한다.
행마다 showsql + 생성 SQL 실행. run_select_ai 를 거치므로 이력에 source=COMPARE 로 남는다. SSE 로 프로필 하나 끝날 때마다 흘려보낸다.
"""
from __future__ import annotations

import time

from app.accuracy import _solve
from app.select_ai import get_profile_attributes

MAX_PROFILES = 3


async def compare_profiles(pool, question: str, profiles: list[str], on_progress) -> dict:
    t0 = time.time()
    profiles = [p for p in dict.fromkeys(p for p in profiles if p)][:MAX_PROFILES]
    metas = []
    for p in profiles:
        try:
            a = await get_profile_attributes(pool, p)
            attrs = {r.get("ATTRIBUTE_NAME"): r.get("ATTRIBUTE_VALUE") for r in (a.get("data") or [])}   # get_profile_attributes → {data: [{PROFILE_NAME, ATTRIBUTE_NAME, ATTRIBUTE_VALUE}]}
        except Exception:
            attrs = {}
        metas.append({"profile": p, "model": attrs.get("model"), "provider": attrs.get("provider"), "object_list": attrs.get("object_list")})
    await on_progress("start", {"question": question, "profiles": metas})
    results = []
    for p in profiles:
        await on_progress("step", {"profile": p, "status": "running"})
        r = await _solve(pool, p, question, with_prompt=False, source="COMPARE")
        r["profile"] = p
        results.append(r)
        await on_progress("step", {"profile": p, "status": "done", **r})
    sqls = [" ".join((r.get("sql") or "").split()).lower() for r in results]
    await on_progress("done", {"elapsed_ms": int((time.time() - t0) * 1000), "all_same_sql": len(set(s for s in sqls if s)) == 1 and all(sqls),
                               "fastest": min((r for r in results if r.get("sql")), key=lambda r: r.get("generate_ms") or 1e12, default={}).get("profile")})
    return {"results": results}
