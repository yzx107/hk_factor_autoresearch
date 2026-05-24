from __future__ import annotations

import unittest

import polars as pl

from harness.run_layered_pre_eval_batch import (
    add_southbound_bucket,
    classify_layer_response,
    compact_layer_rows,
    latest_materialized_entries,
)


class LayeredPreEvalBatchTest(unittest.TestCase):
    def test_add_southbound_bucket_preserves_unknown_separately_from_false(self) -> None:
        frame = pl.DataFrame(
            {
                "instrument_key": ["00001", "00002", "00003"],
                "southbound_eligible": [True, False, False],
                "southbound_eligible_known": [True, True, False],
                "layer_version": ["v1", "v1", "v1"],
            }
        )

        out = add_southbound_bucket(frame)
        buckets = {row["instrument_key"]: row["southbound_bucket"] for row in out.to_dicts()}

        self.assertEqual(buckets["00001"], "southbound_eligible")
        self.assertEqual(buckets["00002"], "southbound_not_eligible")
        self.assertEqual(buckets["00003"], "southbound_unknown")

    def test_classify_layer_response_identifies_small_illiquid_only_risk(self) -> None:
        rows = [
            {"layer_value": "large_liquid_core", "diagnostic_only": False, "abs_rank_ic": 0.02, "nmi": 0.01},
            {"layer_value": "mid_liquid_tradable", "diagnostic_only": False, "abs_rank_ic": 0.03, "nmi": 0.01},
            {"layer_value": "small_illiquid_special", "diagnostic_only": False, "abs_rank_ic": 0.12, "nmi": 0.02},
        ]

        result = classify_layer_response(rows, min_abs_rank_ic=0.05, min_nmi=0.03)

        self.assertEqual(result["classification"], "small_illiquid_only_risk")
        self.assertEqual(result["strongest_layer"], "small_illiquid_special")

    def test_classify_layer_response_identifies_broad_candidate(self) -> None:
        rows = [
            {"layer_value": "large_liquid_core", "diagnostic_only": False, "abs_rank_ic": 0.06, "nmi": 0.01},
            {"layer_value": "mid_liquid_tradable", "diagnostic_only": False, "abs_rank_ic": 0.07, "nmi": 0.01},
            {"layer_value": "new_or_recent_listing", "diagnostic_only": False, "abs_rank_ic": 0.08, "nmi": 0.01},
        ]

        result = classify_layer_response(rows, min_abs_rank_ic=0.05, min_nmi=0.03)

        self.assertEqual(result["classification"], "broad_candidate")
        self.assertEqual(result["signal_layer_count"], 3)

    def test_classify_layer_response_identifies_dominant_layer_before_broad(self) -> None:
        rows = [
            {"layer_value": "large_liquid_core", "diagnostic_only": False, "abs_rank_ic": 0.05, "nmi": 0.04},
            {"layer_value": "mid_liquid_tradable", "diagnostic_only": False, "abs_rank_ic": 0.08, "nmi": 0.04},
            {"layer_value": "small_illiquid_special", "diagnostic_only": False, "abs_rank_ic": 0.20, "nmi": 0.04},
        ]

        result = classify_layer_response(
            rows,
            min_abs_rank_ic=0.05,
            min_nmi=0.03,
            dispersion_threshold=0.08,
        )

        self.assertEqual(result["classification"], "small_illiquid_dominant_risk")
        self.assertEqual(result["strongest_layer"], "small_illiquid_special")

    def test_compact_layer_rows_keeps_only_board_fields(self) -> None:
        summary = {
            "layers": [
                {
                    "layer_value": "large_liquid_core",
                    "diagnostic_only": False,
                    "instrument_count": 10,
                    "labeled_date_count": 2,
                    "joined_rows": 20,
                    "aggregate_metrics": {
                        "rank_ic": 0.1,
                        "abs_rank_ic": 0.1,
                        "nmi": 0.03,
                        "top_bottom_spread": 0.02,
                    },
                    "per_date": [{"verbose": "omitted"}],
                }
            ]
        }

        rows = compact_layer_rows(summary)

        self.assertEqual(rows[0]["layer_value"], "large_liquid_core")
        self.assertEqual(rows[0]["abs_rank_ic"], 0.1)
        self.assertNotIn("per_date", rows[0])

    def test_latest_materialized_entries_selects_latest_per_factor(self) -> None:
        entries = [
            {"factor_name": "f1", "run_dir": "/tmp/missing", "experiment_id": "old"},
            {"factor_name": "f1", "run_dir": "/tmp/still_missing", "experiment_id": "new"},
        ]

        self.assertEqual(latest_materialized_entries(entries), [])


if __name__ == "__main__":
    unittest.main()
