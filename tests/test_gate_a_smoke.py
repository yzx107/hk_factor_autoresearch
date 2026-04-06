from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from gatekeeper.gate_a_data import evaluate_card, load_research_card

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

    def test_missing_target_instrument_universe_fails(self) -> None:
        template = (ROOT / "research_cards/examples/structural_activity_proxy_2026.md").read_text(encoding="utf-8")
        text = template.replace('target_instrument_universe = "stock_research_candidate"\n', "", 1)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "missing_target_instrument_universe.md"
            path.write_text(text, encoding="utf-8")
            result = evaluate_card(path)
        self.assertEqual(result.decision, "fail")
        self.assertTrue(any("target_instrument_universe" in reason for reason in result.reasons))

    def test_missing_source_instrument_universe_fails(self) -> None:
        template = (ROOT / "research_cards/examples/structural_activity_proxy_2026.md").read_text(encoding="utf-8")
        text = template.replace('source_instrument_universe = "target_only"\n', "", 1)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "missing_source_instrument_universe.md"
            path.write_text(text, encoding="utf-8")
            result = evaluate_card(path)
        self.assertEqual(result.decision, "fail")
        self.assertTrue(any("source_instrument_universe" in reason for reason in result.reasons))

    def test_non_stock_target_instrument_universe_fails(self) -> None:
        template = (ROOT / "research_cards/examples/structural_activity_proxy_2026.md").read_text(encoding="utf-8")
        text = template.replace(
            'target_instrument_universe = "stock_research_candidate"',
            'target_instrument_universe = "listed_security_unclassified"',
            1,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "non_stock_target_instrument_universe.md"
            path.write_text(text, encoding="utf-8")
            result = evaluate_card(path)
        self.assertEqual(result.decision, "fail")
        self.assertTrue(any("stock-factor" in reason or "target_instrument_universe" in reason for reason in result.reasons))

    def test_non_target_only_source_instrument_universe_fails(self) -> None:
        template = (ROOT / "research_cards/examples/structural_activity_proxy_2026.md").read_text(encoding="utf-8")
        text = template.replace(
            'source_instrument_universe = "target_only"',
            'source_instrument_universe = "non_equity_source_lane"',
            1,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "non_target_only_source_instrument_universe.md"
            path.write_text(text, encoding="utf-8")
            result = evaluate_card(path)
        self.assertEqual(result.decision, "fail")
        self.assertTrue(any("source_instrument_universe" in reason for reason in result.reasons))

    def test_legacy_instrument_universe_alias_normalizes_to_target_field(self) -> None:
        template = (ROOT / "research_cards/examples/structural_activity_proxy_2026.md").read_text(encoding="utf-8")
        text = template.replace(
            'target_instrument_universe = "stock_research_candidate"\n',
            'instrument_universe = "stock_research_candidate"\n',
            1,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "legacy_instrument_universe_alias.md"
            path.write_text(text, encoding="utf-8")
            card = load_research_card(path)
            result = evaluate_card(path)
        self.assertEqual(card["target_instrument_universe"], "stock_research_candidate")
        self.assertEqual(result.decision, "pass")


if __name__ == "__main__":
    unittest.main()
