from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from harness.run_layered_triage import (
    build_layered_triage_summary,
    derive_layered_decision,
)


def _board_row(
    *,
    factor_name: str = "factor_a",
    classification: str = "broad_candidate",
    strongest_layer: str = "large_liquid_core",
    southbound: float = 0.08,
    unknown: float = 0.02,
    not_eligible: float | None = None,
) -> dict[str, object]:
    southbound_rows: list[dict[str, object]] = [
        {"layer_value": "southbound_eligible", "abs_rank_ic": southbound},
        {"layer_value": "southbound_unknown", "abs_rank_ic": unknown},
    ]
    if not_eligible is not None:
        southbound_rows.append({"layer_value": "southbound_not_eligible", "abs_rank_ic": not_eligible})
    return {
        "factor_name": factor_name,
        "classification": classification,
        "classification_reason": "fixture",
        "strongest_layer": strongest_layer,
        "weakest_layer": "mid_liquid_tradable",
        "signal_layers": ["large_liquid_core", "mid_liquid_tradable", "new_or_recent_listing"],
        "max_abs_rank_ic": 0.11,
        "layer_dispersion": 0.03,
        "run_dir": "/tmp/factor_a",
        "southbound_layer_rows": southbound_rows,
    }


class LayeredTriageTest(unittest.TestCase):
    def test_broad_candidate_with_southbound_gap_requires_split(self) -> None:
        decision = derive_layered_decision(_board_row(), southbound_split_threshold=0.04)

        self.assertEqual(decision["primary_decision"], "needs_southbound_split")
        self.assertEqual(decision["secondary_decisions"], ["promote_broad_candidate"])
        self.assertEqual(decision["research_lane"], "large_southbound_research")

    def test_broad_candidate_with_not_eligible_gap_requires_split(self) -> None:
        decision = derive_layered_decision(
            _board_row(southbound=0.08, unknown=0.07, not_eligible=0.01),
            southbound_split_threshold=0.04,
        )

        self.assertEqual(decision["primary_decision"], "needs_southbound_split")
        self.assertEqual(decision["southbound_comparison_layer"], "southbound_not_eligible")
        self.assertAlmostEqual(decision["southbound_abs_rank_ic_gap"], 0.07)

    def test_new_listing_candidate_stays_in_new_listing_lane(self) -> None:
        decision = derive_layered_decision(
            _board_row(
                classification="new_listing_dominant_watch",
                strongest_layer="new_or_recent_listing",
                southbound=0.05,
                unknown=0.04,
            )
        )

        self.assertEqual(decision["primary_decision"], "research_new_listing_family")
        self.assertEqual(decision["research_lane"], "new_listing_research")

    def test_small_illiquid_candidate_is_risk_only_even_with_southbound_gap(self) -> None:
        decision = derive_layered_decision(
            _board_row(
                classification="small_illiquid_dominant_risk",
                strongest_layer="small_illiquid_special",
            )
        )

        self.assertEqual(decision["primary_decision"], "risk_only_small_illiquid")
        self.assertIn("needs_southbound_split", decision["secondary_decisions"])
        self.assertEqual(decision["research_lane"], "small_illiquid_risk")

    def test_build_layered_triage_summary_writes_log_doc_and_run_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board_path = root / "layered_factor_board.json"
            log_path = root / "registry" / "layered_factor_decisions.tsv"
            doc_path = root / "docs" / "layered_factor_board_summary_2026-05.md"
            run_root = root / "runs"
            board_path.write_text(
                json.dumps(
                    {
                        "board_id": "layer_board_fixture",
                        "classification_counts": {"broad_candidate": 1, "new_listing_dominant_watch": 1},
                        "factors": [
                            _board_row(factor_name="broad_factor"),
                            _board_row(
                                factor_name="new_factor",
                                classification="new_listing_dominant_watch",
                                strongest_layer="new_or_recent_listing",
                                southbound=0.03,
                                unknown=0.02,
                            ),
                        ],
                    }
                ),
                encoding="utf-8",
            )

            triage_id, payload, summary_path = build_layered_triage_summary(
                layered_board_path=board_path,
                decision_log_path=log_path,
                doc_path=doc_path,
                run_root=run_root,
                southbound_split_threshold=0.04,
                notes="fixture",
            )

            self.assertTrue(triage_id.startswith("layered_triage_"))
            self.assertTrue(summary_path.exists())
            self.assertTrue(doc_path.exists())
            self.assertTrue(log_path.exists())
            self.assertEqual(payload["decision_counts"]["needs_southbound_split"], 1)
            self.assertEqual(payload["decision_counts"]["research_new_listing_family"], 1)
            large_lane = [row for row in payload["factor_spec_lanes"] if row["lane"] == "large_southbound_research"][0]
            self.assertEqual(large_lane["factor_names"], ["broad_factor"])
            self.assertIn("large_southbound_research", doc_path.read_text(encoding="utf-8"))
            self.assertIn("sb_compare", doc_path.read_text(encoding="utf-8"))
            self.assertEqual(len(log_path.read_text(encoding="utf-8").strip().splitlines()), 3)


if __name__ == "__main__":
    unittest.main()
