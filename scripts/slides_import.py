#!/usr/bin/env python3
"""장표 변환 — docs/slides/src/<deck>.pdf → docs/slides/out/<deck>/{001.webp…, thumb.webp, manifest.json}

    ./venv/bin/python scripts/slides_import.py            # src/ 의 모든 PDF (원본이 바뀐 것만)
    ./venv/bin/python scripts/slides_import.py vector     # 한 덱만
    ./venv/bin/python scripts/slides_import.py --force    # 전부 다시

규칙은 docs/slides/README.md. 요지:
- 파일명이 덱 ID (영소문자·숫자·`-`). 각 쪽 텍스트에서 꼬리표(`VS-12` 꼴)를 읽어 꼬리표 → 쪽 표를 만든다.
  앱은 쪽 번호가 아니라 꼬리표로 장표를 가리키므로, 슬라이드 순서가 바뀌어도 앵커가 안 깨진다.
- 렌더는 pypdfium2(pdfplumber 의 의존성으로 이미 venv 에 있다) → Pillow WebP. 폭 1600px, 품질 82 — 40쪽 ≈ 4~6MB.
- manifest.json 은 app/slides.py 가 읽어 /api/guide/slides 로 내보낸다. 필드를 바꾸면 거기도 같이.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "slides" / "src"
OUT = ROOT / "docs" / "slides" / "out"

TAG_RE = re.compile(r"\b([A-Z]{2,3}-\d{2,3})\b")
DECK_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
WIDTH = 1600
THUMB_WIDTH = 480
QUALITY = 82
MANIFEST_VERSION = 1


def _page_tags(text: str) -> list[str]:
    """쪽 텍스트에서 꼬리표 후보 전부(등장 순)."""
    return TAG_RE.findall(text or "")


def convert(pdf: pathlib.Path, force: bool = False, code_override: str | None = None) -> dict | None:
    import pypdfium2 as pdfium  # noqa: PLC0415 — 스크립트 진입 뒤 임포트(없으면 메시지가 또렷하게)

    deck = pdf.stem
    if not DECK_RE.match(deck):
        print(f"  ✗ {pdf.name}: 덱 ID 는 영소문자·숫자·'-' 만 ({deck!r})")
        return None
    out = OUT / deck
    manifest_path = out / "manifest.json"
    src_mtime = int(pdf.stat().st_mtime)
    if manifest_path.exists() and not force:
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
            if old.get("source_mtime") == src_mtime and old.get("manifest_version") == MANIFEST_VERSION:
                print(f"  = {deck}: 변경 없음 ({old.get('pages')}쪽)")
                return old
        except (OSError, ValueError) as e:
            print(f"  · {deck}: 옛 manifest 를 못 읽어 다시 만든다 ({e})")

    t0 = time.time()
    doc = pdfium.PdfDocument(str(pdf))
    n = len(doc)
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("*.webp"):
        stale.unlink()

    meta = doc.get_metadata_dict() if hasattr(doc, "get_metadata_dict") else {}
    title = (meta.get("Title") or "").strip()
    texts: list[str] = []
    found_per_page: list[list[str]] = []
    for i in range(n):
        page = doc[i]
        w, h = page.get_size()
        scale = WIDTH / w
        img = page.render(scale=scale).to_pil().convert("RGB")
        img.save(out / f"{i + 1:03d}.webp", "WEBP", quality=QUALITY, method=4)
        if i == 0:
            th = img.copy()
            th.thumbnail((THUMB_WIDTH, int(THUMB_WIDTH * h / w) + 1))
            th.save(out / "thumb.webp", "WEBP", quality=78)
        text = page.get_textpage().get_text_range() or ""
        texts.append(" ".join(text.split())[:300])
        found_per_page.append(_page_tags(text))
    # 덱 코드 = "쪽의 마지막 꼬리표"로 가장 많은 쪽에 나온 접두어(구석 꼬리표는 보통 그 쪽 텍스트의 마지막에 읽힌다).
    # 본문이 다른 덱의 꼬리표(`VS-12` 를 예로 든 문장 등)를 언급해도 밀리지 않는다. --code 로 못 박을 수도 있다.
    code = code_override
    if not code:
        last_hits: dict[str, int] = {}
        any_hits: dict[str, int] = {}
        for found in found_per_page:
            seen = set()
            for tg in found:
                c = tg.split("-")[0]
                if c not in seen:
                    any_hits[c] = any_hits.get(c, 0) + 1
                    seen.add(c)
            if found:
                c = found[-1].split("-")[0]
                last_hits[c] = last_hits.get(c, 0) + 1
        if any_hits:
            code = max(any_hits, key=lambda c: (last_hits.get(c, 0), any_hits[c]))
    tags: dict[str, int] = {}
    page_tag: list[str | None] = []
    for i, found in enumerate(found_per_page):
        mine = [tg for tg in found if code and tg.startswith(code + "-")]
        own = mine[-1] if mine else None  # 구석 꼬리표는 보통 그 쪽 텍스트의 마지막에 읽힌다
        page_tag.append(own)
        if own and own not in tags:
            tags[own] = i + 1
    if not title:
        first = texts[0] if texts else ""
        first = TAG_RE.sub("", first).strip()
        title = first[:60] or deck

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "deck": deck,
        "title": title,
        "pages": n,
        "width": WIDTH,
        "code": code,                       # 덱 코드(꼬리표 접두어) — 없으면 null
        "tags": tags,                       # 꼬리표 → 쪽(1부터)
        "page_tags": page_tag,              # 쪽 순서대로 그 쪽의 꼬리표(없으면 null)
        "page_text": texts,                 # 쪽별 텍스트 앞 300자 — ⌘K 검색용
        "source": f"src/{pdf.name}",
        "source_mtime": src_mtime,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    size = sum(p.stat().st_size for p in out.glob("*.webp")) // 1024
    missing = [i + 1 for i, t in enumerate(page_tag) if not t]
    print(f"  ✓ {deck}: {n}쪽 · 꼬리표 {len(tags)}개 · {size} KB · {time.time() - t0:.1f}초"
          + (f" · 꼬리표 없는 쪽 {missing}" if missing else ""))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("decks", nargs="*", help="덱 ID (생략 시 src/ 전부)")
    ap.add_argument("--force", action="store_true", help="변경 없어도 다시 변환")
    ap.add_argument("--code", help="덱 코드를 못 박는다(예: VS). 자동 판정이 틀릴 때만 — 덱 하나를 지정했을 때 쓴다")
    a = ap.parse_args()
    SRC.mkdir(parents=True, exist_ok=True)
    pdfs = [SRC / f"{d}.pdf" for d in a.decks] if a.decks else sorted(SRC.glob("*.pdf"))
    if not pdfs:
        print(f"변환할 PDF 가 없다: {SRC.relative_to(ROOT)}/ 에 <deck>.pdf 를 넣을 것 (docs/slides/README.md)")
        return 0
    print(f"장표 변환 → {OUT.relative_to(ROOT)}/")
    ok = 0
    for pdf in pdfs:
        if not pdf.exists():
            print(f"  ✗ {pdf.name}: 없음")
            continue
        if convert(pdf, force=a.force or bool(a.code), code_override=a.code):
            ok += 1
    # 원본이 사라진 덱의 out/ 은 남겨 두지 않는다 — 앱이 없는 덱을 광고하면 안 된다
    if not a.decks and OUT.exists():
        live = {p.stem for p in SRC.glob("*.pdf")}
        for d in OUT.iterdir():
            if d.is_dir() and d.name not in live:
                print(f"  · {d.name}: 원본 PDF 가 없어 생성물을 지운다")
                for f in d.iterdir():
                    f.unlink()
                d.rmdir()
    return 0 if ok == len([p for p in pdfs if p.exists()]) else 1


if __name__ == "__main__":
    sys.exit(main())
