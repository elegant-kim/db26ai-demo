#!/usr/bin/env python3
"""docs/design/03_API_명세서.md 생성기 — app/routes.py + app/routers/*.py 의 라우트·docstring 이 정본.

    ./venv/bin/python scripts/gen_api_doc.py
"""
from __future__ import annotations

import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = [ROOT / "app" / "routes.py", *sorted((ROOT / "app" / "routers").glob("*.py"))]
OUT = ROOT / "docs" / "design" / "03_API_명세서.md"

GROUPS = [
    ("공통", ["/health", "/llm/providers"]),
    ("① NL2SQL (Select AI)", ["/ask", "/profiles", "/set-profile", "/apply-annotations", "/remove-annotations", "/schema-info", "/explain-plan", "/execute-sql"]),
    ("② AI Vector Search — 검색·문서", ["/vector/upload", "/vector/search", "/vector/documents", "/vector/index-info", "/vector/embedding-info", "/vector/visualize", "/vector/recent-queries", "/vector/explain-plan"]),
    ("② AI Vector Search — 테이블 관리", ["/vector/drop-tables", "/vector/create-tables", "/vector/table-definition", "/vector/table-data", "/vector/table-indexes"]),
    ("② 임베딩 · ONNX 모델", ["/vector/embedding-config", "/vector/onnx-models"]),
    ("③ JSON Relational Duality", ["/duality/"]),
    ("④ Property Graph", ["/graph/"]),
    ("⑤ 개발생산성 향상", ["/productivity/"]),
    ("⑥ 기타 부가 기능 (AWR)", ["/awr/"]),
    ("매뉴얼", ["/guide/"]),
]


def scan(path: pathlib.Path):
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    prefix = ""
    m = re.search(r'APIRouter\(prefix="(/api[^"]*)"', src)
    if m:
        prefix = m.group(1)[len("/api"):]
    models, eps = {}, []
    for n in tree.body:
        if isinstance(n, ast.ClassDef) and any(getattr(b, "id", "") == "BaseModel" for b in n.bases):
            fields = []
            for st in n.body:
                if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                    d = f" = {ast.unparse(st.value)}" if st.value is not None else " (필수)"
                    fields.append(f"{st.target.id}: {ast.unparse(st.annotation)}{d}")
            models[n.name] = fields
    for n in tree.body:
        if not isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for dec in n.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                continue
            if getattr(dec.func.value, "id", "") != "router":
                continue
            method = dec.func.attr.upper()
            path_ = prefix + (dec.args[0].value if dec.args else "?")
            doc = (ast.get_docstring(n) or "").splitlines()
            req = None
            for a in n.args.args:
                if a.annotation is not None:
                    ann = ast.unparse(a.annotation)
                    if ann in models or ann in ("Request", "UploadFile"):
                        req = ann
            eps.append({"method": method, "path": path_, "doc": doc[0] if doc else "", "req": req,
                        "impl": f"{path.relative_to(ROOT)}:{n.lineno}"})
    return models, eps


models, eps = {}, []
for f in FILES:
    m, e = scan(f)
    models.update(m)
    eps.extend(e)

lines = [f"""# API 명세서

> **정본은 라우트 정의와 docstring 이다** (`app/routes.py` + `app/routers/*.py`). 이 문서는
> `scripts/gen_api_doc.py` 가 생성한다 — **손으로 고치지 말고 코드를 고친 뒤 다시 생성할 것.**
> 엔드포인트를 추가·변경하면 같은 커밋에서 이 문서와 `CLAUDE.md` API 목록을 함께 갱신한다.
> 전체 **{len(eps)}개** 엔드포인트 · 공통 prefix `/api`

## 공통 규약

| 항목 | 내용 |
|---|---|
| Prefix | 모든 경로에 `/api` 가 붙는다 |
| 성공 응답 | 대부분 `{{"success": true, ...}}`. 일부는 `success` 없이 데이터만 반환 |
| 실패 응답 | `JSONResponse(status_code=4xx/5xx, content={{"success": false, "error": "..."}})` |
| DB 미연결 | `503` + `"데이터베이스에 연결되지 않았습니다."` |
| 미정의 `/api/*` | `404` JSON (SPA 셸을 주지 않는다 — `main.py` catch-all) |
| 타임아웃 | DB call 120초 = 프론트엔드 fetch 타임아웃 |
| SSE | `POST /api/vector/upload`, `POST /api/awr/analyze` 만 `text/event-stream` |

### ⚠ 결과 배열 키가 엔드포인트마다 다르다 (부채 D11)

`data`(execute-sql·duality·recent-queries) / `chunks`(vector/search) / `sql_data`·`pgq_data`(graph/compare) /
`models`·`profiles`·`views`. **새 화면은 `web/src/lib/normalize.ts` 한 층이 흡수한다** — 키 이름을 아는 유일한 곳.

---
"""]
used = set()
for title, prefixes in GROUPS:
    sel = [e for e in eps if any(e["path"].startswith(p) for p in prefixes) and e["path"] not in used]
    if not sel:
        continue
    lines.append(f"## {title}\n\n| Method | 경로 | 요청 | 설명 | 구현 |\n|---|---|---|---|---|")
    for e in sorted(sel, key=lambda x: (x["path"], x["method"])):
        used.add(e["path"])
        req = {"Request": "raw JSON", "UploadFile": "multipart 파일", None: "—"}.get(e["req"], e["req"])
        lines.append(f"| `{e['method']}` | `/api{e['path']}` | {req} | {e['doc'] or '—'} | `{e['impl']}` |")
    lines.append("")
rest = [e for e in eps if e["path"] not in used]
if rest:
    lines.append("## 기타\n\n| Method | 경로 | 요청 | 설명 | 구현 |\n|---|---|---|---|---|")
    lines += [f"| `{e['method']}` | `/api{e['path']}` | {e['req'] or '—'} | {e['doc'] or '—'} | `{e['impl']}` |" for e in rest]
    lines.append("")
lines.append("---\n\n## 요청 모델 (Pydantic)\n")
for name, fields in sorted(models.items()):
    lines.append(f"### `{name}`\n\n```python\n" + "\n".join(f"    {f}" for f in fields) + "\n```\n")
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"  ✅ {OUT.relative_to(ROOT)} — {len(eps)}개 엔드포인트, {len(FILES)}개 파일 스캔")
