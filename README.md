# hk_factor_autoresearch

这个 repo 是港股因子研究工厂（research factory）repo。
它不是数据底座 repo，也不是 production 交易系统。

当前范围是 `Phase A / 半自动`：
- 冻结 Layer 0 边界
- 先写 research card，再落因子实现
- 固定回测与评估接口，不在普通实验里漂移
- Gate A 已自动化，Gate B 有最小正式 runner
- lineage 和 experiment registry 采用 append-only
- 实验必须走固定 harness，不允许临时 shell 拼装流程

与 `Hshare_Lab_v2` 的关系：
- 上游 repo：`/Users/yxin/AI_Workstation/Hshare_Lab_v2`
- 本 repo 只读消费上游 verified 和 admissibility 结论
- 本 repo 不得重定义上游字段语义，也不能反向改写上游 Layer 0

现在 repo 里有什么：
- `ARCHITECTURE_ADDENDUM.md`：研究工厂从“能跑”升级到“可持续 feature discovery”的补充架构
- `baselines/`：固定 baseline benchmark set
- `data_contracts/`：固定字段、年份、timing 边界
- `data_contracts/caveat_lane.md`：说明哪些字段只能走 `phase_a_caveat_lane`
- `diagnostics/`：去冗余、切片和失败知识化这类诊断层
- `factor_contracts/`：单因子 metadata 合同
- `factor_specs/`：可批量生成 Gate A 候选的结构化规格
- `factor_families/`：机制家族 yaml，补充 family 级研究视角
- `gates/`：研究晋级门和 promotion policy
- `research_cards/`：研究卡模板和 smoke 示例
- `gatekeeper/gate_a_data.py`：最小 Gate A 合法性检查
- `configs/baseline_phase_a.toml`：冻结 baseline 配置
- `configs/autoresearch_phase_a.toml`：固定候选池配置
- `cache/daily_agg/`：从上游 verified 生成的本地逐日聚合缓存
- `harness/run_phase_a.py`：最小 autoresearch 风格实验入口
- `harness/generate_factor_batch.py`：从 `factor_specs/*.toml` 批量生成候选
- `harness/run_pre_eval.py`：固定 forward-return pre-eval
- `harness/run_gate_b.py`：最小正式 Gate B statistical validity runner
- `harness/autoresearch_cycle.py`：端到端 cycle runner
- `registry/`：append-only 实验留痕骨架

新增的研究工厂控制层：
- `ARCHITECTURE_ADDENDUM.md`：定义 factor contract、family 视角、promotion gates、失败知识化、regime slicing 的升级方向
- `baselines/baseline_registry.toml`：固定 baseline benchmark set
- `diagnostics/redundancy.py`：把“有信号”和“有增量”分开
- `diagnostics/regime_slices.py`：把“在哪些状态下有效”也纳入固定诊断
- `factor_contracts/schema.md`：统一说明每个因子必须声明什么
- `factor_families/*.yaml`：记录每个机制家族的机制假说、最佳变体和失败模式
- `registry/factor_families.tsv`：把候选按机制家族登记，而不是只看单次实验
- `registry/failure_taxonomy.md`：统一失败分类，避免 registry 变成墓地
- `gates/promotion_policy.md`：把 Gate A/B/C/D/E 的目标和输出固定下来

固定 pre-eval 当前输出：
- `aggregate_metrics.mi`
- `aggregate_metrics.rank_ic`
- `aggregate_metrics.top_bottom_spread`
- `aggregate_metrics.nmi`
- `aggregate_metrics.nmi_ic_gap`
- `aggregate_metrics.mi_p_value`
- `aggregate_metrics.mi_excess_over_null`
- `aggregate_metrics.mi_significant_date_ratio`
- `per_date[*].mi` / `per_date[*].nmi` 是日期级 mutual information 指标的 canonical 字段
- `per_date[*].mi_p_value` / `per_date[*].mi_significant` / `per_date[*].nmi_ic_gap` 用于固定 diagnostics
- 兼容旧消费者时，仍同时保留 `mean_rank_ic` / `mean_top_bottom_spread` / `mean_normalized_mutual_info`
- `per_date[*].mutual_info` / `per_date[*].normalized_mutual_info` 只保留为兼容 alias，不再视为新的正式主字段
- `regime_slices.entropy_quantile` 当前明确指的是 `market_turnover_entropy` 的分位切片，也就是成交额分布熵的低熵 / 中熵 / 高熵状态，不是泛化意义上的“市场熵”
- 这里的 entropy quantile 仍然是 descriptive regime labeling，不是可直接生产化的 predictive regime 标签
- transfer entropy 不并入当前 fixed pre-eval / Gate；如果要做 lead-lag 研究，走独立 exploratory utility

这里没有什么：
- 没有多 agent 搜索工厂
- 没有 production backtester
- 没有重型 paper-trading 系统
- 默认不做 broker alpha、signed-flow truth、queue semantics

当前 universe 分层：
- `phase_a_core`：默认安全面，只消费 `verified v1` 的结构字段
- `phase_a_caveat_lane`：受限研究面，只允许显式声明的 caveat-only 字段，并默认人工复核

这里还要额外区分 target/source 证券池边界：
- `phase_a_core` / `phase_a_caveat_lane` 只定义字段 admissibility，不等于“研究对象已经是纯股票池”
- 上游已经明确承认 tick universe 不是纯股票池；若需要股票研究池，必须显式使用 `instrument_profile` sidecar 做 universe 选择
- 本 repo 当前所有 research card 都要求 `target_instrument_universe = "stock_research_candidate"`
- 当前默认还要求 `source_instrument_universe = "target_only"`
- 当前推荐写法是 `stock research candidate target universe`
- 运行时 loader 会按 `instrument_profile` sidecar 对 target universe 做实际过滤，不只是文档声明
- 当前不应把默认研究对象写成 `fully verified equity universe`
- `stock_research_candidate` 只是保守候选池，仍可能残留低位非股票例外
- 非股票证券如果未来要进入研究，只能作为显式 source lane 输入，用于 cross-security dependence / transfer-entropy 扩展研究，不进入默认 scoreboard 主线

最小 smoke：

```bash
python3 -m unittest tests/test_gate_a_smoke.py
```

最小 harness run：

```bash
python3 harness/run_phase_a.py \
  --card research_cards/examples/structural_activity_proxy_2026.md \
  --factor structural_activity_proxy
```

真实 `2026 verified` 数据 run：

```bash
python3 harness/run_verified_factor.py \
  --card research_cards/examples/structural_activity_proxy_2026.md \
  --factor structural_activity_proxy \
  --dates 2026-03-13
```

构建本地逐日聚合缓存：

```bash
python3 harness/build_daily_agg.py --table all --year 2026
```

查看项目进度：

```bash
python3 harness/status.py
```

比较最近两条因子 run：

```bash
python3 harness/compare_factors.py \
  --left-factor structural_activity_proxy \
  --right-factor avg_trade_notional_bias
```

生成候选板：

```bash
python3 harness/scoreboard.py \
  --factors structural_activity_proxy avg_trade_notional_bias
```

对最新因子实验跑固定 pre-eval：

```bash
python3 harness/run_pre_eval.py \
  --factor structural_activity_proxy
```

探索性扫描 lead-lag 关系（独立于固定 pre-eval / Gate）：

```bash
python3 harness/find_lead_factors.py \
  --metric rank_ic \
  --factor structural_activity_proxy avg_trade_notional_bias order_lifecycle_churn
```

对 shortlist 跑最小正式 Gate B：

```bash
python3 harness/run_gate_b.py \
  --factor close_vwap_gap_intensity_change close_vwap_churn_interaction_change
```

导出共享 labels 供 pre-eval 复用：

```bash
python3 harness/export_forward_labels.py --year 2026
```

运行一轮固定 autoresearch cycle：

```bash
python3 harness/autoresearch_cycle.py
```

运行一轮 order-trade interaction family 的最小 batch screen：

```bash
python3 harness/autoresearch_cycle.py \
  --config configs/order_trade_interaction_screen.toml \
  --notes "order-trade interaction entropy screen"
```

从规格批量生成一组 Gate A 候选：

```bash
python3 harness/generate_factor_batch.py \
  --spec factor_specs/order_trade_interaction_batch.toml
```

候选板会额外写出：

```text
runs/<scoreboard_id>/scoreboard_report.md
```

其中默认会展示：
- `mean_nmi`
- `entropy_regime_dispersion`
- `entropy_quantile` 切片下的 `mean_abs_rank_ic` / `mean_nmi`

这里的 `entropy_quantile` 仍然只对应 turnover distribution entropy quantile，
不是更宽泛的市场复杂度刻画；transfer entropy 也还没有进入这一阶段。

每个 verified 因子 run 也会写固定 diagnostics：

```text
runs/<experiment_id>/diagnostics_summary.json
```

其中会附带固定 `regime_annotations`，包括：
- `year_grade`
- `market_turnover_regime`
- `market_volatility_regime`
- `market_turnover_entropy`
- `entropy_quantile`

每个固定 pre-eval run 会写：

```text
runs/<pre_eval_id>/pre_eval_summary.json
```

每个 Gate B run 会写：

```text
runs/<gate_b_id>/gate_b_summary.json
```

每个 autoresearch cycle 会写：

```text
runs/<cycle_id>/cycle_summary.json
```
