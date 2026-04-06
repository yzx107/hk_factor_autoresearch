+++
card_id = "rc_20260329_order_lifecycle_churn_2026"
name = "订单生命周期 churn（Order Lifecycle Churn 2026）"
owner = "codex"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
instrument_universe = "stock_research_candidate"
holding_horizon = "30m_to_1d"
research_modules = ["order_lifecycle_shape_by_event_count"]
required_fields = ["date", "source_file", "OrderId", "Price", "Volume"]
hypothesis = "单个唯一订单对应更高的事件 churn，可能代理更强的流动性争夺和短周期仓位压力。"
mechanism = "围绕同一个项目级 OrderId 的重复结构更新，可能代表更激烈的订单簿博弈，而且不需要假设未验证的事件语义。"
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；只使用 verified 结构性委托字段，以及从 source_file 提取的文件级 instrument key。它依赖项目级 OrderId 生命周期形态，不宣称官方原生身份。"
failure_modes = ["生命周期 churn 可能只是流动性代理。", "信号可能被少数活跃 ETF 或大盘股主导。", "项目级 OrderId 结构在横截面上区分度不够。"]
expected_risks = ["与流动性重叠。", "与换手重叠。", "ETF 集中。"]

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

更高的订单生命周期 churn 可能反映更强的流动性竞争。

## Mechanism

这个因子使用的是项目级 `OrderId` 的事件计数，而不是事件类型标签。

## Holding Horizon

三十分钟到一天。

## Required Fields

`date`、`source_file`、`OrderId`、`Price`、`Volume`

## Info Boundary

不使用 `OrderType`、`TradeDir`、`BrokerNo`、queue 或 vendor code 语义。

## Failure Modes

这个效应可能退化成普通的活跃度或流动性暴露。

## Expected Risks

主要风险是与高换手标的重叠，以及 ETF 集中。
