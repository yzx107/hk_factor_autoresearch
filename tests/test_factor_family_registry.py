from __future__ import annotations

import importlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FACTOR_FAMILY_DIR = ROOT / "factor_families"
TEMPLATE_PATH = ROOT / "research_cards" / "TEMPLATE.md"
FACTOR_MODULES = [
    "avg_trade_notional_bias",
    "avg_trade_notional_bias_change",
    "close_vwap_gap_intensity",
    "close_vwap_gap_intensity_change",
    "order_lifecycle_churn",
    "order_lifecycle_churn_change",
    "structural_activity_proxy",
    "structural_activity_change",
]


class FactorFamilyRegistryTest(unittest.TestCase):
    def test_every_factor_family_has_yaml_registry(self) -> None:
        for module_name in FACTOR_MODULES:
            module = importlib.import_module(f"factor_defs.{module_name}")
            family_id = getattr(module, "FACTOR_FAMILY")
            family_path = FACTOR_FAMILY_DIR / f"{family_id}.yaml"
            self.assertTrue(
                family_path.exists(),
                msg=f"Missing family registry yaml for {module_name}: {family_path.name}",
            )

    def test_research_card_template_mentions_family_and_incremental_sections(self) -> None:
        text = TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertIn('factor_family = "activity_pressure"', text)
        self.assertIn("## Observable Proxies", text)
        self.assertIn("## Why Incremental vs Baselines", text)
        self.assertIn("## Forbidden Semantic Assumptions", text)


if __name__ == "__main__":
    unittest.main()
