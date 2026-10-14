# Single-Factor Quant Research: Stages 1–9

Stages 1–9 of the first roadmap are complete. The work started with three technical spikes—date alignment, cross-sectional statistics, and portfolio backtesting—and now includes a packaged research workflow, backtest, end-to-end CLI, local CSV diagnostics, research summary, and a focused correctness audit.

For setup and usage, see the [usage guide](docs/usage-guide.md) and [roadmap](single-factor-quant-progressive-roadmap.md). Stage records are available in [stages 1–4](docs/acceptance-stages-1-4.md), [stage 5](docs/acceptance-stage-5.md), [stage 6](docs/acceptance-stage-6.md), [stage 7](docs/acceptance-stage-7.md), [stage 8](docs/acceptance-stage-8.md), and the [stage 9 audit](docs/audit-stage-9.md).

## Install and run

Python 3.11 or newer is required. From the project root:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m spike.alignment_demo
.venv\Scripts\python.exe -m spike.research_demo
.venv\Scripts\python.exe -m spike.backtest_demo
.venv\Scripts\python.exe main.py --demo
.venv\Scripts\python.exe -m single_factor_quant --demo
.venv\Scripts\python.exe main.py --input examples/sample_prices.csv
```

The requirements file installs the local package along with pandas, numpy, and pytest. The package uses a `src/` layout. `main.py` forwards to the package entry point. The CLI uses the default `ResearchConfig` and accepts either `--demo` for deterministic synthetic data or `--input PATH` for strict CSV loading.

## Project layout

```text
spike/                           # Accepted technical spikes and three demos
tests/                           # Alignment, research, backtest, config, and loader tests
src/single_factor_quant/
    __init__.py
    __main__.py                   # --demo / --input CLI
    config.py                     # Frozen ResearchConfig
    data/loader.py                # Strict CSV loader
    factors/momentum.py           # Momentum calculated per stock
    preprocess/cross_section.py   # Daily winsorization and standardization
    research/                     # Forward returns, IC/RankIC, and quantile groups
    backtest/simple_backtest.py   # Next-day execution, drifting weights, and costs
    diagnostics/data_profile.py   # CSV profile and pipeline-readiness diagnostics
    reports/summary.py            # Read-only research summary and CLI fields
    pipeline.py                   # End-to-end package orchestration
examples/sample_prices.csv        # Deterministic sample: 10 stocks, 300 trading days
docs/acceptance-stages-1-4.md     # Acceptance evidence
main.py                           # Thin forwarding entry point
```

The root-level `factor_alignment.py`, `cross_section.py`, and `backtest_spike.py` remain as compatibility imports. The stage 1–2 spikes retain the reference data, demos, and compatibility imports; the maintained implementations live in the package.

## Local CSV diagnostics

With `--input`, the CLI first validates the file with the strict loader, then reports the date range, stock count, minimum/median/maximum observations per stock, stocks with at least 252 observations, data-quality issue counts, coverage for both factors and forward labels, valid IC dates, skipped grouping dates, and completed rebalances.

If there is not enough history, the CLI says that each stock needs at least 253 rows. If the default five groups cannot be formed, it says that at least five stocks need both a factor and a label on the same date. Diagnostics only read the local CSV: they do not download prices, connect to a database, infer adjusted prices, or repair input data.

## CSV format

```csv
date,code,close
2024-01-02,000001,10.0
2024-01-03,000001,10.5
```

Each `(date, code)` pair must be unique. Dates must parse strictly; leading and trailing whitespace is removed from codes, while leading zeros are preserved. Prices must be finite and greater than zero.

Missing columns or values, duplicate keys, invalid prices, empty files, and rows with an unexpected number of fields raise a `ValueError` with counts and examples. Valid string codes such as `NA` are preserved. The loader returns a new table sorted by `code` and `date`, containing only the three required columns.

**For real research, `close` must already be adjusted for splits, dividends, and other corporate actions.** The loader does not adjust prices or verify that adjustment was done. It records this warning in `attrs["price_adjustment_warning"]` on the returned table.

```python
from single_factor_quant import ResearchConfig, load_price_csv
from single_factor_quant.factors.momentum import calculate_momentum
from single_factor_quant.preprocess.cross_section import cross_sectional_zscore
from single_factor_quant.research.forward_return import calculate_forward_returns
from single_factor_quant.research.ic import daily_ic_rankic
from single_factor_quant.research.grouping import quintile_forward_returns

config = ResearchConfig()
prices = load_price_csv("prices.csv")
print(prices.attrs["price_adjustment_warning"])
momentum = calculate_momentum(prices, config.momentum_window)
labels = calculate_forward_returns(prices, config.forward_horizon)
# The research modules accept a caller-supplied factor column; they are not
# tied to momentum:
# processed = cross_sectional_zscore(panel, "alpha", config.winsor_lower, config.winsor_upper)
# daily = daily_ic_rankic(panel, factor_col="alpha")
# groups = quintile_forward_returns(panel, factor_col="alpha")
```

## Research method

The workflow measures a factor's predictive power across stocks and uses a simple long-only portfolio backtest to check the timing from signal to return. The default momentum definition is:

```text
momentum_t = close_t / close_(t-252 observations of the same code) - 1
```

Each stock is looked back independently by observation count, so 252 observations do not mean 252 calendar days. Prices after date `t` do not affect momentum at `t`.

The return over the next 20 observations for the same stock is:

```text
forward_return_t = close_(t+20 observations of the same code) / close_t - 1
```

This is an evaluation label, not a signal available at `t`. Using it to make a trading decision would introduce look-ahead bias.

On each date, factor values are clipped at the 1st and 99th percentiles and standardized with `ddof=0`. Standardization returns NaN when there are fewer than two observations or the standard deviation is zero. Daily IC is the Pearson correlation between factor and label after pairwise removal of missing values. It requires at least three pairs and non-constant values in both columns. RankIC is the Pearson correlation of the average ranks. ICIR is the mean daily IC divided by its sample standard deviation (`ddof=1`); it is not annualized in this version.

In the five-group analysis, Q1 contains the lowest factor values and Q5 the highest. A date is included only if at least five stocks have both a factor and a label and five valid quantile groups can be formed. Other dates are counted as skipped. The summary reports the equal-weighted mean forward return for each group across valid dates.

## Backtest and summary

The default backtest forms a signal after the close every 20th market-wide trading day and selects the top 20% of standardized factor values. Ties are broken by `code` in ascending order. Orders execute at the next trading day's close, so a new portfolio does not earn returns from the signal date or from before execution.

Share counts stay fixed between rebalances, so portfolio weights drift with prices. The default one-way fee is 0.1%. At each rebalance:

```text
transaction_cost = fee_rate × sum(abs(target_weight - pre_trade_drifting_weight))
```

The initial portfolio is charged as well. `gross_turnover` is the sum of these absolute weight changes. Cumulative return, annualized return, and maximum drawdown are calculated from the daily net asset value after fees.

The CLI summary is built by `reports/summary.py`. It reads diagnostics, aggregated IC results, mean quintile returns, and backtest statistics already produced by the pipeline; it does not recalculate factors, IC, or backtest results. An `n/a` field includes a reason, such as too few valid IC dates to calculate the IC standard deviation or ICIR.

## Assumptions and extensions

This version works with a complete local price panel and close-to-close returns. It does not model suspensions, slippage, order books, short selling, benchmarks, delistings, survivorship bias, or an exchange trading calendar. Input `close` prices must already reflect corporate actions; the project does not download, repair, or certify data.

To add a factor, implement a pure function under `factors/` that returns a unique `(date, code, factor_column)` table. The existing preprocessing, IC, grouping, and backtest modules can then be reused by passing the new column name through `factor_col`. Factors such as Value or Quality are not included by default.

## Spike calculation conventions

- Momentum uses the previous 252 observations for the same stock. Returns over the next 20 observations are research labels only.
- Winsorization and population-standard-deviation normalization are applied independently each day. IC uses paired non-missing observations and requires at least three pairs; RankIC uses average ranks; ICIR is not annualized.
- Q1 is the lowest group and Q5 the highest. Dates that cannot form five groups are recorded with a reason. `QuintileResult.mean_returns` is the equal-weighted mean across valid dates.
- Signals are formed every 20 market-wide trading days and execute at the next day's close. New positions begin earning close-to-close returns after execution.
- Share counts remain fixed between rebalances while weights drift. The default fee is 0.001, and cost is `fee × sum(abs(target weight − pre-trade drifting weight))`; the initial portfolio is charged too.
- `gross_turnover` sums absolute weight changes at every rebalance, including initial investment. No weight change means no cost.
- Net asset value compounds from 1 after fees. The initial signal day's return is zero and counts as an observation. Annualized return is `final NAV ** (252 / observation count) - 1`; maximum drawdown is `min(nav / nav.cummax() - 1)`.

The backtest spike expects a complete date-by-stock price panel and fails clearly when a trading date is missing. It does not model suspension fills, slippage, or delisting treatment.

Stage-by-stage evidence is in `docs/`. Stage 9 includes a focused audit of look-ahead bias, index alignment, cross-stock contamination, and backtest semantics.
