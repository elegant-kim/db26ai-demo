#!/usr/bin/env python3
"""유통 시연용 샘플 데이터셋 적재 — sql/seed/retail_demo/01~05 를 순서대로 (PoC 3-B).

    ./venv/bin/python scripts/seed_retail_demo.py            # 01→05
    ./venv/bin/python scripts/seed_retail_demo.py teardown   # 09

SQLcl 없이 python-oracledb 로 돌린다. 파일의 `;`/`/` 구분을 단순 규칙으로 자른다(PL/SQL 블록은 `/` 줄까지 한 덩어리).
"""
from __future__ import annotations

import asyncio
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIR = ROOT / "sql" / "seed" / "retail_demo"
sys.path.insert(0, str(ROOT))


def split_statements(text: str) -> list[str]:
    out, buf, in_block = [], [], False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("--") and not buf:
            continue
        if not in_block and re.match(r"^(DECLARE|BEGIN)\b", s, re.I):
            in_block = True
        if in_block:
            if s == "/":
                out.append("\n".join(buf).strip())
                buf = []
                in_block = False
            else:
                buf.append(line)
            continue
        buf.append(line)
        if s.endswith(";"):
            stmt = "\n".join(buf).strip().rstrip(";").strip()
            if stmt and not stmt.startswith("--"):
                out.append(stmt)
            buf = []
    if buf and "".join(buf).strip():
        out.append("\n".join(buf).strip().rstrip(";"))
    return [s for s in out if s and not all(ln.strip().startswith("--") or not ln.strip() for ln in s.splitlines())]


async def run_file(pool, path: pathlib.Path) -> None:
    print(f"── {path.name}")
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for stmt in split_statements(path.read_text(encoding="utf-8")):
                head = " ".join(stmt.split())[:70]
                try:
                    await cur.execute(stmt)
                    if stmt.lstrip().upper().startswith("SELECT"):
                        rows = await cur.fetchall()
                        for r in rows[:12]:
                            print("   ", r)
                    else:
                        print("   OK ", head)
                except Exception as e:
                    msg = str(e).splitlines()[0]
                    if "ORA-00955" in msg or "ORA-01430" in msg:
                        print("   =  ", head, "(이미 있음)")
                    elif "ORA-11553" in msg or "ORA-11561" in msg:
                        pass   # 첫 적재의 DROP Display — 아직 Annotation 이 없어 나는 것. 정상
                    elif "ORA-00942" in msg and "DROP TABLE" in stmt.upper():
                        print("   =  ", head, "(없음)")
                    else:
                        print("   ERR", head, "→", msg[:160])
            await conn.commit()


async def main() -> int:
    from app.database import close_pool, get_pool, init_pool
    await init_pool()
    pool = await get_pool()
    files = [DIR / "09_teardown.sql"] if (len(sys.argv) > 1 and sys.argv[1] == "teardown") else sorted(DIR.glob("0[1-5]_*.sql"))
    for f in files:
        await run_file(pool, f)
    await close_pool()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
