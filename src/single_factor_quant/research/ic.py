"""Daily IC and RankIC statistics."""

import numpy as np
import pandas as pd

from ._panel import keyed_numeric_copy


def daily_ic_rankic(
    panel: pd.DataFrame, factor_col: str, return_col: str = "forward_return_20"
) -> pd.DataFrame:
    """Calculate daily Pearson IC and average-rank Pearson RankIC."""
    working = keyed_numeric_copy(panel, (factor_col, return_col))
    rows: list[dict[str, object]] = []
    for date, group in working.groupby("date", sort=True):
        paired = group.loc[:, [factor_col, return_col]].dropna()
        reason = _invalid_reason(paired, factor_col, return_col)
        if reason is None:
            ic = paired[factor_col].corr(paired[return_col], method="pearson")
            rank_ic = paired[factor_col].rank(method="average").corr(
                paired[return_col].rank(method="average"), method="pearson"
            )
        else:
            ic, rank_ic = np.nan, np.nan
        rows.append({"date": date, "n_pairs": len(paired), "ic": ic, "rank_ic": rank_ic,
                     "invalid_reason": reason})
    return pd.DataFrame(rows, columns=["date", "n_pairs", "ic", "rank_ic", "invalid_reason"])


def summarize_ic(daily_ic: pd.DataFrame) -> pd.DataFrame:
    """Summarize daily IC values with sample standard deviation and ICIR."""
    required = {"ic", "rank_ic"}
    missing = required.difference(daily_ic.columns)
    if missing:
        raise ValueError(f"daily_ic is missing required columns: {sorted(missing)}")
    ic = pd.to_numeric(daily_ic["ic"], errors="raise").dropna()
    rank_ic = pd.to_numeric(daily_ic["rank_ic"], errors="raise").dropna()
    mean_ic = ic.mean()
    ic_std = ic.std(ddof=1) if len(ic) >= 2 else np.nan
    icir = mean_ic / ic_std if pd.notna(ic_std) and ic_std != 0.0 else np.nan
    return pd.DataFrame([{"mean_ic": mean_ic, "mean_rank_ic": rank_ic.mean(),
                          "ic_std": ic_std, "icir": icir}])


def _invalid_reason(paired: pd.DataFrame, factor_col: str, return_col: str) -> str | None:
    """State why a pairwise daily correlation is not statistically defined."""
    if len(paired) < 3:
        return "fewer_than_three_valid_pairs"
    if paired[factor_col].nunique() < 2:
        return "constant_factor"
    if paired[return_col].nunique() < 2:
        return "constant_forward_return"
    return None
