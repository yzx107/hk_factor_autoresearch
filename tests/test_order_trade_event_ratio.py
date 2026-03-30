from __future__ import annotations

import unittest

import polars as pl

from factor_defs.order_trade_event_ratio import OUTPUT_COLUMN, compute_signal


class OrderTradeEventRatioTest(unittest.TestCase):
    def test_compute_signal_prefers_higher_order_pressure(self) -> None:
        frame = pl.DataFrame(
            {
                "date": ["2026-03-13", "2026-03-13"],
                "instrument_key": ["00001", "00002"],
                "trade_count": [10, 20],
                "turnover": [1000.0, 2000.0],
                "total_order_notional": [1500.0, 1800.0],
                "order_event_count": [120, 25],
                "unique_order_ids": [40, 20],
                "churn_ratio": [3.0, 1.25],
                "instrument_key_source": ["file_derived_instrument_key", "file_derived_instrument_key"],
            }
        ).with_columns(pl.col("date").str.to_date()).lazy()
        result = compute_signal(frame).collect()
        self.assertEqual(result.height, 2)
        scores = {
            row["instrument_key"]: row[OUTPUT_COLUMN]
            for row in result.select(["instrument_key", OUTPUT_COLUMN]).to_dicts()
        }
        self.assertGreater(scores["00001"], scores["00002"])


if __name__ == "__main__":
    unittest.main()
