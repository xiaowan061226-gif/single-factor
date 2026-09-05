# 阶段 5：正式因子与研究模块迁移

验收日期：2026-09-05。

## 结论

阶段 5 已完成并通过。动量、未来收益标签、横截面预处理、IC/RankIC 和五分组研究已迁入正式 `src/single_factor_quant/` 包。正式实现通过 `(date, code)` 键还原输出，不依赖调用方的行顺序或 DataFrame 索引；所有公开计算函数均复制所需数据，不修改调用方输入。

## 正式 API

| 模块 | API | 口径 |
|---|---|---|
| `factors/momentum.py` | `calculate_momentum(panel, window=252, output_col=None)` | 同一 `code` 的 `close / shift(window) - 1` |
| `preprocess/cross_section.py` | `cross_sectional_zscore(panel, factor_col, winsor_lower=.01, winsor_upper=.99)` | 每个 `date` 独立裁剪、`ddof=0` 标准化 |
| `research/forward_return.py` | `calculate_forward_returns(panel, horizon=20, output_col=None)` | 同一 `code` 的 `shift(-horizon) / close - 1` |
| `research/ic.py` | `daily_ic_rankic`、`summarize_ic` | 成对去空、至少 3 对、平均秩 RankIC、`ddof=1` ICIR |
| `research/grouping.py` | `quintile_forward_returns(panel, factor_col, return_col, quantiles=5)` | Q1 最低、Q5 最高；无法成组则记录原因 |

`research/_panel.py` 是一个内部验证与键恢复助手，避免时间序列和研究模块各自维护不同的数据校验逻辑。没有引入抽象基类、注册器或插件框架。

## 等价性与回归保护

迁移期间先保留原 spike 算法，并运行新旧 API 的并行测试；结果为 28 passed。比较覆盖：

- 两只股票的手算动量（AAA `2.52`、BBB `0.504`）、前 252 条空值和乱序输入。
- 未来收益的手算值、后 20 条空值，以及修改 `t+2` 价格只改变 `t` 的两期标签。
- 10 股票黄金截面的 z-score、`IC=1`、`RankIC=1` 和 Q1–Q5 收益 `0.015` 至 `0.095`。
- 跨日期隔离、空值成对删除、常数截面、输入不变性与自定义因子列。

新旧等价确认后，`spike/alignment.py` 缩为保留合成面板和演示的正式 API 包装器，`spike/research.py` 缩为兼容导出。由此删除了重复的算法实现，既有 demo 和历史 import 路径仍可用。

## 实际验证

以下命令均通过：

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_spike_alignment.py
.venv\Scripts\python.exe -m pytest -q tests/test_momentum.py tests/test_cross_section.py tests/test_forward_return.py tests/test_ic.py tests/test_grouping.py
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m spike.alignment_demo
.venv\Scripts\python.exe -m spike.research_demo
```

结果分别为 7 passed、10 项正式模块测试通过、75 passed；两个历史 demo 仍打印 PASS。

## 代码量

本阶段新增正式实现 255 行（含三个导出模块）、新增正式 API 测试 213 行，共 468 行 Python，低于 500 行预算。为删除重复实现，`spike/alignment.py` 和 `spike/research.py` 分别从 122 行和 204 行缩减为薄包装/导出；这部分是净删除，不把原有算法重复计入阶段新增代码。

## 仍存在的边界

- `quantiles` 虽可配置，但阶段 5 的默认验收口径仍是五分组，默认诊断名称保留既有 `five` 文本。
- 未来收益仅为研究标签，尚未将正式研究模块接入 CLI 或正式回测；这是阶段 6 的范围。
- 时间序列与研究函数要求键唯一、键非空，数值必须有限；动量和未来收益的 `close` 还必须为正。
