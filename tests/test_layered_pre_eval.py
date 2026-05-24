from __future__ import annotations

import unittest

import polars as pl

from evaluation.pre_eval import LABEL_NAME
from harness.run_layered_pre_eval import build_layered_pre_eval_summary


class LayeredPreEvalTest(unittest.TestCase):
    def test_build_layered_pre_eval_summary_marks_low_coverage_layers(self) -> None:
        dates = ["2026-01-05", "2026-01-06"]
        instruments = ["00001", "00002", "00003", "00004", "00005"]
        factor_df = pl.DataFrame(
            {
                "date": [date for date in dates for _ in instruments],
                "instrument_key": instruments * len(dates),
                "signal": [5.0, 4.0, 3.0, 2.0, 1.0] * len(dates),
            }
        ).with_columns(pl.col("date").str.to_date())
        labels_df = pl.DataFrame(
            {
                "date": [date for date in dates for _ in instruments],
                "next_date": ["2026-01-07"] * (len(dates) * len(instruments)),
                "instrument_key": instruments * len(dates),
                LABEL_NAME: [0.05, 0.04, 0.03, 0.02, 0.01] * len(dates),
                "label_source": ["unit"] * (len(dates) * len(instruments)),
            }
        ).with_columns([pl.col("date").str.to_date(), pl.col("next_date").str.to_date()])
        layers_df = pl.DataFrame(
            {
                "instrument_key": instruments,
                "primary_tradability_layer": [
                    "large_liquid_core",
                    "large_liquid_core",
                    "large_liquid_core",
                    "small_illiquid_special",
                    "small_illiquid_special",
                ],
                "layer_version": ["test_v1"] * len(instruments),
            }
        )

        summary = build_layered_pre_eval_summary(
            factor_df,
            score_column="signal",
            labels_df=labels_df,
            layers_df=layers_df,
            min_instruments=3,
            min_dates=2,
            mi_permutation_count=5,
        )
        rows = {row["layer_value"]: row for row in summary["layers"]}

        self.assertEqual(summary["layer_count"], 2)
        self.assertFalse(rows["large_liquid_core"]["diagnostic_only"])
        self.assertTrue(rows["small_illiquid_special"]["diagnostic_only"])
        self.assertEqual(rows["large_liquid_core"]["instrument_count"], 3)
        self.assertEqual(rows["small_illiquid_special"]["instrument_count"], 2)
        self.assertEqual(summary["unlayered_factor_rows"], 0)

    def test_build_layered_pre_eval_summary_requires_unique_layer_keys(self) -> None:
        factor_df = pl.DataFrame(
            {"date": ["2026-01-05"], "instrument_key": ["00001"], "signal": [1.0]}
        ).with_columns(pl.col("date").str.to_date())
        labels_df = pl.DataFrame(
            {
                "date": ["2026-01-05"],
                "next_date": ["2026-01-06"],
                "instrument_key": ["00001"],
                LABEL_NAME: [0.01],
                "label_source": ["unit"],
            }
        ).with_columns([pl.col("date").str.to_date(), pl.col("next_date").str.to_date()])
        layers_df = pl.DataFrame(
            {
                "instrument_key": ["00001", "00001"],
                "primary_tradability_layer": ["large_liquid_core", "mid_liquid_tradable"],
                "layer_version": ["test_v1", "test_v1"],
            }
        )

        with self.assertRaisesRegex(ValueError, "duplicate instrument_key"):
            build_layered_pre_eval_summary(
                factor_df,
                score_column="signal",
                labels_df=labels_df,
                layers_df=layers_df,
            )


if __name__ == "__main__":
    unittest.main()
