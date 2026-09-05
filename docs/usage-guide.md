# 单因子量化研究使用指南

本项目用于验证单个横截面因子的预测能力，并用简化组合回测检查信号、执行、收益和成本的时间口径。默认流程为：本地价格数据 → 252 期动量 → 按日去极值与标准化 → 20 期未来收益标签 → IC/RankIC → 五分组 → Top 20% 回测 → 研究摘要。

## 1. 环境安装

要求 Python 3.11 或更高版本。在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

验证安装：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 2. 快速运行

运行内置的确定性合成数据：

```powershell
.\.venv\Scripts\python.exe main.py --demo
```

包入口与之等价：

```powershell
.\.venv\Scripts\python.exe -m single_factor_quant --demo
```

运行仓库自带的本地 CSV：

```powershell
.\.venv\Scripts\python.exe main.py --input examples\sample_prices.csv
```

## 3. 准备自己的 CSV

文件必须包含且可以额外包含其他列：

```csv
date,code,close
2024-01-02,000001,10.25
2024-01-03,000001,10.38
```

严格数据约定：

- `(date, code)` 必须唯一；日期必须可解析。
- `code` 按字符串读取并保留前导零。
- `close` 必须是有限正数，不能缺失。
- 回测要求完整的日期 × 股票价格面板，每只股票应覆盖同一组日期。
- 默认五分组至少需要 5 只股票在同一天同时拥有因子和标签。
- 默认 252 期动量与 20 期标签要形成完整研究结果，建议至少准备 273 个共同交易日；示例使用 10 只股票和 300 个交易日。
- `close` 应是已经按拆股、分红等公司行为调整后的价格。项目不会猜测、认证或自动执行复权。

运行自己的数据：

```powershell
.\.venv\Scripts\python.exe main.py --input C:\data\prices.csv
```

数据不合格或历史不足时，CLI 会返回包含问题类型、数量或所需样本数的错误，不会填补、删除或聚合输入行。

## 4. 默认研究口径

同一股票的 252 期动量为：

```text
momentum_t = close_t / close_(t-252 observations) - 1
```

未来 20 期收益为：

```text
forward_return_t = close_(t+20 observations) / close_t - 1
```

未来收益只用于研究标签，不能在日期 `t` 作为交易信号。横截面处理按日期独立进行：先用 1%/99% 分位数裁剪，再用总体标准差 `ddof=0` 标准化。

IC 是每日因子与未来收益的 Pearson 相关；RankIC 是二者平均秩的 Pearson 相关。Q1 表示最低因子组，Q5 表示最高因子组。样本不足、常数截面或不能形成五组的日期会明确记为无效或跳过。

回测每 20 个全市场交易日生成一次信号，选择标准化因子最高的 Top 20%，并在下一交易日收盘执行。调仓之间股数不变，权重随价格漂移。成本公式为：

```text
transaction_cost = fee_rate × sum(abs(target_weight - pre_trade_weight))
```

默认单边费率为 `0.001`，首次建仓也计入换手和成本。

## 5. 解读 CLI 输出

| 字段 | 含义 |
| --- | --- |
| `date_range`、`stocks` | 数据日期范围与股票数量 |
| `factor_coverage_all` | 动量在全部输入行中的覆盖率 |
| `factor_coverage_eligible` | 具备足够历史的行中，动量的覆盖率 |
| `mean_ic`、`mean_rank_ic` | 每日 IC/RankIC 的时间均值 |
| `ic_std`、`icir` | 每日 IC 样本标准差及 `Mean IC / IC std` |
| `Q1`～`Q5` | 各因子组在有效日期上的平均未来收益 |
| `top_20_cumulative_return` | 扣费后 Top 20% 组合累计收益 |
| `annualized_return` | 按 252 个交易日折算的扣费后年化收益 |
| `max_drawdown` | 扣费后净值最大回撤 |
| `average_gross_turnover` | 全部回测日的平均 gross turnover |
| `valid_ic_dates` | 成功计算 IC 的日期数 |
| `skipped_group_dates` | 无法形成分组的日期数 |
| `rebalances` | 实际执行的调仓次数 |
| `unavailable` | 数值为 `n/a` 时对应的明确原因 |

## 6. Python API

```python
from single_factor_quant import ResearchConfig, load_price_csv
from single_factor_quant.pipeline import run_research_pipeline
from single_factor_quant.reports.summary import build_research_summary

config = ResearchConfig()
prices = load_price_csv("prices.csv")
result = run_research_pipeline(prices, config)
summary = build_research_summary(result)

print(summary["mean_ic"])
print(summary["top_20_cumulative_return"])
print(result.factor_data)
print(result.daily_ic)
print(result.quintile_mean_returns)
print(result.backtest.daily)
```

可以通过不可变配置对象调整参数：

```python
config = ResearchConfig(
    momentum_window=252,
    forward_horizon=20,
    quantiles=5,
    top_fraction=0.20,
    rebalance_interval=20,
    transaction_cost=0.001,
    winsor_lower=0.01,
    winsor_upper=0.99,
    annualization_days=252,
)
```

CLI 使用这些默认值；自定义参数目前通过 Python API 传入。

## 7. 扩展新因子

在 `src/single_factor_quant/factors/` 中新增一个纯函数，接收价格面板并返回唯一的 `(date, code, factor_column)`。预处理、IC、分组和回测接口都接受 `factor_col`，因此无需建立抽象基类或修改研究基础设施。

新增因子时应继续保证：按 `code` 独立做时间序列计算、按 `date` 独立做横截面计算、通过 `(date, code)` 显式对齐，并且不原地修改调用者数据。

## 8. 当前边界

本版本不下载行情、不自动复权，也没有建模停牌、退市、幸存者偏差、滑点、订单簿、做空、基准或真实交易日历。回测是完整价格面板上的收盘到收盘研究模型，不能直接视为可实盘成交结果。
