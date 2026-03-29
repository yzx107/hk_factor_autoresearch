+++
card_id = "rc_20260329_order_lifecycle_churn_change_2026"
name = "订单生命周期 churn 变化（Order Lifecycle Churn Change 2026）"
owner = "agent"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "30m_to_1d"
research_modules = ["order_lifecycle_shape_by_event_count"]
required_fields = ["date", "source_file", "OrderId", "Price", "Volume"]
hypothesis = "订单生命周期 churn 的上升变化，可能比原始 churn level 更干净地捕捉新的流动性争夺。"
mechanism = "对 churn proxy 做一日差分，试图隔离每个唯一订单对应的重复活动加速度，而不调用被阻断的订单语义。"
info_boundary = "只使用 verified 结构性委托字段、文件级 instrument key，以及前一个可用 verified 委托日。"
failure_modes = ["变化量可能退化成带噪音的订单流量。", "不活跃标的的覆盖更弱。", "效应仍然可能主要只是活跃度代理。"]
expected_risks = ["与流动性重叠。", "覆盖损失。", "换手 regime shift。"]

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
