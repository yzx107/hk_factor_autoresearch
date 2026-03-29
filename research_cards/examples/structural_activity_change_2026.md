+++
card_id = "rc_20260329_structural_activity_change_2026"
name = "结构活跃度变化（Structural Activity Change 2026）"
owner = "agent"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "30m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["date", "source_file", "Price", "Volume"]
hypothesis = "结构活跃度的日间陡变，比 level 本身更能捕捉新的注意力或库存切换。"
mechanism = "结构活跃度代理的一日差分，试图隔离换手和成交笔数强度的加速度，而且不依赖被阻断语义。"
info_boundary = "只使用 verified 结构性成交字段、文件级 instrument key，以及前一个可用 verified 成交日。"
failure_modes = ["变化量可能主要是事件性换手尖峰带来的噪声。", "前一日覆盖稀疏会削弱可比性。", "差分可能只是重新编码事件污染。"]
expected_risks = ["注意力尖峰。", "事件污染。", "流动性 regime shift。"]

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
