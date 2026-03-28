from __future__ import annotations

import unittest

import polars as pl

from factor_defs.order_lifecycle_churn import OUTPUT_COLUMN, compute_signal


class OrderLifecycleChurnTest(unittest.TestCase):
    def test_compute_signal_outputs_expected_columns(self) -> None:
        frame = pl.DataFrame(
            {
                "date": ["2026-03-13", "2026-03-13", "2026-03-13", "2026-03-13"],
                "instrument_key": ["00001", "00001", "00001", "00002"],
                "OrderId": [1, 1, 2, 3],
                "Price": [10.0, 10.0, 11.0, 5.0],
                "Volume": [100, 120, 200, 300],
            }
        ).lazy()
        result = compute_signal(frame).collect()
        self.assertEqual(result.height, 2)
        self.assertIn("order_event_count", result.columns)
        self.assertIn("unique_order_ids", result.columns)
        self.assertIn("churn_ratio", result.columns)
        self.assertIn(OUTPUT_COLUMN, result.columns)


if __name__ == "__main__":
    unittest.main()
