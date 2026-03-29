+++
card_id = "rc_20260329_avg_trade_notional_bias_change_2026"
name = "Avg Trade Notional Bias Change 2026"
owner = "agent"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "30m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["date", "source_file", "Price", "Volume"]
hypothesis = "A day-over-day change in average trade notional may reveal a fresh shift in participation quality, not just static size exposure."
mechanism = "The one-day difference of log average trade notional isolates acceleration in print size composition using only verified trade structure."
info_boundary = "Uses only verified trade fields, a file-derived instrument key, and the previous available verified trade date."
failure_modes = ["The change is just episodic block-trade noise.", "Prior-day alignment is too sparse for many names.", "Large-cap flow dominates the effect."]
expected_risks = ["Block print contamination.", "Liquidity/style overlap.", "Large-cap concentration."]

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
