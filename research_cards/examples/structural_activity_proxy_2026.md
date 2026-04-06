+++
card_id = "rc_20260329_structural_activity_proxy_2026"
name = "结构活跃度代理（Structural Activity Proxy 2026）"
owner = "codex"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
instrument_universe = "stock_research_candidate"
holding_horizon = "30m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["date", "source_file", "Price", "Volume"]
hypothesis = "日内活跃度的异常集中，可能代理短周期注意力，并延续到后续日内或次日波动。"
mechanism = "异常集中的价量活动可能捕捉到临时信息到达或库存压力，而且不依赖任何被阻断的字段语义。"
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；只使用 verified 结构性成交字段，以及从 source_file 提取的文件级 instrument key。"
failure_modes = ["信号可能只是规模或流动性代理。", "活跃度尖峰可能只是事件污染，无法持续。", "横截面效应在归一化后消失。"]
expected_risks = ["与注意力代理重叠。", "事件污染。", "高换手衰减。"]

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

## Hypothesis

先研究一个安全的结构性活跃度代理，再考虑进入带 caveat 的微观结构信号。

## Mechanism

这个想法只使用 verified 的结构性成交字段。

## Holding Horizon

三十分钟到一天。

## Required Fields

`date`、`source_file`、`Price`、`Volume`

## Info Boundary

不使用 `TradeDir`、`BrokerNo`、queue 或 vendor code 语义。
instrument grouping 只来自 `source_file` 的文件名。

## Failure Modes

这个效应可能在归一化或事件控制后坍塌。

## Expected Risks

主要风险是流动性/风格重叠，以及事件污染。
