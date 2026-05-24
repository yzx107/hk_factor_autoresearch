from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from harness.route_layered_gate_c_followups import (
    build_layered_gate_c_followups,
    derive_followup,
)


def _slice(value: str, *, passed: bool, cost: float) -> dict[str, object]:
    return {
        "slice_value": value,
        "passed": passed,
        "result": {
            "cost_adjusted_spread_return": cost,
            "hit_rate": 0.6,
            "turnover_proxy": 0.7,
            "stability_proxy": 0.6,
        },
    }


def _factor(
    *,
    factor_name: str = "factor_a",
    gate_c_decision: str = "needs_southbound_split",
    direction_hint: str = "as_is_candidate",
    primary_rows: list[dict[str, object]] | None = None,
    southbound_rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "factor_name": factor_name,
        "gate_c_decision": gate_c_decision,
        "direction_hint": direction_hint,
        "gate_c_reasons": ["fixture"],
        "base_backtest": {"cost_adjusted_spread_return": 0.01},
        "primary_layer_backtests": primary_rows
        or [
            _slice("large_liquid_core", passed=True, cost=0.003),
            _slice("small_illiquid_special", passed=False, cost=-0.001),
        ],
        "southbound_backtests": southbound_rows
        or [
            _slice("southbound_eligible", passed=False, cost=-0.002),
            _slice("southbound_unknown", passed=True, cost=0.004),
        ],
    }


class LayeredGateCFollowupTest(unittest.TestCase):
    def test_southbound_split_targets_passing_unknown_bucket(self) -> None:
        followup = derive_followup(_factor())

        self.assertEqual(followup["followup_lane"], "southbound_split_retest")
        self.assertEqual(followup["target_southbound_buckets"], ["southbound_unknown"])
        self.assertEqual(followup["target_primary_layers"], ["large_liquid_core"])
        self.assertEqual(followup["action"], "split_unknown_from_eligible_then_retest")

    def test_layer_split_targets_layer_explicit_rewrite(self) -> None:
        followup = derive_followup(
            _factor(
                factor_name="small_factor",
                gate_c_decision="needs_layer_split",
                direction_hint="inverse_candidate",
                primary_rows=[
                    _slice("large_liquid_core", passed=False, cost=-0.001),
                    _slice("small_illiquid_special", passed=True, cost=0.02),
                ],
            )
        )

        self.assertEqual(followup["followup_lane"], "layer_explicit_rewrite")
        self.assertEqual(followup["target_primary_layers"], ["small_illiquid_special"])
        self.assertEqual(followup["action"], "rewrite_factor_as_layer_explicit_spec")

    def test_build_followups_writes_summary_doc_and_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            summary_path = root / "gate_c_summary.json"
            queue_log = root / "registry" / "layered_followup_queue.tsv"
            doc_path = root / "docs" / "followup.md"
            summary_path.write_text(
                json.dumps(
                    {
                        "gate_c_id": "gate_fixture",
                        "board_id": "board_fixture",
                        "source_triage_id": "triage_fixture",
                        "factors": [
                            _factor(factor_name="southbound_factor"),
                            _factor(
                                factor_name="layer_factor",
                                gate_c_decision="needs_layer_split",
                                primary_rows=[_slice("small_illiquid_special", passed=True, cost=0.02)],
                            ),
                        ],
                    }
                ),
                encoding="utf-8",
            )

            followup_id, payload, out_summary = build_layered_gate_c_followups(
                gate_c_summary_path=summary_path,
                queue_log_path=queue_log,
                doc_path=doc_path,
                run_root=root / "runs",
                notes="fixture",
            )

            self.assertTrue(followup_id.startswith("layered_followup_"))
            self.assertTrue(out_summary.exists())
            self.assertTrue(doc_path.exists())
            self.assertTrue(queue_log.exists())
            self.assertEqual(payload["lane_counts"]["southbound_split_retest"], 1)
            self.assertEqual(payload["lane_counts"]["layer_explicit_rewrite"], 1)
            with queue_log.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual(len(rows), 2)
            self.assertIn("southbound_unknown", rows[0]["target_southbound_buckets_json"])
            self.assertIn("layer_explicit_rewrite", doc_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
