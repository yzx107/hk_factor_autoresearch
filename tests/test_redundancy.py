from __future__ import annotations

import unittest

from diagnostics.redundancy import classify_incremental_hint, derive_baseline_metrics, load_baseline_registry


class RedundancyHelpersTest(unittest.TestCase):
    def test_load_baseline_registry_has_expected_defaults(self) -> None:
        registry = load_baseline_registry()
        self.assertIn("structural_activity_proxy", registry["default_baselines"])
        self.assertIn("close_vwap_gap_intensity", registry["default_baselines"])

    def test_derive_baseline_metrics_for_baseline_anchor(self) -> None:
        metrics = derive_baseline_metrics(
            factor_name="structural_activity_proxy",
            comparison_rows=[],
            baseline_factors=["structural_activity_proxy", "avg_trade_notional_bias"],
        )
        self.assertEqual(metrics["baseline_role"], "baseline_anchor")
        self.assertIsNone(metrics["mean_abs_baseline_corr"])

    def test_derive_baseline_metrics_for_challenger(self) -> None:
        comparison_rows = [
            {
                "left_factor": "structural_activity_change",
                "right_factor": "structural_activity_proxy",
                "per_date_corr": [
                    {"date": "2026-01-05", "pearson_corr": 0.8},
                    {"date": "2026-01-06", "pearson_corr": 0.6},
                ],
                "top_overlap": [
                    {"date": "2026-01-05", "top_overlap_count": 9},
                    {"date": "2026-01-06", "top_overlap_count": 11},
                ],
            }
        ]
        metrics = derive_baseline_metrics(
            factor_name="structural_activity_change",
            comparison_rows=comparison_rows,
            baseline_factors=["structural_activity_proxy"],
        )
        self.assertEqual(metrics["baseline_role"], "challenger")
        self.assertEqual(metrics["baseline_peer_count"], 1)
        self.assertAlmostEqual(metrics["mean_abs_baseline_corr"], 0.7)
        self.assertAlmostEqual(metrics["mean_baseline_top_overlap"], 10.0)

    def test_classify_incremental_hint(self) -> None:
        self.assertEqual(
            classify_incremental_hint(
                baseline_role="challenger",
                mean_abs_rank_ic=0.08,
                mean_abs_baseline_corr=0.25,
            ),
            "potential_incremental",
        )
        self.assertEqual(
            classify_incremental_hint(
                baseline_role="challenger",
                mean_abs_rank_ic=0.08,
                mean_abs_baseline_corr=0.9,
            ),
            "likely_redundant",
        )


if __name__ == "__main__":
    unittest.main()
