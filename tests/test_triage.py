from __future__ import annotations

import unittest

from harness.instrument_universe import UNIVERSE_FILTER_VERSION
from harness.triage import derive_reject_reasons


class TriageTest(unittest.TestCase):
    def test_negative_signed_candidate_becomes_watch_before_backtest(self) -> None:
        row = {
            "factor_name": "demo_inverse_candidate",
            "mean_rank_ic": -0.08,
            "mean_abs_rank_ic": 0.08,
            "mean_nmi": 0.03,
            "mean_top_bottom_spread": -0.01,
            "mean_coverage_ratio": 1.0,
            "mi_significant_date_ratio": 1.0,
            "mean_mi_p_value": 0.01,
            "mean_abs_baseline_corr": 0.2,
            "sign_consistency": 1.0,
            "entropy_regime_summary": [
                {"slice_value": "low", "mean_abs_rank_ic": 0.05},
                {"slice_value": "mid", "mean_abs_rank_ic": 0.04},
                {"slice_value": "high", "mean_abs_rank_ic": 0.04},
            ],
            "target_instrument_universe": "stock_research_candidate",
            "source_instrument_universe": "target_only",
            "contains_cross_security_source": False,
            "contains_caveat_fields": False,
            "universe_filter_version": UNIVERSE_FILTER_VERSION,
        }
        factor_profile = {
            "factor_name": "demo_inverse_candidate",
            "family_name": "demo_family",
            "target_universe_scope": "stock_research_candidate",
            "source_universe_scope": "target_only",
            "contains_cross_security_source": False,
            "contains_caveat_fields": False,
            "universe_filter_version": UNIVERSE_FILTER_VERSION,
        }

        primary, secondary, readiness, snapshot = derive_reject_reasons(
            row,
            factor_profile=factor_profile,
        )

        self.assertEqual(primary, "inverse_candidate_only")
        self.assertEqual(secondary, [])
        self.assertEqual(readiness, "watch")
        self.assertEqual(snapshot["promotion_readiness"], "watch")
        self.assertEqual(snapshot["primary_reject_reason"], "inverse_candidate_only")


if __name__ == "__main__":
    unittest.main()
