#!/bin/bash
# 커밋 전 시크릿 게이트 — 이 저장소는 GitHub 공개(PUBLIC)다.
#
# 2026-09-04 신설. 계기가 두 가지다.
#  ① 인라인으로 쓰던 게이트가 실제로는 **막지 못했다**:
#     ( scan && echo ok || echo fail ) && git commit ...
#     서브셸이 항상 0을 반환해 뒤의 커밋이 그냥 실행됐다. 게이트가 장식이었다.
#     → 스크립트로 분리하고 exit code 로 확실히 막는다.
#  ② 정규식 자체를 문서에 적었더니 스캐너가 그 문서를 시크릿으로 오탐했다.
#     → 정규식 메타문자가 섞인 줄은 "패턴의 정의"로 보고 건너뛴다.
#
# 사용: scripts/check-secrets.sh            # 스테이징된 변경 검사 (기본)
#       scripts/check-secrets.sh --tracked  # 추적 중인 파일 전체 검사
set -u

PAT='gsk_[A-Za-z0-9]{20,}|AIzaSy[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|BEGIN [A-Z ]*PRIVATE KEY|ocid1\.(tenancy|user)\.[a-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|xoxb-[0-9A-Za-z-]{20,}'

if [ "${1:-}" = "--tracked" ]; then
  RAW=$(git grep -nIE "$PAT" -- . 2>/dev/null)
  SCOPE="추적 파일 전체"
else
  RAW=$(git diff --cached -U0 | grep -nIE "$PAT" 2>/dev/null)
  SCOPE="스테이징된 변경"
fi

# 정규식 정의가 적힌 줄(문서·이 스크립트 자체)은 제외한다.
HITS=$(printf '%s\n' "$RAW" | grep -vE '\{20,\}|\{16\}|\{30,\}|\[A-Za-z0-9\]|grep -nIE|PAT=' | grep -v '^$')

if [ -n "$HITS" ]; then
  echo "❌ 시크릿 의심 — 커밋 중단 ($SCOPE)"
  printf '%s\n' "$HITS" | sed -E 's/(gsk_|AIzaSy|sk-ant-|ghp_|xoxb-)[A-Za-z0-9_-]{8,}/\1<REDACTED>/g' | head -20
  echo
  echo "실제 시크릿이면: 값을 자리표시자로 바꾸고 원본은 sql/setup/_private/ 또는 .env 로 옮긴다."
  echo "오탐이면: 이 스크립트의 제외 규칙을 조정한다 (근거를 주석으로 남길 것)."
  exit 1
fi

echo "✅ 시크릿 0건 ($SCOPE)"
exit 0
