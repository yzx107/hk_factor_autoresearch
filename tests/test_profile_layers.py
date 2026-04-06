from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest

from factor_contracts.profile import build_factor_profile
from factor_families.profile import build_family_profile
from harness.instrument_universe import UNIVERSE_FILTER_VERSION


class ProfileLayerTest(unittest.TestCase):
    def test_build_factor_profile_populates_universe_and_mechanism_fields(self) -> None:
        module = SimpleNamespace(
            __name__="factor_defs.demo_factor",
            FACTOR_ID="demo_factor_id",
            FACTOR_FAMILY="demo_family",
            MECHANISM="demo mechanism",
            DAILY_AGG_TABLE="demo_daily_table",
        )
        card = {
            "years": ["2025", "2026"],
            "timing": {"mode": "coarse_only"},
            "holding_horizon": "1d",
            "horizon_scope": "1d",
            "failure_modes": ["low_coverage"],
            "baseline_refs": ["baseline_a"],
            "semantics": {"TradeDir": "unused"},
            "universe": "phase_a_core",
        }

        profile = build_factor_profile(
            factor_name="demo_factor",
            card=card,
            module=module,
            family_profile={"family_name": "demo_family"},
            research_card_path="/tmp/demo_card.md",
            target_instrument_universe="stock_research_candidate",
            source_instrument_universe="target_only",
            contains_cross_security_source=False,
            universe_filter_version=UNIVERSE_FILTER_VERSION,
            label_definition="forward_return_1d_close_like",
            family_registry_path="/tmp/families.tsv",
        ).as_dict()

        self.assertEqual(profile["factor_name"], "demo_factor")
        self.assertEqual(profile["family_name"], "demo_family")
        self.assertEqual(profile["required_data_lane"], "daily_agg")
        self.assertEqual(profile["target_universe_scope"], "stock_research_candidate")
        self.assertEqual(profile["source_universe_scope"], "target_only")
        self.assertTrue(profile["supports_default_lane"])
        self.assertFalse(profile["supports_extension_lane"])
        self.assertFalse(profile["contains_caveat_fields"])
        self.assertEqual(profile["required_year_grade"], ["coarse_only", "fine_ok"])
        self.assertEqual(profile["baseline_comparators"], ["baseline_a"])
        self.assertEqual(profile["known_failure_modes"], ["low_coverage"])
        self.assertEqual(profile["universe_filter_version"], UNIVERSE_FILTER_VERSION)
        self.assertEqual(profile["family_expand_direction"], "")

    def test_build_family_profile_normalizes_family_yaml(self) -> None:
        with TemporaryDirectory() as tmpdir:
            family_yaml = {
                "family_id": "demo_family",
                "family_name": "demo_family",
                "mechanism_hypothesis": "demo mechanism",
                "allowed_input_lane": "phase_a_core",
                "current_members": ["variant_a", "variant_b"],
                "current_best_variant": ["variant_b"],
                "known_failure_modes": ["weak_ic", "high_redundancy"],
                "redundancy_pattern": "demo redundancy",
                "baseline_refs": ["baseline_a"],
                "expected_regime": "high_entropy",
                "extension_lane_eligibility": "default_lane_only",
                "whether_to_expand_further": "monitor",
                "status": "active",
                "notes": "demo",
            }
            profile = build_family_profile(
                "demo_family",
                family_yaml=family_yaml,
                family_registry_path=Path(tmpdir) / "factor_families.tsv",
            ).as_dict()

        self.assertEqual(profile["family_name"], "demo_family")
        self.assertEqual(profile["mechanism_hypothesis"], "demo mechanism")
        self.assertEqual(profile["common_variants"], ["variant_a", "variant_b"])
        self.assertEqual(profile["current_best_variants"], ["variant_b"])
        self.assertEqual(profile["known_failure_patterns"], ["weak_ic", "high_redundancy"])
        self.assertEqual(profile["baseline_refs"], ["baseline_a"])
        self.assertEqual(profile["regime_sensitivity"], ["high_entropy"])
        self.assertEqual(profile["extension_lane_eligibility"], "default_lane_only")
        self.assertEqual(profile["allowed_input_lane"], "phase_a_core")
        self.assertEqual(profile["redundancy_pattern"], "demo redundancy")


if __name__ == "__main__":
    unittest.main()
