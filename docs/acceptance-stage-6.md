# 阶段 6：正式回测与端到端 CLI

验收日期：2026-09-05。

## 结论

阶段 6 已完成并通过。正式回测位于 `backtest/simple_backtest.py`，阶段 3 的独立手算测试已改为直接调用正式 API。`pipeline.py` 将价格输入、动量、按日裁剪与标准化、未来收益标签、IC/RankIC、五分组和 Top 20% 回测串为一个结构化结果；`main.py` 只转发到包 CLI。

## 保持的回测口径

- 信号在日期 `t` 收盘后生成，只能在下一交易日收盘执行。
- 持仓以股数记录，在调仓之间自然漂移；不会每日恢复等权。
- Top 20% 向上取整，同分以代码升序选择。
- 成本为 `费率 × sum(abs(目标权重 - 调仓前漂移权重))`；首次建仓也收费。
- 日净值从 1.0 开始。年化使用 `ResearchConfig.annualization_days`，默认 252。

迁移前后，阶段 3 的 14 项手算测试在正式 API 上通过，包括一日执行滞后、无费净值 1.32、含费净值 1.31604264、首次与完整换仓成本、持仓漂移、同分选择和末期边界。之后 `spike/backtest.py` 缩为黄金数据与正式 API 兼容层，不再维护第二份回测算法。

## CLI 与流水线

```powershell
.venv\Scripts\python.exe main.py --demo
.venv\Scripts\python.exe -m single_factor_quant --demo
.venv\Scripts\python.exe main.py --input prices.csv
```

`--demo` 生成 10 只股票、300 个交易日的确定性面板。默认配置下，它给出：

```text
rows=3000; valid_ic_dates=28; quintile_rows=140
initial_nav=1.000000; final_nav=1.090762; rebalances=2
```

端到端测试检查因子数据非空、`(date, code)` 唯一、日期有序、五分组和已执行调仓存在、净值全为有限数且首日净值严格为 1.0。它还验证流水线不修改调用方价格表，以及 CLI 的 `--demo` 和 `--input` 两种路径。

## 实际验证

以下命令均以退出码 0 完成：

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_simple_backtest.py tests/test_pipeline.py
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe main.py --demo
.venv\Scripts\python.exe -m single_factor_quant --demo
.venv\Scripts\python.exe -m spike.backtest_demo
```

结果为 16 passed、77 passed；两个 CLI demo 都给出上述摘要，历史回测 demo 仍打印 PASS。

## 代码量与边界

本阶段新增正式回测、流水线、CLI 增量和端到端测试共 283 行 Python：正式新增生产代码 232 行，CLI 改写净增 16 行，端到端测试 33 行，阶段 3 测试导入改写 2 行。低于 500 行预算。重复 spike 回测从 271 行缩为 41 行兼容层，未将原有算法重复计入新增代码。

当前范围仍是完整价格面板上的收盘到收盘模拟。未加入订单簿、滑点、做空、基准、数据库、图形界面或真实数据诊断；这些不属于阶段 6。
