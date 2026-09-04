"""단위 테스트 — DB·서버 없이 도는 순수 함수 검증."""
from __future__ import annotations

import pytest

from app.vector_search import _ctx_stem, _vec_to_str, to_contains_query


class TestToContainsQuery:
    """자연어 → Oracle Text ACCUM 구문 변환.

    회귀 가드: 2026-09-04 이전에는 사용자 문장을 CONTAINS 에 그대로 넣어
    ORA-29902 로 터졌고, LIKE 폴백이 0건이라 하이브리드가 벡터 전용으로 퇴화했다.
    """

    def test_자연어_문장이_ACCUM_구문으로_변환된다(self):
        got = to_contains_query("인덱스를 효율적으로 사용하려면 어떻게 SQL을 작성해야 하나요?")
        assert got is not None
        assert "?" not in got, "예약 연산자가 남으면 ORA-29902 가 난다"
        assert "," in got, "AND 가 아니라 ACCUM(쉼표)이어야 한다"
        assert "인덱스%" in got, "조사를 떼고 우측 절단해야 한다"

    def test_영문에는_우측절단을_붙이지_않는다(self):
        # "SQL을" 을 우측 절단하면 "SQ%" 로 과매칭된다
        got = to_contains_query("SQL을 작성한다")
        assert "SQL" in got
        assert "SQ%" not in got

    def test_질문_어투는_불용어로_빠진다(self):
        got = to_contains_query("인덱스가 무엇인가요")
        assert "무엇" not in got

    @pytest.mark.parametrize("bad", ["", "?!?", "   ", "&|~"])
    def test_쓸모없는_입력은_None(self, bad):
        # None 이면 호출부가 LIKE 로 폴백한다
        assert to_contains_query(bad) is None

    def test_중복_어간은_한_번만(self):
        got = to_contains_query("인덱스 인덱스를 인덱스가")
        assert got.count("인덱스") == 1


class TestCtxStem:
    @pytest.mark.parametrize("token,expected", [
        ("인덱스를", "인덱스"),
        ("효율적으로", "효율"),
        ("SQL을", "SQL"),
        ("인덱스", "인덱스"),
        ("SELECT", "SELECT"),
    ])
    def test_어간_추출(self, token, expected):
        assert _ctx_stem(token) == expected


class TestVecToStr:
    def test_벡터를_오라클_리터럴로(self):
        assert _vec_to_str([1.0, -0.5, 0.25]) == "[1.0,-0.5,0.25]"

    def test_공백이_없어야_한다(self):
        # 공백이 섞이면 TO_VECTOR 파싱이 실패할 수 있다
        assert " " not in _vec_to_str([0.1, 0.2, 0.3])
