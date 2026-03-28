from __future__ import annotations

import unittest

import polars as pl

from factor_defs.close_vwap_gap_intensity import OUTPUT_COLUMN, compute_signal


class CloseVwapGapIntensityTest(unittest.TestCase):
    def test_compute_signal_uses_last_price_vs_vwap(self) -> None:
        trades = pl.DataFrame(
            {
                "date": ["2026-03-13", "2026-03-13", "2026-03-13", "2026-03-13"],
                "source_file": ["trade/00001.csv", "trade/00001.csv", "trade/00002.csv", "trade/00002.csv"],
                "instrument_key": ["00001", "00001", "00002", "00002"],
                "Time": [93000, 160000, 93000, 160000],
                "row_num_in_file": [1, 2, 1, 2],
                "Price": [10.0, 11.0, 20.0, 19.0],
                "Volume": [100, 100, 100, 100],
            }
        ).lazy()

        signal = compute_signal(trades).collect()
        self.assertEqual(signal.height, 2)
        scores = {
            row["instrument_key"]: row[OUTPUT_COLUMN]
            for row in signal.select(["instrument_key", OUTPUT_COLUMN]).to_dicts()
        }
        self.assertGreater(scores["00001"], 0.0)
        self.assertLess(scores["00002"], 0.0)


if __name__ == "__main__":
    unittest.main()
