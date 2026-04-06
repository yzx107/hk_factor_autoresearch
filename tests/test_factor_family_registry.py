from __future__ import annotations

import importlib
from pathlib import Path
import unittest

from factor_families.profile import REQUIRED_FAMILY_KEYS, load_family_yaml

ROOT = Path(__file__).resolve().parents[1]
FACTOR_FAMILY_DIR = ROOT / "factor_families"
TEMPLATE_PATH = ROOT / "research_cards" / "TEMPLATE.md"
FACTOR_DIR = ROOT / "factor_defs"
SKIP_MODULES = {"change_support", "example_structural_factor", "order_trade_interaction_support"}


def _factor_modules() -> list[str]:
    names: list[str] = []
    for path in sorted(FACTOR_DIR.glob("*.py")):
        if path.stem.startswith("__") or path.stem in SKIP_MODULES:
            continue
        module = importlib.import_module(f"factor_defs.{path.stem}")
        if hasattr(module, "FACTOR_ID"):
            names.append(path.stem)
    return names


FACTOR_MODULES = _factor_modules()


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
            family_yaml = load_family_yaml(family_id)
            self.assertTrue(REQUIRED_FAMILY_KEYS.issubset(family_yaml))

    def test_research_card_template_mentions_family_and_incremental_sections(self) -> None:
        text = TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertIn('factor_family = "activity_pressure"', text)
        self.assertIn("## Observable Proxies", text)
        self.assertIn("## Why Incremental vs Baselines", text)
        self.assertIn("## Forbidden Semantic Assumptions", text)
        self.assertIn('contains_cross_security_source = false', text)


if __name__ == "__main__":
    unittest.main()
