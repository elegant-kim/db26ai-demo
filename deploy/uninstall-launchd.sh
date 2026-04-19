#!/bin/bash
PLIST_DST="$HOME/Library/LaunchAgents/com.db26ai.server.plist"

if [ -f "$PLIST_DST" ]; then
    launchctl unload -w "$PLIST_DST" 2>/dev/null || true
    rm "$PLIST_DST"
    echo "[uninstall-launchd] ✅ 제거 완료"
else
    echo "[uninstall-launchd] 설치된 에이전트 없음"
fi

REMAIN=$(lsof -ti:8247 2>/dev/null || true)
if [ -n "$REMAIN" ]; then
    echo "[uninstall-launchd] 포트 8247 잔여 프로세스 종료: $REMAIN"
    kill -9 $REMAIN 2>/dev/null || true
fi
