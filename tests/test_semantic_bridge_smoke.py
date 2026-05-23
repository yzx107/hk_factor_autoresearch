from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import types
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _install_fake_polars() -> None:
    fake_polars = types.ModuleType("polars")
    fake_polars.DataFrame = object
    fake_polars.String = object()
    sys.modules.setdefault("polars", fake_polars)


class SemanticBridgeSmokeTest(unittest.TestCase):
    def test_semantic_bridge_import(self) -> None:
        _install_fake_polars()

        import harness.semantic_bridge as semantic_bridge

        self.assertTrue(hasattr(semantic_bridge, "evaluate_semantic_gate"))

    def test_append_semantic_gate_log_writes_json_columns(self) -> None:
        _install_fake_polars()

        import harness.semantic_bridge as semantic_bridge

        with TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "semantic_gate_log.tsv"
            semantic_bridge.append_semantic_gate_log(
                scoreboard_id="sb-1",
                factor_name="factor_a",
                family_name="family_a",
                gate_payload={
                    "semantic_gate_status": "semantic_allowed",
                    "semantic_gate_source_loaded": True,
                    "semantic_gate_mapping_source": "explicit_metadata",
                    "semantic_gate_modules": ["signed_flow", "aggressor_side_inference"],
                    "semantic_supported_modules": ["signed_flow"],
                    "semantic_blocked_modules": ["aggressor_side_inference"],
                    "semantic_blocking_areas": ["trade_direction"],
                    "semantic_gate_reason": "ok",
                },
                notes="smoke",
                path=log_path,
            )

            with log_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(json.loads(row["semantic_gate_modules_json"]), ["signed_flow", "aggressor_side_inference"])
        self.assertEqual(json.loads(row["semantic_supported_modules_json"]), ["signed_flow"])
        self.assertEqual(json.loads(row["semantic_blocked_modules_json"]), ["aggressor_side_inference"])
        self.assertEqual(json.loads(row["semantic_blocking_areas_json"]), ["trade_direction"])

    def test_run_semantic_scoreboard_help_works_with_script_entrypoint(self) -> None:
        with TemporaryDirectory() as tmpdir:
            fake_site = Path(tmpdir) / "fake_site"
            fake_site.mkdir()
            (fake_site / "polars.py").write_text(
                "class DataFrame:\n"
                "    def __init__(self, *args, **kwargs):\n"
                "        pass\n"
                "String = object()\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join(
                [str(fake_site), env.get("PYTHONPATH", "")]
            ).strip(os.pathsep)

            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "harness" / "run_semantic_scoreboard.py"), "--help"],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Build a semantic-aware scoreboard from latest factor runs.", result.stdout)


if __name__ == "__main__":
    unittest.main()
