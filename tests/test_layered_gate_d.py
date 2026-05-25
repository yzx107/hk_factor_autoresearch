from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

import polars as pl

from harness.run_layered_gate_d import (
    build_layered_gate_d_summary,
    select_followup_rows,
)


def _write_factor_run(path: Path, factor_name: str, score_column: str) -> None:
    path.mkdir(parents=True)
    dates = ["2026-01-02", "2026-01-03", "2026-01-05", "2026-01-06"]
    pl.DataFrame(
        {
            "date": [date for date in dates for _ in range(2)],
            "instrument_key": ["A", "B"] * len(dates),
            score_column: [2.0, 1.0] * len(dates),
        }
    ).write_parquet(path / "factor_output.parquet")
    (path / "data_run_summary.json").write_text(
        json.dumps({"factor_name": factor_name, "score_column": score_column}),
        encoding="utf-8",
    )


class LayeredGateDTest(unittest.TestCase):
    def test_select_followup_rows_uses_latest_batch_and_parses_targets(self) -> None:
        rows = [
            {
                "followup_batch_id": "old",
                "created_at": "2026-01-01T00:00:00+00:00",
                "gate_c_id": "gate_1",
                "factor_name": "old_factor",
                "target_primary_layers_json": "[]",
                "target_southbound_buckets_json": "[]",
            },
            {
                "followup_batch_id": "new",
                "created_at": "2026-01-02T00:00:00+00:00",
                "gate_c_id": "gate_1",
                "factor_name": "new_factor",
                "target_primary_layers_json": '["small_illiquid_special"]',
                "target_southbound_buckets_json": '["southbound_unknown"]',
            },
        ]

        selected = select_followup_rows(rows, gate_c_id="gate_1")

        self.assertEqual([row["factor_name"] for row in selected], ["new_factor"])
        self.assertEqual(selected[0]["target_primary_layers"], ["small_illiquid_special"])
        self.assertEqual(selected[0]["target_southbound_buckets"], ["southbound_unknown"])

    def test_build_gate_d_summary_writes_log_doc_and_research_only_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            factor_run = root / "factor_run"
            _write_factor_run(factor_run, "small_factor", "score")
            labels_path = root / "labels.parquet"
            layers_path = root / "layers.parquet"
            dates = ["2026-01-02", "2026-01-03", "2026-01-05", "2026-01-06"]
            pl.DataFrame(
                {
                    "date": [date for date in dates for _ in range(2)],
                    "instrument_key": ["A", "B"] * len(dates),
                    "forward_return_1d_close_like": [0.03, -0.02] * len(dates),
                }
            ).write_parquet(labels_path)
            pl.DataFrame(
                {
                    "instrument_key": ["A", "B"],
                    "primary_tradability_layer": ["small_illiquid_special", "small_illiquid_special"],
                    "southbound_eligible": [False, False],
                    "southbound_eligible_known": [False, False],
                }
            ).write_parquet(layers_path)
            gate_c_path = root / "gate_c.json"
            gate_c_path.write_text(
                json.dumps(
                    {
                        "gate_c_id": "gate_fixture",
                        "labels_path": str(labels_path),
                        "layer_path": str(layers_path),
                        "factors": [
                            {
                                "factor_name": "small_factor",
                                "source_run_dir": str(factor_run),
                                "score_column": "score",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            queue_path = root / "registry" / "layered_followup_queue.tsv"
            queue_path.parent.mkdir(parents=True)
            with queue_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "followup_batch_id",
                        "created_at",
                        "gate_c_id",
                        "followup_id",
                        "factor_name",
                        "gate_c_decision",
                        "direction_hint",
                        "followup_lane",
                        "target_primary_layers_json",
                        "target_southbound_buckets_json",
                    ],
                    delimiter="\t",
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "followup_batch_id": "followup_fixture",
                        "created_at": "2026-01-02T00:00:00+00:00",
                        "gate_c_id": "gate_fixture",
                        "followup_id": "followup_1",
                        "factor_name": "small_factor",
                        "gate_c_decision": "needs_layer_split",
                        "direction_hint": "as_is_candidate",
                        "followup_lane": "layer_explicit_rewrite",
                        "target_primary_layers_json": '["small_illiquid_special"]',
                        "target_southbound_buckets_json": "[]",
                    }
                )
            log_path = root / "registry" / "gate_d.tsv"
            doc_path = root / "docs" / "gate_d.md"

            gate_d_id, payload, summary_path = build_layered_gate_d_summary(
                gate_c_summary_path=gate_c_path,
                followup_queue_path=queue_path,
                gate_d_log_path=log_path,
                doc_path=doc_path,
                run_root=root / "runs",
                min_sample_out_dates=1,
                cost_bps=5.0,
                sample_out_fraction=0.5,
                notes="fixture",
            )

            self.assertTrue(gate_d_id.startswith("layered_gate_d_"))
            self.assertTrue(summary_path.exists())
            self.assertTrue(doc_path.exists())
            self.assertTrue(log_path.exists())
            self.assertEqual(payload["decision_counts"]["research_only_capacity_risk"], 1)
            self.assertEqual(payload["factors"][0]["sample_out_passed"], True)
            self.assertIn("research_only_capacity_risk", doc_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
