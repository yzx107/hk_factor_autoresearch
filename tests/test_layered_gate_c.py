from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import polars as pl

from harness.run_layered_gate_c import (
    build_layered_gate_c_summary,
    _decide_gate_c,
    select_gate_c_candidates,
)


class LayeredGateCTest(unittest.TestCase):
    def test_select_gate_c_candidates_uses_latest_triage_and_promoted_only(self) -> None:
        rows = [
            {
                "triage_id": "old",
                "created_at": "2026-01-01T00:00:00+00:00",
                "factor_name": "old_factor",
                "primary_decision": "promote_broad_candidate",
            },
            {
                "triage_id": "new",
                "created_at": "2026-01-02T00:00:00+00:00",
                "factor_name": "new_factor",
                "primary_decision": "promote_broad_candidate",
            },
            {
                "triage_id": "new",
                "created_at": "2026-01-02T00:00:00+00:00",
                "factor_name": "watch_factor",
                "primary_decision": "research_new_listing_family",
            },
        ]

        selected = select_gate_c_candidates(rows)

        self.assertEqual([row["factor_name"] for row in selected], ["new_factor"])

    def test_build_layered_gate_c_summary_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_dir = tmp / "factor_run"
            run_dir.mkdir(parents=True)
            factor = pl.DataFrame(
                {
                    "date": [
                        "2026-01-02",
                        "2026-01-02",
                        "2026-01-02",
                        "2026-01-02",
                        "2026-01-03",
                        "2026-01-03",
                        "2026-01-03",
                        "2026-01-03",
                    ],
                    "instrument_key": ["A", "B", "C", "D", "A", "B", "C", "D"],
                    "score": [4.0, 3.0, 2.0, 1.0, 4.0, 3.0, 2.0, 1.0],
                }
            )
            labels = pl.DataFrame(
                {
                    "date": [
                        "2026-01-02",
                        "2026-01-02",
                        "2026-01-02",
                        "2026-01-02",
                        "2026-01-03",
                        "2026-01-03",
                        "2026-01-03",
                        "2026-01-03",
                    ],
                    "instrument_key": ["A", "B", "C", "D", "A", "B", "C", "D"],
                    "forward_return_1d_close_like": [-0.08, 0.03, -0.04, 0.05, -0.07, 0.02, -0.03, 0.04],
                }
            )
            layers = pl.DataFrame(
                {
                    "instrument_key": ["A", "B", "C", "D"],
                    "primary_tradability_layer": [
                        "large_liquid_core",
                        "large_liquid_core",
                        "mid_liquid_tradable",
                        "mid_liquid_tradable",
                    ],
                    "southbound_eligible": [True, False, True, False],
                    "southbound_eligible_known": [True, True, True, True],
                }
            )
            factor.write_parquet(run_dir / "factor_output.parquet")
            (run_dir / "data_run_summary.json").write_text(
                json.dumps({"factor_name": "demo_factor", "score_column": "score"}),
                encoding="utf-8",
            )
            labels_path = tmp / "labels.parquet"
            layer_path = tmp / "layers.parquet"
            labels.write_parquet(labels_path)
            layers.write_parquet(layer_path)
            board_path = tmp / "layered_factor_board.json"
            board_path.write_text(
                json.dumps(
                    {
                        "board_id": "layer_board_fixture",
                        "labels_path": str(labels_path),
                        "layer_path": str(layer_path),
                    }
                ),
                encoding="utf-8",
            )
            decision_log = tmp / "registry" / "layered_factor_decisions.tsv"
            decision_log.parent.mkdir(parents=True)
            decision_log.write_text(
                "\t".join(["triage_id", "created_at", "factor_name", "primary_decision", "run_dir"])
                + "\n"
                + "\t".join(
                    [
                        "triage_fixture",
                        "2026-01-02T00:00:00+00:00",
                        "demo_factor",
                        "promote_broad_candidate",
                        str(run_dir),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            gate_log = tmp / "registry" / "layered_gate_c_log.tsv"
            doc_path = tmp / "docs" / "layered_gate_c_summary_2026-05.md"

            gate_c_id, payload, summary_path = build_layered_gate_c_summary(
                layered_board_path=board_path,
                decision_log_path=decision_log,
                gate_log_path=gate_log,
                doc_path=doc_path,
                run_root=tmp / "runs",
                min_evaluated_dates=1,
                min_hit_rate=0.5,
                min_stability=0.5,
                notes="fixture",
            )

            self.assertTrue(gate_c_id.startswith("layered_gate_c_"))
            self.assertTrue(summary_path.exists())
            self.assertTrue(doc_path.exists())
            self.assertTrue(gate_log.exists())
            self.assertEqual(payload["factor_count"], 1)
            self.assertEqual(payload["factors"][0]["factor_name"], "demo_factor")
            self.assertEqual(payload["factors"][0]["direction_hint"], "inverse_candidate")
            self.assertIn(payload["factors"][0]["gate_c_decision"], payload["decision_counts"])

    def test_decide_gate_c_requires_both_southbound_named_buckets_to_pass(self) -> None:
        decision, reasons = _decide_gate_c(
            base_passed=True,
            primary_rows=[
                {"slice_value": "large_liquid_core", "passed": True},
                {"slice_value": "mid_liquid_tradable", "passed": True},
            ],
            southbound_rows=[
                {"slice_value": "southbound_eligible", "passed": False},
                {"slice_value": "southbound_unknown", "passed": False},
            ],
            time_rows=[
                {"slice_value": "early_half", "passed": True},
                {"slice_value": "late_half", "passed": True},
            ],
            policy={"min_primary_pass_layers": 2},
        )

        self.assertEqual(decision, "needs_southbound_split")
        self.assertIn("southbound", reasons[0])


if __name__ == "__main__":
    unittest.main()
