# Program

## Harness 法则

这个 repo 遵守 `autoresearch` 的 harness 法则：
- 实验对象可以变
- 普通研究中的评估 harness 不可以漂移

落地到本项目：
- 人主要维护 `program.md`
- 当研究工厂制度升级时，同时维护 `ARCHITECTURE_ADDENDUM.md`
- agent 只在狭窄的 mutable surface 内工作
- 所有实验都要走同一套 harness 和 append-only registry
- 每个正式候选都要有 factor contract，并归属到一个 family

## 不可变 Layer 0

以下面向在显式变更控制前都视为冻结：
- `data_contracts/`
- `backtest_engine/`
- `evaluation/`
- `gatekeeper/`
- `configs/baseline_phase_a.toml`
- `harness/`
- `registry/` 的 schema

继承自上游 `Hshare_Lab_v2` 的 Phase A 边界：
- `2025 = coarse_only`
- `2026 = fine_ok`，但仍受字段语义约束
- 默认研究面 = `phase_a_core`
- caveat-only 研究面 = `phase_a_caveat_lane`
- `phase_a_core` / `phase_a_caveat_lane` 只定义字段输入边界，不自动定义“纯股票研究池”
- 本 repo 的正式 research card 当前固定要求 `target_instrument_universe = "stock_research_candidate"`
- 本 repo 的正式 research card 当前固定要求 `source_instrument_universe = "target_only"`
- 本 repo 的正式 research card 当前固定要求 `contains_cross_security_source = false`
- 本 repo 的正式 research card 当前固定要求 `universe_filter_version = "stock_research_candidate_filter_v1"`
- 若研究目标限定为股票候选池，必须显式引用上游 `instrument_profile` sidecar / `stock_research_candidate`
- `stock_research_candidate` 仍不是 pure common-equity proof
- 非股票证券只能作为未来显式 source lane 的扩展研究输入，不能回流成默认 mixed target universe
- `TradeDir`：`2025 = stable_code_structure_only`
- `TradeDir`：`2026 = vendor_aggressor_proxy_only`
- `BrokerNo`：两年都只能 `reference_lookup_only`
- `Level`、`VolumePre` 和 queue semantics 一律阻断
- `OrderType`、`Type`、`OrderSideVendor` 只能走 caveat lane
- full `Ext` 不能当默认真值，也不能直接进入因子面
- 本 repo 只读消费上游 verified 和 admissibility 输出

## Agent 可以改什么

- 新增或修改 `research_cards/`
- 新增或修改 `factor_specs/`
- 新增或修改 `factor_defs/`、`transforms/`、`combos/`
- 维护 `factor_contracts/`、`factor_families/` 和 family registry
- 新增或修改 `harness/run_auto_triage.py`、`harness/run_minimal_backtest.py` 这类下游评估 harness
- 在 `configs/` 下添加派生 run 配置，但不能改冻结 baseline
- 追加 experiment rows 和 lineage entries

单次实验默认只允许改很窄的一层：
- 一张 research card
- 一个 factor spec batch，或一次很小的候选生成
- 一个 factor definition，或一次很小的 transform/combo 改动
- 同一轮实验里不改 harness

## Agent 不可以改什么

- `/Users/yxin/AI_Workstation/Hshare_Lab_v2` 里的任何内容
- 为了配合某个因子去改 data contract
- 为了挽救弱结果去改 evaluator、metrics 或 cost rules
- 为了放行被阻断语义去改 gate policy
- 通过删除失败记录来改写实验历史

## 晋级纪律

1. 先写 research card，再写实现。
2. 任何回测或收益表述前先过 Gate A。
3. 候选排序前先跑固定 pre-eval harness。
4. `allow_with_caveat` 仍然必须人工复核。
5. 失败实验必须保留在 registry 中。
6. 给同一 idea 换名字不等于重置 lineage。
7. 正式候选必须登记 factor family，并显式写出 forbidden semantic assumptions。

## Autoresearch 循环

1. 当研究政策变化时，由人更新 `program.md`。
2. agent 通过 research card 提出一条有边界的实验。
3. agent 只改这条实验允许变动的窄表面。
4. agent 跑 Phase A harness。
5. agent 对已经 materialize 的因子输出跑固定 pre-eval。
固定 pre-eval 可以包含 normalized mutual information 这类非线性指标，
但前提是分箱规则和 label 规则都被冻结。
6. agent 在同一套冻结规则下重建 comparison 和 scoreboard。
7. agent 对配置中的候选池运行固定 autoresearch cycle。
8. harness 记录 `pass`、`allow_with_caveat` 或 `fail`。
9. `fail` 表示丢弃该候选修订。
10. `allow_with_caveat` 表示进入人工复核，不是自动晋级。
11. `pass` 只表示可以进入下一受控阶段。

## Token 纪律

为了降低 token 消耗：
- 行动前只读 `program.md`、baseline config、当前 active card，以及最近几条 registry
- 优先使用 card front matter 和紧凑的 machine-readable 输出，而不是长篇 prose
- 长命令输出写入 `runs/` artifact，不把整段日志贴回对话
- 默认用 harness runner 的 compact summary 做状态汇报
