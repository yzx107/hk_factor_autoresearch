# Research Card Template

请使用 TOML front matter。Gate A 只读取 front matter。

```toml
+++
card_id = "rc_YYYYMMDD_slug"
name = "简短因子名"
owner = "human_or_agent"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "5m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["Time", "Price", "Volume"]
hypothesis = "写清楚事前假设。"
mechanism = "写清楚市场机制，不要写事后解释。"
info_boundary = "准确说明使用了哪些上游字段和 caveat。"
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

## Hypothesis

写一句简短的事前判断。

## Mechanism

解释这个效应为什么可能在港股里存在。

## Holding Horizon

重述计划持有周期，并解释它为什么与信号匹配。

## Required Fields

只列出这张卡真正需要的上游原始字段。

## Info Boundary

明确说明哪些字段是 vendor-defined、带 caveat 或被阻断。

## Failure Modes

列出这个信号可能如何失效、泄漏或坍塌。

## Expected Risks

列出换手、事件污染、流动性、风格和语义风险。
