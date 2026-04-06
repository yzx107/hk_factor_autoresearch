from __future__ import annotations

import unittest

from harness.scoreboard import _render_markdown


class ScoreboardReportTest(unittest.TestCase):
    def test_render_markdown_includes_factor_board(self) -> None:
        payload = {
            "scoreboard_id": "score_x",
            "created_at": "2026-03-29T00:00:00+00:00",
            "factor_count": 1,
            "comparison_count": 0,
            "pre_eval_count": 1,
            "baseline_factors": [],
            "factor_board": [
                {
                    "factor_name": "f1",
                    "factor_family": "activity_pressure",
                    "baseline_role": "challenger",
                    "table_name": "verified_trades",
                    "output_rows": 10,
                    "distinct_instruments": 5,
                    "mean_abs_peer_corr": 0.0,
                    "mean_top_overlap_count": 0.0,
                    "mean_abs_baseline_corr": 0.25,
                    "mean_abs_rank_ic": 0.12,
                    "mean_rank_ic": 0.12,
                    "mean_normalized_mutual_info": 0.03,
                    "mean_nmi": 0.03,
                    "mean_nmi_ic_gap": 0.01,
                    "mi_significant_date_ratio": 1.0,
                    "mean_top_bottom_spread": 0.01,
                    "mean_coverage_ratio": 1.0,
                    "entropy_regime_dispersion": 0.08,
                    "evaluated_dates": ["2026-03-13"],
                    "joined_rows": 10,
                    "incremental_hint": "potential_incremental",
                    "regime_metadata": {"label_mode": "descriptive_only"},
                    "regime_slices": {
                        "entropy_quantile": [
                            {"slice_value": "q1_low_entropy", "mean_abs_rank_ic": 0.12, "mean_nmi": 0.03},
                            {"slice_value": "q3_high_entropy", "mean_abs_rank_ic": 0.04, "mean_nmi": 0.01},
                        ],
                        "year_grade": [
                            {"slice_value": "fine_ok", "mean_abs_rank_ic": 0.12}
                        ]
                    },
                }
            ],
            "comparisons": [],
            "missing_comparisons": [],
        }
        text = _render_markdown(payload)
        self.assertIn("Candidate Scoreboard", text)
        self.assertIn("f1", text)
        self.assertIn("mean_abs_rank_ic", text)
        self.assertIn("mean_nmi", text)
        self.assertIn("entropy_dispersion=`0.0800`", text)
        self.assertIn("incremental_hint=`potential_incremental`", text)
        self.assertIn("nmi_ic_gap=`0.0100`", text)
        self.assertIn("mi_sig_ratio=`1.000`", text)
        self.assertIn("year_grade=`fine_ok:0.1200`", text)
        self.assertIn("entropy_quantile=`q1_low_entropy:ic=0.1200|nmi=0.0300", text)
        self.assertIn("label_mode=`descriptive_only`", text)


if __name__ == "__main__":
    unittest.main()
