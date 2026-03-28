from __future__ import annotations

import unittest

import polars as pl

from factor_defs.avg_trade_notional_bias import OUTPUT_COLUMN, compute_signal


class AvgTradeNotionalBiasTest(unittest.TestCase):
    def test_compute_signal_outputs_expected_columns(self) -> None:
        frame = pl.DataFrame(
            {
                "date": ["2026-03-13", "2026-03-13", "2026-03-13"],
                "instrument_key": ["00001", "00001", "00002"],
                "Price": [10.0, 11.0, 5.0],
                "Volume": [100, 200, 300],
            }
        ).lazy()
        result = compute_signal(frame).collect()
        self.assertEqual(result.height, 2)
        self.assertIn("avg_trade_notional", result.columns)
        self.assertIn(OUTPUT_COLUMN, result.columns)


if __name__ == "__main__":
    unittest.main()
