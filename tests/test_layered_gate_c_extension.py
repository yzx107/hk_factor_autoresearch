from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from harness.run_layered_gate_c_extension import (
    annotate_extension_doc,
    load_candidate_config,
    write_extended_decision_rows,
)
import harness.run_layered_gate_c_extension as extension_module


class LayeredGateCExtensionTest(unittest.TestCase):
    def test_load_candidate_config_keeps_module_and_transform(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.toml"
            path.write_text(
                """
[[candidates]]
factor = "level_factor"
card = "research_cards/examples/level.md"

[[candidates]]
factor = "change_factor"
module = "base_factor"
transform = "one_day_difference"
card = "research_cards/examples/base.md"
""".strip(),
                encoding="utf-8",
            )

            config = load_candidate_config(path)

            self.assertEqual(config["level_factor"]["module"], "")
            self.assertEqual(config["level_factor"]["transform"], "level")
            self.assertEqual(config["change_factor"]["module"], "base_factor")
            self.assertEqual(config["change_factor"]["transform"], "one_day_difference")

    def test_write_extended_decision_rows_repoints_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "decisions.tsv"
            write_extended_decision_rows(
                rows=[
                    {
                        "triage_id": "source_triage",
                        "created_at": "old",
                        "factor_name": "factor_a",
                        "primary_decision": "promote_broad_candidate",
                        "run_dir": "/old",
                    }
                ],
                extension_id="extension_1",
                run_dir_by_factor={"factor_a": "/new"},
                path=out,
            )

            lines = out.read_text(encoding="utf-8").strip().splitlines()

            self.assertEqual(len(lines), 2)
            self.assertIn("extension_1", lines[1])
            self.assertIn("/new", lines[1])

    def test_cached_daily_dates_requires_cached_previous_date(self) -> None:
        original_available_dates = extension_module.available_dates
        original_missing_daily = extension_module.missing_daily_agg_dates
        try:
            extension_module.available_dates = lambda table, year: ["2026-01-02", "2026-01-05", "2026-01-06"]
            extension_module.missing_daily_agg_dates = (
                lambda table, dates: ["2026-01-02"] if table == "verified_trades_daily" else []
            )

            dates = extension_module.cached_daily_dates("2026")

            self.assertEqual(dates, ["2026-01-06"])
        finally:
            extension_module.available_dates = original_available_dates
            extension_module.missing_daily_agg_dates = original_missing_daily

    def test_annotate_extension_doc_adds_date_context_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "doc.md"
            path.write_text("- cost_bps: `15.0`\n\n## Decision Counts\n", encoding="utf-8")

            annotate_extension_doc(path, target_dates=["2026-01-05", "2026-01-06"])
            annotate_extension_doc(path, target_dates=["2026-01-05", "2026-01-06"])

            text = path.read_text(encoding="utf-8")
            self.assertEqual(text.count("extension_date_count"), 1)
            self.assertIn("2026-01-05", text)


if __name__ == "__main__":
    unittest.main()
