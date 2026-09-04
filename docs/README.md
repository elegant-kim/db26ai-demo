# db26ai-demo 문서 인덱스

> 최종 갱신: 2026-09-04 · **`docs/`는 사람이 읽는 문서 전용.**
> 앱이 쓰는 SQL 스크립트는 `sql/setup/`, 자격증명이 든 원본은 `sql/setup/_private/`(gitignore).

---

## 어디부터 읽나

| 상황 | 읽을 것 |
|---|---|
| **오랜만에 열었다 / 새 대화창을 시작했다** | **[SESSION_HANDOFF.md](SESSION_HANDOFF.md)** ← 여기부터 |
| 이 앱이 무엇인지 알고 싶다 | [../CLAUDE.md](../CLAUDE.md) (구조·API·Oracle 사용법 정본) |
| 어떻게 작업하는지 알고 싶다 | [개발노하우.md](개발노하우.md) (작업 규율·검증·반복 함정) |
| 앞으로 무엇을 할지 알고 싶다 | [ROADMAP.md](ROADMAP.md) (업데이트/수정 계획서) |
| 구조·API·DB 를 자세히 알고 싶다 | [design/](design/) — 개요·아키텍처·API 명세·DB 설계 |
| 기능이 어디 있고 언제 쓰나 | **[guides/01_사용자_가이드.md](guides/01_사용자_가이드.md)** (앱 「매뉴얼」 탭에서도 열림) |

## 문서 체계 (4층)

| 층 | 파일 | 독자 | 로드 방식 |
|---|---|---|---|
| **L1** | `../CLAUDE.md` | Claude + 사람 | 매 세션 자동 |
| **L2** | `개발노하우.md` | Claude | `@import` 자동 |
| **L3** | `SESSION_HANDOFF.md` | Claude + 사람 | 세션 시작 시 수동 |
| **L4** | `guides/*.md` | **사람** | 앱 「매뉴얼」 탭 (Phase 3 예정) |

**원칙**: 정본은 한 곳에만 둔다. 순서·목록의 정본은 코드의 정의이고, 문서는 "정본 참조"라고만 쓴다.

## 폴더 구조

```
docs/
├── README.md              ← 이 파일
├── SESSION_HANDOFF.md     L3 — 현재 상태 스냅샷 · 직전 세션 · 열린 과제
├── 개발노하우.md            L2 — 작업 규율 · 검증 사이클 · 반복 함정 (@import)
├── ROADMAP.md             업데이트/수정 계획서 (Phase 0~6, 작업별 권고 모델·공수)
├── FEATURES.md            6탭 기능 설명서 (2026-04 작성 — guides/01 의 모태)
│
├── 📘 design/             설계 명세
│   ├── 01_프로젝트_개요.md      무엇을 왜 만드나 · 6탭 · 기술스택 · 규모
│   ├── 02_아키텍처_설계서.md    레이어 규칙 · 기동 시퀀스 · 데이터 흐름 · 성능 규칙
│   ├── 03_API_명세서.md         53개 엔드포인트 (routes.py docstring 에서 추출)
│   ├── 04_DB_설계서.md          테이블 · 인덱스 · Duality · Graph · Oracle 제약
│   └── 05_SPA_이식_설계서.md    (Phase 4 예정)
│
├── 📗 guides/             인앱 매뉴얼 원본 — 앱 「매뉴얼」 탭에서 열린다
│   ├── 01_사용자_가이드.md      ✅ 6탭 사용법 · 성능 기준값 · 용어
│   ├── 02_운영_가이드.md        ✅ 구동 구조 · 배포 절차 · ADB keepalive · 백업 · 시크릿
│   ├── 03_트러블슈팅.md         (예정) 증상 → 원인 → 조치
│   └── 04_데모_시연_가이드.md    (예정) 발표용 시나리오
│
└── 📋 roadmap/
    └── changelog/         세션별 변경 기록
```

> `guides/` 문서는 화이트리스트 API(`/api/guide/docs`)를 통해 앱 「매뉴얼」 탭에서 열린다
> (Phase 3). 새 문서를 만들면 **화이트리스트에도 등록해야 화면에 뜬다.**

## 관련 위치

| 경로 | 내용 |
|---|---|
| `sql/setup/*.sql` | 일회성 셋업·마이그레이션 SQL (시크릿은 자리표시자) |
| `sql/setup/_private/` | 위의 원본(자격증명 포함) — **gitignore** |
| `scripts/check-secrets.sh` | 커밋 전 시크릿 게이트 |
| `deploy/` | macOS launchd 상시 구동 정의 |
