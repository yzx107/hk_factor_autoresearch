from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import polars as pl

from harness.build_universe_layers import (
    build_liquidity_proxy_frame,
    build_universe_layer_frame,
    load_layer_config,
    summarize_universe_layers,
)


def _config() -> dict[str, object]:
    return {
        "version": "universe_layers_phase_a_v1",
        "target_instrument_universe": "stock_research_candidate",
        "thresholds": {
            "early_listing_days": 90,
            "recent_listing_days": 365,
            "large_liquidity_quantile": 0.80,
            "small_liquidity_quantile": 0.30,
            "min_observed_trades_days": 2,
            "min_observed_orders_days": 2,
        },
        "liquidity": {"min_liquidity_days": 2},
    }


class UniverseLayerTest(unittest.TestCase):
    def test_build_liquidity_proxy_frame_aggregates_daily_turnover(self) -> None:
        daily = pl.DataFrame(
            {
                "date": ["2026-03-13", "2026-03-14", "2026-03-13"],
                "instrument_key": ["00001", "00001", "00002"],
                "turnover": [100.0, 300.0, 50.0],
                "share_volume": [10.0, 30.0, 5.0],
                "trade_count": [2.0, 4.0, 1.0],
            }
        )

        out = build_liquidity_proxy_frame(daily)
        rows = {row["instrument_key"]: row for row in out.to_dicts()}

        self.assertEqual(rows["00001"]["active_liquidity_days"], 2)
        self.assertAlmostEqual(rows["00001"]["avg_daily_turnover_hkd"], 200.0)
        self.assertAlmostEqual(rows["00001"]["avg_daily_share_volume"], 20.0)

    def test_build_universe_layer_frame_assigns_primary_layers(self) -> None:
        profile = pl.DataFrame(
            {
                "instrument_key": ["00001", "00002", "00003", "00004", "ETF01"],
                "as_of_date": ["2026-05-25"] * 5,
                "listing_date": ["2020-01-01", "2020-01-01", "2026-03-01", "2020-01-01", "2020-01-01"],
                "float_mktcap_hkd": [None, None, None, None, None],
                "circulating_mktcap_hkd": [1000.0, 500.0, 100.0, 10.0, 999.0],
                "southbound_eligible": [True, False, False, False, False],
                "observed_trades_days": [10, 10, 10, 1, 10],
                "observed_orders_days": [10, 10, 10, 1, 10],
                "instrument_family": ["equity"] * 5,
                "stock_research_candidate": [True, True, True, True, False],
            }
        )
        liquidity = pl.DataFrame(
            {
                "date": ["2026-03-13", "2026-03-14"] * 4,
                "instrument_key": ["00001", "00001", "00002", "00002", "00003", "00003", "00004", "00004"],
                "turnover": [1000.0, 1000.0, 500.0, 500.0, 100.0, 100.0, 10.0, 10.0],
                "share_volume": [1.0] * 8,
                "trade_count": [1.0] * 8,
            }
        )

        frame, diagnostics = build_universe_layer_frame(
            profile,
            year="2026",
            config=_config(),
            liquidity=liquidity,
            source_trace={"unit": "test"},
        )
        rows = {row["instrument_key"]: row for row in frame.to_dicts()}

        self.assertNotIn("ETF01", rows)
        self.assertEqual(rows["00001"]["primary_tradability_layer"], "large_liquid_core")
        self.assertEqual(rows["00002"]["primary_tradability_layer"], "mid_liquid_tradable")
        self.assertEqual(rows["00003"]["primary_tradability_layer"], "new_or_recent_listing")
        self.assertEqual(rows["00004"]["primary_tradability_layer"], "small_illiquid_special")
        self.assertTrue(rows["00001"]["southbound_eligible"])
        self.assertTrue(rows["00001"]["southbound_eligible_known"])
        self.assertEqual(rows["00001"]["size_proxy_source"], "circulating_mktcap_hkd")
        self.assertTrue(rows["00004"]["legacy_illiquid_risk_proxy"])
        self.assertFalse(rows["00001"]["top_of_book_bounded_ready"])
        self.assertEqual(diagnostics["liquidity_input_rows"], 8)

    def test_build_universe_layer_frame_fails_closed_when_liquidity_is_missing(self) -> None:
        profile = pl.DataFrame(
            {
                "instrument_key": ["00001"],
                "as_of_date": ["2026-05-25"],
                "listing_date": ["2020-01-01"],
                "stock_research_candidate": [True],
                "observed_trades_days": [10],
                "observed_orders_days": [10],
            }
        )

        frame, _ = build_universe_layer_frame(profile, year="2026", config=_config())
        row = frame.to_dicts()[0]

        self.assertEqual(row["primary_tradability_layer"], "unknown")
        self.assertEqual(row["liquidity_proxy_source"], "missing")
        self.assertFalse(row["southbound_eligible_known"])
        self.assertEqual(row["southbound_active_proxy"], "source_missing")
        self.assertEqual(row["index_flow_bucket"], "source_missing")

    def test_southbound_complete_seed_marks_absent_candidates_known_false(self) -> None:
        profile = pl.DataFrame(
            {
                "instrument_key": ["00001", "00002"],
                "as_of_date": ["2026-05-25", "2026-05-25"],
                "listing_date": ["2020-01-01", "2020-01-01"],
                "circulating_mktcap_hkd": [1000.0, 500.0],
                "stock_research_candidate": [True, True],
                "observed_trades_days": [10, 10],
                "observed_orders_days": [10, 10],
            }
        )
        seed = pl.DataFrame(
            {
                "instrument_key": ["00001"],
                "southbound_eligible": [True],
                "as_of_date": ["2026-05-22"],
                "source_label": ["fixture_full_list"],
            }
        )
        config = {
            **_config(),
            "southbound": {
                "complete_eligible_list_absence_means_false": True,
                "absence_source_label": "fixture_absence_not_eligible",
            },
        }

        frame, diagnostics = build_universe_layer_frame(
            profile,
            year="2026",
            config=config,
            southbound_seed=seed,
        )
        rows = {row["instrument_key"]: row for row in frame.to_dicts()}

        self.assertTrue(rows["00001"]["southbound_eligible"])
        self.assertFalse(rows["00002"]["southbound_eligible"])
        self.assertTrue(rows["00002"]["southbound_eligible_known"])
        self.assertEqual(rows["00002"]["southbound_source_label"], "fixture_absence_not_eligible")
        self.assertEqual(diagnostics["southbound_seed_rows"], 1)

    def test_summarize_universe_layers_reports_layer_and_missing_counts(self) -> None:
        profile = pl.DataFrame(
            {
                "instrument_key": ["00001"],
                "as_of_date": ["2026-05-25"],
                "listing_date": ["2026-03-01"],
                "stock_research_candidate": [True],
                "observed_trades_days": [10],
                "observed_orders_days": [10],
            }
        )
        frame, diagnostics = build_universe_layer_frame(profile, year="2026", config=_config())
        summary = summarize_universe_layers(
            frame,
            year="2026",
            config=_config(),
            source_paths={"instrument_profile": "unit"},
            diagnostics=diagnostics,
        )

        self.assertEqual(summary["row_count"], 1)
        self.assertEqual(summary["coverage_by_layer"]["new_or_recent_listing"], 1)
        self.assertEqual(summary["unknown_counts"]["liquidity_proxy_missing"], 1)
        self.assertEqual(summary["unknown_counts"]["size_proxy_missing"], 1)
        self.assertEqual(summary["unknown_counts"]["southbound_eligible_unknown"], 1)

    def test_build_universe_layer_frame_uses_reference_market_cap_when_liquidity_is_missing(self) -> None:
        profile = pl.DataFrame(
            {
                "instrument_key": ["00001", "00002", "00003"],
                "as_of_date": ["2026-05-25"] * 3,
                "listing_date": ["2020-01-01"] * 3,
                "circulating_mktcap_hkd": [1000.0, 500.0, 100.0],
                "stock_research_candidate": [True, True, True],
                "observed_trades_days": [10, 10, 10],
                "observed_orders_days": [10, 10, 10],
            }
        )

        frame, diagnostics = build_universe_layer_frame(profile, year="2026", config=_config())
        rows = {row["instrument_key"]: row for row in frame.to_dicts()}

        self.assertEqual(rows["00001"]["primary_tradability_layer"], "large_liquid_core")
        self.assertEqual(rows["00002"]["primary_tradability_layer"], "mid_liquid_tradable")
        self.assertEqual(rows["00003"]["primary_tradability_layer"], "small_illiquid_special")
        self.assertEqual(rows["00001"]["size_proxy_source"], "circulating_mktcap_hkd")
        self.assertEqual(rows["00001"]["liquidity_proxy_source"], "missing")
        self.assertIsNotNone(diagnostics["large_liquidity_cutoff"])

    def test_load_layer_config_requires_stock_candidate_target(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.toml"
            path.write_text(
                'version = "x"\n'
                'target_instrument_universe = "all"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "stock_research_candidate"):
                load_layer_config(path)


if __name__ == "__main__":
    unittest.main()
