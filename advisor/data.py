from __future__ import annotations

import numpy as np
import pandas as pd


CHINA_DEMO_ASSETS = {
    "510300": "A股宽基",
    "159920": "港股宽基",
    "511260": "中国国债",
    "518880": "黄金ETF",
}


def validate_prices(prices: pd.DataFrame, min_rows: int = 120) -> pd.DataFrame:
    """Validate and align price histories before any model sees them."""

    if not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError("Price data must use a DatetimeIndex")
    if prices.empty or prices.shape[1] < 2:
        raise ValueError("At least two assets are required")

    cleaned = prices.copy().sort_index()
    cleaned = cleaned.loc[~cleaned.index.duplicated(keep="last")]
    cleaned = cleaned.apply(pd.to_numeric, errors="coerce").dropna(how="any")
    if len(cleaned) < min_rows:
        raise ValueError(f"At least {min_rows} aligned observations are required")
    if (cleaned <= 0).any().any():
        raise ValueError("Prices must be positive")
    if cleaned.columns.duplicated().any():
        raise ValueError("Asset symbols must be unique")
    return cleaned


def make_demo_prices(
    start: str = "2018-01-02", periods: int = 1_800, seed: int = 14
) -> pd.DataFrame:
    """Create deterministic synthetic prices for an offline, honest demo mode."""

    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, periods=periods)
    annual_returns = np.array([0.08, 0.075, 0.03, 0.05])
    annual_vols = np.array([0.22, 0.25, 0.06, 0.15])
    correlations = np.array(
        [
            [1.0, 0.65, -0.10, 0.05],
            [0.65, 1.0, -0.08, 0.08],
            [-0.10, -0.08, 1.0, 0.05],
            [0.05, 0.08, 0.05, 1.0],
        ]
    )
    covariance = np.outer(annual_vols, annual_vols) * correlations / 252
    daily_drift = annual_returns / 252 - 0.5 * (annual_vols**2) / 252
    log_returns = rng.multivariate_normal(daily_drift, covariance, len(dates))
    prices = 100 * np.exp(np.cumsum(log_returns, axis=0))
    return validate_prices(
        pd.DataFrame(prices, index=dates, columns=CHINA_DEMO_ASSETS)
    )


def parse_uploaded_prices(file_obj) -> pd.DataFrame:
    """Accept a wide CSV with a date column and one close-price column per asset."""

    raw = pd.read_csv(file_obj)
    date_candidates = [c for c in raw.columns if c.lower() in {"date", "datetime", "time"}]
    if not date_candidates:
        raise ValueError("CSV must contain a date, datetime, or time column")
    date_col = date_candidates[0]
    prices = raw.set_index(pd.to_datetime(raw.pop(date_col)))
    prices.index.name = "date"
    return validate_prices(prices)
