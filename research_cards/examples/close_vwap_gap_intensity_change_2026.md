+++
card_id = "rc_20260329_close_vwap_gap_intensity_change_2026"
name = "收盘-VWAP 偏离强度变化（Close VWAP Gap Intensity Change 2026）"
owner = "agent"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "30m_to_1d"
research_modules = ["matched_edge_session_profile"]
required_fields = ["date", "source_file", "Time", "row_num_in_file", "Price", "Volume"]
hypothesis = "close-to-VWAP 压力的日间变化，可能代表新的尾盘失衡切换，而不只是持续性的 level 效应。"
mechanism = "对 close-VWAP gap intensity 做一日差分，只用 verified 成交结构来捕捉尾盘压力的加速度。"
info_boundary = "只使用 verified 成交字段、文件级 instrument key，以及前一个可用 verified 成交日。"
failure_modes = ["变化量可能被一次性尾盘成交主导。", "围绕事件日的前一日比较可能不稳定。", "信号可能对反转噪声过度反应。"]
expected_risks = ["尾盘成交噪音。", "事件污染。", "短周期反转。"]

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
