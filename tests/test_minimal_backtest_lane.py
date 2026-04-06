from __future__ import annotations

import unittest

import polars as pl

from backtest_engine.minimal_lane import run_minimal_backtest
from harness.instrument_universe import UNIVERSE_FILTER_VERSION


class MinimalBacktestLaneTest(unittest.TestCase):
    def test_minimal_backtest_returns_spread_turnover_and_stability(self) -> None:
        factor_scores = pl.DataFrame(
            {
                "date": [
                    "2026-01-02",
                    "2026-01-02",
                    "2026-01-02",
                    "2026-01-02",
                    "2026-01-03",
                    "2026-01-03",
                    "2026-01-03",
                    "2026-01-03",
                ],
                "instrument_key": ["A", "B", "C", "D", "A", "B", "C", "D"],
                "score": [4.0, 3.0, 2.0, 1.0, 1.0, 4.0, 2.0, 3.0],
            }
        )
        labels = pl.DataFrame(
            {
                "date": [
                    "2026-01-02",
                    "2026-01-02",
                    "2026-01-02",
                    "2026-01-02",
                    "2026-01-03",
                    "2026-01-03",
                    "2026-01-03",
                    "2026-01-03",
                ],
                "instrument_key": ["A", "B", "C", "D", "A", "B", "C", "D"],
                "forward_return_1d_close_like": [0.08, 0.05, -0.01, -0.04, 0.02, 0.07, -0.02, -0.05],
            }
        )

        result = run_minimal_backtest(
            factor_scores,
            labels,
            factor_name="demo_factor",
            score_column="score",
            label_column="forward_return_1d_close_like",
            target_instrument_universe="stock_research_candidate",
            source_instrument_universe="target_only",
            contains_cross_security_source=False,
            universe_filter_version=UNIVERSE_FILTER_VERSION,
            horizon="1d",
            top_fraction=0.25,
            cost_bps=10.0,
        )

        self.assertEqual(result.joined_rows, 8)
        self.assertEqual(result.evaluated_dates, 2)
        self.assertEqual(result.coverage_ratio, 1.0)
        self.assertGreater(result.spread_return or 0.0, 0.0)
        self.assertLess(result.cost_adjusted_spread_return or 0.0, result.spread_return or 0.0)
        self.assertGreaterEqual(result.turnover_proxy or 0.0, 0.0)
        self.assertLessEqual(result.turnover_proxy or 0.0, 1.0)
        self.assertEqual(result.hit_rate, 1.0)
        self.assertEqual(result.stability_proxy, 1.0)
        self.assertTrue(result.per_date)

    def test_missing_score_column_raises(self) -> None:
        factor_scores = pl.DataFrame({"date": ["2026-01-02"], "instrument_key": ["A"], "wrong": [1.0]})
        labels = pl.DataFrame(
            {
                "date": ["2026-01-02"],
                "instrument_key": ["A"],
                "forward_return_1d_close_like": [0.01],
            }
        )

        with self.assertRaises(ValueError):
            run_minimal_backtest(
                factor_scores,
                labels,
                factor_name="demo_factor",
                score_column="score",
            )


if __name__ == "__main__":
    unittest.main()
