from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .backtest import BacktestResult, compare_strategies
from .data import validate_prices
from .portfolio import STRATEGIES
from .risk import RiskAnswers, RiskProfile, assess_risk


@dataclass(frozen=True)
class AdvisorReport:
    profile: RiskProfile
    selected_strategy: str
    weights: pd.Series
    primary_result: BacktestResult
    comparisons: dict[str, BacktestResult]
    explanation: tuple[str, ...]
    guardrails: tuple[str, ...]
    workflow_trace: tuple[str, ...]
    data_label: str


class PortfolioAdvisorAgent:
    """A deterministic decision agent with explicit tools and guardrails."""

    def run(
        self,
        prices: pd.DataFrame,
        answers: RiskAnswers,
        strategy: str = "风险适配",
        fee_bps: float = 10.0,
        data_label: str = "用户数据",
    ) -> AdvisorReport:
        if strategy not in STRATEGIES:
            raise ValueError(f"Unknown strategy: {strategy}")

        workflow: list[str] = []
        clean_prices = validate_prices(prices)
        workflow.append(f"数据校验：{len(clean_prices)} 个对齐交易日，{len(clean_prices.columns)} 类资产")

        profile = assess_risk(answers)
        workflow.append(f"风险评估：得分 {profile.score}/100，识别为{profile.level}")

        comparisons = compare_strategies(clean_prices, profile, fee_bps=fee_bps)
        primary = comparisons[strategy]
        workflow.append(f"策略执行：用前 65% 数据拟合，在后 35% 数据做样本外检验")
        workflow.append("风险复核：检查回撤容忍度、集中度与数据使用边界")

        guardrails = self._build_guardrails(clean_prices, profile, primary, data_label)
        explanation = self._build_explanation(profile, primary)
        return AdvisorReport(
            profile=profile,
            selected_strategy=strategy,
            weights=primary.weights,
            primary_result=primary,
            comparisons=comparisons,
            explanation=explanation,
            guardrails=guardrails,
            workflow_trace=tuple(workflow),
            data_label=data_label,
        )

    @staticmethod
    def _build_guardrails(
        prices: pd.DataFrame,
        profile: RiskProfile,
        result: BacktestResult,
        data_label: str,
    ) -> tuple[str, ...]:
        notes: list[str] = []
        drawdown = abs(result.metrics["最大回撤"])
        if drawdown > profile.max_drawdown_tolerance:
            notes.append(
                f"回撤预警：样本外最大回撤 {drawdown:.1%}，超过用户容忍上限 "
                f"{profile.max_drawdown_tolerance:.1%}；该方案需要降风险后才能进入执行环节。"
            )
        else:
            notes.append(
                f"回撤校验通过：样本外最大回撤 {drawdown:.1%}，未超过问卷上限 "
                f"{profile.max_drawdown_tolerance:.1%}。"
            )

        risky_weights = result.weights.drop("现金")
        if risky_weights.max() >= profile.max_asset_weight - 1e-4:
            notes.append("集中度提醒：至少一类资产触及配置上限，需关注单一风险来源。")
        if len(prices) < 504:
            notes.append("数据提醒：历史不足两个交易年，结论稳定性有限。")
        if "演示" in data_label or "合成" in data_label:
            notes.append("证据边界：当前为合成演示数据，指标只用于验证流程，不代表真实投资业绩。")
        notes.append("合规边界：输出是研究与产品演示，不构成个性化证券买卖建议。")
        return tuple(notes)

    @staticmethod
    def _build_explanation(
        profile: RiskProfile, result: BacktestResult
    ) -> tuple[str, ...]:
        largest_asset = result.weights.drop("现金").idxmax()
        largest_weight = result.weights.drop("现金").max()
        return (
            f"用户被识别为{profile.level}（{profile.score}/100）。{profile.rationale}",
            f"本次选择“{result.strategy}”策略，保留 {result.weights['现金']:.1%} 现金，"
            f"最高配置为{largest_asset} {largest_weight:.1%}。",
            f"评价只使用未参与拟合的后 35% 时间区间；样本外年化收益为"
            f" {result.metrics['年化收益']:.1%}，最大回撤为 {result.metrics['最大回撤']:.1%}。",
            "收益指标用于策略比较，最终是否可执行必须同时满足回撤、集中度和数据质量约束。",
        )

