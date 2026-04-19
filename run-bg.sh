#!/bin/bash
# db26ai-demo 백그라운드 실행 (터미널 닫아도 유지)
# 로그: db26ai.log
set -e

cd "$(dirname "$0")"

EXISTING=$(lsof -ti:8247 2>/dev/null || true)
if [ -n "$EXISTING" ]; then
    echo "[run-bg] 포트 8247 선점 프로세스 종료: $EXISTING"
    kill -9 $EXISTING 2>/dev/null || true
    sleep 1
fi

nohup caffeinate -i venv/bin/python main.py > db26ai.log 2>&1 &
PID=$!
echo $PID > db26ai.pid

echo "[run-bg] 시작됨 — PID=$PID"
echo "[run-bg] 로그: tail -f db26ai.log"
echo "[run-bg] 중지: kill \$(cat db26ai.pid)"
