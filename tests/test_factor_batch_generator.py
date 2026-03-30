from __future__ import annotations

from pathlib import Path
import unittest

from harness.generate_factor_batch import load_batch_spec


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "factor_specs" / "order_trade_interaction_batch.toml"


class FactorBatchGeneratorTest(unittest.TestCase):
    def test_load_batch_spec_reads_expected_prototypes(self) -> None:
        spec = load_batch_spec(SPEC_PATH)
        self.assertEqual(spec.family, "order_trade_interaction_pressure")
        self.assertEqual(len(spec.prototypes), 3)
        self.assertEqual(
            [prototype.slug for prototype in spec.prototypes],
            [
                "order_unique_trade_participation_gap",
                "order_notional_vs_trade_notional_gap",
                "close_vwap_churn_interaction",
            ],
        )


if __name__ == "__main__":
    unittest.main()
