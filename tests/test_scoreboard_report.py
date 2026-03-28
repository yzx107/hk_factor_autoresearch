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
            "factor_board": [
                {
                    "factor_name": "f1",
                    "table_name": "verified_trades",
                    "output_rows": 10,
                    "distinct_instruments": 5,
                    "mean_abs_peer_corr": 0.0,
                    "mean_top_overlap_count": 0.0,
                }
            ],
            "comparisons": [],
            "missing_comparisons": [],
        }
        text = _render_markdown(payload)
        self.assertIn("Candidate Scoreboard", text)
        self.assertIn("f1", text)


if __name__ == "__main__":
    unittest.main()
