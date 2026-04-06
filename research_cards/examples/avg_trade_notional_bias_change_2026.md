+++
card_id = "rc_20260329_avg_trade_notional_bias_change_2026"
name = "平均单笔成交额偏离变化（Avg Trade Notional Bias Change 2026）"
owner = "agent"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
target_instrument_universe = "stock_research_candidate"
source_instrument_universe = "target_only"
holding_horizon = "30m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["date", "source_file", "Price", "Volume"]
hypothesis = "平均单笔成交额的日间变化，可能揭示新的参与者结构变化，而不只是静态规模暴露。"
mechanism = "对 log 平均单笔成交额做一日差分，只用 verified 成交结构来隔离成交尺寸结构的加速度。"
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；只使用 verified 成交字段、文件级 instrument key，以及前一个可用 verified 成交日。"
failure_modes = ["变化量可能只是阶段性 block trade 噪声。", "很多标的的前一日对齐过于稀疏。", "大盘股资金流可能主导效应。"]
expected_risks = ["大单成交污染。", "流动性/风格重叠。", "大盘股集中。"]

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
