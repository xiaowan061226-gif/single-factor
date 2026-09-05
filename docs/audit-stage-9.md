# 阶段 9 专项审计

审计范围是现有阶段 1--8 的正式实现与测试；本阶段未新增研究或回测业务功能。

## 高风险操作位置

| 类别 | 位置 | 审计结论 |
| --- | --- | --- |
| 时间序列动量偏移 | `factors/momentum.py:18-19` | 先按 `code,date` 稳定排序，再以 `groupby("code")` 计算 `close / shift(window) - 1`。 |
| 未来标签偏移 | `research/forward_return.py:18-19` | 同样逐 `code`，使用 `shift(-horizon) / close - 1`。 |
| 排序和键还原 | `research/_panel.py:43-56` | 计算前按键排序，结果经 `date,code` 的一对一 `merge` 返回原输入键。 |
| 横截面截尾与标准化 | `preprocess/cross_section.py:17-28` | 逐 `date` 分组；无 `rolling`。 |
| IC / RankIC | `research/ic.py:15-26` | 逐 `date` 且仅使用成对非空值；常数或少于三个配对值写出无效原因。 |
| 五分组 | `research/grouping.py:33-49` | 逐 `date`；`qcut` 标签 0--4 映射 Q1--Q5；样本或离散值不足时跳过并记录原因。 |
| 键合并 | `pipeline.py:47-50,80-83`、`diagnostics/data_profile.py:48-51` | 均以 `date,code` 合并，并启用一对一校验。 |
| 信号与执行 | `backtest/simple_backtest.py:99-112` | 信号为第 `t` 个交易日收盘后可见的因子，订单仅在 `t+1` 收盘执行；末日信号显式跳过。 |
| 资产收益和净值 | `backtest/simple_backtest.py:49-68` | 当日先用旧 shares 按价格得到交易前净值，再执行订单；净收益按与上一日净值之比计算。 |
| 权重与成本 | `backtest/simple_backtest.py:54-70` | 目标权重只在执行日更新；非执行日 shares 不变、权重随价格漂移；成本为 `cost_rate * sum(abs(target - prior_weight))`，只在实际订单时计入。 |

`rg` 审计未发现生产代码中的 `rolling` 调用。旧 `spike/alignment.py` 的 `merge` 仅用于历史对照，未在正式流水线调用。

## 破坏性测试

`tests/test_audit_semantics.py` 使用独立手算值或不变量，不能由被测函数生成预期：

| 风险 | 断言 |
| --- | --- |
| 漏掉按股票分组 | 交错 AAA/BBB 输入给出各自手算动量；新增/删除其他股票仍不改变 AAA 的动量和标签。 |
| 标签方向错误 | 将 AAA 的未来价格改为 240，`t=1` 的两日标签必须为 `240 / 105 - 1`；改未来价格不改变 `t=2` 动量。 |
| 输入行顺序 | 完整流水线使用随机打乱的输入，因子表、IC、分组结果、每日净值和调仓记录按键完全相同。 |
| 分组方向与伪统计 | 上升因子/标签使 Q1=1.5%、Q5=9.5%；常数截面 IC 为 NaN 且记录原因，五分组跳过；四只股票也跳过。 |
| 回测语义 | 信号日无收益无成本、次日才执行；非交易日成本为零；shares 不变而上涨资产权重上升。 |

现有 `tests/test_simple_backtest.py` 还独立覆盖首次建仓一侧换手、全换仓双侧换手、首笔信号不赚取信号日收益、末日信号跳过和零成交日零成本。
