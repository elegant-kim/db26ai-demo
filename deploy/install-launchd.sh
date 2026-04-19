#!/bin/bash
# macOS launchd agent 설치 — db26ai-demo 부팅 시 자동 시작
set -e

cd "$(dirname "$0")/.."
PLIST_SRC="$(pwd)/deploy/com.db26ai.server.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.db26ai.server.plist"

if [ -f "$PLIST_DST" ]; then
    echo "[install-launchd] 기존 에이전트 언로드"
    launchctl unload -w "$PLIST_DST" 2>/dev/null || true
fi

EXISTING=$(lsof -ti:8247 2>/dev/null || true)
if [ -n "$EXISTING" ]; then
    echo "[install-launchd] 포트 8247 기존 프로세스 종료: $EXISTING"
    kill -9 $EXISTING 2>/dev/null || true
    sleep 1
fi

mkdir -p "$HOME/Library/LaunchAgents"
cp "$PLIST_SRC" "$PLIST_DST"
launchctl load -w "$PLIST_DST"

sleep 2
echo ""
echo "[install-launchd] ✅ 설치 완료"
echo ""
echo "상태 확인:   launchctl list | grep db26ai"
echo "로그 확인:   tail -f db26ai.log"
echo "수동 중지:   launchctl unload -w $PLIST_DST"
echo "포트 확인:   lsof -iTCP:8247 -sTCP:LISTEN"
