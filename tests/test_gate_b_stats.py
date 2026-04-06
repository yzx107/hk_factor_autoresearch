from __future__ import annotations

import unittest

from gates.gate_b_stats import evaluate_gate_b


class GateBStatsTest(unittest.TestCase):
    def test_evaluate_gate_b_passes_strong_consistent_signal(self) -> None:
        payload = evaluate_gate_b(
            {
                "aggregate_metrics": {
                    "rank_ic": 0.12,
                    "abs_rank_ic": 0.12,
                    "nmi": 0.03,
                    "coverage_ratio": 0.95,
                    "top_bottom_spread": 0.02,
                    "nmi_ic_gap": 0.04,
                    "mi_significant_date_ratio": 2.0 / 3.0,
                },
                "per_date": [
                    {"rank_ic": 0.10},
                    {"rank_ic": 0.12},
                    {"rank_ic": 0.14},
                ],
            }
        )

        self.assertEqual(payload["decision"], "pass")
        self.assertEqual(payload["metrics"]["dominant_sign"], "positive")
        self.assertAlmostEqual(payload["metrics"]["sign_consistency"], 1.0)
        self.assertEqual(payload["metrics"]["signal_shape_hint"], "nonlinear_candidate")
        self.assertEqual(payload["direction_hint"], "as_is_candidate")

    def test_evaluate_gate_b_monitors_borderline_signal(self) -> None:
        payload = evaluate_gate_b(
            {
                "mean_rank_ic": -0.05,
                "mean_abs_rank_ic": 0.05,
                "mean_normalized_mutual_info": 0.008,
                "mean_coverage_ratio": 0.82,
                "mean_top_bottom_spread": -0.01,
                "mean_nmi_ic_gap": 0.0,
                "mi_significant_date_ratio": 1.0 / 3.0,
                "per_date": [
                    {"rank_ic": -0.07},
                    {"rank_ic": -0.05},
                    {"rank_ic": 0.01},
                ],
            }
        )

        self.assertEqual(payload["decision"], "monitor")
        self.assertEqual(payload["direction_hint"], "inverse_candidate")
        self.assertIn("below_pass:mean_abs_rank_ic", payload["reasons"])

    def test_evaluate_gate_b_fails_weak_sparse_signal(self) -> None:
        payload = evaluate_gate_b(
            {
                "mean_rank_ic": 0.01,
                "mean_abs_rank_ic": 0.01,
                "mean_normalized_mutual_info": 0.001,
                "mean_coverage_ratio": 0.60,
                "mean_top_bottom_spread": 0.0,
                "mi_significant_date_ratio": 0.0,
                "per_date": [
                    {"rank_ic": 0.02},
                    {"rank_ic": 0.0},
                ],
            }
        )

        self.assertEqual(payload["decision"], "fail")
        self.assertIn("below_monitor:evaluated_date_count", payload["reasons"])
        self.assertIn("below_monitor:mean_abs_rank_ic", payload["reasons"])


if __name__ == "__main__":
    unittest.main()
