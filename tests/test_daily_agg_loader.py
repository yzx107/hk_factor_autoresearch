from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import polars as pl

from harness.daily_agg import load_daily_agg_lazy


class DailyAggLoaderTest(unittest.TestCase):
    def test_load_daily_agg_lazy_filters_target_universe(self) -> None:
        with TemporaryDirectory() as tmpdir:
            data_path = Path(tmpdir) / "daily.parquet"
            profile_path = Path(tmpdir) / "instrument_profile.parquet"
            pl.DataFrame(
                {
                    "date": ["2026-03-13", "2026-03-13"],
                    "instrument_key": ["00001", "00002"],
                    "close_like_price": [10.0, 20.0],
                }
            ).write_parquet(data_path)
            pl.DataFrame(
                {
                    "instrument_key": ["00002"],
                    "stock_research_candidate": [True],
                }
            ).write_parquet(profile_path)

            with (
                patch("harness.daily_agg.build_daily_agg_paths", return_value=[data_path]),
                patch("harness.instrument_universe.INSTRUMENT_PROFILE_PATH", profile_path),
            ):
                out = load_daily_agg_lazy(
                    "verified_trades_daily",
                    ["2026-03-13"],
                    ["date", "close_like_price"],
                    target_instrument_universe="stock_research_candidate",
                ).collect()

        self.assertEqual(out.columns, ["date", "close_like_price"])
        self.assertEqual(out.to_dicts(), [{"date": "2026-03-13", "close_like_price": 20.0}])
