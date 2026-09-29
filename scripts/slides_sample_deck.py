#!/usr/bin/env python3
"""표본 덱 생성 — docs/slides/src/sample.pdf (2쪽, 꼬리표 SM-01 · SM-02).

    ./venv/bin/python scripts/slides_sample_deck.py

장표 연동(P5)의 뷰어·꼬리표 인식·⌘K·딥링크를 실제 덱 없이 끝까지 검증하기 위한 것.
내용은 docs/slides/README.md 의 준비 규칙 요약이라, 매뉴얼에서 열어도 뜻이 있다.
헤드리스 Chrome 의 print-to-pdf 를 쓴다 — reportlab 없이 한글 폰트가 그대로 박히고 텍스트가 살아 있어
slides_import.py 가 꼬리표를 읽을 수 있다(이미지 PDF 였다면 못 읽는다).
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "slides" / "src" / "sample.pdf"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

HTML = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>장표 연동 표본 덱</title>
<style>
@page { size: 338.67mm 190.5mm; margin: 0; }
html, body { margin: 0; padding: 0; }
.slide { width: 338.67mm; height: 190.5mm; box-sizing: border-box; padding: 22mm 26mm; position: relative;
  page-break-after: always; font-family: "Apple SD Gothic Neo", "Noto Sans KR", sans-serif; color: #1f2933; background: #fff; }
.slide:last-child { page-break-after: auto; }
h1 { font-size: 34pt; margin: 0 0 6mm; color: #312d2a; }
h1 small { display: block; font-size: 14pt; color: #c74634; font-weight: 600; margin-bottom: 3mm; letter-spacing: .04em; }
p, li { font-size: 16pt; line-height: 1.5; }
ul { margin: 4mm 0 0 0; padding-left: 8mm; }
code { font-family: Menlo, monospace; font-size: 14pt; background: #f3efe9; padding: 0 2mm; border-radius: 2mm; }
.tag { position: absolute; right: 14mm; bottom: 10mm; font-family: Menlo, monospace; font-size: 11pt; color: #8a8580; }
.bar { position: absolute; left: 0; top: 0; width: 100%; height: 6mm; background: #c74634; }
.foot { position: absolute; left: 26mm; bottom: 10mm; font-size: 10pt; color: #8a8580; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12mm; margin-top: 6mm; }
.box { border: 1px solid #ddd6cc; border-radius: 4mm; padding: 6mm 8mm; }
.box h3 { margin: 0 0 3mm; font-size: 17pt; color: #c74634; }
</style></head><body>

<section class="slide"><div class="bar"></div>
<h1><small>ORACLE AI DATABASE 26ai 데모 · 장표 연동</small>장표는 이렇게 준비한다</h1>
<ul>
  <li>지금 쓰는 도구(PowerPoint · Keynote)로 만들고 <b>PDF 로 내보낸다</b> — 한 덱 = 한 PDF, 16:9</li>
  <li><b>파일명 = 덱 ID</b> (앱 탭과 같게): <code>vector.pdf</code> <code>selectai.pdf</code> <code>graph.pdf</code> …</li>
  <li><b>장표마다 꼬리표</b>를 구석에 작게: <code>VS-12</code> 처럼 <i>덱코드-번호</i>. 앱은 쪽 번호가 아니라 꼬리표로 장표를 가리킨다 → 순서를 바꿔도 안 깨진다</li>
  <li><code>docs/slides/src/</code> 에 넣고 <code>scripts/slides_import.py</code> 한 번 — 쪽 이미지 + 꼬리표 표가 생긴다</li>
</ul>
<div class="foot">이 덱은 표본이다 — 뷰어·꼬리표 인식·⌘K·딥링크 검증용. 실제 덱이 오면 지워도 된다.</div>
<div class="tag">SM-01</div>
</section>

<section class="slide"><div class="bar"></div>
<h1><small>ORACLE AI DATABASE 26ai 데모 · 장표 연동</small>앱에서는 이렇게 보인다</h1>
<div class="two">
  <div class="box"><h3>페이지 헤더 「장표 n」</h3><p>지금 보는 화면에 연결된 장표가 오른쪽 슬라이드오버에 뜬다. 살아 있는 검색 결과 옆에 장표가 나란히 선다 — 화면을 떠나지 않는다.</p></div>
  <div class="box"><h3>⌘K · 딥링크</h3><p><code>장표: 제목 p3 · VS-03</code> 으로 바로 열기. <code>?slide=VS-12</code> 는 <code>?sub=</code> <code>?run=</code> 과 같은 층 — 시연 대본의 링크 하나가 화면과 장표를 같이 연다.</p></div>
  <div class="box"><h3>앵커의 정본</h3><p><code>app/feature_registry.py</code> 기능 항목의 <code>slides</code> 자리. 기능 지도 · ⌘K · 화면 버튼이 같은 정본을 본다. 덱이 없으면 버튼이 숨는다.</p></div>
  <div class="box"><h3>공개 저장소 주의</h3><p><code>docs/slides/</code> 는 기본 gitignore. 고객명·내부 수치가 든 장표를 실수로 공개하지 않기 위해서다. 공개해도 되는 덱만 골라 추적한다.</p></div>
</div>
<div class="tag">SM-02</div>
</section>
</body></html>"""


def main() -> int:
    if not pathlib.Path(CHROME).exists():
        print(f"Chrome 이 없다: {CHROME}", file=sys.stderr)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        html = pathlib.Path(td) / "deck.html"
        html.write_text(HTML, encoding="utf-8")
        cmd = [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
               f"--print-to-pdf={OUT}", "--virtual-time-budget=3000", html.as_uri()]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if not OUT.exists() or OUT.stat().st_size == 0:
            print("PDF 생성 실패:", r.stderr[-800:], file=sys.stderr)
            return 1
    print(f"✓ {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
