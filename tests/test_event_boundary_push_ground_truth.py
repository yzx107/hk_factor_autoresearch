from __future__ import annotations

from pathlib import Path
import tempfile
import textwrap
import unittest

import polars as pl

from event_boundary_push._ground_truth import build_ground_truth_matches_frame, load_ground_truth_config


class EventBoundaryPushGroundTruthTest(unittest.TestCase):
    def test_ground_truth_validation_matches_best_case_and_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            event_config_path = root / "event.toml"
            validation_config_path = root / "validation.toml"
            ground_truth_path = root / "truth.csv"

            event_config_path.write_text(
                textwrap.dedent(
                    """
                    [inputs]
                    year = "2026"
                    cache_root = "cache/daily_agg"
                    trade_table = "verified_trades_daily"
                    order_table = "verified_orders_daily"
                    instrument_profile_csv = ""
                    control_feature_csv = ""
                    start_date = ""
                    end_date = ""

                    [universe]
                    max_listing_age_days = 730
                    min_observed_days = 20
                    size_percentile_min = 0.10
                    size_percentile_max = 0.80
                    require_non_southbound_proxy = true

                    [states]
                    boundary_lookback_days = 10
                    control_lookback_days = 10
                    push_lookback_days = 10
                    control_build_threshold = 0.85
                    control_build_sustain_threshold = 0.78
                    control_event_ratio_weight = 0.30
                    control_notional_ratio_weight = 0.50
                    control_churn_weight = 0.20
                    control_broker_blend_weight = 0.25
                    boundary_target_percentile = 0.85
                    boundary_band_width = 0.04
                    push_positive_share_min = 0.70
                    push_return_min = 0.08
                    push_drawdown_floor = -0.06
                    max_gap_sessions = 2

                    [outputs]
                    root = "event_boundary_push/outputs"
                    event_universe = "event_universe.parquet"
                    event_state_daily = "event_state_daily.parquet"
                    event_cases = "event_cases.parquet"
                    event_review_pack = "event_review_pack.csv"
                    review_top_n = 80
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            validation_config_path.write_text(
                textwrap.dedent(
                    f"""
                    [inputs]
                    event_config = "{event_config_path}"
                    ground_truth_csv = "{ground_truth_path}"

                    [matching]
                    lookback_days = 30
                    lag_tolerance_days = 0
                    include_event_types = [
                      "full_path_signal",
                      "boundary_control_setup",
                      "control_push",
                      "boundary_push",
                    ]

                    [outputs]
                    root = "{root / 'validation_outputs'}"
                    matches = "matches.parquet"
                    noise_cases = "noise.parquet"
                    summary = "summary.json"
                    max_noise_cases = 10
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            ground_truth_path.write_text(
                "truth_id,ticker,instrument_key,inclusion_date,event_label,source,notes\n"
                "truth_1,00001,00001,2026-03-15,southbound_inclusion,test,expected to match\n"
                "truth_2,00002,00002,2026-03-15,southbound_inclusion,test,expected to miss\n",
                encoding="utf-8",
            )

            config = load_ground_truth_config(validation_config_path)
            cases = pl.DataFrame(
                {
                    "event_id": [
                        "00001__boundary_push__2026-03-01__2026-03-10",
                        "00001__full_path_signal__2026-03-11__2026-03-14",
                        "00003__control_push__2026-03-12__2026-03-15",
                    ],
                    "instrument_key": ["00001", "00001", "00003"],
                    "ticker": ["00001", "00001", "00003"],
                    "event_type": ["boundary_push", "full_path_signal", "control_push"],
                    "start_date": ["2026-03-01", "2026-03-11", "2026-03-12"],
                    "end_date": ["2026-03-10", "2026-03-14", "2026-03-15"],
                    "event_day_count": [4, 3, 2],
                    "peak_event_strength": [0.42, 0.88, 0.55],
                    "price_return_during_event": [0.12, 0.24, 0.08],
                }
            ).with_columns([pl.col("start_date").str.to_date(), pl.col("end_date").str.to_date()])

            matches, noise_cases = build_ground_truth_matches_frame(config, cases=cases)
            self.assertEqual(matches.height, 2)
            matched = matches.filter(pl.col("truth_id") == "truth_1").row(0, named=True)
            self.assertTrue(matched["matched"])
            self.assertEqual(matched["best_event_type"], "full_path_signal")
            self.assertEqual(matched["lead_days_from_end"], 1)
            missed = matches.filter(pl.col("truth_id") == "truth_2").row(0, named=True)
            self.assertFalse(missed["matched"])
            self.assertEqual(noise_cases.height, 1)
            self.assertEqual(noise_cases.row(0, named=True)["ticker"], "00003")


if __name__ == "__main__":
    unittest.main()
