"""장표(PPT/PDF) 서빙 — docs/slides/ 를 읽어 「매뉴얼 › 장표」·페이지 헤더 「장표」 버튼·⌘K·`?slide=` 가 쓰는 카탈로그를 만든다.

2026-09-29 신설 (Vector 탭 재편 P5). 준비 규칙은 docs/slides/README.md, 변환은 scripts/slides_import.py.

두 경로를 한 카탈로그로 낸다:
- **이미지(정본 A)**: `out/<deck>/manifest.json` 이 있으면 쪽 이미지(`/slides/out/<deck>/001.webp`)와 꼬리표 → 쪽 표.
- **PDF(임시 B)**: `src/<deck>.pdf` 만 있으면 브라우저 내장 뷰어(`/slides/src/<deck>.pdf#page=n`). 꼬리표는 모른다(변환 전).

앵커의 정본은 app/feature_registry.py 의 `slides` 필드다. 여기서는 그 꼬리표를 덱에서 찾아 (deck, page) 로 풀고,
못 찾은 것은 `unresolved` 로 따로 돌려준다 — 조용히 빠지되 매뉴얼에서는 보이게.
카탈로그는 요청마다 디스크를 읽는다(덱은 몇 개 안 되고, 변환 직후 재기동 없이 반영되는 쪽이 낫다).
"""
from __future__ import annotations

import json
import logging
import os
import re

from app.feature_registry import FEATURES

logger = logging.getLogger(__name__)

SLIDES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "slides")
SRC_DIR = os.path.join(SLIDES_DIR, "src")
OUT_DIR = os.path.join(SLIDES_DIR, "out")

TAG_RE = re.compile(r"^[A-Z]{2,3}-\d{2,3}$")
DECK_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def is_tag(s: str) -> bool:
    return bool(TAG_RE.match(s or ""))


def _read_manifest(deck: str) -> dict | None:
    path = os.path.join(OUT_DIR, deck, "manifest.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            m = json.load(f)
        if not isinstance(m.get("pages"), int) or m["pages"] < 1:
            raise ValueError("pages 가 없다")
        return m
    except (OSError, ValueError) as e:
        logger.warning("장표 manifest 를 못 읽었다 (%s): %s", deck, e)
        return None


def list_decks() -> list[dict]:
    """덱 카탈로그. src/ 의 PDF 와 out/ 의 manifest 를 합친다(둘 중 하나만 있어도 덱이다)."""
    ids: set[str] = set()
    if os.path.isdir(SRC_DIR):
        ids |= {f[:-4] for f in os.listdir(SRC_DIR) if f.endswith(".pdf")}
    if os.path.isdir(OUT_DIR):
        ids |= {d for d in os.listdir(OUT_DIR) if os.path.isfile(os.path.join(OUT_DIR, d, "manifest.json"))}
    decks: list[dict] = []
    for deck in sorted(ids):
        if not DECK_RE.match(deck):
            logger.warning("장표 덱 ID 가 규칙에 안 맞아 건너뛴다: %r", deck)
            continue
        has_pdf = os.path.isfile(os.path.join(SRC_DIR, f"{deck}.pdf"))
        m = _read_manifest(deck)
        if m:
            decks.append({
                "deck": deck, "title": m.get("title") or deck, "pages": m["pages"], "mode": "images",
                "code": m.get("code"), "tags": m.get("tags") or {}, "page_tags": m.get("page_tags") or [],
                "page_text": m.get("page_text") or [],
                "image_base": f"/slides/out/{deck}/", "thumb": f"/slides/out/{deck}/thumb.webp",
                "pdf": f"/slides/src/{deck}.pdf" if has_pdf else None,
                "generated_at": m.get("generated_at"),
            })
        elif has_pdf:
            decks.append({
                "deck": deck, "title": deck, "pages": None, "mode": "pdf",
                "code": None, "tags": {}, "page_tags": [], "page_text": [],
                "image_base": None, "thumb": None, "pdf": f"/slides/src/{deck}.pdf", "generated_at": None,
            })
    return decks


def resolve_anchors(decks: list[dict]) -> tuple[list[dict], list[dict]]:
    """기능 레지스트리의 `slides` 꼬리표를 (deck, page) 로 푼다. 반환: (풀린 앵커, 못 푼 앵커)."""
    by_tag: dict[str, tuple[dict, int]] = {}
    for d in decks:
        for tag, page in (d.get("tags") or {}).items():
            by_tag.setdefault(tag, (d, int(page)))
    anchors: list[dict] = []
    unresolved: list[dict] = []
    for f in FEATURES:
        for tag in f.get("slides") or []:
            base = {"tag": tag, "feature": f["name"], "tab": f["tab"], "tab_label": f["tab_label"], "path": f["path"]}
            hit = by_tag.get(tag)
            if hit:
                d, page = hit
                anchors.append({**base, "deck": d["deck"], "deck_title": d["title"], "page": page})
            else:
                unresolved.append(base)
    return anchors, unresolved


def catalog() -> dict:
    decks = list_decks()
    anchors, unresolved = resolve_anchors(decks)
    return {
        "available": bool(decks),
        "decks": decks,
        "anchors": anchors,
        "unresolved": unresolved,
        "slides_dir": "docs/slides",
    }
