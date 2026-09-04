"""6탭 API 스모크 — 구동 중인 서버와 실제 ADB 가 필요하다(없으면 자동 skip).

`launchctl kickstart -k gui/$(id -u)/com.db26ai.server` 후 실행할 것.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestHealth:
    def test_기본_상태(self, health):
        assert health["status"] == "ok"
        assert health["database_connected"] is True
        assert health["schema"]
        assert "26ai" in health["db_version"]

    def test_ONNX_모델을_정직하게_보고한다(self, client, health):
        """회귀 가드 (c3526d6): /api/health 가 5개월간 onnx_models 를 [] 로 거짓 보고했다.

        get_onnx_models() 는 list 를 반환하는데 .get("models") 를 호출해 AttributeError 가
        났고, bare `except: pass` 가 그것을 삼켰다. 두 엔드포인트가 같은 답을 해야 한다.
        """
        direct = client.get("/api/vector/onnx-models").json()
        assert direct["success"] is True
        names_direct = sorted(m["model_name"] for m in direct["models"])
        names_health = sorted(m["model_name"] for m in health["onnx_models"])
        assert names_health == names_direct, "/api/health 와 /api/vector/onnx-models 가 어긋난다"

    def test_임베딩_수가_청크_수와_어긋나지_않는다(self, health):
        """회귀 가드 (31cf617): 업로드가 임베딩 실패(ORA-51932)를 '성공'으로 보고해
        청크 79개 전부 embedding 이 NULL 인데도 정상처럼 보였다."""
        if health["chunk_count"] == 0:
            pytest.skip("적재된 청크가 없다")
        assert health["embedded_count"] > 0, "청크는 있는데 임베딩이 하나도 없다"


class TestTabsReachable:
    """6탭 대표 엔드포인트가 살아 있는가."""

    @pytest.mark.parametrize("path", [
        "/api/profiles",                  # ① NL2SQL
        "/api/vector/documents",          # ② Vector Search
        "/api/vector/embedding-config",
        "/api/vector/index-info",
        "/api/duality/views",             # ③ Duality
        "/api/graph/queries",             # ④ Property Graph
        "/api/productivity/recent-queries",  # ⑤ 개발생산성
        "/api/llm/providers",             # ⑥ AWR 이 쓰는 LLM 목록
    ])
    def test_GET_200(self, client, path):
        r = client.get(path)
        assert r.status_code == 200, f"{path} → {r.status_code}"


class TestNL2SQL:
    def test_showsql_이_SQL_을_돌려준다(self, client, health):
        if not health["profile_count"]:
            pytest.skip("AI 프로필이 없다")
        r = client.post("/api/ask", json={"prompt": "고객 수는?", "action": "showsql"})
        assert r.status_code == 200
        d = r.json()
        assert d["success"] is True
        assert "SELECT" in str(d["result"]).upper()

    def test_잘못된_action_은_400(self, client):
        r = client.post("/api/ask", json={"prompt": "x", "action": "nosuchaction"})
        assert r.status_code == 400

    def test_execute_sql_은_SELECT_만_허용(self, client):
        r = client.post("/api/execute-sql", json={"sql": "DROP TABLE doc_chunks"})
        assert r.json()["success"] is False


class TestVectorSearch:
    @pytest.fixture(autouse=True)
    def _need_chunks(self, health):
        if health["chunk_count"] == 0 or health["embedded_count"] == 0:
            pytest.skip("임베딩된 청크가 없다 — PDF 를 먼저 업로드할 것")

    @pytest.mark.parametrize("mode", ["vector", "keyword", "hybrid"])
    def test_검색_모드가_결과를_돌려준다(self, client, mode):
        r = client.post("/api/vector/search",
                        json={"query": "인덱스 사용 지침", "mode": mode, "top_k": 3})
        assert r.status_code == 200
        d = r.json()
        assert d["success"] is True
        assert len(d.get("chunks") or []) > 0, f"{mode} 모드가 0건"

    def test_compare_모드는_양쪽을_모두_반환(self, client):
        r = client.post("/api/vector/search",
                        json={"query": "인덱스", "mode": "compare", "top_k": 3})
        d = r.json()
        assert d["success"] is True
        for side in ("keyword_results", "vector_results"):
            assert side in d, f"{side} 가 없다"

    def test_키워드_검색이_CONTAINS_를_쓴다(self, client):
        """회귀 가드 (31cf617): Oracle Text 인덱스가 없으면 LIKE 로 폴백해
        9.9초가 걸리고 구(句) 질의는 0건이 된다."""
        d = client.post("/api/vector/search",
                        json={"query": "인덱스 사용 지침", "mode": "keyword", "top_k": 3}).json()
        assert "CONTAINS" in (d.get("sql_executed") or "").upper(), \
            "LIKE 폴백 중 — doc_chunks_text_idx 가 있는지 확인할 것"

    def test_자연어_질문에도_키워드_점수가_붙는다(self, client):
        """회귀 가드 (2b707e5): 자연어 문장을 CONTAINS 에 그대로 넣어 ORA-29902 로 터지고
        LIKE 폴백이 0건이라, 하이브리드가 이름만 하이브리드고 실제로는 벡터 전용이었다."""
        d = client.post("/api/vector/search", json={
            "query": "인덱스를 효율적으로 사용하려면 어떻게 SQL을 작성해야 하나요?",
            "mode": "hybrid", "top_k": 3,
        }).json()
        assert d["success"] is True
        chunks = d.get("chunks") or []
        assert chunks, "하이브리드가 0건"
        assert any(c.get("keyword_score", 0) > 0 for c in chunks), \
            "자연어 질문에서 키워드 성분이 전부 0 — 하이브리드가 벡터 전용으로 퇴화했다"


class TestPropertyGraph:
    def test_SQL_과_PGQ_가_같은_결과를_낸다(self, client):
        """회귀 가드 (c4aa907): 이 탭의 존재 이유가 '두 방식이 같은 결과를 낸다'인데,
        하나는 ORA-49011 로 0행이었고 다른 하나는 정렬이 없어 서로 다른 10행을 보여줬다."""
        n = len((client.get("/api/graph/queries").json() or {}).get("compare") or [])
        assert n > 0, "비교 쿼리 목록이 비었다"
        for i in range(n):
            d = client.post("/api/graph/compare", json={"query_index": i}).json()
            assert not d.get("pgq_error"), f"[{i}] PGQ 오류: {d.get('pgq_error')}"
            assert not d.get("sql_error"), f"[{i}] SQL 오류: {d.get('sql_error')}"
            sql = [list(map(str, r.values())) for r in (d.get("sql_data") or [])]
            pgq = [list(map(str, r.values())) for r in (d.get("pgq_data") or [])]
            assert sql, f"[{i}] SQL 결과 0행"
            assert sql == pgq, f"[{i}] '{d.get('label')}' — SQL 과 PGQ 결과가 다르다"

    def test_패턴_질의가_동작한다(self, client):
        n = len((client.get("/api/graph/queries").json() or {}).get("pattern") or [])
        for i in range(n):
            d = client.post("/api/graph/pattern", json={"query_index": i}).json()
            assert not d.get("error"), f"[{i}] {d.get('error')}"


class TestDuality:
    def test_관계형과_JSON_이_모두_반환된다(self, client):
        views = (client.get("/api/duality/views").json() or {}).get("views") or []
        if not views:
            pytest.skip("Duality View 가 없다")
        name = views[0].get("view_name") or views[0].get("VIEW_NAME")
        d = client.post("/api/duality/compare", json={"view_name": name, "limit": 3}).json()
        assert d.get("success") is not False


class TestGuideDocs:
    """인앱 매뉴얼 API — 화이트리스트 밖은 절대 열리면 안 된다."""

    def test_목록에_가이드와_현황문서가_모두_있다(self, client):
        d = client.get("/api/guide/docs").json()
        assert d["success"] is True
        assert d["guides"] and d["docs"]
        assert any(x["available"] for x in d["docs"]), "현황 문서가 하나도 안 열린다"

    def test_현황문서_원문이_열린다(self, client):
        d = client.get("/api/guide/docs/handoff").json()
        assert d["success"] is True
        assert len(d["content"]) > 100

    @pytest.mark.parametrize("key", ["../../.env", "nosuch", "..%2F..%2F.env"])
    def test_화이트리스트_밖은_404(self, client, key):
        assert client.get(f"/api/guide/docs/{key}").status_code == 404


class TestFeatureRegistry:
    """기능 지도 — 탭 라벨이 화면과 어긋나면 사람이 기능을 못 찾는다."""

    def test_6탭_전부_기능이_있다(self, client):
        d = client.get("/api/guide/features").json()
        assert d["success"] is True
        assert d["total"] >= 30
        assert len(d["groups"]) == 6
        for g in d["groups"]:
            assert g["items"], f"{g['tab_label']} 에 기능이 하나도 없다"

    def test_모든_항목이_필수_필드를_갖는다(self, client):
        for g in client.get("/api/guide/features").json()["groups"]:
            for it in g["items"]:
                for f in ("name", "desc", "how", "path", "keyword"):
                    assert it.get(f), f"{it.get('name')} 의 {f} 가 비었다"
