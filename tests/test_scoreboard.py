from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from harness.scoreboard import _pre_eval_row


class ScoreboardTest(unittest.TestCase):
    def test_scoreboard_payload_shape(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            payload = {
                "scoreboard_id": "score_x",
                "factor_count": 2,
                "comparison_count": 1,
                "missing_comparisons": [],
            }
            path = tmp / "scoreboard_summary.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["factor_count"], 2)
            self.assertEqual(loaded["comparison_count"], 1)

    def test_pre_eval_row_prefers_aggregate_metrics_and_entropy_slice_summary(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            summary_path = tmp / "pre_eval_summary.json"
            summary_path.write_text(
                json.dumps(
                    {
                        "label_name": "forward_return_1d_close_like",
                        "labeled_dates": ["2026-03-13"],
                        "skipped_dates": [],
                        "joined_rows": 10,
                        "aggregate_metrics": {
                            "rank_ic": 0.02,
                            "abs_rank_ic": 0.12,
                            "mi": 0.01,
                            "nmi": 0.03,
                            "top_bottom_spread": 0.01,
                            "coverage_ratio": 1.0,
                        },
                        "mean_rank_ic": 999.0,
                        "mean_abs_rank_ic": 999.0,
                        "mean_mutual_info": 999.0,
                        "mean_normalized_mutual_info": 999.0,
                        "mean_top_bottom_spread": 999.0,
                        "mean_coverage_ratio": 999.0,
                        "regime_slices": {
                            "entropy_quantile": [
                                {"slice_value": "q1_low_entropy", "mean_abs_rank_ic": 0.12, "mean_nmi": 0.03},
                                {"slice_value": "q3_high_entropy", "mean_abs_rank_ic": 0.04, "mean_nmi": 0.01},
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            row = _pre_eval_row(
                {
                    "pre_eval_id": "pre_x",
                    "experiment_id": "exp_x",
                    "factor_name": "f1",
                    "summary_path": str(summary_path),
                }
            )
            assert row is not None
            self.assertAlmostEqual(row["mean_nmi"], 0.03)
            self.assertAlmostEqual(row["mean_abs_rank_ic"], 0.12)
            self.assertAlmostEqual(row["entropy_regime_dispersion"], 0.08)
            self.assertEqual(row["entropy_regime_strongest_slice"], "q1_low_entropy")


if __name__ == "__main__":
    unittest.main()
