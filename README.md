# 单因子量化研究：阶段 1–9

第一版 roadmap 的阶段 1–9 已完成：时间对齐、横截面统计、组合回测三个技术探针，以及正式包的配置、研究模块、回测、端到端 CLI、本地 CSV 诊断、研究摘要和专项正确性审计。
详见 [使用指南](docs/usage-guide.md)、[roadmap](single-factor-quant-progressive-roadmap.md)、[阶段 1–4 验收记录](docs/acceptance-stages-1-4.md)、[阶段 5 迁移记录](docs/acceptance-stage-5.md)、[阶段 6 迁移记录](docs/acceptance-stage-6.md)、[阶段 7 验收记录](docs/acceptance-stage-7.md)、[阶段 8 验收记录](docs/acceptance-stage-8.md) 和 [阶段 9 审计记录](docs/audit-stage-9.md)。

## 安装和运行

要求 Python 3.11+。在项目根目录执行：

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

依赖清单安装本地包及 pandas、numpy、pytest；正式包采用 `src/` 布局。
`main.py` 只转发到包入口。CLI 使用默认 `ResearchConfig`，支持 `--demo` 的确定性合成数据与 `--input PATH` 的严格 CSV 读取。

## 当前目录

```text
spike/                         # 已验收的技术探针和三个 demo
tests/                         # 时间对齐、研究、回测、配置、loader 测试
src/single_factor_quant/
    __init__.py
    __main__.py                 # --demo / --input CLI
    config.py                  # 冻结的 ResearchConfig
    data/loader.py             # 严格 CSV 读取
    factors/momentum.py        # 按股票独立计算动量
    preprocess/cross_section.py # 按日期去极值和标准化
    research/                  # 未来标签、IC/RankIC、分组研究
    backtest/simple_backtest.py # 次日执行、漂移权重、交易成本
    diagnostics/data_profile.py # CSV 画像与流水线可用性诊断
    reports/summary.py          # 只读研究摘要与 CLI 字段输出
    pipeline.py                 # 端到端正式编排
examples/sample_prices.csv      # 10 股票、300 交易日的确定性本地示例
docs/acceptance-stages-1-4.md   # 本次验收证据
main.py                        # 薄转发入口
```

根目录的 `factor_alignment.py`、`cross_section.py`、`backtest_spike.py` 保留原有公开导入接口。阶段 1–2 的 spike 仅保留黄金数据、演示与兼容导入；算法实现统一位于正式包。

## 本地 CSV 诊断

`--input` 会先使用严格 loader 检查数据，再输出日期范围、股票数、每股观测数的最小值/中位数/最大值、够 252 条历史的股票数、质量问题计数、两种因子覆盖率、未来标签覆盖率、有效 IC 日期、分组跳过日期和已执行调仓次数。

历史不足时会提示每股至少需要 253 行；默认五分组无法形成时会提示至少需要 5 只同时拥有因子和标签的股票。诊断只读取本地 CSV，不下载行情、连接数据库、推测复权或修复输入数据。

## CSV 约定

```csv
date,code,close
2024-01-02,000001,10.0
2024-01-03,000001,10.5
```

每行的 `(date, code)` 必须唯一；日期必须能严格转换，代码裁掉首尾空白并保留前导零，价格必须是有限正数。
缺列、缺值、重复键、非法价格、空文件、字段数量异常均抛出包含数量和样例的 `ValueError`。
合法的字符串代码（例如 `NA`）会保留。loader 返回按 `code/date` 排序的新表，只保留三个必需列。

**真实研究的 close 必须是已按拆股、分红等公司行为调整的价格。** loader 不自动复权，也不能证明输入已复权；返回表的 `attrs["price_adjustment_warning"]` 明确记录此提示。

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
# 因子列名可自定义；研究模块不绑定 momentum：
# processed = cross_sectional_zscore(panel, "alpha", config.winsor_lower, config.winsor_upper)
# daily = daily_ic_rankic(panel, factor_col="alpha")
# groups = quintile_forward_returns(panel, factor_col="alpha")
```

## 研究方法

项目用单因子研究流程验证一个因子在横截面上的预测能力，并用简化的长期组合回测检查从信号到收益的时间口径。默认动量定义为：

```text
momentum_t = close_t / close_(t-252 observations of the same code) - 1
```

每只股票独立按观测数回看，因而不是 252 个自然日。日期 `t` 之后的价格不会改变 `t` 的动量。

未来 20 个同股观测的收益定义为：

```text
forward_return_t = close_(t+20 observations of the same code) / close_t - 1
```

它是评估标签，不是可在 `t` 使用的交易信号；把它用于交易决策会引入未来数据泄漏。

每个交易日独立对因子按 1%/99% 分位数裁剪，再以 `ddof=0` 标准化。样本不足两个或标准差为零时标准化结果为 NaN。IC 对同日因子与标签成对去空后计算 Pearson 相关，至少需要三对且两列都不是常数；RankIC 对两列使用平均秩后计算 Pearson 相关。ICIR 为每日 IC 均值除以每日 IC 样本标准差（`ddof=1`），第一版不年化。

五分组中 Q1 是最低因子、Q5 是最高因子。只有在同日存在至少五只同时拥有因子和标签、且能形成五个有效分位组的股票时才记录组收益；其他日期明确计为跳过。摘要显示 Q1–Q5 的有效日期等权平均未来收益。

## 回测与摘要

默认回测每 20 个全市场交易日于收盘后形成信号，选择标准化因子最高的 Top 20%，同分时按 `code` 升序。信号日在下一交易日收盘执行，因此新组合不获得信号日或执行日之前的收益。调仓之间保持股数不变，权重随价格漂移。

单边费率默认 0.1%，每次成本为：

```text
transaction_cost = fee_rate × sum(abs(target_weight - pre_trade_drifting_weight))
```

首次建仓也计费。`gross_turnover` 是上述权重绝对变化的总和；累计收益、年化收益与最大回撤均由扣费后的日净值计算。

CLI 使用 `reports/summary.py` 生成字段化摘要。摘要仅读取流水线已经产出的诊断、IC 汇总、五分组均值和回测结构，不会重新计算因子、IC 或回测。`n/a` 字段会同时给出原因，例如有效 IC 日期不足导致 IC 标准差或 ICIR 不可用。

## 简化假设与扩展

本版本仅处理完整的本地价格面板和收盘到收盘收益；未模拟停牌、滑点、订单簿、做空、基准、退市、幸存者偏差或真实交易日历。输入 `close` 必须已经按公司行为调整，项目不会下载、修复或认证数据。

新增因子时，在 `factors/` 中实现一个返回唯一 `(date, code, factor_column)` 的纯函数即可。随后复用 `preprocess/cross_section.py`、`research/ic.py`、`research/grouping.py` 和 `backtest/simple_backtest.py`，并通过 `factor_col` 传入新列名。无需改写研究基础设施，也无需在本项目中预先实现 Value、Quality 等因子。

## 探针计算口径

- 动量使用同一股票过去 252 条观测；未来 20 条观测的收益仅作为研究标签。
- 每日独立分位裁剪和总体标准差标准化；IC 成对去空且至少三个有效样本；RankIC 用平均秩相关；ICIR 不年化。
- Q1 最低、Q5 最高；无法形成五组的日期记录原因。`QuintileResult.mean_returns` 对有效日期等权平均。
- 信号每 20 个全市场交易日形成，下一交易日收盘执行；新仓位从执行后的下一段收盘到收盘收益生效。
- 调仓间股数不变、权重漂移；默认费率 0.001，成本比例为 `费率 × sum(abs(目标权重 − 调仓前漂移权重))`，首次建仓包含在内。
- `gross_turnover` 汇总所有调仓的双边权重变化绝对值，包含首次建仓；未发生权重变化时成本为零。
- 扣费净值从 1 开始复合，初始信号日收益为零并计入观测日数；年化为 `最终净值 ** (252 / 观测日数) - 1`，最大回撤为 `min(nav / nav.cummax() - 1)`。

当前回测探针要求完整的日期 × 股票价格面板，缺交易日价格会明确失败；尚未建模停牌撮合、滑点或退市处置。

阶段 1–9 的逐阶段证据保存在 `docs/`；阶段 9 已针对未来数据泄漏、索引错位、跨股票污染和回测语义完成专项审计。
