"""Thin orchestration of the formal single-factor research workflow."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest.simple_backtest import BacktestResult, run_top_quantile_backtest
from .config import ResearchConfig
from .factors.momentum import calculate_momentum
from .preprocess.cross_section import cross_sectional_zscore
from .research.forward_return import calculate_forward_returns
from .research.grouping import QuintileResult, quintile_forward_returns
from .research.ic import daily_ic_rankic, summarize_ic


@dataclass(frozen=True)
class ResearchPipelineResult:
    """Structured outputs from factor construction through simple backtesting."""

    factor_data: pd.DataFrame
    daily_ic: pd.DataFrame
    ic_summary: pd.DataFrame
    quintiles: QuintileResult
    backtest: BacktestResult


def run_research_pipeline(prices: pd.DataFrame, config: ResearchConfig | None = None) -> ResearchPipelineResult:
    """Run the configured factor, research, and top-quantile backtest workflow."""
    settings = config or ResearchConfig()
    momentum = calculate_momentum(prices, settings.momentum_window)
    factor_col = f"momentum_{settings.momentum_window}"
    standardized = cross_sectional_zscore(
        momentum, factor_col, settings.winsor_lower, settings.winsor_upper
    )
    labels = calculate_forward_returns(prices, settings.forward_horizon)
    return_col = f"forward_return_{settings.forward_horizon}"
    factor_data = _merge_by_key(momentum, standardized, labels).sort_values(
        ["date", "code"], kind="stable", ignore_index=True
    )
    daily_ic = daily_ic_rankic(factor_data, "factor_zscore", return_col)
    quintiles = quintile_forward_returns(factor_data, "factor_zscore", return_col, settings.quantiles)
    backtest_input = prices.loc[:, ["date", "code", "close"]].merge(
        standardized.loc[:, ["date", "code", "factor_zscore"]],
        on=["date", "code"], how="left", validate="one_to_one",
    )
    backtest = run_top_quantile_backtest(
        backtest_input, "factor_zscore", settings.rebalance_interval, settings.top_fraction,
        settings.transaction_cost, settings.annualization_days,
    )
    return ResearchPipelineResult(factor_data, daily_ic, summarize_ic(daily_ic), quintiles, backtest)


def make_demo_price_panel(periods: int = 300, stocks: int = 10) -> pd.DataFrame:
    """Create deterministic prices sufficient for all default research stages."""
    if isinstance(periods, bool) or not isinstance(periods, int) or periods < 280:
        raise ValueError("periods must be an integer at least 280")
    if isinstance(stocks, bool) or not isinstance(stocks, int) or stocks < 10:
        raise ValueError("stocks must be an integer at least 10 for default quintiles")
    dates = pd.bdate_range("2020-01-02", periods=periods)
    steps = np.arange(periods, dtype=float)
    frames = [pd.DataFrame({
        "date": dates, "code": f"S{rank:02d}",
        "close": 80.0 + rank * 7.0 + (0.20 + rank * 0.08) * steps,
    }) for rank in range(1, stocks + 1)]
    return pd.concat(frames, ignore_index=True).sort_values(["date", "code"], kind="stable", ignore_index=True)


def _merge_by_key(*frames: pd.DataFrame) -> pd.DataFrame:
    """Inner-merge independently calculated outputs with one-to-one key checks."""
    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.merge(frame, on=["date", "code"], how="inner", validate="one_to_one")
    return merged
