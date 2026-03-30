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
                    "mean_top_bottom_spread": 0.01,
                    "mean_coverage_ratio": 1.0,
                    "evaluated_dates": ["2026-03-13"],
                    "joined_rows": 10,
                    "incremental_hint": "potential_incremental",
                    "regime_slices": {
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
        self.assertIn("incremental_hint=`potential_incremental`", text)
        self.assertIn("year_grade=`fine_ok:0.1200`", text)


if __name__ == "__main__":
    unittest.main()
