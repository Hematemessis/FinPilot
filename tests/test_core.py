import numpy as np

from advisor.agent import PortfolioAdvisorAgent
from advisor.backtest import backtest_strategy
from advisor.data import make_demo_prices
from advisor.portfolio import STRATEGIES, build_weights
from advisor.risk import RiskAnswers, assess_risk


def balanced_answers() -> RiskAnswers:
    return RiskAnswers(4, 3, 4, 3, 4)


def test_higher_liquidity_need_lowers_risk_score():
    low_need = RiskAnswers(4, 3, 4, 1, 4)
    high_need = RiskAnswers(4, 3, 4, 5, 4)
    assert assess_risk(low_need).score > assess_risk(high_need).score


def test_all_strategies_return_valid_weights():
    prices = make_demo_prices(periods=500)
    profile = assess_risk(balanced_answers())
    for strategy in STRATEGIES:
        weights = build_weights(prices.iloc[:300], profile, strategy)
        assert np.isclose(weights.sum(), 1.0)
        assert (weights >= 0).all()
        assert np.isclose(weights["现金"], profile.min_cash_weight)


def test_backtest_is_out_of_sample_and_finite():
    prices = make_demo_prices(periods=500)
    profile = assess_risk(balanced_answers())
    result = backtest_strategy(prices, profile, "风险适配")
    assert result.train_end < result.test_start
    assert len(result.daily_returns) > 0
    assert all(np.isfinite(value) for value in result.metrics.values())


def test_agent_exposes_comparisons_and_synthetic_data_boundary():
    report = PortfolioAdvisorAgent().run(
        make_demo_prices(periods=500),
        balanced_answers(),
        data_label="合成演示数据",
    )
    assert set(report.comparisons) == set(STRATEGIES)
    assert any("不代表真实投资业绩" in note for note in report.guardrails)

