# Research Card Template

请使用 TOML front matter。Gate A 只读取 front matter。
正式候选进入 `factor_defs/` 前，下面的 front matter 字段和正文段落都视为必填。

```toml
+++
card_id = "rc_YYYYMMDD_slug"
name = "简短因子名"
owner = "human_or_agent"
status = "draft"
factor_family = "activity_pressure"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "5m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["Time", "Price", "Volume"]
horizon_scope = "30m_to_1d"
hypothesis = "写清楚事前假设。"
mechanism = "写清楚市场机制，不要写事后解释。"
info_boundary = "准确说明使用了哪些上游字段和 caveat。"
observable_proxies = ["列出可观测代理。"]
baseline_refs = ["structural_activity_proxy"]
promotion_target = "exploratory_only"
failure_modes = ["列出这个想法在结构上会怎样失败。"]
expected_risks = ["列出风格、流动性、事件和语义风险。"]

[timing]
mode = "coarse_only"
uses_precise_lag = false
uses_strict_ordering = false
uses_queue_semantics = false

[semantics]
TradeDir = "unused"
BrokerNo = "unused"
OrderType = "unused"
Level = "unused"
VolumePre = "unused"
Type = "unused"
Ext = "unused"
+++
```

默认 `phase_a_core` 只适合安全结构字段。
如果 research card 要使用 `TradeDir`、`OrderType`、`Type` 或 `OrderSideVendor`，
就必须改成 `universe = "phase_a_caveat_lane"`，并在 semantics 中写明 caveat-only 用法。

## Hypothesis

写一句简短的事前判断。

## Mechanism

解释这个效应为什么可能在港股里存在。

## Observable Proxies

列出这个机制在当前 admissible 数据里能落成哪些可观测代理。

## Holding Horizon

重述计划持有周期，并解释它为什么与信号匹配。

## Required Fields

只列出这张卡真正需要的上游原始字段。

## Info Boundary

明确说明哪些字段是 vendor-defined、带 caveat 或被阻断。

## Failure Modes

列出这个信号可能如何失效、泄漏或坍塌。

## Expected Winning Regimes

写明你预期它在哪些 regime 更强。

## Expected Failure Regimes

写明你预期它在哪些 regime 更弱或失效。

## Why Incremental vs Baselines

解释为什么这个想法不是已有 baseline 或已有家族成员的换皮版本。

## Forbidden Semantic Assumptions

明确列出没有使用的隐含语义，例如 aggressor truth、queue semantics、broker identity truth。

## Promotion Target

说明这次实验的目标是 `exploratory only`、`family screening`、`baseline challenger` 或 `promotion candidate`。

## Expected Risks

列出换手、事件污染、流动性、风格和语义风险。

## Checklist

正式候选在进入 `factor_defs/` 前，至少要满足：
- `factor_family` 已存在于 `factor_families/`
- `Observable Proxies` 不是空段落
- `Why Incremental vs Baselines` 明确点名至少一个 baseline 或 family sibling
- `Forbidden Semantic Assumptions` 明确写出未使用的隐含语义
- 如果用了 caveat-only 字段，`universe` 必须是 `phase_a_caveat_lane`
