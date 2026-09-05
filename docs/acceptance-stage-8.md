# 阶段 8：研究摘要、README 与回归保护

验收日期：2026-09-05。

## 结论

阶段 8 已完成并通过。`reports/summary.py` 只读取 `ResearchPipelineResult` 已经产出的诊断、IC 汇总、五分组均值和回测结果；它不调用动量、预处理、标签、IC、分组或回测函数。CLI 使用该摘要的字段化文本输出。

## 摘要字段

摘要包含：

- 数据日期范围、股票数量、总体因子覆盖率和合格行因子覆盖率。
- Mean IC、Mean RankIC、IC 标准差和 ICIR。
- Q1–Q5 平均未来收益。
- Top 20% 累计收益、年化收益、最大回撤和平均 `gross_turnover`。
- 有效 IC 日期数、分组跳过日期数和已执行调仓次数。
- 公司行为调整后价格提示。

每个 NaN 指标都会转为 `n/a (原因)`，同时在摘要字典的 `unavailable` 中保留字段到原因的映射。例如，IC 标准差在有效 IC 日期少于两个时会明确标注样本不足；ICIR 在标准差为零或不可用时不会显示伪造数值。

默认 demo / 示例 CSV 输出的关键数值为：

```text
mean_ic=0.993885; mean_rank_ic=1.000000; ic_std=0.000576; icir=1724.959475
quintile_mean_forward_returns=Q1:0.036352; Q2:0.041345; Q3:0.044364; Q4:0.046389; Q5:0.047842
top_20_cumulative_return=0.090762; annualized_return=0.075705; max_drawdown=-0.001000; average_gross_turnover=0.003334
valid_ic_dates=28; skipped_group_dates=272; rebalances=2
```

## README

README 已补充项目目的、目录、CSV 格式、调整后价格前提、安装与两种 CLI 路径、动量和未来标签公式、IC/RankIC、五分组、次日执行、成本公式、简化假设及因子扩展方式。新增因子只需在 `factors/` 返回唯一 `(date, code, factor_column)`，即可复用既有的 `factor_col` 研究和回测接口。

## 回归保护与验证

新增摘要测试覆盖：

- 必填字段、日期范围、股票数、覆盖率、有效/跳过日期与调仓次数。
- Q1–Q5 均存在，且摘要不会修改结构化回测结果。
- 人为置为 NaN 的 IC 汇总会保留为 `None`，输出具体不可用原因。
- CLI 包含 Mean RankIC、五分组收益、平均换手、`unavailable` 和调整后价格提示。

以下命令均以退出码 0 完成：

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe main.py --demo
.venv\Scripts\python.exe main.py --input examples/sample_prices.csv
```

结果为 83 passed；两条 CLI 路径均输出相同的字段化摘要。

## 代码量与边界

本阶段新增/实质改写 Python 共 175 行：摘要模块 96 行、流水线结构化分组均值 5 行、CLI 输出改写 14 行、字段级 CLI 回归调整 4 行、摘要测试 56 行。低于 500 行预算。

摘要是研究结果展示，不是新的风险模型或数据源。项目仍不包含新因子、真实行情下载、自动复权、滑点、订单簿、基准或多因子合成逻辑。
