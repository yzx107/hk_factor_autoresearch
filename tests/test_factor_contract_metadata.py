from __future__ import annotations

import csv
import importlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FAMILY_REGISTRY = ROOT / "registry" / "factor_families.tsv"
FACTOR_MODULES = [
    "structural_activity_proxy",
    "avg_trade_notional_bias",
    "order_lifecycle_churn",
    "close_vwap_gap_intensity",
    "structural_activity_change",
    "avg_trade_notional_bias_change",
    "order_lifecycle_churn_change",
    "close_vwap_gap_intensity_change",
]
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

        self.assertEqual(set(FACTOR_MODULES), registered_members)


if __name__ == "__main__":
    unittest.main()
