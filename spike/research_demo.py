"""Deterministic stage-2 golden statistics and skipped-day diagnostics."""
import numpy as np
import pandas as pd

from .research import daily_ic_rankic, quintile_forward_returns, summarize_ic


def main() -> None:
    """Print checked golden statistics and count one invalid cross-section."""
    golden = pd.DataFrame({"date": pd.Timestamp("2024-01-02"), "code": list("ABCDEFGHIJ"),
                           "alpha": np.arange(1., 11.), "forward_return_20": np.arange(1., 11.) / 100})
    panel = pd.concat([golden, golden.assign(date=pd.Timestamp("2024-01-03"), alpha=1.)])
    daily = daily_ic_rankic(panel, "alpha")
    groups = quintile_forward_returns(panel, "alpha")
    assert np.allclose(daily.loc[0, ["ic", "rank_ic"]].astype(float), [1, 1])
    assert np.allclose(groups.mean_returns.mean_forward_return, [.015, .035, .055, .075, .095])
    assert len(groups.skipped) == 1
    print("IC=1; RankIC=1; Q1<Q2<Q3<Q4<Q5: PASS")
    print(summarize_ic(daily).to_string(index=False))
    print(groups.mean_returns.to_string(index=False))
    print(f"skipped_dates={len(groups.skipped)}; reasons={groups.skipped.reason.value_counts().to_dict()}")


if __name__ == "__main__":
    main()
