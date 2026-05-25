from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

import polars as pl

from harness.run_small_illiquid_capacity_gate import (
    _capacity_decision,
    build_capacity_gate_summary,
)


def _write_factor_run(path: Path) -> None:
    path.mkdir(parents=True)
    dates = ["2026-01-02", "2026-01-03", "2026-01-05", "2026-01-06"]
    pl.DataFrame(
        {
            "date": [date for date in dates for _ in range(2)],
            "instrument_key": ["A", "B"] * len(dates),
            "score": [2.0, 1.0] * len(dates),
        }
    ).write_parquet(path / "factor_output.parquet")
    (path / "data_run_summary.json").write_text(
        json.dumps({"factor_name": "small_factor", "score_column": "score"}),
        encoding="utf-8",
    )


class SmallIlliquidCapacityGateTest(unittest.TestCase):
    def test_capacity_decision_rejects_negative_50bps_stress(self) -> None:
        decision, reasons = _capacity_decision(
            {
                "missing_turnover_ratio": 0.0,
                "stress_results": {"50": {"cost_adjusted_spread_return": -0.001}},
                "capacity_by_participation": {"0.01": {"p25_gross_capacity_hkd": 10_000_000.0}},
                "concentration": {"top_abs_contribution_share": 0.1},
            },
            {
                "max_missing_turnover_ratio": 0.05,
                "pass_stress_bps": 50.0,
                "pass_participation_rate": 0.01,
                "max_concentration_share": 0.35,
                "min_gross_capacity_hkd": 5_000_000.0,
            },
        )

        self.assertEqual(decision, "reject_capacity")
        self.assertIn("50bps", reasons[0])

    def test_build_capacity_gate_summary_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            factor_run = root / "factor_run"
            _write_factor_run(factor_run)
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
                    "southbound_eligible_known": [True, True],
                }
            ).write_parquet(layers_path)
            gate_c_path = root / "gate_c.json"
            gate_c_path.write_text(
                json.dumps(
                    {
                        "gate_c_id": "gate_c_fixture",
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
            gate_d_path = root / "gate_d.json"
            gate_d_path.write_text(
                json.dumps(
                    {
                        "gate_d_id": "gate_d_fixture",
                        "gate_c_summary_path": str(gate_c_path),
                        "factors": [
                            {
                                "factor_name": "small_factor",
                                "followup_id": "followup_1",
                                "gate_d_decision": "research_only_capacity_risk",
                                "direction_hint": "as_is_candidate",
                                "target_primary_layers": ["small_illiquid_special"],
                                "target_southbound_buckets": ["southbound_not_eligible"],
                                "sample_out_dates": dates,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            liquidity = pl.DataFrame(
                {
                    "date": [date for date in dates for _ in range(2)],
                    "instrument_key": ["A", "B"] * len(dates),
                    "turnover": [100_000.0, 200_000.0] * len(dates),
                }
            )
            log_path = root / "registry" / "capacity.tsv"
            doc_path = root / "docs" / "capacity.md"

            capacity_id, payload, summary_path = build_capacity_gate_summary(
                gate_d_summary_path=gate_d_path,
                capacity_log_path=log_path,
                doc_path=doc_path,
                run_root=root / "runs",
                min_gross_capacity_hkd=10_000.0,
                max_concentration_share=0.9,
                liquidity_df=liquidity,
                notes="fixture",
            )

            self.assertTrue(capacity_id.startswith("small_illiquid_capacity_"))
            self.assertTrue(summary_path.exists())
            self.assertTrue(doc_path.exists())
            self.assertTrue(log_path.exists())
            self.assertEqual(payload["decision_counts"]["research_only_micro_capacity"], 1)
            self.assertGreater(payload["factors"][0]["metrics"]["stress_results"]["50"]["cost_adjusted_spread_return"], 0)
            with log_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
