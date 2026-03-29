+++
card_id = "rc_20260329_order_lifecycle_churn_change_2026"
name = "Order Lifecycle Churn Change 2026"
owner = "agent"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "30m_to_1d"
research_modules = ["order_lifecycle_shape_by_event_count"]
required_fields = ["date", "source_file", "OrderId", "Price", "Volume"]
hypothesis = "A rising day-over-day change in order lifecycle churn may capture new liquidity contestation more cleanly than the raw churn level."
mechanism = "The one-day difference of the churn proxy isolates acceleration in repeated order activity per unique order without invoking blocked order semantics."
info_boundary = "Uses only verified structural order fields, a file-derived instrument key, and the previous available verified order date."
failure_modes = ["The change collapses into noisy order traffic.", "Coverage is weaker for less active names.", "The effect is still mostly an activity proxy."]
expected_risks = ["Liquidity overlap.", "Coverage loss.", "Turnover regime shifts."]

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
