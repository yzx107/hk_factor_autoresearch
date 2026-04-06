+++
card_id = "rc_20260326_brokerno_direct_alpha"
name = "BrokerNo 直接 Alpha"
owner = "codex"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
target_instrument_universe = "stock_research_candidate"
source_instrument_universe = "target_only"
holding_horizon = "30m_to_1d"
research_modules = ["matched_edge_session_profile"]
required_fields = ["Time", "Price", "Volume", "BrokerNo"]
hypothesis = "特定 broker seat 可以预测下一阶段收益。"
mechanism = "把 BrokerNo 直接当作 alpha 输入。"
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；试图把 BrokerNo 直接升级为 broker alpha。"
failure_modes = ["身份歧义会让信号失效。"]
expected_risks = ["语义过度宣称。", "lookup 覆盖缺口。", "vendor 导出不匹配。"]

[timing]
mode = "coarse_only"
uses_precise_lag = false
uses_strict_ordering = false
uses_queue_semantics = false

[semantics]
TradeDir = "unused"
BrokerNo = "direct_alpha"
OrderType = "unused"
Level = "unused"
VolumePre = "unused"
Type = "unused"
Ext = "unused"
+++

## Hypothesis

这张卡是故意用来违反 broker 边界的。

## Mechanism

它把 BrokerNo 当成了已经确认的官方身份。

## Holding Horizon

三十分钟到一天。

## Required Fields

`BrokerNo`、`Time`、`Price`、`Volume`

## Info Boundary

这是专门给 smoke test 用的非法示例。

## Failure Modes

这个字段的身份语义并未验证。

## Expected Risks

直接 broker alpha 超出了当前 admissibility 边界。
