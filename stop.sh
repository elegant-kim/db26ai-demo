#!/bin/bash
# db26ai-demo 서버 중지
cd "$(dirname "$0")"

if [ -f db26ai.pid ]; then
    PID=$(cat db26ai.pid)
    if kill -0 $PID 2>/dev/null; then
        echo "[stop] PID $PID 종료 중..."
        kill $PID
        sleep 1
        kill -9 $PID 2>/dev/null || true
    fi
    rm -f db26ai.pid
fi

REMAIN=$(lsof -ti:8247 2>/dev/null || true)
if [ -n "$REMAIN" ]; then
    echo "[stop] 포트 8247 잔여 프로세스 종료: $REMAIN"
    kill -9 $REMAIN 2>/dev/null || true
fi

echo "[stop] 완료"
