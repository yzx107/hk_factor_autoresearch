from __future__ import annotations

import csv
import importlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FAMILY_REGISTRY = ROOT / "registry" / "factor_families.tsv"
FACTOR_DIR = ROOT / "factor_defs"
SKIP_MODULES = {"change_support", "example_structural_factor", "order_trade_interaction_support"}
REQUIRED_METADATA = [
    "FACTOR_ID",
    "FACTOR_FAMILY",
    "MECHANISM",
    "INPUT_DEPENDENCIES",
    "RESEARCH_UNIT",
    "HORIZON_SCOPE",
    "VERSION",
    "TRANSFORM_CHAIN",
    "EXPECTED_REGIME",
    "FORBIDDEN_SEMANTIC_ASSUMPTIONS",
]


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


class FactorContractMetadataTest(unittest.TestCase):
    def test_factor_modules_export_required_metadata(self) -> None:
        for module_name in FACTOR_MODULES:
            module = importlib.import_module(f"factor_defs.{module_name}")
            for attr in REQUIRED_METADATA:
                self.assertTrue(hasattr(module, attr), f"{module_name} missing {attr}")

            self.assertIsInstance(module.FACTOR_ID, str)
            self.assertIsInstance(module.FACTOR_FAMILY, str)
            self.assertIsInstance(module.MECHANISM, str)
            self.assertIsInstance(module.INPUT_DEPENDENCIES, list)
            self.assertIsInstance(module.TRANSFORM_CHAIN, list)
            self.assertIsInstance(module.FORBIDDEN_SEMANTIC_ASSUMPTIONS, list)
            self.assertTrue(module.FACTOR_ID)
            self.assertTrue(module.FACTOR_FAMILY)
            self.assertTrue(module.INPUT_DEPENDENCIES)
            self.assertTrue(module.TRANSFORM_CHAIN)
            self.assertTrue(module.FORBIDDEN_SEMANTIC_ASSUMPTIONS)

    def test_family_registry_covers_current_factor_inventory(self) -> None:
        with FAMILY_REGISTRY.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))

        self.assertGreaterEqual(len(rows), 4)
        registered_members: set[str] = set()
        for row in rows:
            self.assertTrue(row["family_id"])
            self.assertTrue(row["current_members"])
            registered_members.update(member.strip() for member in row["current_members"].split(",") if member.strip())

        self.assertTrue(set(FACTOR_MODULES).issubset(registered_members))


if __name__ == "__main__":
    unittest.main()
