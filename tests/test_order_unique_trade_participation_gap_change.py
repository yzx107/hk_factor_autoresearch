from __future__ import annotations

import unittest

import polars as pl

from factor_defs.order_unique_trade_participation_gap_change import OUTPUT_COLUMN, compute_signal


class OrderUniqueTradeParticipationGapChangeTest(unittest.TestCase):
    def test_compute_signal_tracks_participation_gap_change(self) -> None:
        frame = pl.DataFrame(
            {
                "date": ["2026-03-12", "2026-03-12", "2026-03-13", "2026-03-13"],
                "instrument_key": ["00001", "00002", "00001", "00002"],
                "trade_count": [10, 10, 10, 10],
                "turnover": [1000.0, 1000.0, 1000.0, 1000.0],
                "total_order_notional": [1000.0, 1000.0, 1000.0, 1000.0],
                "order_event_count": [20, 20, 20, 20],
                "unique_order_ids": [10, 20, 40, 10],
                "churn_ratio": [2.0, 2.0, 2.0, 2.0],
                "close_like_price": [10.0, 10.0, 10.0, 10.0],
                "vwap": [10.0, 10.0, 10.0, 10.0],
                "instrument_key_source": ["file_derived_instrument_key"] * 4,
            }
        ).with_columns(pl.col("date").str.to_date()).lazy()
        result = compute_signal(
            frame,
            target_dates=["2026-03-13"],
            previous_date_map={"2026-03-13": "2026-03-12"},
        ).collect()
        scores = {row["instrument_key"]: row[OUTPUT_COLUMN] for row in result.select(["instrument_key", OUTPUT_COLUMN]).to_dicts()}
        self.assertGreater(scores["00001"], scores["00002"])


if __name__ == "__main__":
    unittest.main()
