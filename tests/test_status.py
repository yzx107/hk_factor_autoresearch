from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from harness.status import build_status_snapshot, read_experiment_log, read_lineage


class StatusTest(unittest.TestCase):
    def test_snapshot_counts_keep_and_latest_data_run(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            log = tmp / "experiment_log.tsv"
            log.write_text(
                "experiment_id\tcreated_at\towner\tfactor_name\tcard_path\tconfig_version\t"
                "harness_version\tgate_a_decision\tresult_summary\tstatus\t"
                "parent_experiment_id\trun_dir\tnotes\n"
                f"exp1\t2026-03-29T00:00:00+00:00\ttest\tf1\tc1\tcfg\th1\tpass\tok\tkeep\t\t{tmp / 'runs' / 'exp1'}\tfirst\n",
                encoding="utf-8",
            )
            run_dir = tmp / "runs" / "exp1"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "data_run_summary.json").write_text(
                json.dumps(
                    {
                        "factor_name": "f1",
                        "dates": ["2026-03-13"],
                        "output_rows": 10,
                        "table_name": "verified_trades",
                    }
                ),
                encoding="utf-8",
            )
            lineage = tmp / "lineage.json"
            lineage.write_text('{"version":"test","experiments":[{"experiment_id":"exp1"}]}', encoding="utf-8")

            entries = read_experiment_log(log)
            lineage_payload = read_lineage(lineage)
            snapshot = build_status_snapshot(entries)

            self.assertEqual(snapshot.experiment_count, 1)
            self.assertEqual(snapshot.keep_count, 1)
            self.assertEqual(snapshot.latest_data_run["output_rows"], 10)
            self.assertEqual(lineage_payload["version"], "test")


if __name__ == "__main__":
    unittest.main()
