from __future__ import annotations

import unittest

import polars as pl

from evaluation.pre_eval import LABEL_NAME, build_forward_return_labels, build_pre_eval_summary


class PreEvalTest(unittest.TestCase):
    def test_build_forward_return_labels_joins_current_and_next_close_like(self) -> None:
        close_like = pl.DataFrame(
            {
                "date": ["2026-01-05", "2026-01-05", "2026-01-06", "2026-01-06"],
                "instrument_key": ["00001", "00002", "00001", "00002"],
                "close_like_price": [10.0, 20.0, 11.0, 18.0],
            }
        ).with_columns(pl.col("date").str.to_date())

        labels = build_forward_return_labels(
            close_like,
            next_date_map={"2026-01-05": "2026-01-06"},
        )

        self.assertEqual(labels.height, 2)
        returns = {
            row["instrument_key"]: row[LABEL_NAME]
            for row in labels.select(["instrument_key", LABEL_NAME]).to_dicts()
        }
        self.assertAlmostEqual(returns["00001"], 0.1)
        self.assertAlmostEqual(returns["00002"], -0.1)

    def test_build_pre_eval_summary_reports_rank_ic_and_spread(self) -> None:
        factor_df = pl.DataFrame(
            {
                "date": ["2026-01-05", "2026-01-05", "2026-01-05", "2026-01-05"],
                "instrument_key": ["00001", "00002", "00003", "00004"],
                "signal": [4.0, 3.0, 2.0, 1.0],
            }
        ).with_columns(pl.col("date").str.to_date())

        labels_df = pl.DataFrame(
            {
                "date": ["2026-01-05", "2026-01-05", "2026-01-05", "2026-01-05"],
                "next_date": ["2026-01-06", "2026-01-06", "2026-01-06", "2026-01-06"],
                "instrument_key": ["00001", "00002", "00003", "00004"],
                LABEL_NAME: [0.4, 0.3, 0.2, 0.1],
                "label_source": ["test_source"] * 4,
            }
        ).with_columns([pl.col("date").str.to_date(), pl.col("next_date").str.to_date()])

        summary = build_pre_eval_summary(
            factor_df,
            score_column="signal",
            labels_df=labels_df,
            label_column=LABEL_NAME,
            top_fraction=0.25,
        )

        self.assertEqual(summary["joined_rows"], 4)
        self.assertEqual(summary["labeled_dates"], ["2026-01-05"])
        self.assertEqual(summary["skipped_dates"], [])
        self.assertAlmostEqual(summary["mean_rank_ic"], 1.0)
        self.assertAlmostEqual(summary["mean_abs_rank_ic"], 1.0)
        self.assertGreater(summary["mean_top_bottom_spread"], 0.0)
        self.assertEqual(len(summary["per_date"]), 1)


if __name__ == "__main__":
    unittest.main()
