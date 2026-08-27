import pytest

from advisor.china_market_data import (
    DEFAULT_CHINA_ALLOCATION_SYMBOLS,
    SECURITY_MASTER,
    parse_eastmoney_klines,
    research_source_plan,
)
from advisor.data import make_demo_prices


def sample_payload(code: str = "510300") -> dict:
    return {
        "data": {
            "code": code,
            "klines": [
                "2025-01-02,3.900,3.950,3.980,3.880,100000,395000",
                "2025-01-03,3.960,4.000,4.030,3.940,110000,440000",
            ],
        }
    }


def test_china_security_master_has_unique_codes_and_expected_currencies():
    assert len(SECURITY_MASTER) == len(set(SECURITY_MASTER))
    assert SECURITY_MASTER["600519"].currency == "CNY"
    assert SECURITY_MASTER["00700"].currency == "HKD"
    for symbol in DEFAULT_CHINA_ALLOCATION_SYMBOLS:
        assert SECURITY_MASTER[symbol].currency == "CNY"


def test_default_allocation_maps_to_four_rmb_traded_products():
    assert DEFAULT_CHINA_ALLOCATION_SYMBOLS == (
        "510300",
        "159920",
        "511260",
        "518880",
    )
    assert SECURITY_MASTER["510300"].exposure_market == "A股"
    assert SECURITY_MASTER["159920"].exposure_market == "港股"
    assert SECURITY_MASTER["511260"].instrument_type == "债券ETF"
    assert SECURITY_MASTER["518880"].instrument_type == "商品ETF"
    assert set(make_demo_prices(periods=200).columns) == set(
        DEFAULT_CHINA_ALLOCATION_SYMBOLS
    )


def test_parse_eastmoney_klines_returns_sorted_code_named_series():
    security = SECURITY_MASTER["510300"]
    series = parse_eastmoney_klines(sample_payload(), security)
    assert series.name == "510300"
    assert series.index.is_monotonic_increasing
    assert series.iloc[-1] == 4.0


def test_parse_eastmoney_klines_rejects_empty_mismatch_and_nonpositive_prices():
    security = SECURITY_MASTER["510300"]
    with pytest.raises(ValueError, match="未返回"):
        parse_eastmoney_klines({"data": None}, security)
    with pytest.raises(ValueError, match="代码不匹配"):
        parse_eastmoney_klines(sample_payload("159920"), security)

    invalid = sample_payload()
    invalid["data"]["klines"][0] = (
        "2025-01-02,3.900,-1.000,3.980,3.880,100000,395000"
    )
    with pytest.raises(ValueError, match="非正数"):
        parse_eastmoney_klines(invalid, security)


def test_research_source_plan_preserves_official_and_licensed_gaps():
    a_share_sources = research_source_plan("A股")
    hk_sources = research_source_plan("港股")
    assert any(source.source_id == "cninfo" for source in a_share_sources)
    assert any(source.source_id == "hkexnews" for source in hk_sources)
    assert any(
        source.source_id == "licensed_consensus"
        and source.implementation_status == "未接入"
        for source in a_share_sources
    )
    with pytest.raises(ValueError, match="A股 or 港股"):
        research_source_plan("美股")
