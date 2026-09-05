"""Date-local factor clipping and standardization."""

import numpy as np
import pandas as pd

from ..research._panel import keyed_numeric_copy


def cross_sectional_zscore(
    panel: pd.DataFrame, factor_col: str, winsor_lower: float = 0.01, winsor_upper: float = 0.99
) -> pd.DataFrame:
    """Winsorize ``factor_col`` by date, then z-score with population deviation."""
    if not 0 <= winsor_lower < winsor_upper <= 1:
        raise ValueError("winsor quantiles must satisfy 0 <= lower < upper <= 1")
    working = keyed_numeric_copy(panel, (factor_col,))
    outputs: list[pd.DataFrame] = []
    for _, group in working.groupby("date", sort=True):
        values = group[factor_col]
        valid = values.dropna()
        clipped = values.copy()
        zscore = pd.Series(np.nan, index=group.index, dtype=float)
        if len(valid) >= 2:
            lower, upper = valid.quantile([winsor_lower, winsor_upper])
            clipped = values.clip(lower=lower, upper=upper)
            std = clipped.dropna().std(ddof=0)
            if std != 0.0:
                zscore = (clipped - clipped.mean()) / std
        outputs.append(pd.DataFrame({
            "date": group["date"], "code": group["code"],
            "factor_winsorized": clipped, "factor_zscore": zscore,
        }))
    if outputs:
        return pd.concat(outputs, ignore_index=True)
    return pd.DataFrame(columns=["date", "code", "factor_winsorized", "factor_zscore"])
