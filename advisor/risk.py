from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RiskLevel = Literal["稳健型", "平衡型", "进取型"]


@dataclass(frozen=True)
class RiskAnswers:
    """Normalized questionnaire answers. Every dimension uses a 1-5 scale."""

    investment_horizon: int
    loss_tolerance: int
    income_stability: int
    liquidity_need: int
    loss_reaction: int

    def validate(self) -> None:
        for field_name, value in self.__dict__.items():
            if not 1 <= value <= 5:
                raise ValueError(f"{field_name} must be between 1 and 5")


@dataclass(frozen=True)
class RiskProfile:
    score: int
    level: RiskLevel
    max_drawdown_tolerance: float
    min_cash_weight: float
    max_asset_weight: float
    target_volatility: float
    rationale: str


LOSS_TOLERANCE = {1: 0.05, 2: 0.10, 3: 0.15, 4: 0.25, 5: 0.35}


def assess_risk(answers: RiskAnswers) -> RiskProfile:
    """Translate user answers into explicit, auditable allocation constraints."""

    answers.validate()
    # A stronger liquidity need must lower, rather than raise, the risk score.
    normalized_liquidity = 6 - answers.liquidity_need
    raw_total = (
        answers.investment_horizon
        + answers.loss_tolerance
        + answers.income_stability
        + normalized_liquidity
        + answers.loss_reaction
    )
    score = round((raw_total - 5) / 20 * 100)

    if score < 35:
        level: RiskLevel = "稳健型"
        min_cash, max_asset, target_vol = 0.20, 0.45, 0.08
        rationale = "优先保留流动性并控制单一资产暴露，收益目标服从回撤约束。"
    elif score < 70:
        level = "平衡型"
        min_cash, max_asset, target_vol = 0.10, 0.60, 0.13
        rationale = "在增长与抗波动之间折中，通过多资产分散控制组合风险。"
    else:
        level = "进取型"
        min_cash, max_asset, target_vol = 0.02, 0.80, 0.20
        rationale = "接受更高净值波动以争取长期增长，但仍保留集中度上限。"

    return RiskProfile(
        score=score,
        level=level,
        max_drawdown_tolerance=LOSS_TOLERANCE[answers.loss_tolerance],
        min_cash_weight=min_cash,
        max_asset_weight=max_asset,
        target_volatility=target_vol,
        rationale=rationale,
    )

