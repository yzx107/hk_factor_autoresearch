from __future__ import annotations

import unittest

import polars as pl

from diagnostics.regime_slices import apply_regime_labels, build_regime_slice_summary


class RegimeSlicesTest(unittest.TestCase):
    def test_apply_regime_labels(self) -> None:
        stats = pl.DataFrame(
            {
                "date": ["2026-01-05", "2026-01-06", "2026-01-07"],
                "market_total_turnover": [100.0, 200.0, 300.0],
                "market_abs_close_return": [None, 0.02, 0.10],
                "market_turnover_entropy": [0.10, 0.55, 0.90],
            }
        ).with_columns(pl.col("date").str.to_date())

        labeled = apply_regime_labels(stats)
        rows = labeled.sort("date").to_dicts()
        self.assertEqual(rows[0]["year_grade"], "fine_ok")
        self.assertEqual(rows[0]["market_turnover_regime"], "low_turnover")
        self.assertEqual(rows[0]["market_volatility_regime"], "insufficient_history")
        self.assertEqual(rows[0]["entropy_quantile"], "q1_low_entropy")
        self.assertEqual(rows[2]["market_turnover_regime"], "high_turnover")
        self.assertEqual(rows[2]["market_volatility_regime"], "high_vol")
        self.assertEqual(rows[2]["entropy_quantile"], "q3_high_entropy")

    def test_build_regime_slice_summary(self) -> None:
        per_date_rows = [
            {
                "date": "2026-01-05",
                "labeled_rows": 10,
                "rank_ic": 0.2,
                "normalized_mutual_info": 0.03,
                "top_bottom_spread": 0.01,
                "coverage_ratio": 1.0,
            },
            {
                "date": "2026-01-06",
                "labeled_rows": 20,
                "rank_ic": -0.4,
                "normalized_mutual_info": 0.05,
                "top_bottom_spread": -0.02,
                "coverage_ratio": 0.8,
            },
        ]
        annotations = pl.DataFrame(
            {
                "date": ["2026-01-05", "2026-01-06"],
                "year_grade": ["fine_ok", "fine_ok"],
                "market_turnover_regime": ["low_turnover", "high_turnover"],
                "market_volatility_regime": ["low_vol", "high_vol"],
                "entropy_quantile": ["q1_low_entropy", "q3_high_entropy"],
            }
        ).with_columns(pl.col("date").str.to_date())

        summary = build_regime_slice_summary(per_date_rows, annotations)
        self.assertEqual(
            sorted(summary.keys()),
            ["entropy_quantile", "market_turnover_regime", "market_volatility_regime", "year_grade"],
        )
        self.assertIn("year_grade", summary)
        self.assertIn("market_turnover_regime", summary)
        self.assertIn("entropy_quantile", summary)
        year_grade = summary["year_grade"][0]
        self.assertEqual(year_grade["slice_value"], "fine_ok")
        self.assertEqual(year_grade["date_count"], 2)
        self.assertAlmostEqual(year_grade["mean_abs_rank_ic"], 0.3)
        self.assertAlmostEqual(summary["entropy_quantile"][0]["mean_nmi"], 0.03)


if __name__ == "__main__":
    unittest.main()
