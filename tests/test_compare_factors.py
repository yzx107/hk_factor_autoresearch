from __future__ import annotations

import unittest

import polars as pl


class CompareFactorsTest(unittest.TestCase):
    def test_overlap_join_shape_for_comparable_outputs(self) -> None:
        left = pl.DataFrame(
            {
                "date": ["2026-03-13", "2026-03-13", "2026-03-14"],
                "instrument_key": ["00001", "00002", "00001"],
                "left_score": [1.0, 2.0, 3.0],
            }
        )
        right = pl.DataFrame(
            {
                "date": ["2026-03-13", "2026-03-13", "2026-03-14"],
                "instrument_key": ["00001", "00002", "00001"],
                "right_score": [1.5, 2.5, 2.0],
            }
        )
        joined = left.join(right, on=["date", "instrument_key"], how="inner")
        self.assertEqual(joined.height, 3)
        corr = joined.group_by("date").agg(pl.corr("left_score", "right_score").alias("corr"))
        self.assertEqual(corr.height, 2)


if __name__ == "__main__":
    unittest.main()
