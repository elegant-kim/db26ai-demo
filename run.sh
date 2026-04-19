#!/bin/bash
# db26ai-demo 서버 실행 (포어그라운드)
# - 포트 8247 선점 프로세스 자동 종료
# - caffeinate로 감싸 macOS 절전(sleep) 방지
set -e

cd "$(dirname "$0")"
source venv/bin/activate

EXISTING=$(lsof -ti:8247 2>/dev/null || true)
if [ -n "$EXISTING" ]; then
    echo "[run.sh] 포트 8247 선점 프로세스 종료: $EXISTING"
    kill -9 $EXISTING 2>/dev/null || true
    sleep 1
fi

echo "[run.sh] caffeinate + python main.py 시작 (잠자기 방지)"
exec caffeinate -i python main.py
