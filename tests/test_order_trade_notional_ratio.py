from __future__ import annotations

import unittest

import polars as pl

from factor_defs.order_trade_notional_ratio import OUTPUT_COLUMN, compute_signal


class OrderTradeNotionalRatioTest(unittest.TestCase):
    def test_compute_signal_prefers_higher_order_notional_pressure(self) -> None:
        frame = pl.DataFrame(
            {
                "date": ["2026-03-13", "2026-03-13"],
                "instrument_key": ["00001", "00002"],
                "trade_count": [10, 10],
                "turnover": [1000.0, 2000.0],
                "total_order_notional": [4000.0, 2500.0],
                "order_event_count": [20, 20],
                "unique_order_ids": [10, 10],
                "churn_ratio": [2.0, 2.0],
                "instrument_key_source": ["file_derived_instrument_key", "file_derived_instrument_key"],
            }
        ).with_columns(pl.col("date").str.to_date()).lazy()
        result = compute_signal(frame).collect()
        scores = {
            row["instrument_key"]: row[OUTPUT_COLUMN]
            for row in result.select(["instrument_key", OUTPUT_COLUMN]).to_dicts()
        }
        self.assertGreater(scores["00001"], scores["00002"])


if __name__ == "__main__":
    unittest.main()
