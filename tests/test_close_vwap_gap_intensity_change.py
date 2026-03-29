from __future__ import annotations

import unittest

import polars as pl

from factor_defs.close_vwap_gap_intensity_change import OUTPUT_COLUMN, compute_signal


class CloseVwapGapIntensityChangeTest(unittest.TestCase):
    def test_compute_signal_tracks_gap_change(self) -> None:
        frame = pl.DataFrame(
            {
                "date": [
                    "2026-03-12",
                    "2026-03-12",
                    "2026-03-12",
                    "2026-03-12",
                    "2026-03-13",
                    "2026-03-13",
                    "2026-03-13",
                    "2026-03-13",
                ],
                "instrument_key": ["00001", "00001", "00002", "00002", "00001", "00001", "00002", "00002"],
                "Time": [93000, 160000, 93000, 160000, 93000, 160000, 93000, 160000],
                "row_num_in_file": [1, 2, 1, 2, 1, 2, 1, 2],
                "Price": [10.0, 10.5, 10.0, 10.0, 10.0, 12.0, 10.0, 10.0],
                "Volume": [100, 100, 100, 100, 100, 100, 100, 100],
            }
        ).with_columns(pl.col("date").str.to_date()).lazy()
        result = compute_signal(
            frame,
            target_dates=["2026-03-13"],
            previous_date_map={"2026-03-13": "2026-03-12"},
        ).collect()
        self.assertEqual(result.height, 2)
        scores = {row["instrument_key"]: row[OUTPUT_COLUMN] for row in result.select(["instrument_key", OUTPUT_COLUMN]).to_dicts()}
        self.assertGreater(scores["00001"], scores["00002"])


if __name__ == "__main__":
    unittest.main()
