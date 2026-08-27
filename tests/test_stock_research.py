from datetime import date

import pytest

from advisor.stock_research import (
    CompanyResearchSnapshot,
    StockResearchAgent,
    ValuationInputs,
    assess_valuation,
    calculate_pe,
    make_demo_company_snapshot,
)


def test_pe_is_not_reported_for_non_positive_earnings():
    assert calculate_pe(100.0, 5.0) == 20.0
    assert calculate_pe(100.0, 0.0) is None
    assert calculate_pe(100.0, -2.0) is None


def test_forward_valuation_flags_estimate_cuts():
    inputs = ValuationInputs(
        price=100.0,
        currency="USD",
        eps_ttm=4.0,
        eps_ntm=5.0,
        eps_fy1=4.8,
        peer_median_ntm_pe=22.0,
        historical_median_ntm_pe=24.0,
        estimate_revision_90d=-0.08,
        estimate_dispersion=0.10,
        analyst_count=10,
        price_as_of=date(2026, 1, 15),
        estimate_as_of=date(2026, 1, 15),
        price_source_id="price",
        estimate_source_id="estimates",
    )
    result = assess_valuation(inputs)
    assert result.pe_ttm == 25.0
    assert result.pe_ntm == 20.0
    assert "等待盈利验证" in result.posture
    assert any("盈利预测明显下调" in warning for warning in result.warnings)


def test_demo_card_is_explicitly_non_live_and_not_a_buy_signal():
    card = StockResearchAgent().run(make_demo_company_snapshot())
    assert card.research_status == "等待业绩验证"
    assert card.evidence_confidence == "流程演示"
    assert "虚构离线样例" in card.boundary_note
    assert "买入" not in card.research_status
    assert len(card.sources) >= 3


def test_demo_research_samples_use_a_share_and_hk_share_currencies():
    assert make_demo_company_snapshot("A股").valuation.currency == "CNY"
    assert make_demo_company_snapshot("港股").valuation.currency == "HKD"
    with pytest.raises(ValueError, match="A股 or 港股"):
        make_demo_company_snapshot("美股")


def test_missing_metric_source_downgrades_research_status():
    snapshot = make_demo_company_snapshot()
    broken_metric = snapshot.metrics[0].__class__(
        name="无法溯源的指标",
        display_value="10%",
        period="演示期",
        source_id="missing_source",
        evidence_type="未知",
    )
    broken_snapshot = CompanyResearchSnapshot(
        company_name=snapshot.company_name,
        ticker=snapshot.ticker,
        exchange=snapshot.exchange,
        business_summary=snapshot.business_summary,
        earning_power=snapshot.earning_power,
        latest_event=snapshot.latest_event,
        primary_risk=snapshot.primary_risk,
        market_expectation=snapshot.market_expectation,
        variant_hypothesis=snapshot.variant_hypothesis,
        first_rejection=snapshot.first_rejection,
        validation_conditions=snapshot.validation_conditions,
        invalidation_conditions=snapshot.invalidation_conditions,
        missing_evidence=snapshot.missing_evidence,
        critical_flags=snapshot.critical_flags,
        metrics=(broken_metric, *snapshot.metrics[1:]),
        valuation=snapshot.valuation,
        sources=snapshot.sources,
        is_synthetic=snapshot.is_synthetic,
    )
    card = StockResearchAgent().run(broken_snapshot)
    assert card.research_status == "数据不足"
    assert any("missing_source" in gap for gap in card.missing_evidence)


def test_valuation_rejects_invalid_price():
    with pytest.raises(ValueError, match="Price"):
        ValuationInputs(
            price=0.0,
            currency="USD",
            eps_ttm=1.0,
            eps_ntm=1.0,
            eps_fy1=1.0,
            peer_median_ntm_pe=20.0,
            historical_median_ntm_pe=20.0,
            estimate_revision_90d=0.0,
            estimate_dispersion=0.1,
            analyst_count=5,
            price_as_of=date(2026, 1, 1),
            estimate_as_of=date(2026, 1, 1),
            price_source_id="price",
            estimate_source_id="estimates",
        )
