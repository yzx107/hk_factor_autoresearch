# ARCHITECTURE_ADDENDUM

## 1. 文档目的

本文档是 `hk_factor_autoresearch` 的架构补充说明。

它不改写 `README.md` 已定义的 Phase A 范围，也不改变上游 / 下游仓库分工。
它的目标只有一个：

> 把当前“能跑的 research factory 骨架”补成“可持续扩展、可积累知识、可控地做 feature discovery 的研究工厂”。

本文档默认遵守以下边界：

- 上游事实源仍然只有 `Hshare_Lab_v2`
- 本 repo 只读消费上游 verified / admissibility 结论
- 本 repo 不得重定义 Layer 0 字段语义
- 本 repo 不默认引入 broker alpha、signed-flow truth、queue semantics 等未放行语义

## 2. 当前问题

当前骨架已经具备：

- `research_cards/`
- `factor_defs/`
- `transforms/`
- `evaluation/`
- `gatekeeper/gate_a_data.py`
- `harness/run_phase_a.py`
- `harness/run_pre_eval.py`
- `harness/autoresearch_cycle.py`
- append-only `registry/`

这意味着：

- Phase A 的最小实验闭环已经存在
- 固定 pre-eval 已存在
- lineage 留痕方向是对的

但目前仍然缺少几层关键“约束层”：

1. 缺少单因子统一合同
2. 缺少 family 级视角
3. 缺少完整 promotion gates
4. 缺少失败知识化
5. 缺少增量 / 冗余控制
6. 缺少 regime slicing 的一等公民地位

如果不补这些层，repo 会逐渐从“研究工厂”退化成“实验脚本集合”。

## 3. 补充原则

### 3.1 contract-first

先补合同，再补更多因子。

### 3.2 family-first

优先评估“机制家族是否成立”，而不是追逐孤立公式。

### 3.3 append-only

实验、失败、晋级、废弃都保留记录，不做覆盖式清洗。

### 3.4 regime-aware

不默认因子是全样本普适 alpha。
条件 alpha 也是合法研究成果。

### 3.5 no hidden semantics

任何因子不得偷偷引入上游未放行的字段解释。

## 4. 新增核心部件

### 4.1 Factor Contract

新增目录目标：

```text
factor_contracts/
├─ schema.md
├─ fields.md
└─ examples/
```

#### 目标

为每个 factor 建立统一合同，保证：

- 可审计
- 可复现
- 可比较
- 不偷渡语义前提

#### 每个 factor 最少必须声明

```text
factor_id
factor_family
mechanism
research_unit
input_dependencies
allowed_years
admissibility_scope
transform_chain
expected_regimes
forbidden_assumptions
owner
version
status
```

#### 字段解释

`factor_id`
: 唯一标识，不随实验名漂移。

`factor_family`
: 所属机制家族，例如 `pressure`、`persistence`、`crowding`、`liquidity_conditioning`、`reversal`。

`mechanism`
: 一句话写清楚该因子押的市场机制。

`research_unit`
: 例如 `ticker_day`、`ticker_bar`、`ticker_event`。

`input_dependencies`
: 显式列出依赖的上游 verified 字段、缓存层、聚合层。

`allowed_years`
: 例如 `2026` 或 `2025,2026`。

`admissibility_scope`
: 必须显式写清 `2025 coarse_only`、`2026 fine_ok` 或两者组合。

`transform_chain`
: 从原始 observable 到最终 factor 的变换链。

`expected_regimes`
: 预期有效样本，例如 `high_vol`、`open_window`、`low_liquidity`、`concentrated_flow`。

`forbidden_assumptions`
: 必须显式声明未使用的隐含语义，例如 `no aggressor inference`、`no queue reconstruction`、`no signed-flow truth`、`no hidden broker identity semantics`。

`status`
: 例如 `proposed`、`gate_a_passed`、`gate_b_passed`、`promoted`、`deprecated`、`rejected`。

### 4.2 Family Registry

新增目录目标：

```text
factor_families/
├─ pressure.yaml
├─ persistence.yaml
├─ crowding.yaml
├─ liquidity_conditioning.yaml
└─ reversal.yaml
```

#### 目标

把研究单位从“单因子”升级为“机制家族”。

#### 每个 family 应记录

```text
family_id
mechanism_hypothesis
core_observables
approved_factor_ids
rejected_factor_ids
baseline_refs
current_best_variant
known_failure_modes
notes
```

#### 为什么必须要有

如果没有 family registry，后面会不断积累：

- 看起来有效但彼此重复的因子
- 只在一个窗口偶然有效的公式
- 无法总结的失败经验

family registry 的目标不是展示漂亮结果，而是回答：

> 这个机制方向整体是否还活着？

### 4.3 Promotion Gates

新增目录目标：

```text
promotion/
├─ gate_b_stats.py
├─ gate_c_robustness.py
├─ gate_d_incremental.py
└─ gate_e_tradeability.py
```

#### Gate A

现有数据合法性 gate，保留不动。

#### Gate B: Statistical Validity

最少检查：

- rank IC
- top-bottom spread
- NMI
- sign consistency
- sample coverage

#### Gate C: Robustness

最少切片：

- by year
- by liquidity bucket
- by cap bucket
- by session
- by volatility regime

#### Gate D: Incrementality

最少检查：

- vs baseline factors
- vs same-family siblings
- vs currently promoted set

#### Gate E: Tradeability

最少检查：

- turnover proxy
- holding concentration
- decay speed
- crude cost sensitivity

#### Gate 结果输出

统一为：

```text
pass
watch
fail
```

并附失败标签。

### 4.4 Failure Taxonomy

新增目标：

```text
diagnostics/failure_taxonomy.py
registry/failures/
```

#### 固定失败标签

```text
data_invalid
leakage_suspected
too_sparse
unstable_by_year
unstable_by_bucket
redundant_to_baseline
non_incremental
not_tradeable
hypothesis_falsified
semantic_scope_violation
```

#### 原则

失败实验不是垃圾，而是知识资产。

任何失败实验进入 registry 时，都必须至少有：

- `failure_code`
- `one-line reason`
- `related factor_id / family_id`
- `failure stage`
- `timestamp`

### 4.5 Baseline Benchmark Set

新增目录目标：

```text
baselines/
├─ baseline_registry.yaml
└─ baseline_reports/
```

#### 目标

禁止新 factor 脱离基准独立自夸。

#### 最少基准组

建议固定包括：

- activity baseline
- turnover baseline
- volatility baseline
- liquidity baseline
- 当前最佳 broker-flow baseline

#### 规则

任何新 factor 默认必须回答：

1. 它是否优于至少一个 baseline
2. 它是否对 promoted baseline 有增量
3. 它是否只是 baseline 的换皮表达

### 4.6 Redundancy / Orthogonality Layer

新增文件目标：

```text
diagnostics/redundancy.py
```

#### 目标

把“有效”与“有增量”分开。

#### 最少输出

对每个 factor 额外输出：

- corr with baselines
- rank corr with baselines
- NMI with baselines
- same-family redundancy score
- incremental score conditional on baseline set

#### 判定逻辑

如果一个 factor：

- 对 target 有效
- 但与 promoted baseline 几乎完全共线
- 且没有稳定增量

则默认不晋级。

### 4.7 Regime Slicing as First-Class Citizen

新增文件目标：

```text
diagnostics/regime_slices.py
```

#### 目标

将“条件有效性”正式纳入架构。

#### 默认固定切片

所有 Gate B / C 报表默认至少切：

- `2025 coarse_only`
- `2026 fine_ok`
- high_vol / low_vol
- high_turnover / low_turnover
- open / midday / close
- large / mid / small cap

#### 原则

“只在特定 regime 下有效”不是失败；
“说不清在哪些 regime 下有效”才是失败。

## 5. 目录建议

建议在现有目录上补成：

```text
hk_factor_autoresearch/
├─ backtest_engine/
├─ combos/
├─ configs/
├─ data_contracts/
├─ diagnostics/
│  ├─ redundancy.py
│  ├─ regime_slices.py
│  └─ failure_taxonomy.py
├─ evaluation/
├─ factor_contracts/
│  ├─ schema.md
│  ├─ fields.md
│  └─ examples/
├─ factor_defs/
├─ factor_families/
│  ├─ pressure.yaml
│  ├─ persistence.yaml
│  ├─ crowding.yaml
│  ├─ liquidity_conditioning.yaml
│  └─ reversal.yaml
├─ baselines/
│  ├─ baseline_registry.yaml
│  └─ baseline_reports/
├─ gatekeeper/
├─ harness/
├─ promotion/
│  ├─ gate_b_stats.py
│  ├─ gate_c_robustness.py
│  ├─ gate_d_incremental.py
│  └─ gate_e_tradeability.py
├─ registry/
│  ├─ experiments/
│  ├─ families/
│  ├─ failures/
│  └─ promoted/
├─ research_cards/
├─ tests/
└─ transforms/
```

## 6. Research Card 扩展要求

现有“先写 research card，再落因子实现”的原则保留。
但 research card 模板建议增加以下必填段落：

```text
Mechanism
Observable Proxies
Expected Winning Regimes
Expected Failure Regimes
Why Incremental vs Baselines
Forbidden Semantic Assumptions
Promotion Target
```

### 说明

`Mechanism`
: 不是写公式，而是写市场机制假说。

`Observable Proxies`
: 列出该假说在当前 admissible 数据中的代理变量。

`Expected Winning Regimes`
: 提前声明预计在哪些状态更强。

`Expected Failure Regimes`
: 提前声明预计在哪些状态失效。

`Why Incremental vs Baselines`
: 必须解释为什么不是旧因子换皮。

`Forbidden Semantic Assumptions`
: 明确没有偷偷借用上游未验证语义。

`Promotion Target`
: 说明本实验目标是 `exploratory only`、`family screening`、`baseline challenger` 或 `promotion candidate`。

## 7. 因子生命周期

建议统一定义：

```text
proposed
→ gate_a_passed
→ gate_b_passed
→ gate_c_passed
→ gate_d_passed
→ gate_e_passed
→ promoted
→ monitored
→ deprecated / rejected
```

### 说明

- `promoted` 不代表生产交易，只代表进入更高优先级研究集合
- `deprecated` 也保留历史，不做删除
- `rejected` 必须附 failure code

## 8. 与上游 repo 的接口约束

本 addendum 不改变与上游 `Hshare_Lab_v2` 的边界：

- 上游仍负责 truth / admissibility / semantic scope
- 下游仍不得反向定义上游字段意义
- 下游任何 family / factor contract 中，若使用了上游尚未放行的语义，直接判为 `semantic_scope_violation`

## 9. 实施优先级

不建议一次性全补完。
按优先级分三步：

### P0

- factor contract
- promotion gates
- research card 扩展

### P1

- family registry
- failure taxonomy
- baseline benchmark set

### P2

- redundancy layer
- regime slicing first-class
- promoted set governance

## 10. 最终目标

本 repo 的目标不是成为“能跑很多脚本的仓库”，而是成为：

> 在受控语义边界内，持续发现、筛选、淘汰、积累 feature family 知识的 research factory。

如果未来要扩到 Phase B，优先扩的是：

- promotion governance
- family-level search orchestration
- richer incremental diagnostics

而不是先扩多 agent 或更重型 backtester。
