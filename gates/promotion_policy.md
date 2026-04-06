# Promotion Policy

这个文件定义 research factory 的标准晋级门（promotion gates）。

当前状态：
- Gate A 已实装
- Gate B 有最小正式 runner
- Gate C 之后仍以制度定义为主，代码实现是逐步补齐

## Gate A: Data Admissibility

目标：
- 检查研究卡是否越过数据边界和语义边界

输入：
- research card front matter

输出：
- `pass`
- `allow_with_caveat`
- `fail`

当前实现：
- `gatekeeper/gate_a_data.py`

典型拦截：
- `2025` 精细 timing
- queue semantics
- `BrokerNo` direct alpha
- 把 `TradeDir` 写成 signed-side truth

## Gate B: Statistical Validity

目标：
- 检查信号是否在固定 label 和固定评估规则下表现出稳定统计关系

最小输入：
- factor output
- shared labels
- fixed pre-eval summary

最小输出：
- `pass`
- `monitor`
- `fail`

最小检查项：
- mean rank IC
- mean absolute rank IC
- normalized mutual information
- coverage ratio
- sign consistency

当前状态：
- `pre_eval` 已有基础件
- `harness/run_gate_b.py` 已把最小 policy 固化为 machine-readable rules
- 当前 Gate B 仍是轻量统计 gate，不等于正式组合回测

## Gate C: Robustness

目标：
- 检查该因子是否只是在单一时间段、单一 bucket 或单一 regime 偶然成立

最小检查项：
- year slice
- volatility slice
- turnover slice
- entropy slice
- open / midday / close
- large / mid / small cap

输出：
- `pass`
- `monitor`
- `fail`

当前状态：
- 只定义政策，尚未标准化落地

## Gate D: Incrementality

目标：
- 检查该因子是否只是把已有 baseline 或 sibling factor 换一种写法重说一遍

最小检查项：
- vs frozen benchmark set 的相关性
- vs family siblings 的 redundancy
- peer overlap
- conditional incremental score

输出：
- `pass`
- `monitor`
- `fail`

当前状态：
- comparison 和 scoreboard 已有雏形
- benchmark set 和条件增量规则仍待固化

## Gate E: Tradability

目标：
- 检查这个因子是否能进入更真实的组合或交易层，而不是停留在研究叙事

最小检查项：
- coverage and sparsity
- turnover burden
- concentration
- execution realism compatibility

输出：
- `pass`
- `monitor`
- `fail`

当前状态：
- 只定义政策，尚未作为正式 gate 执行

## 决策纪律

- `fail`：该 revision 停止晋级，但保留在 registry 中
- `monitor`：保留候选身份，不进入自动晋级
- `allow_with_caveat`：只用于 Gate A 这类边界门，必须人工复核
- `pass`：只表示进入下一受控阶段，不等于 production ready

## Phase A 推荐工作流

1. 先写 research card
2. 过 Gate A
3. materialize factor output
4. 跑 Gate B-lite pre-eval
5. 对 shortlist 跑正式 Gate B
6. 进入 scoreboard
7. 再决定是否进入更正式的 Gate C/D/E

这套 policy 的目的不是把每个因子都一次性判死刑，而是让“为什么保留、为什么淘汰、为什么暂缓”变得可追踪。
