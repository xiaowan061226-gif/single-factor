# 单因子量化研究：阶段 1–6

当前完成时间对齐、横截面统计、组合回测三个技术探针，以及正式包的配置、研究模块、回测和端到端 CLI。
详见 [roadmap](single-factor-quant-progressive-roadmap.md)、[阶段 1–4 验收记录](docs/acceptance-stages-1-4.md)、[阶段 5 迁移记录](docs/acceptance-stage-5.md) 和 [阶段 6 迁移记录](docs/acceptance-stage-6.md)。

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
.venv\Scripts\python.exe main.py --input prices.csv
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
    pipeline.py                 # 端到端正式编排
docs/acceptance-stages-1-4.md   # 本次验收证据
main.py                        # 薄转发入口
```

根目录的 `factor_alignment.py`、`cross_section.py`、`backtest_spike.py` 保留原有公开导入接口。阶段 1–2 的 spike 仅保留黄金数据、演示与兼容导入；算法实现统一位于正式包。

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

## 探针计算口径

- 动量使用同一股票过去 252 条观测；未来 20 条观测的收益仅作为研究标签。
- 每日独立分位裁剪和总体标准差标准化；IC 成对去空且至少三个有效样本；RankIC 用平均秩相关；ICIR 不年化。
- Q1 最低、Q5 最高；无法形成五组的日期记录原因。`QuintileResult.mean_returns` 对有效日期等权平均。
- 信号每 20 个全市场交易日形成，下一交易日收盘执行；新仓位从执行后的下一段收盘到收盘收益生效。
- 调仓间股数不变、权重漂移；默认费率 0.001，成本比例为 `费率 × sum(abs(目标权重 − 调仓前漂移权重))`，首次建仓包含在内。
- `gross_turnover` 汇总所有调仓的双边权重变化绝对值，包含首次建仓；未发生权重变化时成本为零。
- 扣费净值从 1 开始复合，初始信号日收益为零并计入观测日数；年化为 `最终净值 ** (252 / 观测日数) - 1`，最大回撤为 `min(nav / nav.cummax() - 1)`。

当前回测探针要求完整的日期 × 股票价格面板，缺交易日价格会明确失败；尚未建模停牌撮合、滑点或退市处置。

阶段 5 已完成正式因子与研究模块迁移；本节中“阶段 1–4”的历史验收说明由本次迁移记录补充和更新。
这份验收限于阶段 1–4；正式研究模块迁移、全链路 CLI、真实 CSV 研究诊断和最终报告仍按后续阶段实施。
