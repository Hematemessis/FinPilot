import pandas as pd
import pytest

from advisor.official_research import (
    evidence_audit_summary,
    get_official_company_research,
    load_evidence_tables,
    research_universe,
)


def test_official_research_universe_contains_moutai_and_tencent():
    assert research_universe() == {
        "600519": "贵州茅台（600519）",
        "00700": "腾讯控股（00700）",
    }


def test_moutai_card_uses_verified_interim_financials():
    research = get_official_company_research("600519")
    assert research.research_status == "等待盈利恢复"
    assert research.valuation_status == "动态估值数据不足"
    assert any(fact.value == "907.0 亿元" for fact in research.facts)
    assert any(fact.change == "同比 -1.95%" for fact in research.facts)
    assert all(source.source_id.startswith("SRC-MT-") for source in research.sources)


def test_tencent_card_separates_fundamentals_from_valuation():
    research = get_official_company_research("00700")
    assert research.research_status == "基本面通过，估值待补"
    assert research.valuation_status == "动态估值数据不足"
    assert any(fact.value == "4,012.4 亿元" for fact in research.facts)
    assert "补齐估值" in research.suggested_action
    assert all(source.source_id.startswith("SRC-TC-") for source in research.sources)


def test_evidence_tables_have_complete_provenance_and_passed_checks():
    source_index, financials, qa_flags, checks = load_evidence_tables()
    assert set(financials["source_id"]).issubset(set(source_index["source_id"]))
    assert not financials[["period_end", "currency", "units"]].isna().any().any()
    assert (checks["result"] == "pass").all()
    assert (qa_flags["status"] == "open").any()
    assert pd.api.types.is_numeric_dtype(financials["normalized_value"])


def test_audit_summary_matches_persisted_audit_outputs():
    summary = evidence_audit_summary()
    assert summary["sources"] == 5
    assert summary["financial_rows"] >= 25
    assert summary["passed_checks"] == 9
    assert summary["open_flags"] == 6


def test_unsupported_company_is_rejected():
    with pytest.raises(ValueError, match="不支持"):
        get_official_company_research("000001")
