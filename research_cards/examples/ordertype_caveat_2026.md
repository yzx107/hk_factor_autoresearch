+++
card_id = "rc_20260330_ordertype_caveat_2026"
name = "OrderType 弱语义检查 2026"
owner = "codex"
status = "draft"
years = ["2026"]
universe = "phase_a_caveat_lane"
target_instrument_universe = "stock_research_candidate"
source_instrument_universe = "target_only"
holding_horizon = "5m_to_1d"
research_modules = ["ordertype_weak_consistency_check"]
required_fields = ["OrderId", "Time", "Price", "Volume", "OrderType"]
hypothesis = "OrderType 的稳定 vendor event code 可能帮助区分生命周期形态。"
mechanism = "把 OrderType 只当作 stable vendor event code，而不是官方 message identity。"
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；使用上游 caveat-only 边界。OrderType 只在弱一致性与生命周期形态研究中使用。"
failure_modes = ["枚举稳定但没有经济含义。", "只是重复表达已有 lifecycle 信息。"]
expected_risks = ["event semantics 未正式毕业。", "需要人工复核。", "不可写成官方 Add/Modify/Delete truth。"]

[timing]
mode = "fine_ok"
uses_precise_lag = false
uses_strict_ordering = false
uses_queue_semantics = false

[semantics]
TradeDir = "unused"
BrokerNo = "unused"
OrderType = "stable_vendor_event_code_only"
Level = "unused"
VolumePre = "unused"
Type = "unused"
Ext = "unused"
+++

## Hypothesis

OrderType 的弱语义分桶可能帮助描述订单生命周期形态。

## Mechanism

它不是官方 event semantics，只是稳定的 vendor event code。

## Holding Horizon

五分钟到一天。

## Required Fields

`OrderId`、`Time`、`Price`、`Volume`、`OrderType`

## Info Boundary

只允许做弱一致性和生命周期形态研究，不允许宣称官方 message identity。

## Failure Modes

如果只是复述已有 lifecycle 指标，就没有增量。

## Expected Risks

这是典型 caveat-only 示例，必须人工复核。
