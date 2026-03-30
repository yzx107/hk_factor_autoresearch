from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from gatekeeper.gate_a_data import evaluate_card

ROOT = Path(__file__).resolve().parents[1]


class GateASmokeTest(unittest.TestCase):
    def test_trade_dir_candidate_2026_is_allow_with_caveat(self) -> None:
        result = evaluate_card(ROOT / "research_cards/examples/tradedir_candidate_2026.md")
        self.assertEqual(result.decision, "allow_with_caveat")
        self.assertTrue(any("TradeDir" in reason for reason in result.reasons))

    def test_ordertype_caveat_2026_is_allow_with_caveat(self) -> None:
        result = evaluate_card(ROOT / "research_cards/examples/ordertype_caveat_2026.md")
        self.assertEqual(result.decision, "allow_with_caveat")
        self.assertTrue(any("OrderType" in reason for reason in result.reasons))

    def test_brokerno_direct_alpha_fails(self) -> None:
        result = evaluate_card(ROOT / "research_cards/examples/brokerno_direct_alpha.md")
        self.assertEqual(result.decision, "fail")
        self.assertTrue(any("BrokerNo" in reason for reason in result.reasons))

    def test_queue_precision_2025_fails(self) -> None:
        result = evaluate_card(ROOT / "research_cards/examples/queue_precision_2025.md")
        self.assertEqual(result.decision, "fail")
        self.assertTrue(any("2025" in reason or "Queue" in reason for reason in result.reasons))

    def test_caveat_field_in_core_universe_fails(self) -> None:
        template = (ROOT / "research_cards/examples/tradedir_candidate_2026.md").read_text(encoding="utf-8")
        text = template.replace('universe = "phase_a_caveat_lane"', 'universe = "phase_a_core"', 1)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad_core_card.md"
            path.write_text(text, encoding="utf-8")
            result = evaluate_card(path)
        self.assertEqual(result.decision, "fail")
        self.assertTrue(any("phase_a_caveat_lane" in reason for reason in result.reasons))


if __name__ == "__main__":
    unittest.main()
