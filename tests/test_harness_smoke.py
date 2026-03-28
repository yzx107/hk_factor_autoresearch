from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from harness.run_phase_a import run_experiment

ROOT = Path(__file__).resolve().parents[1]


class HarnessSmokeTest(unittest.TestCase):
    def test_run_experiment_records_pass_card(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            log_path = tmp / "experiment_log.tsv"
            log_path.write_text(
                "experiment_id\tcreated_at\towner\tfactor_name\tcard_path\tconfig_version\t"
                "harness_version\tgate_a_decision\tresult_summary\tstatus\t"
                "parent_experiment_id\trun_dir\tnotes\n",
                encoding="utf-8",
            )
            lineage_path = tmp / "lineage.json"
            lineage_path.write_text('{"version":"test","experiments":[]}', encoding="utf-8")
            record = run_experiment(
                card_path=ROOT / "research_cards/examples/structural_activity_proxy_2026.md",
                factor_name="structural_activity_proxy",
                owner="test",
                notes="",
                parent_experiment_id="",
                log_path=log_path,
                lineage_path=lineage_path,
                run_root=tmp / "runs",
            )
            self.assertEqual(record.gate_a_decision, "pass")
            self.assertEqual(record.status, "keep")
            lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
            self.assertEqual(len(lineage["experiments"]), 1)


if __name__ == "__main__":
    unittest.main()
