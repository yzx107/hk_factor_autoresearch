+++
card_id = "rc_20260329_close_vwap_gap_intensity_change_2026"
name = "Close VWAP Gap Intensity Change 2026"
owner = "agent"
status = "draft"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "30m_to_1d"
research_modules = ["matched_edge_session_profile"]
required_fields = ["date", "source_file", "Time", "row_num_in_file", "Price", "Volume"]
hypothesis = "A day-over-day change in close-to-VWAP pressure may signal a fresh shift in end-of-day imbalance rather than a persistent level effect."
mechanism = "The one-day difference of the close-VWAP gap intensity captures acceleration in end-of-day pressure with only verified trade structure."
info_boundary = "Uses only verified trade fields, a file-derived instrument key, and the previous available verified trade date."
failure_modes = ["The change is dominated by one-off close prints.", "The previous-day comparison is unstable around event dates.", "The signal overreacts to reversal noise."]
expected_risks = ["Close print noise.", "Event contamination.", "Short-horizon reversal."]

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
