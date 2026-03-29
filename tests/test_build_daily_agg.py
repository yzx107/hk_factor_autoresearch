from __future__ import annotations

import unittest

import polars as pl

from harness.build_daily_agg import build_orders_daily_agg, build_trades_daily_agg


class BuildDailyAggTest(unittest.TestCase):
    def test_build_trades_daily_agg(self) -> None:
        trades = pl.DataFrame(
            {
                "date": ["2026-03-13", "2026-03-13", "2026-03-13"],
                "source_file": ["trade/00001.csv", "trade/00001.csv", "trade/00002.csv"],
                "instrument_key": ["00001", "00001", "00002"],
                "Time": [93000, 93100, 93200],
                "Price": [10.0, 11.0, 20.0],
                "Volume": [100, 200, 300],
                "row_num_in_file": [1, 2, 1],
            }
        ).lazy()

        out = build_trades_daily_agg(trades)
        rows = out.to_dicts()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["instrument_key"], "00001")
        self.assertEqual(rows[0]["trade_count"], 2)
        self.assertAlmostEqual(rows[0]["turnover"], 3200.0)
        self.assertAlmostEqual(rows[0]["share_volume"], 300.0)
        self.assertAlmostEqual(rows[0]["avg_trade_size"], 150.0)
        self.assertAlmostEqual(rows[0]["close_like_price"], 11.0)
        self.assertAlmostEqual(rows[0]["vwap"], 3200.0 / 300.0)

    def test_build_orders_daily_agg(self) -> None:
        orders = pl.DataFrame(
            {
                "date": ["2026-03-13", "2026-03-13", "2026-03-13"],
                "source_file": ["order/00001.csv", "order/00001.csv", "order/00002.csv"],
                "instrument_key": ["00001", "00001", "00002"],
                "OrderId": [1, 1, 2],
                "Price": [10.0, 11.0, 20.0],
                "Volume": [100, 200, 300],
            }
        ).lazy()

        out = build_orders_daily_agg(orders)
        rows = out.to_dicts()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["instrument_key"], "00001")
        self.assertEqual(rows[0]["order_event_count"], 2)
        self.assertEqual(rows[0]["unique_order_ids"], 1)
        self.assertAlmostEqual(rows[0]["total_order_notional"], 3200.0)
        self.assertAlmostEqual(rows[0]["churn_ratio"], 2.0)


if __name__ == "__main__":
    unittest.main()
