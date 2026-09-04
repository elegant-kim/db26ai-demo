"""테스트 공통 설정.

이 저장소의 테스트는 두 종류다.
  · 단위 테스트  — DB·서버 없이 순수 함수만 검증. 항상 돈다.
  · 통합 테스트  — 구동 중인 서버(:8247)와 실제 ADB 가 필요하다.
                  서버가 없으면 자동으로 skip 되므로 CI·오프라인에서도 안전하다.

통합 테스트를 돌리려면 서버가 떠 있어야 한다:
    launchctl kickstart -k gui/$(id -u)/com.db26ai.server
"""
from __future__ import annotations

import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.getenv("DB26AI_TEST_URL", "http://localhost:8247")
TIMEOUT = 180.0   # 임베딩·LLM 호출이 있는 엔드포인트가 있다


def _server_up() -> bool:
    try:
        r = httpx.get(f"{BASE_URL}/api/health", timeout=10.0)
        return r.status_code == 200 and r.json().get("database_connected") is True
    except Exception:
        return False


SERVER_UP = _server_up()


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as c:
        yield c


@pytest.fixture(scope="session")
def health(client):
    return client.get("/api/health").json()


def pytest_collection_modifyitems(config, items):
    """서버가 없으면 integration 마커가 붙은 테스트를 통째로 skip."""
    if SERVER_UP:
        return
    skip = pytest.mark.skip(reason=f"서버 미구동 또는 DB 미연결 ({BASE_URL})")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
