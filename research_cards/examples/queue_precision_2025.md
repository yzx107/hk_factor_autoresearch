+++
card_id = "rc_20260326_queue_precision_2025"
name = "2025 Queue 精细语义违规示例（Queue Precision 2025）"
owner = "codex"
status = "draft"
years = ["2025"]
universe = "phase_a_core"
target_instrument_universe = "stock_research_candidate"
source_instrument_universe = "target_only"
holding_horizon = "seconds"
research_modules = ["queue_position_or_depletion", "precise_order_to_trade_lag"]
required_fields = ["SeqNum", "OrderId", "Time", "Level", "VolumePre"]
hypothesis = "2025 年的 queue depletion 和 precise lag 可以预测即时收益。"
mechanism = "试图从 2025 委托记录中推断 strict queue order 和 precise latency。"
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；尝试使用被阻断的 queue 与精细 timing 语义。"
failure_modes = ["2025 年并不存在可用的 timing anchor。"]
expected_risks = ["硬性 admissibility 违规。", "queue 语义未验证。"]

[timing]
mode = "fine_ok"
uses_precise_lag = true
uses_strict_ordering = true
uses_queue_semantics = true

[semantics]
TradeDir = "unused"
BrokerNo = "unused"
OrderType = "unused"
Level = "queue_semantics"
VolumePre = "queue_semantics"
Type = "unused"
Ext = "unused"
+++

## Hypothesis

这张卡是故意用来违反 2025 timing 边界的。

## Mechanism

它假设了当前并不 admissible 的 queue 顺序和精细 lag。

## Holding Horizon

秒级。

## Required Fields

`SeqNum`、`OrderId`、`Time`、`Level`、`VolumePre`

## Info Boundary

这是专门给 smoke test 用的非法示例。

## Failure Modes

2025 年没有这个锚点。

## Expected Risks

属于硬性的 timing 与语义失败。
