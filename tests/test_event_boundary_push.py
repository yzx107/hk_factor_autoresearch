from __future__ import annotations

from pathlib import Path
import tempfile
import textwrap
import unittest

import polars as pl

from event_boundary_push._core import (
    build_event_cases_frame,
    build_event_review_pack_frame,
    build_event_state_frame,
    build_event_universe_frame,
    load_config,
)


DATES = [
    "2026-01-02",
    "2026-01-05",
    "2026-01-06",
    "2026-01-07",
    "2026-01-08",
    "2026-01-09",
]


class EventBoundaryPushTest(unittest.TestCase):
    def test_event_pipeline_builds_full_path_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cache_root = root / "cache" / "daily_agg"
            output_root = root / "outputs"
            self._write_daily_inputs(cache_root)
            config_path = root / "boundary_push.toml"
            config_path.write_text(
                textwrap.dedent(
                    f"""
                    [inputs]
                    year = "2026"
                    cache_root = "{cache_root}"
                    trade_table = "verified_trades_daily"
                    order_table = "verified_orders_daily"
                    instrument_profile_csv = ""
                    control_feature_csv = ""
                    start_date = ""
                    end_date = ""

                    [universe]
                    max_listing_age_days = 1000
                    min_observed_days = 3
                    size_percentile_min = 0.0
                    size_percentile_max = 1.0
                    require_non_southbound_proxy = false

                    [states]
                    boundary_lookback_days = 3
                    control_lookback_days = 3
                    push_lookback_days = 3
                    control_build_threshold = 0.70
                    control_build_sustain_threshold = 0.65
                    boundary_target_percentile = 0.50
                    boundary_band_width = 0.20
                    push_positive_share_min = 0.66
                    push_return_min = 0.03
                    push_drawdown_floor = -0.05
                    max_gap_sessions = 1

                    [outputs]
                    root = "{output_root}"
                    event_universe = "event_universe.parquet"
                    event_state_daily = "event_state_daily.parquet"
                    event_cases = "event_cases.parquet"
                    event_review_pack = "event_review_pack.csv"
                    review_top_n = 20
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            config = load_config(config_path)
            universe = build_event_universe_frame(config)
            self.assertEqual(universe.filter(pl.col("event_universe_included")).height, 3)

            states = build_event_state_frame(config, universe=universe)
            self.assertGreater(states.filter(pl.col("event_type").is_not_null()).height, 0)

            cases = build_event_cases_frame(config, state_panel=states)
            self.assertGreaterEqual(cases.height, 1)
            self.assertIn("full_path_signal", set(cases["event_type"].to_list()))
            focus_case = cases.filter(pl.col("ticker") == "00001").sort("peak_event_strength", descending=True).row(0, named=True)
            self.assertEqual(focus_case["event_type"], "full_path_signal")
            self.assertGreaterEqual(focus_case["event_day_count"], 1)
            self.assertEqual(focus_case["end_date"], "2026-01-09")

            review = build_event_review_pack_frame(config, cases=cases)
            self.assertGreaterEqual(review.height, 1)
            self.assertIn("annotator", review.columns)
            self.assertEqual(review.row(0, named=True)["ticker"], "00001")


    def test_event_pipeline_handles_empty_universe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cache_root = root / "cache" / "daily_agg"
            output_root = root / "outputs"
            self._write_daily_inputs(cache_root)
            config_path = root / "boundary_push_empty_universe.toml"
            config_path.write_text(
                textwrap.dedent(
                    f"""
                    [inputs]
                    year = "2026"
                    cache_root = "{cache_root}"
                    trade_table = "verified_trades_daily"
                    order_table = "verified_orders_daily"
                    instrument_profile_csv = ""
                    control_feature_csv = ""
                    start_date = ""
                    end_date = ""

                    [universe]
                    max_listing_age_days = 1000
                    min_observed_days = 99
                    size_percentile_min = 0.0
                    size_percentile_max = 1.0
                    require_non_southbound_proxy = false

                    [states]
                    boundary_lookback_days = 3
                    control_lookback_days = 3
                    push_lookback_days = 3
                    control_build_threshold = 0.70
                    control_build_sustain_threshold = 0.65
                    boundary_target_percentile = 0.50
                    boundary_band_width = 0.20
                    push_positive_share_min = 0.66
                    push_return_min = 0.03
                    push_drawdown_floor = -0.05
                    max_gap_sessions = 1

                    [outputs]
                    root = "{output_root}"
                    event_universe = "event_universe.parquet"
                    event_state_daily = "event_state_daily.parquet"
                    event_cases = "event_cases.parquet"
                    event_review_pack = "event_review_pack.csv"
                    review_top_n = 20
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            config = load_config(config_path)
            universe = build_event_universe_frame(config)
            self.assertEqual(universe.filter(pl.col("event_universe_included")).height, 0)

            states = build_event_state_frame(config, universe=universe)
            self.assertEqual(states.height, 0)
            self.assertIn("event_type", states.columns)

            cases = build_event_cases_frame(config, state_panel=states)
            self.assertEqual(cases.height, 0)
            self.assertIn("event_id", cases.columns)

            review = build_event_review_pack_frame(config, cases=cases)
            self.assertEqual(review.height, 0)
            self.assertIn("annotator", review.columns)

    def test_event_pipeline_one_day_input_produces_no_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cache_root = root / "cache" / "daily_agg"
            output_root = root / "outputs"
            self._write_daily_inputs(cache_root)
            config_path = root / "boundary_push_one_day.toml"
            config_path.write_text(
                textwrap.dedent(
                    f"""
                    [inputs]
                    year = "2026"
                    cache_root = "{cache_root}"
                    trade_table = "verified_trades_daily"
                    order_table = "verified_orders_daily"
                    instrument_profile_csv = ""
                    control_feature_csv = ""
                    start_date = "2026-01-02"
                    end_date = "2026-01-02"

                    [universe]
                    max_listing_age_days = 1000
                    min_observed_days = 1
                    size_percentile_min = 0.0
                    size_percentile_max = 1.0
                    require_non_southbound_proxy = false

                    [states]
                    boundary_lookback_days = 3
                    control_lookback_days = 3
                    push_lookback_days = 3
                    control_build_threshold = 0.70
                    control_build_sustain_threshold = 0.65
                    boundary_target_percentile = 0.50
                    boundary_band_width = 0.20
                    push_positive_share_min = 0.66
                    push_return_min = 0.03
                    push_drawdown_floor = -0.05
                    max_gap_sessions = 1

                    [outputs]
                    root = "{output_root}"
                    event_universe = "event_universe.parquet"
                    event_state_daily = "event_state_daily.parquet"
                    event_cases = "event_cases.parquet"
                    event_review_pack = "event_review_pack.csv"
                    review_top_n = 20
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            config = load_config(config_path)
            universe = build_event_universe_frame(config)
            self.assertEqual(universe.filter(pl.col("event_universe_included")).height, 3)

            states = build_event_state_frame(config, universe=universe)
            self.assertEqual(states.height, 3)
            self.assertEqual(states.filter(pl.col("event_type").is_not_null()).height, 0)

            cases = build_event_cases_frame(config, state_panel=states)
            self.assertEqual(cases.height, 0)

    def test_event_pipeline_raises_when_no_overlapping_partitions_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cache_root = root / "cache" / "daily_agg"
            output_root = root / "outputs"
            config_path = root / "boundary_push_missing_inputs.toml"
            config_path.write_text(
                textwrap.dedent(
                    f"""
                    [inputs]
                    year = "2026"
                    cache_root = "{cache_root}"
                    trade_table = "verified_trades_daily"
                    order_table = "verified_orders_daily"
                    instrument_profile_csv = ""
                    control_feature_csv = ""
                    start_date = ""
                    end_date = ""

                    [universe]
                    max_listing_age_days = 1000
                    min_observed_days = 1
                    size_percentile_min = 0.0
                    size_percentile_max = 1.0
                    require_non_southbound_proxy = false

                    [states]
                    boundary_lookback_days = 3
                    control_lookback_days = 3
                    push_lookback_days = 3
                    control_build_threshold = 0.70
                    control_build_sustain_threshold = 0.65
                    boundary_target_percentile = 0.50
                    boundary_band_width = 0.20
                    push_positive_share_min = 0.66
                    push_return_min = 0.03
                    push_drawdown_floor = -0.05
                    max_gap_sessions = 1

                    [outputs]
                    root = "{output_root}"
                    event_universe = "event_universe.parquet"
                    event_state_daily = "event_state_daily.parquet"
                    event_cases = "event_cases.parquet"
                    event_review_pack = "event_review_pack.csv"
                    review_top_n = 20
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            config = load_config(config_path)
            with self.assertRaises(FileNotFoundError):
                build_event_universe_frame(config)
    def _write_daily_inputs(self, cache_root: Path) -> None:
        trade_rows = {
            "00001": {
                "trade_count": [50, 55, 55, 60, 60, 65],
                "turnover": [100, 110, 120, 130, 140, 150],
                "share_volume": [10, 10, 10, 10, 10, 10],
                "avg_trade_size": [2.0, 2.0, 2.2, 2.2, 2.3, 2.3],
                "close_like_price": [10.0, 10.2, 10.5, 10.8, 11.0, 11.2],
                "vwap": [9.95, 10.0, 10.3, 10.55, 10.8, 10.95],
            },
            "00002": {
                "trade_count": [30, 30, 30, 32, 32, 34],
                "turnover": [60, 58, 57, 59, 58, 57],
                "share_volume": [12, 12, 12, 12, 12, 12],
                "avg_trade_size": [1.2, 1.2, 1.2, 1.3, 1.3, 1.3],
                "close_like_price": [5.0, 4.98, 4.97, 4.99, 5.0, 5.01],
                "vwap": [5.0, 4.99, 4.98, 4.98, 4.99, 5.0],
            },
            "00003": {
                "trade_count": [80, 82, 84, 84, 86, 88],
                "turnover": [200, 205, 210, 212, 215, 218],
                "share_volume": [20, 20, 20, 20, 20, 20],
                "avg_trade_size": [2.5, 2.5, 2.5, 2.5, 2.5, 2.5],
                "close_like_price": [15.0, 15.02, 15.03, 15.05, 15.04, 15.06],
                "vwap": [14.98, 15.0, 15.01, 15.02, 15.02, 15.03],
            },
        }
        order_rows = {
            "00001": {
                "order_event_count": [80, 90, 100, 110, 120, 130],
                "unique_order_ids": [18, 18, 19, 20, 20, 21],
                "total_order_notional": [160, 180, 205, 230, 255, 280],
                "churn_ratio": [3.5, 4.0, 4.5, 5.0, 5.3, 5.6],
            },
            "00002": {
                "order_event_count": [18, 18, 17, 18, 18, 18],
                "unique_order_ids": [10, 10, 10, 10, 10, 10],
                "total_order_notional": [40, 39, 38, 39, 39, 40],
                "churn_ratio": [1.0, 1.0, 0.9, 1.0, 1.0, 1.0],
            },
            "00003": {
                "order_event_count": [40, 40, 41, 41, 42, 42],
                "unique_order_ids": [22, 22, 22, 22, 23, 23],
                "total_order_notional": [180, 182, 184, 185, 186, 188],
                "churn_ratio": [1.8, 1.8, 1.8, 1.8, 1.9, 1.9],
            },
        }

        for idx, date in enumerate(DATES):
            trade_frame = pl.DataFrame(
                {
                    "date": [date, date, date],
                    "instrument_key": ["00001", "00002", "00003"],
                    "trade_count": [trade_rows[key]["trade_count"][idx] for key in ["00001", "00002", "00003"]],
                    "turnover": [trade_rows[key]["turnover"][idx] for key in ["00001", "00002", "00003"]],
                    "share_volume": [trade_rows[key]["share_volume"][idx] for key in ["00001", "00002", "00003"]],
                    "avg_trade_size": [trade_rows[key]["avg_trade_size"][idx] for key in ["00001", "00002", "00003"]],
                    "close_like_price": [trade_rows[key]["close_like_price"][idx] for key in ["00001", "00002", "00003"]],
                    "vwap": [trade_rows[key]["vwap"][idx] for key in ["00001", "00002", "00003"]],
                    "instrument_key_source": ["source_file_proxy", "source_file_proxy", "source_file_proxy"],
                }
            ).with_columns(pl.col("date").str.to_date())
            order_frame = pl.DataFrame(
                {
                    "date": [date, date, date],
                    "instrument_key": ["00001", "00002", "00003"],
                    "order_event_count": [order_rows[key]["order_event_count"][idx] for key in ["00001", "00002", "00003"]],
                    "unique_order_ids": [order_rows[key]["unique_order_ids"][idx] for key in ["00001", "00002", "00003"]],
                    "total_order_notional": [order_rows[key]["total_order_notional"][idx] for key in ["00001", "00002", "00003"]],
                    "churn_ratio": [order_rows[key]["churn_ratio"][idx] for key in ["00001", "00002", "00003"]],
                }
            ).with_columns(pl.col("date").str.to_date())

            trade_path = cache_root / "verified_trades_daily" / "year=2026" / f"date={date}" / "part-00000.parquet"
            order_path = cache_root / "verified_orders_daily" / "year=2026" / f"date={date}" / "part-00000.parquet"
            trade_path.parent.mkdir(parents=True, exist_ok=True)
            order_path.parent.mkdir(parents=True, exist_ok=True)
            trade_frame.write_parquet(trade_path)
            order_frame.write_parquet(order_path)


if __name__ == "__main__":
    unittest.main()
