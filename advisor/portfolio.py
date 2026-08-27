from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .risk import RiskProfile


STRATEGIES = ("风险适配", "最小方差", "最大夏普", "等权配置")


@dataclass(frozen=True)
class OptimizationConfig:
    annual_risk_free_rate: float = 0.02


def annualized_statistics(prices: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    returns = prices.pct_change().dropna()
    return returns.mean() * 252, returns.cov() * 252


def _risky_budget(profile: RiskProfile) -> float:
    return 1.0 - profile.min_cash_weight


def _bounds(profile: RiskProfile, asset_count: int) -> tuple[tuple[float, float], ...]:
    budget = _risky_budget(profile)
    feasible_cap = max(profile.max_asset_weight, budget / asset_count)
    return tuple((0.0, feasible_cap) for _ in range(asset_count))


def _solve(
    objective,
    profile: RiskProfile,
    asset_count: int,
) -> np.ndarray:
    budget = _risky_budget(profile)
    initial = np.repeat(budget / asset_count, asset_count)
    result = minimize(
        objective,
        initial,
        method="SLSQP",
        bounds=_bounds(profile, asset_count),
        constraints={"type": "eq", "fun": lambda w: np.sum(w) - budget},
        options={"maxiter": 1_000, "ftol": 1e-12},
    )
    if not result.success or not np.isfinite(result.x).all():
        return initial
    weights = np.clip(result.x, 0, None)
    return weights * budget / weights.sum()


def minimum_variance_weights(prices: pd.DataFrame, profile: RiskProfile) -> np.ndarray:
    _, covariance = annualized_statistics(prices)
    cov = covariance.to_numpy()
    return _solve(lambda w: float(w @ cov @ w), profile, len(prices.columns))


def maximum_sharpe_weights(
    prices: pd.DataFrame,
    profile: RiskProfile,
    config: OptimizationConfig = OptimizationConfig(),
) -> np.ndarray:
    expected, covariance = annualized_statistics(prices)
    mu, cov = expected.to_numpy(), covariance.to_numpy()

    def negative_sharpe(weights: np.ndarray) -> float:
        volatility = float(np.sqrt(max(weights @ cov @ weights, 1e-12)))
        excess_return = float(weights @ (mu - config.annual_risk_free_rate))
        return -excess_return / volatility

    return _solve(negative_sharpe, profile, len(prices.columns))


def build_weights(
    prices: pd.DataFrame,
    profile: RiskProfile,
    strategy: str = "风险适配",
) -> pd.Series:
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy}")

    asset_count = len(prices.columns)
    budget = _risky_budget(profile)
    if strategy == "等权配置":
        risky = np.repeat(budget / asset_count, asset_count)
    elif strategy == "最小方差":
        risky = minimum_variance_weights(prices, profile)
    elif strategy == "最大夏普":
        risky = maximum_sharpe_weights(prices, profile)
    else:
        min_var = minimum_variance_weights(prices, profile)
        max_sharpe = maximum_sharpe_weights(prices, profile)
        _, covariance = annualized_statistics(prices)
        cov = covariance.to_numpy()
        min_vol = float(np.sqrt(min_var @ cov @ min_var))
        max_sharpe_vol = float(np.sqrt(max_sharpe @ cov @ max_sharpe))
        if max_sharpe_vol > min_vol + 1e-8:
            target_share = (profile.target_volatility - min_vol) / (
                max_sharpe_vol - min_vol
            )
        else:
            target_share = 0.5
        # Combine stated risk capacity with the volatility implied by market history.
        growth_share = np.clip(
            0.5 * profile.score / 100 + 0.5 * target_share, 0.10, 0.90
        )
        risky = (1 - growth_share) * min_var + growth_share * max_sharpe

    all_weights = pd.Series(
        [*risky, profile.min_cash_weight], index=[*prices.columns, "现金"], dtype=float
    )
    all_weights = all_weights.clip(lower=0)
    return all_weights / all_weights.sum()
