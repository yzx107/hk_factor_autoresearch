+++
card_id = "rc_20260329_avg_trade_notional_bias_2026"
name = "平均单笔成交额偏离（Average Trade Notional Bias 2026）"
owner = "codex"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
target_instrument_universe = "stock_research_candidate"
source_instrument_universe = "target_only"
contains_cross_security_source = false
universe_filter_version = "stock_research_candidate_filter_v1"
holding_horizon = "30m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["date", "source_file", "Price", "Volume"]
hypothesis = "平均单笔成交额异常偏大的标的，可能代理更集中的参与者结构和短期信息压力。"
mechanism = "每笔成交的平均 notional 可以区分更像块状的集中交易和碎片化的小单交易，而且不依赖被阻断语义。"
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；只使用 verified 结构性成交字段，以及从 source_file 提取的文件级 instrument key。"
failure_modes = ["信号可能只是价格水平代理。", "效应可能被低流动性标的主导。", "单次事件爆发无法泛化。"]
expected_risks = ["横截面价格偏置。", "与流动性重叠。", "事件污染。"]

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

平均单笔成交额偏大，可能代表更集中的即时性需求或注意力。

## Mechanism

这个因子完全停留在 verified 结构性成交字段内，不触碰方向或 broker 语义。

## Holding Horizon

三十分钟到一天。

## Required Fields

`date`、`source_file`、`Price`、`Volume`

## Info Boundary

instrument grouping 只来自 `source_file` 的文件名。

## Failure Modes

价格水平和流动性可能主导原始横截面。

## Expected Risks

这个因子可能和规模、流动性、事件驱动尖峰重叠。
