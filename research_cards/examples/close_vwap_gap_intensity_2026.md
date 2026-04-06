+++
card_id = "rc_20260329_close_vwap_gap_intensity_2026"
name = "收盘-VWAP 偏离强度（Close VWAP Gap Intensity 2026）"
owner = "codex"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
target_instrument_universe = "stock_research_candidate"
source_instrument_universe = "target_only"
holding_horizon = "30m_to_1d"
research_modules = ["matched_edge_session_profile"]
required_fields = ["date", "source_file", "Time", "row_num_in_file", "Price", "Volume"]
hypothesis = "尾盘 close-like 成交若明显高于或低于当日 VWAP，可能代理未消化的压力，并延续到下一交易时段。"
mechanism = "最后观测成交价与成交量加权平均价之间持续存在的日内缺口，可能反映失衡或紧迫性，而且不依赖被阻断的 queue 或 side 语义。"
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；只使用 verified 成交字段、文件级 instrument grouping、按 Time 和 row_num_in_file 选出的最后成交价，以及当日 VWAP。"
failure_modes = ["信号可能只是噪声化的收盘成交伪影。", "偏离强度可能被事件驱动标的主导。", "一旦对符号做标准化或重中心化，边际优势可能消失。"]
expected_risks = ["收盘竞价污染。", "大盘股集中。", "短周期反转噪声。"]

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

研究同日 close-to-VWAP 缺口是否携带短周期信息。

## Mechanism

这个想法比较最后观测成交价和同日 VWAP，再按成交活跃度做缩放。

## Holding Horizon

三十分钟到一天。

## Required Fields

`date`、`source_file`、`Time`、`row_num_in_file`、`Price`、`Volume`

## Info Boundary

不使用 `TradeDir`、`BrokerNo`、queue 或 vendor code 语义。

## Failure Modes

这个信号可能退化为带噪音的尾盘成交或事件污染。

## Expected Risks

主要风险是尾盘成交噪音、事件集中和短周期反转。
