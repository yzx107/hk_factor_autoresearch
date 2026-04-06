# Factor Contract Schema

`factor contract` 用来把“一个因子到底是什么、依赖什么、明确不假设什么”固定下来。

在这个 repo 里，单个因子的合同由三部分组成：
- research card front matter：记录研究动机、边界、失败方式
- factor module metadata：记录可执行实现的统一元数据
- family registry：记录该因子属于哪个机制家族

这三层会被解析成一份 machine-readable `factor_profile.json`，并随每次 verified run 一起落盘。

## 当前落盘结构

当前正式 harness 会把以下 machine-readable profile 写进：
- `runs/<experiment_id>/factor_profile.json`
- `runs/<experiment_id>/family_profile.json`
- `runs/<experiment_id>/data_run_summary.json`

其中 `factor_profile` 当前至少稳定表达：
- `factor_name`
- `factor_id`
- `family_id`
- `family_name`
- `mechanism_hypothesis`
- `target_universe_scope`
- `source_universe_scope`
- `contains_cross_security_source`
- `universe_filter_version`
- `required_data_lane`
- `required_year_grade`
- `time_grade_requirement`
- `contains_caveat_fields`
- `supports_default_lane`
- `supports_extension_lane`
- `label_definition`
- `evaluation_horizons`
- `known_failure_modes`
- `baseline_comparators`
- `requires_cross_security_mapping`

## 适用范围

Phase A 下，所有进入 `factor_defs/` 的正式候选都应当导出统一 metadata。
示例和实验草稿也应尽量遵守同一格式。

## 必填 module metadata

每个正式 factor module 应至少导出以下常量：

- `FACTOR_ID`
  一个稳定的、不会因为输出列名变化而频繁变化的标识
- `FACTOR_FAMILY`
  机制家族标识，例如 `close_vwap_pressure`
- `MECHANISM`
  一句话说明该因子到底试图捕捉什么
- `RESEARCH_UNIT`
  当前研究粒度，例如 `date_x_instrument_key`
- `INPUT_DEPENDENCIES`
  因子真正依赖的上游字段、缓存层或聚合字段
- `ALLOWED_YEARS`
  当前允许研究的年份列表
- `ADMISSIBILITY_SCOPE`
  例如 `2025 coarse_only`、`2026 fine_ok` 或两者组合
- `TRANSFORM_CHAIN`
  level、change、clip、scale 等变换链
- `EXPECTED_REGIMES`
  最可能工作的状态描述列表
- `FORBIDDEN_SEMANTIC_ASSUMPTIONS`
  这个因子明确没有做出的语义假设
- `OWNER`
  负责人或默认维护者
- `VERSION`
  公式版本，例如 `v1`
- `STATUS`
  当前生命周期状态，例如 `proposed`、`gate_a_passed`

## 推荐 metadata

如果后续要扩更严格的 Gate B/C/D，可以继续补：

- `BENCHMARK_GROUP`
- `PRIMARY_LABEL`
- `REGIME_SLICES`
- `FAILURE_TAGS`
- `PROMOTION_NOTES`

## 与 research card 的关系

research card 负责回答：
- 为什么研究
- 用了哪些字段
- 边界是什么
- 可能怎么失败
- 预计在哪些 regime 更强或更弱
- 为什么它可能对 baseline 有增量

factor contract 负责回答：
- 代码实现的对象是谁
- 同一家族里的版本链是什么
- 后续该拿什么去比较
- 它明确没有越过哪些语义边界
- 允许在哪些年份和 admissibility scope 下使用
- 当前处于哪个生命周期状态

两者不能互相替代。

## 推荐字段格式

字符串字段：
- `FACTOR_ID`
- `FACTOR_FAMILY`
- `MECHANISM`
- `RESEARCH_UNIT`
- `ADMISSIBILITY_SCOPE`
- `HORIZON_SCOPE`
- `OWNER`
- `VERSION`
- `STATUS`

列表字段：
- `INPUT_DEPENDENCIES`
- `ALLOWED_YEARS`
- `TRANSFORM_CHAIN`
- `EXPECTED_REGIMES`
- `FORBIDDEN_SEMANTIC_ASSUMPTIONS`

## 最小示例

```python
FACTOR_ID = "close_vwap_gap_intensity_v1"
FACTOR_FAMILY = "close_vwap_pressure"
MECHANISM = "Measure unresolved end-of-day dislocation versus same-day VWAP."
RESEARCH_UNIT = "date_x_instrument_key"
INPUT_DEPENDENCIES = ["date", "source_file", "Time", "row_num_in_file", "Price", "Volume"]
ALLOWED_YEARS = ["2026"]
ADMISSIBILITY_SCOPE = "2026 fine_ok"
HORIZON_SCOPE = "30m_to_1d"
VERSION = "v1"
TRANSFORM_CHAIN = ["level"]
EXPECTED_REGIMES = ["end_of_day_pressure_unresolved"]
FORBIDDEN_SEMANTIC_ASSUMPTIONS = [
    "no_trade_side_truth",
    "no_broker_identity_truth",
    "no_queue_semantics",
]
OWNER = "agent"
STATUS = "gate_a_passed"
```

## Phase A 强制边界

contract 不能写出任何与 Layer 0 边界冲突的假设，尤其不能暗示：
- `TradeDir` 是 confirmed signed side
- `BrokerNo` 是 confirmed broker identity alpha
- `Level` 或 `VolumePre` 已经可用于 queue semantics
- `2025` 可以做 precise lag / strict ordering / queue depletion

如果一个因子必须依赖这些假设，它就不属于当前 Phase A factor contract。

## 当前实现关系

当前 repo 不是要求每个 factor module 自己重复声明完整 profile，
而是用：
- module metadata
- research card front matter
- family yaml

三者合成统一 `factor_profile` / `family_profile`。

也就是说，代码层继续保持最小 metadata 常量集，但 registry / scoreboard / cycle 看到的是统一的 resolved profile。
