# 장표(PPT/PDF) 연동 — 준비 규칙

> 2026-09-29 신설 (Vector 탭 재편 P5). 발표 자료를 **앱 화면 옆에** 띄우기 위한 규칙이다.
> 문서는 지금 쓰는 도구(PowerPoint · Keynote)로 그대로 만들고, 앱이 여기에 맞춘다.
> 정본 코드: `scripts/slides_import.py`(변환) · `app/slides.py`(서빙) · `app/feature_registry.py` 의 `slides` 필드(앵커).

## 1. 이 폴더는 기본 비추적이다 (gitignore)

이 저장소는 GitHub **공개**다. 장표에는 고객명·내부 수치가 들어갈 수 있어 `docs/slides/**` 는 기본 gitignore 다.
추적되는 것은 이 README 와 표본 덱 `src/sample.pdf` 뿐이다. 공개해도 되는 덱은 나중에 `.gitignore` 에 `!docs/slides/src/<deck>.pdf` 한 줄로 골라 넣는다.
`out/` 은 언제나 생성물이라 추적하지 않는다 — clone 뒤 `slides_import.py` 를 한 번 돌리면 된다.

## 2. 문서를 이렇게 준비한다

1. **PDF 로 내보낸다.** 한 덱 = 한 PDF, 16:9. (PowerPoint: 파일 › 내보내기 › PDF · Keynote: 파일 › 다음으로 내보내기 › PDF)
2. **파일명 = 덱 ID.** 앱의 탭 ID 와 같게 — `selectai.pdf` · `vector.pdf` · `duality.pdf` · `graph.pdf` · `productivity.pdf` · `awr.pdf` · `overview.pdf`. 영문 소문자·숫자·`-` 만.
3. **장표마다 꼬리표를 단다.** 각 슬라이드 구석에 작은 글씨로 `덱코드-번호` — 예 `SA-03`, `VS-12`.
   - 형식: 영대문자 2~3자 + `-` + 숫자 2~3자 (`^[A-Z]{2,3}-\d{2,3}$`). 덱 코드는 덱 안에서 하나로 통일한다.
   - **앱은 쪽 번호가 아니라 꼬리표로 장표를 가리킨다.** 슬라이드를 끼워 넣거나 순서를 바꿔도 앵커가 안 깨진다.
   - PowerPoint 에서 내보낸 PDF 는 텍스트가 살아 있으므로 변환 스크립트가 꼬리표를 자동으로 읽는다. 이미지로만 된 장표(스캔·캡처)는 꼬리표를 못 읽는다 — 텍스트 상자로 넣을 것.
4. **넣는 곳**: `docs/slides/src/<deck>.pdf`
5. **변환**: 프로젝트 루트에서

   ```bash
   ./venv/bin/python scripts/slides_import.py            # src/ 의 모든 PDF (바뀐 것만)
   ./venv/bin/python scripts/slides_import.py vector     # 한 덱만
   ./venv/bin/python scripts/slides_import.py --force    # 전부 다시
   ```

   결과: `docs/slides/out/<deck>/001.webp …` + `thumb.webp` + `manifest.json`(제목 · 쪽 수 · 꼬리표→쪽 · 쪽별 텍스트 앞부분).
   한 덱 40쪽 ≈ 4~6MB. 변환은 쪽당 0.1~0.3초.

**변환을 안 돌려도 된다.** `src/<deck>.pdf` 만 있으면 앱이 브라우저 내장 PDF 뷰어로 그 쪽을 연다(임시 경로 B — 툴바가 앱 디자인 밖이고 `#page=` 는 Chrome 에서만 확실). 변환하면 자동으로 이미지 뷰어(정본 경로 A)로 격이 올라간다.

## 3. 앱에서 이렇게 보인다

| 어디 | 무엇 |
|---|---|
| 각 페이지 헤더 우상단 「장표 n」 | 지금 보는 화면(탭·서브탭)에 연결된 장표. 누르면 오른쪽 슬라이드오버에 장표가 뜬다 — 화면을 떠나지 않는다. 연결된 장표가 없으면 버튼이 숨는다 |
| ⌘K | `장표: <덱 제목> p3 · VS-03` 항목. 기능에 연결된 꼬리표는 기능 이름으로도 검색된다 |
| 딥링크 `?slide=VS-12` | 기존 `?sub=` `?run=` 과 같은 층. 시연 대본에서 "화면 + 장표" 를 링크 하나로 연다 |
| 매뉴얼 › 장표 | 덱 목록(썸네일 · 쪽 수 · 꼬리표 수 · 변환 여부)과 이 규칙 요약 |

**앵커의 정본은 `app/feature_registry.py`** — 기능 항목 튜플의 7번째 자리에 `["VS-12", "VS-13"]` 처럼 적는다. 기능 지도 · ⌘K · 화면 버튼이 같은 정본을 본다.
덱이 없거나 꼬리표가 덱에 없으면 그 앵커는 조용히 빠진다(문서 준비 전에도 앱은 그대로 돈다). 안 맞는 꼬리표는 매뉴얼 › 장표 에 「덱에 없는 꼬리표」로 표시된다.

## 4. 표본 덱 `src/sample.pdf`

이 규칙 자체를 2쪽(`SM-01`, `SM-02`)으로 만든 표본이다. `scripts/slides_sample_deck.py` 가 헤드리스 Chrome 으로 만든다.
새 환경에서 뷰어가 도는지 확인하는 용도이며, 실제 덱이 들어오면 지워도 된다.
