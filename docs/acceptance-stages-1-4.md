# Roadmap 阶段 1–4 验收记录

验收日期：2026-09-05。范围为 roadmap 表格中的阶段 1、2、3、4，不包含阶段 5–9。

**结论：发现的缺项与缺陷已补齐，前四阶段全部 PASS。**

## 初始状态与修复

原有 40 项测试通过，但交付并不完整。本次先补失败用例，再修复缺陷：

1. 将三个已有算法探针整理至 `spike/`，测试整理至 `tests/`，补齐 roadmap 指定的演示入口。根目录保留兼容转发，避免重复算法。
2. 阶段 1 演示增加真正执行断言的 `cross_code_guard` 与 `lookahead_guard`；补测稀疏交易观测、重复行索引、全体未来价格变动与输入不变性。
3. 增加跨日期平均五组收益、可配置的 winsor 分位数，以及平均秩并列值、分位边界坍塌、标签缺值、常数标签等测试。
4. 验证信号日和执行日收益隔离、六只股票 Top 20% 向上取整、同分代码排序、漂移后的再平衡换手、无交易不收费、复合净值、年化、回撤、全空因子和最后一期。
5. 回测调仓周期拒绝布尔值和非整数；配置费率限制与回测统一为 `[0, 0.5)`，保证最大双边换手为 2 时扣费后净值仍为正。
6. 增加 `requirements.txt`、包 `__main__.py`、薄根入口、`data/loader.py` 和基础使用说明。
7. CSV 不再把字符串股票代码 `NA` 自动当作缺失；空文件和空表明确失败。增加字段数量预检，阻止 pandas 将额外字段静默当作索引而丢弃；缺失字段也有数量及样例诊断。
8. 数据检查结果附带未验证复权的提示，README 明确调整后价格前提。

新增验收用例曾复现 9 项失败；CSV 字段数量预检的补充用例又复现 2 项失败。修复后均通过。

## 逐阶段验收

| 阶段 | 验收内容 | 结果 |
|---|---|---|
| 1 | 两股 300 日确定性数据；同股 shift；前 252/后 20 空值边界；乱序和重复索引；未来价格变形测试；按观测数计窗口 | PASS，7 项测试 |
| 2 | 日内独立去极值、ddof=0 标准化；成对去空 IC/RankIC；ddof=1 ICIR；黄金五组；跨日平均；异常日诊断 | PASS，11 项测试 |
| 3 | 次日收盘执行；20 日信号周期；Top 20% 向上取整和同分顺序；持股漂移；首次与双边成本；指标与末期边界 | PASS，14 项测试 |
| 4 | src 包可安装和导入；冻结配置与范围检查；严格 loader、代码保真、排序及可定位报错；两个薄入口 | PASS，33 项测试 |

P1 Gate 的四项已逐条进行代码及手算复核：黄金样例、未来价格不改变当期因子、第二只股票不串组、执行日期与费用全部满足。

## 手算证据

| 项目 | 独立预期 | 实测 |
|---|---|---|
| 第 252 条后的首次动量 AAA / BBB | `352/100-1=2.52` / `1504/1000-1=0.504` | 一致 |
| 同序黄金样例 IC / RankIC | 1 / 1 | 一致 |
| 黄金五组收益 Q1–Q5 | 0.015、0.035、0.055、0.075、0.095 | 一致 |
| 两日期五组均值 | 0.0225、0.0525、0.0825、0.1125、0.1425 | 一致 |
| 首次建仓净值 | `1 × (1-0.001) = 0.999` | 一致 |
| A 涨 10% 后换入 B，换仓收费后净值 | `0.999 × 1.1 × (1-0.002) = 1.0967022` | 一致 |
| 无费最终净值 | `1.1 × 1.2 = 1.32` | 1.32000000 |
| 含费最终净值 | `0.999 × 1.1 × 0.998 × 1.2` | 1.31604264 |
| 总 gross_turnover | `1 + 2 + 0 = 3` | 一致 |
| 最大回撤 | -0.002 | 一致 |
| 双持仓漂移权重 | `11/21`、`10/21`，股数不变 | 一致 |

研究 demo 记录 1 个跳过日期，原因是常数截面无法形成五组。其 IC 标准差和 ICIR 为 NaN，因为仅有 1 个有效 IC 日期，这是预期的样本不足行为。

## 已实际运行的验证

本机默认 PATH 没有 `python`，先用应用提供的 Python 运行基线，再在项目创建全新 `.venv` 并从依赖清单安装：

```powershell
uv --cache-dir .cache/uv venv .venv --python 'C:\Users\pc\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
uv --cache-dir .cache/uv pip install --python .venv/Scripts/python.exe -r requirements.txt
```

安装成功。实测环境为 Python 3.12.14、numpy 2.5.2、pandas 3.0.5、pytest 9.1.1。

以下命令均在新环境运行，退出码为 0：

| 命令 | 结果 |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q` | 65 passed |
| `.venv/Scripts/python.exe -m pytest -q tests/test_spike_alignment.py` | 7 passed |
| `.venv/Scripts/python.exe -m pytest -q tests/test_spike_alignment.py tests/test_spike_research.py` | 18 passed |
| `.venv/Scripts/python.exe -m pytest -q tests/test_spike_alignment.py tests/test_spike_research.py tests/test_spike_backtest.py` | 32 passed |
| `.venv/Scripts/python.exe -m pytest -q tests/test_config.py tests/test_loader.py` | 33 passed |
| `.venv/Scripts/python.exe -m spike.alignment_demo` | cross_code_guard=PASS、lookahead_guard=PASS |
| `.venv/Scripts/python.exe -m spike.research_demo` | IC=1、RankIC=1、五组严格递增、skipped_dates=1 |
| `.venv/Scripts/python.exe -m spike.backtest_demo` | 两种成本净值与手算一致，PASS |
| `.venv/Scripts/python.exe main.py` | 输出完整默认配置 |
| `.venv/Scripts/python.exe -m single_factor_quant` | 输出完整默认配置 |

另从项目目录外 `E:\Projects` 使用新环境解释器成功导入 `ResearchConfig` 与 `load_price_csv`，证明正式包导入不依赖 pytest 的路径注入。

## Python 行数

计数包含生产代码、测试、demo、兼容转发、docstring、空白行；空 `__init__.py` 和 Markdown 不计。移动文件按原实现对照，不把单纯迁移重复算作新增。
因为初始项目文件均未被 Git 跟踪，本次以开工时保存的文件内容为基准，通过逐行差异计数。

| 阶段 | 本次新增/替换后的行 | 删除/替换前的行 | 当前全部 Python 行数 | roadmap 预算 |
|---|---:|---:|---:|---:|
| 1 | 40 | 4 | 242 | ≤350 |
| 2 | 89 | 3 | 412 | ≤450 |
| 3 | 66 | 3 | 420 | ≤500 |
| 4 | 90 | 13 | 383 | ≤400 |

即便按每阶段全部现存 Python 代码的更严格口径，也均未超预算。

## 适用边界

- Python 最低版本声明为 3.11，本次实测版本为 3.12.14，未声称已跑过完整多版本矩阵。
- 阶段 3 是完整价格面板上的收盘到收盘模型；停牌、退市、个股缺交易日和滑点尚未建模。缺失价格面板明确报错。
- 实际 CSV 必须使用调整后价格，loader 只能验证格式和数值，不能认证复权状态。
- 年化分母包含输入面板所有观测日期，初始现金日期的零收益也计入；完整默认黄金样例为 42 日。
- 阶段 5–9 的正式研究迁移、完整 CLI、真实数据诊断和最终报告未纳入本次验收。前四阶段通过不代表整个 roadmap 已完成。
