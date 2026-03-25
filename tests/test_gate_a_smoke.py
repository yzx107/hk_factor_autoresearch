from __future__ import annotations

from pathlib import Path
import unittest

from gatekeeper.gate_a_data import evaluate_card

ROOT = Path(__file__).resolve().parents[1]


class GateASmokeTest(unittest.TestCase):
    def test_trade_dir_candidate_2026_is_allow_with_caveat(self) -> None:
        result = evaluate_card(ROOT / "research_cards/examples/tradedir_candidate_2026.md")
        self.assertEqual(result.decision, "allow_with_caveat")
        self.assertTrue(any("TradeDir" in reason for reason in result.reasons))

    def test_brokerno_direct_alpha_fails(self) -> None:
        result = evaluate_card(ROOT / "research_cards/examples/brokerno_direct_alpha.md")
        self.assertEqual(result.decision, "fail")
        self.assertTrue(any("BrokerNo" in reason for reason in result.reasons))

    def test_queue_precision_2025_fails(self) -> None:
        result = evaluate_card(ROOT / "research_cards/examples/queue_precision_2025.md")
        self.assertEqual(result.decision, "fail")
        self.assertTrue(any("2025" in reason or "Queue" in reason for reason in result.reasons))


if __name__ == "__main__":
    unittest.main()
