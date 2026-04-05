from __future__ import annotations

from pathlib import Path
import tempfile
import textwrap
import unittest

import polars as pl

from event_boundary_push._core import build_event_state_frame, build_event_universe_frame, load_config


DATES = ["2026-01-02", "2026-01-05", "2026-01-06"]


class EventBoundaryPushProfileTest(unittest.TestCase):
    def test_event_pipeline_prefers_instrument_profile_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cache_root = root / "cache" / "daily_agg"
            output_root = root / "outputs"
            profile_path = root / "instrument_profile.csv"
            self._write_daily_inputs(cache_root)
            profile_path.write_text(
                "instrument_key,ticker,listing_date,float_mktcap,southbound_eligible\n"
                "00001,00001,2025-06-01,100000000.0,false\n"
                "00002,00002,2025-07-15,200000000.0,true\n",
                encoding="utf-8",
            )
            config_path = root / "boundary_push_profile.toml"
            config_path.write_text(
                textwrap.dedent(
                    f"""
                    [inputs]
                    year = "2026"
                    cache_root = "{cache_root}"
                    trade_table = "verified_trades_daily"
                    order_table = "verified_orders_daily"
                    instrument_profile_csv = "{profile_path}"
                    control_feature_csv = ""
                    start_date = ""
                    end_date = ""

                    [universe]
                    max_listing_age_days = 1000
                    min_observed_days = 2
                    size_percentile_min = 0.0
                    size_percentile_max = 1.0
                    require_non_southbound_proxy = true

                    [states]
                    boundary_lookback_days = 2
                    control_lookback_days = 2
                    push_lookback_days = 2
                    control_build_threshold = 0.70
                    control_build_sustain_threshold = 0.65
                    control_event_ratio_weight = 0.30
                    control_notional_ratio_weight = 0.50
                    control_churn_weight = 0.20
                    control_broker_blend_weight = 0.25
                    boundary_target_percentile = 0.50
                    boundary_band_width = 0.30
                    push_positive_share_min = 0.50
                    push_return_min = 0.00
                    push_drawdown_floor = -0.20
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
            row_1 = universe.filter(pl.col("instrument_key") == "00001").row(0, named=True)
            row_2 = universe.filter(pl.col("instrument_key") == "00002").row(0, named=True)
            self.assertEqual(row_1["listing_date_source"], "instrument_profile")
            self.assertEqual(row_1["boundary_proxy_source"], "float_mktcap_effective")
            self.assertEqual(row_1["southbound_source"], "instrument_profile")
            self.assertTrue(row_1["event_universe_included"])
            self.assertFalse(row_2["event_universe_included"])

            states = build_event_state_frame(config, universe=universe)
            self.assertEqual(set(states["instrument_key"].to_list()), {"00001"})
            self.assertEqual(set(states["boundary_proxy_source"].drop_nulls().to_list()), {"float_mktcap_effective"})
            self.assertEqual(set(states["listing_date_source"].drop_nulls().to_list()), {"instrument_profile"})

    def _write_daily_inputs(self, cache_root: Path) -> None:
        trade_rows = {
            "00001": {
                "trade_count": [10, 11, 12],
                "turnover": [1000.0, 1200.0, 1500.0],
                "share_volume": [10000, 10000, 10000],
                "avg_trade_size": [1000.0, 1090.9, 1250.0],
                "close_like_price": [10.0, 10.5, 11.0],
                "vwap": [9.9, 10.2, 10.7],
            },
            "00002": {
                "trade_count": [8, 8, 8],
                "turnover": [900.0, 910.0, 920.0],
                "share_volume": [9000, 9000, 9000],
                "avg_trade_size": [1000.0, 1000.0, 1000.0],
                "close_like_price": [9.0, 9.1, 9.2],
                "vwap": [9.0, 9.05, 9.1],
            },
        }
        order_rows = {
            "00001": {
                "order_event_count": [20, 24, 28],
                "unique_order_ids": [10, 11, 12],
                "total_order_notional": [2000.0, 2400.0, 3000.0],
                "churn_ratio": [2.0, 2.1, 2.2],
            },
            "00002": {
                "order_event_count": [10, 10, 10],
                "unique_order_ids": [8, 8, 8],
                "total_order_notional": [1000.0, 1010.0, 1020.0],
                "churn_ratio": [1.2, 1.2, 1.2],
            },
        }
        for idx, date in enumerate(DATES):
            trade_frame = pl.DataFrame(
                {
                    "date": [date, date],
                    "instrument_key": ["00001", "00002"],
                    "trade_count": [trade_rows[key]["trade_count"][idx] for key in ["00001", "00002"]],
                    "turnover": [trade_rows[key]["turnover"][idx] for key in ["00001", "00002"]],
                    "share_volume": [trade_rows[key]["share_volume"][idx] for key in ["00001", "00002"]],
                    "avg_trade_size": [trade_rows[key]["avg_trade_size"][idx] for key in ["00001", "00002"]],
                    "close_like_price": [trade_rows[key]["close_like_price"][idx] for key in ["00001", "00002"]],
                    "vwap": [trade_rows[key]["vwap"][idx] for key in ["00001", "00002"]],
                    "instrument_key_source": ["source_file_proxy", "source_file_proxy"],
                }
            ).with_columns(pl.col("date").str.to_date())
            order_frame = pl.DataFrame(
                {
                    "date": [date, date],
                    "instrument_key": ["00001", "00002"],
                    "order_event_count": [order_rows[key]["order_event_count"][idx] for key in ["00001", "00002"]],
                    "unique_order_ids": [order_rows[key]["unique_order_ids"][idx] for key in ["00001", "00002"]],
                    "total_order_notional": [order_rows[key]["total_order_notional"][idx] for key in ["00001", "00002"]],
                    "churn_ratio": [order_rows[key]["churn_ratio"][idx] for key in ["00001", "00002"]],
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
