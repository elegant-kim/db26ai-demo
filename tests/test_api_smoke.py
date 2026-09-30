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


class TestProductivity:
    """⑤ 개발생산성 — 시뮬레이션의 '서사'가 곧 데모의 주장이므로 단계별 성공/실패를 고정한다."""

    def test_lockfree_는_동시_차감이_되고_CHECK_로만_거부된다(self, client):
        d = client.post("/api/productivity/lockfree").json()
        assert d.get("success"), d
        steps = d["steps"]
        assert len(steps) >= 5, steps
        assert steps[2]["success"] is True, "Session B 의 동시 차감이 성공해야 Lock-Free 다"
        assert steps[3]["success"] is False, "Session C(300) 는 CHECK(balance >= 0) 로 거부돼야 한다"
        assert "400" in steps[4]["description"], "A 롤백 후 최종 잔액은 400 (500 - 100)"

    def test_priority_tx_는_6단계를_모두_돌려준다(self, client):
        d = client.post("/api/productivity/priority-tx").json()
        assert d.get("success"), d
        assert len(d["steps"]) == 6
        assert all("description" in s for s in d["steps"])


class TestDuality:
    """③ Duality — 2026-09-05 실측: 관계형 쪽 SAMPLE 문법 오류(ORA-03049)와 ETag 시뮬 4단계 중단·원복 실패가
    모두 HTTP 200 뒤에 숨어 있었다. 데모의 주장(같은 행 비교 · DB 가 ETag 로 거부 · 원복)을 고정한다."""

    def _view(self, client):
        views = (client.get("/api/duality/views").json() or {}).get("views") or []
        if not views:
            pytest.skip("Duality View 가 없다")
        return views[0].get("name") or views[0].get("view_name")

    def test_관계형과_JSON_이_같은_행을_돌려준다(self, client):
        name = self._view(client)
        d = client.post("/api/duality/compare", json={"view_name": name, "limit": 3}).json()
        assert d.get("success"), d
        assert not d.get("relational_error"), d.get("relational_error")
        assert not d.get("json_error"), d.get("json_error")
        rel, docs = d["relational_data"], d["json_data"]
        assert len(rel) == len(docs) == 3
        pk = d["relational_columns"][0]
        assert [str(r[pk]) for r in rel] == [str(x["_id"]) for x in docs], "양쪽이 같은 엔티티를 같은 순서로 보여줘야 비교다"
        assert all("_metadata" in x and x["_metadata"].get("etag") for x in docs), "문서마다 ETag 가 실려 와야 한다"

    def test_etag_시뮬은_DB가_거부하고_원복한다(self, client):
        self._view(client)
        d = client.post("/api/duality/etag-simulation").json()
        assert d.get("success") and not d.get("error"), d.get("error")
        steps = d["steps"]
        assert len(steps) == 5, [s["description"] for s in steps]
        assert steps[2]["success"] is True
        assert steps[3]["success"] is False and "ORA-42699" in steps[3]["description"], "4단계는 DB 의 ETag 검사로 거부돼야 한다"
        assert steps[4]["success"] is True and "원복" in steps[4]["description"]
        # 원복 확인 — SH 표준 신용한도 밖의 값이 남으면 시뮬이 데이터를 오염시킨 것
        q = "SELECT COUNT(*) N FROM admin.customers WHERE cust_credit_limit NOT IN (1500,3000,5000,7000,9000,10000,11000,15000)"
        r = client.post("/api/execute-sql", json={"sql": q}).json()
        assert r.get("success") and r["data"][0]["N"] == 0, r


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

    def test_작성된_가이드는_available_이_되고_열린다(self, client):
        """파일만 만들면 API 가 번호 prefix glob 으로 자동으로 집는다(코드 변경 불필요)."""
        guides = client.get("/api/guide/docs").json()["guides"]
        avail = [g for g in guides if g["available"]]
        assert avail, "작성된 가이드가 하나도 없다"
        for g in avail:
            d = client.get(f"/api/guide/docs/{g['key']}").json()
            assert d["success"] is True
            assert len(d["content"]) > 500, f"{g['key']} 내용이 너무 짧다"


class TestServing:
    """SPA 단일 서빙 (Phase 6-1 이후 레거시 없음): 비-API 경로는 전부 web/dist/index.html, 미정의 /api/* 는 JSON 404."""

    def test_루트는_SPA_index(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert 'id="app"' in r.text and "app.js?v=" not in r.text

    def test_딥링크_경로도_SPA_index(self, client):
        r = client.get("/vector?sub=search")
        assert r.status_code == 200 and 'id="app"' in r.text

    def test_legacy_경로는_더_이상_없다(self, client):
        r = client.get("/legacy")
        assert r.status_code == 200 and "app.js?v=" not in r.text  # SPA 셸이 받아 홈으로 보낸다

    def test_미정의_api_는_JSON_404(self, client):
        r = client.get("/api/nope")
        assert r.status_code == 404 and r.json().get("success") is False


class TestSelectAiShorthand:
    """`SELECT AI …` 축약구문을 /api/execute-sql 이 받는다 (2026-09-07).

    회귀 가드: 풀 커넥션에는 세션 프로필이 없어 축약구문이 일반 SELECT 로 파싱되고
    ORA-00923 이 났다. 같은 커넥션에서 SET_PROFILE 후 실행해야 한다.
    """

    PROFILE = "GEMINI_SH_PROFILE"

    def test_프로필과_함께_보내면_번역된다(self, client):
        r = client.post("/api/execute-sql", json={"sql": "select AI showsql 고객이 몇 명인가요", "profile_name": self.PROFILE}).json()
        assert r.get("success"), r.get("error")
        assert r["select_ai"] is True and r["profile_name"] == self.PROFILE
        assert r["columns"] == ["RESPONSE"], r["columns"]
        assert "CUSTOMERS" in str(r["data"][0]["RESPONSE"]).upper(), r["data"]
        assert r["select_ai_action"] == "showsql" and r["select_ai_prompt"] == "고객이 몇 명인가요"

    def test_액션을_생략하면_runsql_로_실제_결과가_온다(self, client):
        """사용자가 실제로 친 형태 — `select ai 질문`. RESPONSE 한 칸이 아니라 진짜 결과 집합이어야 한다."""
        r = client.post("/api/execute-sql", json={"sql": "select ai 고객이 몇 명인가요", "profile_name": self.PROFILE}).json()
        assert r.get("success"), r.get("error")
        assert r["select_ai_action"] == "runsql" and r["select_ai_prompt"] == "고객이 몇 명인가요"
        assert r["columns"] != ["RESPONSE"] and r["row_count"] == 1, (r["columns"], r["row_count"])

    def test_프로필_없이_보내면_명확한_오류(self, client):
        r = client.post("/api/execute-sql", json={"sql": "select AI showsql 고객이 몇 명인가요"}).json()
        assert r.get("success") is False
        assert "프로필" in r["error"], r["error"]

    def test_일반_SELECT_는_프로필_인자를_무시한다(self, client):
        r = client.post("/api/execute-sql", json={"sql": "SELECT 1 AS N FROM dual", "profile_name": self.PROFILE}).json()
        assert r.get("success") and r["data"][0]["N"] == 1
        assert r["select_ai"] is False and r["profile_name"] == ""


class TestVectorIndexPaths:
    """2026-09-08 — ① 근사 검색이 HNSW 를 타는가 · ② Hybrid Vector Index · ③ DB 안 배치 임베딩 (설계서 05 §6.6 보완)."""

    def test_실행계획_술어_유무로_HNSW_사용이_갈린다(self, client):
        d = client.post("/api/vector/explain-plan").json()
        assert d.get("success"), d.get("error")
        assert d["before"]["uses_index"] is False and "FULL" in d["before"]["access"], d["before"]["access"]
        assert d["after"]["uses_index"] is True and "HNSW" in d["after"]["access"], d["after"]["access"]

    def test_의미_검색_SQL_은_근사_검색이다(self, client):
        d = client.post("/api/vector/search", json={"query": "보험금 청구 절차", "mode": "vector", "top_k": 3}).json()
        assert d.get("success"), d.get("error")
        assert "FETCH APPROX FIRST" in d["sql_executed"] and "IS NOT NULL" not in d["sql_executed"]

    def test_하이브리드_인덱스가_있고_융합_검색이_점수_3종을_준다(self, client):
        st = client.get("/api/vector/hybrid-index").json()
        if not st.get("exists"):
            pytest.skip("Hybrid Vector Index 없음 — Vector Store 탭에서 생성")
        assert st["legacy_text_index"] is False, "옛 CONTEXT 인덱스가 남아 있으면 같은 컬럼 중복(ORA-29880)"
        d = client.post("/api/vector/search", json={"query": "자동차 사고 시 보험금 청구 절차는 어떻게 되나요?", "mode": "hvi", "top_k": 3}).json()
        assert d.get("success"), d.get("error")
        assert d["match_count"] > 0 and "DBMS_HYBRID_VECTOR.SEARCH" in d["sql_executed"]
        c = d["chunks"][0]
        assert {"hybrid_score", "similarity", "keyword_score"} <= set(c) and 0 < c["hybrid_score"] <= 1

    def test_인덱스_정보의_차원은_실측값이다(self, client):
        """2026-09-09 보완 ⑤: vector_dimensions 가 설정 상수(768 하드코딩)였다 — 저장된 벡터의 VECTOR_DIMS 로 잰다."""
        d = client.get("/api/vector/index-info").json()
        assert d["dimensions_measured"] is True and isinstance(d["vector_dimensions"], int) and d["vector_dimensions"] > 0
        assert "CREATE VECTOR INDEX" in d.get("hnsw_ddl", "")

    def test_하이브리드_인덱스_내부_표본(self, client):
        """P4 (2026-09-09): 인덱스 하나 = 테이블 여러 개. $I 토큰 · $VR 조각(벡터 차원 포함)이 표본으로 온다."""
        d = client.get("/api/vector/hybrid-index/internals").json()
        assert d.get("success"), d.get("error")
        if not d["exists"]:
            pytest.skip("Hybrid Vector Index 없음")
        names = [t["name"] for t in d["tables"]]
        assert any(n.endswith("$I") for n in names) and any(n.endswith("$VR") for n in names), names
        assert d["tokens"] and d["tokens"][0]["count"] >= d["tokens"][-1]["count"]
        assert d["pieces"] and all(p["dims"] > 0 and p["text"] for p in d["pieces"])

    def test_키워드_검색은_여전히_CONTAINS_로_돈다(self, client):
        d = client.post("/api/vector/search", json={"query": "보험금 청구", "mode": "keyword", "top_k": 3}).json()
        assert d.get("success"), d.get("error")
        assert "CONTAINS" in d["sql_executed"] and "LIKE 폴백" not in d["sql_executed"], d["sql_executed"][:200]


class TestVectorSubtabLinks:
    """2026-09-09 P1 — Vector 서브탭 재편(env/load/search/internals). 기능 지도의 딥링크가 존재하는 서브탭만 가리켜야 한다."""

    def test_기능지도_vector_딥링크는_새_서브탭_id_만_쓴다(self, client):
        d = client.get("/api/guide/features").json()
        import re
        subs = set()
        for g in d["groups"]:
            for f in g.get("features", g.get("items", [])):
                m = re.search(r"/vector\?sub=([a-z]+)", f.get("path", ""))
                if m:
                    subs.add(m.group(1))
        assert subs and subs <= {"env", "load", "search", "internals"}, subs


class TestSlides:
    """장표 연동(P5, 2026-09-29) — 카탈로그 API 와 /slides 정적 서빙. 표본 덱(docs/slides/src/sample.pdf)은 추적 파일이라 항상 있어야 한다."""

    def test_카탈로그_모양과_표본_덱(self, client):
        d = client.get("/api/guide/slides").json()
        assert d["success"] is True
        for k in ("available", "decks", "anchors", "unresolved"):
            assert k in d
        sample = next((x for x in d["decks"] if x["deck"] == "sample"), None)
        assert sample, "표본 덱 sample 이 카탈로그에 없다 — docs/slides/src/sample.pdf 가 있어야 한다"
        assert sample["mode"] in ("images", "pdf") and sample["pdf"] == "/slides/src/sample.pdf"
        if sample["mode"] == "images":
            assert sample["pages"] == 2 and sample["tags"] == {"SM-01": 1, "SM-02": 2}, sample["tags"]
            assert sample["page_tags"] == ["SM-01", "SM-02"]

    def test_정적_서빙_pdf_와_이미지(self, client):
        r = client.get("/slides/src/sample.pdf")
        assert r.status_code == 200 and r.headers["content-type"].startswith("application/pdf")
        d = client.get("/api/guide/slides").json()
        sample = next(x for x in d["decks"] if x["deck"] == "sample")
        if sample["mode"] == "images":
            r = client.get(sample["image_base"] + "001.webp")
            assert r.status_code == 200 and "image" in r.headers["content-type"]
            assert client.get(sample["thumb"]).status_code == 200

    def test_기능_항목마다_slides_필드가_있다(self, client):
        for g in client.get("/api/guide/features").json()["groups"]:
            for it in g["items"]:
                assert isinstance(it.get("slides"), list), it["name"]

    def test_앵커는_덱에_있는_꼬리표와_일치한다(self, client):
        d = client.get("/api/guide/slides").json()
        tags = {t for x in d["decks"] for t in x["tags"]}
        for a in d["anchors"]:
            assert a["tag"] in tags and a["page"] >= 1
        for u in d["unresolved"]:
            assert u["tag"] not in tags

    def test_slides_경로_밖은_못_읽는다(self, client):
        """`..` 를 URL 인코딩으로 숨겨도 StaticFiles 가 docs/slides 밖을 주면 안 된다. (클라이언트는 맨 `..` 을 미리 접어 `/.env` 로 보내는데,
        그건 SPA 셸(HTML)이 받는다 — 시크릿이 아닌 것까지 확인한다.)"""
        r = client.get("/slides/src/%2e%2e/%2e%2e/%2e%2e/.env")
        assert r.status_code in (404, 400), r.status_code
        r = client.get("/.env")
        assert "text/html" in r.headers["content-type"] and "ORACLE_" not in r.text


class TestConversationAndLog:
    """PoC 1-A (2026-09-29) — 멀티턴 대화 발급·삭제, 모든 Select AI 호출의 AI_QUERY_LOG 기록."""

    def _last_log(self, client, log_id):
        d = client.post("/api/execute-sql", json={"sql": f"SELECT id, source, action, status, conversation_id, model, row_count FROM ai_query_log WHERE id = {int(log_id)}"}).json()
        assert d["success"] and d["data"], d
        return d["data"][0]

    def test_대화_발급과_삭제(self, client):
        r = client.post("/api/conversations", json={"title": "pytest"}).json()
        assert r["success"] and len(r["conversation_id"]) == 36, r
        assert client.delete(f"/api/conversations/{r['conversation_id']}").json()["success"] is True

    def test_ask_는_이력_id_와_대화_id_를_돌려주고_로그에_남는다(self, client):
        cid = client.post("/api/conversations", json={"title": "pytest"}).json()["conversation_id"]
        try:
            r = client.post("/api/ask", json={"prompt": "한 단어로 인사", "action": "chat", "profile_name": "GEMINI_SH_PROFILE", "conversation_id": cid}).json()
            assert r["success"], r
            assert r["conversation_id"] == cid and r["log_id"] and r["model"], r
            row = self._last_log(client, r["log_id"])
            assert row["SOURCE"] == "GENERATE" and row["ACTION"] == "chat" and row["STATUS"] == "SUCCEEDED" and row["CONVERSATION_ID"] == cid
        finally:
            client.delete(f"/api/conversations/{cid}")

    def test_잘못된_프로필도_FAILED_로_로그에_남는다(self, client):
        r = client.post("/api/ask", json={"prompt": "x", "action": "chat", "profile_name": "NO_SUCH_PROFILE_XYZ"})
        assert r.status_code == 500
        d = r.json()
        assert d["success"] is False and d.get("log_id"), d
        assert self._last_log(client, d["log_id"])["STATUS"] == "FAILED"

    def test_직접_실행한_SELECT_AI_도_RAWSQL_로_남는다(self, client):
        before = client.post("/api/execute-sql", json={"sql": "SELECT NVL(MAX(id),0) m FROM ai_query_log"}).json()["data"][0]["M"]
        r = client.post("/api/execute-sql", json={"sql": "SELECT AI chat 한 단어로 인사", "profile_name": "GEMINI_SH_PROFILE"}).json()
        assert r["success"] and r["select_ai"], r
        d = client.post("/api/execute-sql", json={"sql": f"SELECT source, action, status FROM ai_query_log WHERE id > {before} ORDER BY id DESC FETCH FIRST 1 ROWS ONLY"}).json()
        assert d["data"] and d["data"][0]["SOURCE"] == "RAWSQL" and d["data"][0]["ACTION"] == "chat", d


class TestQueryHistory:
    """PoC 1-C (2026-09-29) — 이력 API. LLM 을 부르지 않는다(이미 쌓인 AI_QUERY_LOG 를 읽는다)."""

    def test_목록_모양과_페이징(self, client):
        d = client.get("/api/nl2sql/history", params={"size": 5}).json()
        assert d["success"] and d["page"] == 1 and d["size"] == 5 and "sql" in d
        assert isinstance(d["total"], int) and len(d["rows"]) <= 5
        if d["rows"]:
            r = d["rows"][0]
            for k in ("ID", "STARTED_AT", "SOURCE", "PROFILE_NAME", "ACTION", "QUESTION", "STATUS", "ELAPSED_MS", "FEEDBACK_TYPE"):
                assert k in r, k

    def test_필터가_바인드로_먹는다(self, client):
        d = client.get("/api/nl2sql/history", params={"q": "인사", "status": "SUCCEEDED", "action": "chat"}).json()
        assert d["success"]
        for r in d["rows"]:
            assert r["STATUS"] == "SUCCEEDED" and r["ACTION"] == "chat" and "인사" in (r["QUESTION"] or "")
        assert "'인사'" in d["sql"] and ":q" not in d["sql"]

    def test_잘못된_필터는_400(self, client):
        assert client.get("/api/nl2sql/history", params={"action": "dropdb"}).status_code == 400
        assert client.get("/api/nl2sql/history", params={"feedback": "maybe"}).status_code == 400

    def test_요약_카드(self, client):
        d = client.get("/api/nl2sql/history/summary").json()
        assert d["success"]
        for k in ("total", "succeeded", "failed", "success_rate", "avg_ms", "max_ms", "feedback_rate", "by_profile", "by_action"):
            assert k in d, k
        assert d["total"] == d["succeeded"] + d["failed"]

    def test_상세와_404(self, client):
        d = client.get("/api/nl2sql/history", params={"size": 1}).json()
        if d["rows"]:
            x = client.get(f"/api/nl2sql/history/{d['rows'][0]['ID']}").json()
            assert x["success"] and "QUESTION" in x and isinstance(x["feedback"], list)
        assert client.get("/api/nl2sql/history/999999999").status_code == 404


class TestPromptPresets:
    """PoC 1-D (2026-09-29) — 저장 질문 프리셋 CRUD. 시드(72번)가 들어 있으면 SH 프로필에 14건 이상."""

    def test_프로필별_목록(self, client):
        d = client.get("/api/nl2sql/presets", params={"profile": "GEMINI_SH_PROFILE"}).json()
        assert d["success"] and isinstance(d["presets"], list)
        for p in d["presets"]:
            assert p["PROFILE_NAME"] is None or "SH" in p["PROFILE_NAME"], p
            assert p["TITLE"] and p["QUESTION"]

    def test_추가_수정_삭제(self, client):
        r = client.post("/api/nl2sql/presets", json={"title": "pytest 프리셋", "question": "pytest 질문입니다", "action": "showsql", "profile_name": "%PYTEST%"}).json()
        assert r["success"] and r["id"], r
        pid = r["id"]
        try:
            got = [p for p in client.get("/api/nl2sql/presets", params={"profile": "MY_PYTEST_PROFILE"}).json()["presets"] if p["ID"] == pid]
            assert got and got[0]["ACTION"] == "showsql"
            assert not [p for p in client.get("/api/nl2sql/presets", params={"profile": "GEMINI_SH_PROFILE"}).json()["presets"] if p["ID"] == pid], "패턴이 안 맞는 프로필에 보이면 안 된다"
            u = client.put(f"/api/nl2sql/presets/{pid}", json={"title": "수정", "question": "수정된 질문", "action": "runsql", "profile_name": None}).json()
            assert u["success"]
            assert [p for p in client.get("/api/nl2sql/presets", params={"profile": "GEMINI_SH_PROFILE"}).json()["presets"] if p["ID"] == pid and p["TITLE"] == "수정"], "NULL 패턴은 모든 프로필에 보여야 한다"
        finally:
            assert client.delete(f"/api/nl2sql/presets/{pid}").json()["success"]
        assert client.delete(f"/api/nl2sql/presets/{pid}").status_code == 404

    def test_검증_400(self, client):
        assert client.post("/api/nl2sql/presets", json={"title": "", "question": "q"}).status_code == 400
        assert client.post("/api/nl2sql/presets", json={"title": "t", "question": "q", "action": "dropdb"}).status_code == 400


class TestFeedback:
    """PoC 1-B (2026-09-30) — DBMS_CLOUD_AI.FEEDBACK + AI_FEEDBACK_LOG. 등록은 SELECT AI 문장을 만들기 위해 LLM 을 1회 부른다."""

    def test_상태(self, client):
        d = client.get("/api/nl2sql/feedback/status", params={"profile": "GEMINI_SH_PROFILE"}).json()
        assert d["success"]
        for k in ("embedding_model", "index_name", "index_rows", "app_rows", "ready"):
            assert k in d, k
        assert d["ready"] is True, "GEMINI_SH_PROFILE 에 embedding_model 이 있어야 한다(51번 §2)"

    def test_잘못된_type_과_없는_이력(self, client):
        assert client.post("/api/nl2sql/feedback", json={"log_id": 1, "feedback_type": "meh"}).status_code == 400
        assert client.post("/api/nl2sql/feedback", json={"log_id": 999999999, "feedback_type": "positive"}).status_code == 404

    def test_등록_교체_삭제_한_사이클(self, client):
        # 성공한 showsql 이력 하나를 고른다(질문이 있어야 한다)
        rows = client.get("/api/nl2sql/history", params={"status": "SUCCEEDED", "action": "showsql", "profile": "GEMINI_SH_PROFILE", "size": 1}).json()["rows"]
        if not rows:
            pytest.skip("피드백을 붙일 showsql 이력이 없다")
        log_id = rows[0]["ID"]
        r = client.post("/api/nl2sql/feedback", json={"log_id": log_id, "feedback_type": "positive", "feedback_content": "pytest 좋음"}).json()
        assert r["success"], r
        fid = r["feedback_id"]
        try:
            r2 = client.post("/api/nl2sql/feedback", json={"log_id": log_id, "feedback_type": "negative", "feedback_content": "pytest 나쁨", "corrected_sql": "SELECT 1 FROM dual"}).json()
            assert r2["success"] and r2["replaced"] is True, r2
            fid = r2["feedback_id"]
            d = client.get(f"/api/nl2sql/history/{log_id}").json()
            assert len(d["feedback"]) == 1 and d["feedback"][0]["FEEDBACK_TYPE"] == "negative"
            st = client.get("/api/nl2sql/feedback/status", params={"profile": "GEMINI_SH_PROFILE"}).json()
            assert st["index_rows"] is not None and st["index_rows"] >= 1
        finally:
            assert client.delete(f"/api/nl2sql/feedback/{fid}").json()["success"]
        assert client.get(f"/api/nl2sql/history/{log_id}").json()["feedback"] == []


class TestFewshot:
    """PoC 2-A (2026-09-30) — 템플릿·파싱·검증(EXPLAIN PLAN)·등록 1건(LLM 1회)·삭제."""

    def test_템플릿_csv(self, client):
        r = client.get("/api/nl2sql/fewshot/template")
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv") and r.text.startswith("question,sql,note")

    def test_파싱과_검증(self, client):
        csv = "question,sql,note\n채널 수는?,SELECT COUNT(*) FROM channels,ok\n틀린 SQL,SELECT * FROM no_such_table_xyz,bad\nDML,DELETE FROM channels,dml\n"
        d = client.post("/api/nl2sql/fewshot/parse", files={"file": ("t.csv", csv.encode("utf-8"), "text/csv")}).json()
        assert d["success"] and d["total"] == 3, d
        v = client.post("/api/nl2sql/fewshot/validate", json={"rows": d["rows"]}).json()
        assert v["success"] and v["valid"] == 1 and v["invalid"] == 2, v
        assert v["rows"][0]["valid"] is True and "ORA-00942" in (v["rows"][1]["error"] or "") and "SELECT" in (v["rows"][2]["error"] or "")

    def test_등록_1건_SSE_후_삭제(self, client):
        rows = [{"row": 1, "question": "pytest fewshot 채널 수는?", "sql": "SELECT COUNT(*) FROM channels", "note": "pytest"}]
        with client.stream("POST", "/api/nl2sql/fewshot/register", json={"rows": rows, "profile_name": "GEMINI_SH_PROFILE"}) as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            events = []
            for line in r.iter_lines():
                if line.startswith("data: "):
                    import json as _j
                    events.append(_j.loads(line[6:]))
        row = next(e for e in events if "ok" in e)
        done = next(e for e in events if "total" in e)
        assert row["ok"] is True and row["feedback_id"], row
        assert done["ok"] == 1 and done["failed"] == 0
        fb = client.get("/api/nl2sql/feedback", params={"profile": "GEMINI_SH_PROFILE"}).json()["feedback"]
        mine = [f for f in fb if f["ID"] == row["feedback_id"]]
        assert mine and mine[0]["SOURCE"] == "FEWSHOT" and mine[0]["HAS_CORRECTED"] == 1
        assert client.delete(f"/api/nl2sql/feedback/{row['feedback_id']}").json()["success"]


class TestAccuracyScenario:
    """PoC 2-B·2-C (2026-09-30) — 3단계 SSE. LLM 을 5~6회 부른다(1분 안팎). 끝나면 프로필 속성이 원래대로여야 한다."""

    def test_3단계_후_속성_복원(self, client):
        import json as _j
        before = client.post("/api/env-info", json={"kind": "profile", "profile_name": "GEMINI_SH_PROFILE"}).json()["result"]["data"]
        attrs0 = {r["ATTRIBUTE_NAME"]: str(r["ATTRIBUTE_VALUE"]) for r in before if r["ATTRIBUTE_NAME"] in ("annotations", "comments")}
        events = []
        with client.stream("POST", "/api/nl2sql/accuracy-scenario", json={"question": "판매 채널은 몇 개인가?", "profile_name": "GEMINI_SH_PROFILE"}) as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            cur_type = ""
            for line in r.iter_lines():
                if line.startswith("event: "):
                    cur_type = line[7:].strip()
                elif line.startswith("data: "):
                    events.append((cur_type, _j.loads(line[6:])))
        types = [t for t, _ in events]
        assert types[0] == "start" and types[-1] == "done", types
        done = [d for t, d in events if t == "done"][0]
        steps = {d["n"]: d for t, d in events if t == "step" and d.get("status") == "done"}
        assert set(steps) == {1, 2, 3}, steps.keys()
        assert steps[2].get("sql") and steps[2].get("prompt"), steps[2]
        assert steps[3].get("prompt") and "examples" in steps[3]["prompt"].lower(), "③ 프롬프트에 피드백 예시가 주입돼야 한다"
        assert done["feedback_kept"] is False and done["feedback_id"]
        after = client.post("/api/env-info", json={"kind": "profile", "profile_name": "GEMINI_SH_PROFILE"}).json()["result"]["data"]
        attrs1 = {r["ATTRIBUTE_NAME"]: str(r["ATTRIBUTE_VALUE"]) for r in after if r["ATTRIBUTE_NAME"] in ("annotations", "comments")}
        assert attrs1 == attrs0, (attrs0, attrs1)


class TestCompareProfiles:
    """PoC 3-C (2026-09-30) — 같은 질문을 프로필 2개로 (SSE). GROQ 는 키 문제로 실패할 수 있어 '실패도 한 열' 로 받는다."""

    def test_두_프로필_SSE(self, client):
        import json as _j
        events = []
        with client.stream("POST", "/api/nl2sql/compare-profiles", json={"question": "판매 채널은 몇 개인가?", "profiles": ["GEMINI_SH_PROFILE", "GROQ_SH_PROFILE"]}) as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            cur = ""
            for line in r.iter_lines():
                if line.startswith("event: "):
                    cur = line[7:].strip()
                elif line.startswith("data: "):
                    events.append((cur, _j.loads(line[6:])))
        start = [d for t, d in events if t == "start"][0]
        assert [m["profile"] for m in start["profiles"]] == ["GEMINI_SH_PROFILE", "GROQ_SH_PROFILE"] and start["profiles"][0]["model"]
        done_steps = {d["profile"]: d for t, d in events if t == "step" and d.get("status") == "done"}
        assert set(done_steps) == {"GEMINI_SH_PROFILE", "GROQ_SH_PROFILE"}
        assert done_steps["GEMINI_SH_PROFILE"].get("sql")
        assert events[-1][0] == "done" and "fastest" in events[-1][1]

    def test_프로필_하나면_400(self, client):
        assert client.post("/api/nl2sql/compare-profiles", json={"question": "x", "profiles": ["GEMINI_SH_PROFILE"]}).status_code == 400


class TestProfileWizardApi:
    """PoC 3-A — 메타 · 미리보기 · 실제 생성/삭제(OpenAI 호환 + OCI 모의). LLM 은 부르지 않는다."""

    def test_메타(self, client):
        d = client.get("/api/nl2sql/profile-wizard/meta").json()
        assert d["success"] and d["providers"] and d["oci_regions"] and any(c["credential_name"] == "GEMINI_CRED" for c in d["credentials"])
        assert any(t["name"] == "POC_STORES" for t in d["tables"])

    def test_미리보기와_검증(self, client):
        r = client.post("/api/profiles/create", json={"profile_name": "WIZ_PREVIEW", "form": {"provider": "openai", "credential_name": "GEMINI_CRED", "model": "gemini-3.8-flash"}, "preview_only": True}).json()
        assert r["success"] and r["preview"] and "CREATE_PROFILE" in r["plsql"]
        r = client.post("/api/profiles/create", json={"profile_name": "bad name", "form": {"provider": "oci", "credential_name": "X"}, "preview_only": True})
        assert r.status_code == 400 and "region" in r.json()["error"]

    def test_생성_환경탭_삭제(self, client):
        # OCI 모의 프로필 — 크리덴셜은 아무 것이나(생성은 호출 없이 된다), 환경 탭이 region 으로 호스트를 만드는지 본다
        r = client.post("/api/profiles/create", json={"profile_name": "WIZ_OCI_TEST", "form": {"provider": "oci", "credential_name": "GEMINI_CRED", "model": "cohere.command-r-plus-08-2024", "region": "ap-osaka-1", "oci_apiformat": "COHERE", "object_list": [{"owner": "ADMIN", "name": "POC_STORES"}]}, "description": "pytest"}).json()
        assert r["success"], r
        try:
            attrs = {x["ATTRIBUTE_NAME"]: str(x["ATTRIBUTE_VALUE"]) for x in client.post("/api/env-info", json={"kind": "profile", "profile_name": "WIZ_OCI_TEST"}).json()["result"]["data"]}
            assert attrs["provider"] == "oci" and attrs["region"] == "ap-osaka-1" and attrs["oci_apiformat"] == "COHERE"
            assert any(p["profile_name"] == "WIZ_OCI_TEST" for p in client.get("/api/profiles").json()["profiles"])
        finally:
            assert client.delete("/api/profiles/WIZ_OCI_TEST").json()["success"]
        assert not any(p["profile_name"] == "WIZ_OCI_TEST" for p in client.get("/api/profiles").json()["profiles"])

