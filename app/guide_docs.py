"""인앱 문서(docs/) 화이트리스트 리졸버 — 「매뉴얼」 탭이 쓰는 서비스.

investhub 의 `app/services/guide_docs_service.py` 를 이식했다(2026-09-04).
db26ai-demo 는 아직 app/ 이 평면 구조라 그 관례를 따랐다 — Phase 5 에서
routers/services 로 한꺼번에 쪼갠다.

보안: key → (파일 번호 prefix, 제목, 부제) 화이트리스트 + 번호 prefix glob 으로
파일명을 docs/ 안에서만 해석한다. 경로 traversal 과 한글 NFC/NFD 우회를 원천 차단.
(macOS APFS 에서 한글 파일명은 NFD 로 저장되어 파이썬 문자열 비교가 빗나간다.)
"""
from __future__ import annotations

import glob as _glob
import os as _os

_DOCS_DIR = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "docs"
)

# key → (파일 번호 prefix, 표시 제목, 부제)
Whitelist = dict[str, tuple[str, str, str]]


def _resolve(whitelist: Whitelist, key: str, subdir: str) -> tuple[str, str, str] | None:
    """key → (실제 경로, 제목, 부제). 화이트리스트 밖이거나 파일이 없으면 None."""
    spec = whitelist.get(key)
    if not spec:
        return None
    base = _os.path.join(_DOCS_DIR, subdir) if subdir else _DOCS_DIR
    matches = _glob.glob(_os.path.join(base, f"{spec[0]}*.md"))
    if not matches:
        return None
    path = _os.path.realpath(sorted(matches)[0])
    # realpath 로 정규화한 뒤 docs/ 하위인지 반드시 재확인한다
    if not path.startswith(_os.path.realpath(_DOCS_DIR) + _os.sep):
        return None
    return path, spec[1], spec[2]


def list_docs(whitelist: Whitelist, subdir: str = "guides") -> list[dict]:
    """화이트리스트 문서 목록. 아직 안 쓴 문서는 available=False 로 나온다."""
    return [
        {
            "key": key,
            "title": spec[1],
            "subtitle": spec[2],
            "available": _resolve(whitelist, key, subdir) is not None,
        }
        for key, spec in whitelist.items()
    ]


def read_doc(whitelist: Whitelist, key: str, subdir: str = "guides") -> dict | None:
    """단일 문서의 마크다운 원문. 없으면 None."""
    r = _resolve(whitelist, key, subdir)
    if not r:
        return None
    path, title, subtitle = r
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return {"key": key, "title": title, "subtitle": subtitle, "content": content}
