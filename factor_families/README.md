# Factor Families

这个目录按机制家族维护研究库存。

用途不是替代 `registry/factor_families.tsv`，而是补一层更稳定的家族说明：
- `registry/factor_families.tsv` 适合做 append-only 表格登记
- `factor_families/*.yaml` 适合写清楚某个 family 的机制假说、核心 observables、当前最佳变体和已知失败模式

Phase A 最小要求：
- 每个正式候选必须在 research card 和 factor contract 里写明 `factor_family`
- `factor_family` 应当能在本目录里找到对应 yaml
- family yaml 不得越过上游 admissibility 语义边界

当前 family yaml 至少要能表达：
- `family_id`
- `family_name`
- `mechanism_hypothesis`
- `allowed_input_lane`
- `common_variants`
- `current_best_variants`
- `known_failure_patterns`
- `redundancy_pattern`
- `regime_sensitivity`
- `extension_lane_eligibility`
- `whether_to_expand_further`

这些字段会被 `scoreboard`、`run_auto_triage.py`、`autoresearch_cycle.py` 和 family-level registry feedback 直接消费。

当前已落地的 family：
- `activity_pressure.yaml`
- `trade_notional_composition.yaml`
- `order_lifecycle_pressure.yaml`
- `close_vwap_pressure.yaml`
- `order_trade_interaction_pressure.yaml`
