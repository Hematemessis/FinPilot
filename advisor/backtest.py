from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .portfolio import OptimizationConfig, STRATEGIES, build_weights
from .risk import RiskProfile


@dataclass(frozen=True)
class BacktestResult:
    strategy: str
    weights: pd.Series
    daily_returns: pd.Series
    equity_curve: pd.Series
    metrics: dict[str, float]
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def performance_metrics(
    daily_returns: pd.Series,
    annual_risk_free_rate: float = 0.02,
    turnover: float = 0.0,
) -> dict[str, float]:
    if daily_returns.empty:
        raise ValueError("Cannot calculate metrics from empty returns")

    equity = (1 + daily_returns).cumprod()
    years = len(daily_returns) / 252
    total_return = float(equity.iloc[-1] - 1)
    annual_return = float(equity.iloc[-1] ** (1 / years) - 1) if years > 0 else 0.0
    annual_volatility = float(daily_returns.std(ddof=1) * np.sqrt(252))
    sharpe = (
        (annual_return - annual_risk_free_rate) / annual_volatility
        if annual_volatility > 1e-12
        else 0.0
    )
    drawdown = equity / equity.cummax() - 1
    max_drawdown = float(drawdown.min())
    calmar = annual_return / abs(max_drawdown) if max_drawdown < -1e-12 else 0.0
    return {
        "累计收益": total_return,
        "年化收益": annual_return,
        "年化波动": annual_volatility,
        "夏普比率": float(sharpe),
        "最大回撤": max_drawdown,
        "Calmar比率": float(calmar),
        "初始换手率": float(turnover),
    }


def backtest_strategy(
    prices: pd.DataFrame,
    profile: RiskProfile,
    strategy: str,
    train_ratio: float = 0.65,
    fee_bps: float = 10.0,
    config: OptimizationConfig = OptimizationConfig(),
) -> BacktestResult:
    """Fit only on the earlier period and evaluate on the untouched later period."""

    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy}")
    if not 0.5 <= train_ratio <= 0.85:
        raise ValueError("train_ratio must be between 0.5 and 0.85")
    if fee_bps < 0:
        raise ValueError("fee_bps cannot be negative")

    split_index = int(len(prices) * train_ratio)
    if split_index < 60 or len(prices) - split_index < 30:
        raise ValueError("Insufficient observations for an out-of-sample backtest")

    train_prices = prices.iloc[:split_index]
    # Include the last training close solely as the base for the first test return.
    test_prices = prices.iloc[split_index - 1 :]
    weights = build_weights(train_prices, profile, strategy)

    risky_returns = test_prices.pct_change().dropna()
    cash_daily_return = (1 + config.annual_risk_free_rate) ** (1 / 252) - 1
    portfolio_returns = risky_returns.mul(weights[prices.columns], axis=1).sum(axis=1)
    portfolio_returns = portfolio_returns + weights["现金"] * cash_daily_return

    # Starting from all cash, one-way turnover equals the capital moved into risky assets.
    turnover = float(1 - weights["现金"])
    portfolio_returns.iloc[0] -= turnover * fee_bps / 10_000
    equity_curve = (1 + portfolio_returns).cumprod().rename(strategy)
    metrics = performance_metrics(
        portfolio_returns,
        annual_risk_free_rate=config.annual_risk_free_rate,
        turnover=turnover,
    )

    return BacktestResult(
        strategy=strategy,
        weights=weights,
        daily_returns=portfolio_returns.rename(strategy),
        equity_curve=equity_curve,
        metrics=metrics,
        train_start=train_prices.index[0],
        train_end=train_prices.index[-1],
        test_start=risky_returns.index[0],
        test_end=risky_returns.index[-1],
    )


def compare_strategies(
    prices: pd.DataFrame,
    profile: RiskProfile,
    fee_bps: float = 10.0,
) -> dict[str, BacktestResult]:
    return {
        strategy: backtest_strategy(prices, profile, strategy, fee_bps=fee_bps)
        for strategy in STRATEGIES
    }

