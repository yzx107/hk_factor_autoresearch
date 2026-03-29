+++
card_id = "rc_20260329_structural_activity_change_2026"
name = "Structural Activity Change 2026"
owner = "agent"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "30m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["date", "source_file", "Price", "Volume"]
hypothesis = "A sharp day-over-day change in structural activity can capture fresh attention or inventory transitions better than the level itself."
mechanism = "The one-day difference of the structural activity proxy isolates acceleration in turnover and trade-count intensity without relying on blocked semantics."
info_boundary = "Uses only verified structural trade fields, a file-derived instrument key, and the previous available verified trade date."
failure_modes = ["Change is mostly noise from episodic turnover bursts.", "Sparse prior-day coverage weakens comparability.", "The difference only re-encodes event contamination."]
expected_risks = ["Attention spikes.", "Event contamination.", "Liquidity regime shifts."]

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
