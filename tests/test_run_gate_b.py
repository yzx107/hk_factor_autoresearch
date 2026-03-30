from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from harness.run_gate_b import run_gate_b_for_factor


class RunGateBTest(unittest.TestCase):
    def test_run_gate_b_for_factor_writes_summary_and_log(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            registry = tmp / "registry"
            runs = tmp / "runs"
            registry.mkdir(parents=True, exist_ok=True)
            runs.mkdir(parents=True, exist_ok=True)

            pre_eval_summary_path = runs / "pre_x" / "pre_eval_summary.json"
            pre_eval_summary_path.parent.mkdir(parents=True, exist_ok=True)
            pre_eval_summary_path.write_text(
                json.dumps(
                    {
                        "pre_eval_id": "pre_x",
                        "factor_name": "demo_factor",
                        "experiment_id": "exp_x",
                        "mean_rank_ic": 0.09,
                        "mean_abs_rank_ic": 0.09,
                        "mean_normalized_mutual_info": 0.02,
                        "mean_coverage_ratio": 0.9,
                        "mean_top_bottom_spread": 0.01,
                        "per_date": [
                            {"rank_ic": 0.08},
                            {"rank_ic": 0.09},
                            {"rank_ic": 0.10},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            pre_eval_log = registry / "pre_eval_log.tsv"
            pre_eval_log.write_text(
                "pre_eval_id\tcreated_at\texperiment_id\tfactor_name\tscore_column\t"
                "label_name\tevaluated_dates\tjoined_rows\tmean_rank_ic\tmean_abs_rank_ic\t"
                "mean_top_bottom_spread\tsummary_path\tnotes\n"
                f"pre_x\t2026-03-30T00:00:00+00:00\texp_x\tdemo_factor\tsignal\t"
                f"forward_return_1d_close_like\t2026-01-05,2026-02-24,2026-03-13\t100\t0.09\t0.09\t"
                f"0.01\t{pre_eval_summary_path}\ttest\n",
                encoding="utf-8",
            )
            gate_b_log = registry / "gate_b_log.tsv"

            gate_b_id, payload, summary_path = run_gate_b_for_factor(
                factor_name="demo_factor",
                pre_eval_log_path=pre_eval_log,
                gate_b_log_path=gate_b_log,
                run_root=runs,
                notes="unit test",
            )

            self.assertTrue(gate_b_id.startswith("gateb_"))
            self.assertEqual(payload["decision"], "pass")
            self.assertTrue(summary_path.exists())
            self.assertTrue(gate_b_log.exists())
            log_text = gate_b_log.read_text(encoding="utf-8")
            self.assertIn("demo_factor", log_text)
            self.assertIn("\tpass\t", log_text)


if __name__ == "__main__":
    unittest.main()
