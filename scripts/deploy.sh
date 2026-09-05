#!/bin/bash
# 배포 = 검증 → 프론트 빌드 → 재기동 → 스모크 (운영 가이드 3절, 설계서 05 §5.3)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "① 백엔드 검증"
./venv/bin/python -m pytest tests/ -q
./venv/bin/ruff check .

echo "② 프론트 빌드 (undef-check + typecheck + vite build)"
if [ -d web/node_modules ]; then (cd web && npm run build); else echo "   web/node_modules 없음 — 'cd web && npm install' 먼저"; exit 1; fi

echo "③ 재기동"
launchctl kickstart -k gui/$(id -u)/com.db26ai.server
for i in $(seq 1 30); do sleep 1; curl -sf localhost:8247/api/health >/dev/null 2>&1 && break; done

echo "④ 스모크"
curl -s localhost:8247/api/health | python3 -c "import sys,json;d=json.load(sys.stdin);print('   health:',d['status'],'· db',d['database_connected'],'· 임베딩',d['embedded_count'],'/',d['chunk_count'])"
if curl -s localhost:8247/ | grep -q 'id="app"'; then echo "   / → SPA (web/dist)"; else echo "   / → 레거시 (dist 없음)"; fi
echo "   ⏳ 커넥션 풀 워밍은 ~15초 뒤 완료 — 첫 벡터 질의는 그 후가 정확하다"
