from __future__ import annotations

from tg_time_logger.shop_pricing import extract_nok_candidates, nok_to_fun_minutes, parse_nok_literal, pick_nok_candidate


def test_parse_nok_literal_variants() -> None:
    assert parse_nok_literal("4990nok") == 4990
    assert parse_nok_literal("nok4990") == 4990
    assert parse_nok_literal("kr2490") == 2490
    assert parse_nok_literal("2490") is None


def test_extract_nok_candidates_from_search_text() -> None:
    text = "Apple Watch around 5 490 kr in Norway. Another shop: NOK 5,790."
    values = extract_nok_candidates(text)
    assert values
    assert values[0] == 5490
    assert 5790 in values
    assert pick_nok_candidate(text) == 5490


def test_nok_to_fun_minutes_ratio() -> None:
    assert nok_to_fun_minutes(100, 3) == 300
    assert nok_to_fun_minutes(2490, 3) == 7470

