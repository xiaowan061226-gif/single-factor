"""Date-local factor quantile research."""

from dataclasses import dataclass

import pandas as pd

from ._panel import keyed_numeric_copy


@dataclass(frozen=True)
class QuintileResult:
    """Daily group returns and dates skipped because groups were not formable."""

    returns: pd.DataFrame
    skipped: pd.DataFrame

    @property
    def mean_returns(self) -> pd.DataFrame:
        """Average daily group means with equal weight for each valid date."""
        return self.returns.groupby("quintile", as_index=False)["mean_forward_return"].mean()


def quintile_forward_returns(
    panel: pd.DataFrame, factor_col: str, return_col: str = "forward_return_20", quantiles: int = 5
) -> QuintileResult:
    """Return date-local Q1--Q5 forward-return means and explicit skip reasons."""
    if isinstance(quantiles, bool) or not isinstance(quantiles, int) or quantiles < 2:
        raise ValueError("quantiles must be an integer at least 2")
    working = keyed_numeric_copy(panel, (factor_col, return_col))
    quantity = "five" if quantiles == 5 else str(quantiles)
    return_rows: list[dict[str, object]] = []
    skipped_rows: list[dict[str, object]] = []
    for date, group in working.groupby("date", sort=True):
        paired = group.loc[:, [factor_col, return_col]].dropna()
        if len(paired) < quantiles:
            skipped_rows.append({"date": date, "reason": f"fewer_than_{quantity}_valid_stocks"})
            continue
        if paired[factor_col].nunique() < quantiles:
            skipped_rows.append({"date": date, "reason": f"fewer_than_{quantity}_distinct_factor_values"})
            continue
        bins = pd.qcut(paired[factor_col], q=quantiles, labels=False, duplicates="drop")
        if bins.nunique() != quantiles:
            skipped_rows.append({"date": date, "reason": f"cannot_form_{quantity}_groups"})
            continue
        for bucket_number, bucket in paired.assign(quintile=bins).groupby("quintile", sort=True):
            return_rows.append({"date": date, "quintile": f"Q{int(bucket_number) + 1}",
                                "n_stocks": len(bucket),
                                "mean_forward_return": bucket[return_col].mean()})
    return QuintileResult(
        returns=pd.DataFrame(return_rows, columns=["date", "quintile", "n_stocks", "mean_forward_return"]),
        skipped=pd.DataFrame(skipped_rows, columns=["date", "reason"]),
    )
