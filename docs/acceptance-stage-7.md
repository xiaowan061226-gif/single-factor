# 阶段 7：本地 CSV 可运行性与诊断

验收日期：2026-09-05。

## 结论

阶段 7 已完成并通过。系统只接受用户提供的本地 CSV；没有添加下载器、数据库或第三方行情 SDK。严格 loader 仍然是唯一数据入口：坏 CSV 在读取时失败，不会被诊断层修复、填充或聚合。

## 新增诊断

`ResearchPipelineResult.diagnostics` 提供只读的 `DataDiagnostics`，包括：

- 数据日期范围、股票数、总行数和每股完整观测数序列；CLI 显示最小值、中位数和最大值。
- 至少有 252 条同股历史、因而能产生有效默认动量的股票数。这里每只股票至少需要 253 行，第一行有效因子的前面才有完整 252 条历史。
- 重复键、缺失必需值、非法收盘价的计数。通过 loader 的输入这些值均为 0；任何非零问题都已在 loader 中以带样例的错误拒绝。
- 全部输入行的原始动量覆盖率、仅在有足够历史的行中的动量覆盖率、标准化因子覆盖率和未来标签覆盖率。
- 有效 IC 日期数、五分组跳过日期数、形成五分组的日期数和已执行调仓次数。

CLI 在每次 `--demo` 或 `--input` 运行时明确提示：`close` 应为公司行为调整后的价格；系统不会自动复权，也不会猜测输入是否已调整。

## 示例 CSV

[sample_prices.csv](../examples/sample_prices.csv) 是由 [generate_sample_prices.py](../examples/generate_sample_prices.py) 生成的确定性本地文件。它含 10 只股票、300 个交易日和 3,000 条价格行，因此在默认配置下可以形成动量、20 日标签、五分组和两次调仓。

```powershell
.venv\Scripts\python.exe main.py --input examples/sample_prices.csv
```

诊断摘要：

```text
date_range=2020-01-02..2021-02-24; stocks=10; rows=3000
observations_per_stock=min:300; median:300.0; max:300; stocks_with_252_history=10
quality=duplicate_keys:0; missing_required:0; illegal_close:0
factor_coverage_all=0.1600; factor_coverage_eligible=1.0000; forward_label_coverage=0.9333
valid_ic_dates=28; skipped_group_dates=272; rebalances=2
initial_nav=1.000000; final_nav=1.090762
```

## 可行动错误

流水线不会返回空研究结果：

- 没有任何一行有 252 条历史时，错误提示每股至少需要 253 行。
- 不能标准化时，错误提示同一日期至少需要两个非恒定因子值。
- 无法形成默认五分组时，错误提示同一日期至少需要 5 只同时有因子与未来标签的股票。
- 不能执行调仓时，错误提示需要在有效因子出现后仍有一个计划调仓日期。

CLI 会将这些 `ValueError` 作为标准参数错误输出，避免 Python 回溯掩盖数据问题。

## 实际验证

以下命令均以退出码 0 完成：

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe main.py --demo
.venv\Scripts\python.exe main.py --input examples/sample_prices.csv
.venv\Scripts\python.exe -m single_factor_quant --input examples/sample_prices.csv
```

结果为 80 passed；两条示例输入路径都产生上述诊断。临时目录 CSV 集成测试覆盖 loader → pipeline → CLI，并验证调用方 DataFrame 保持不变；短历史和四股票横截面测试确认了错误信息可行动。

## 代码量与边界

本阶段新增/实质改写 Python 共 194 行：诊断模块和示例生成器 110 行、流水线和 CLI 增量 17 行、集成测试 67 行。低于 450 行预算。

限制仍然是本地、完整价格面板研究。示例 CSV 是合成数据，只用于验证流程，不能用作投资结论。没有实现真实行情下载、复权、退市处理、交易日历、幸存者偏差处理或数据源适配器。
