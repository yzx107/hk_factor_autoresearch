from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import polars as pl

from harness.verified_reader import (
    build_partition_paths,
    load_verified_lazy,
    next_available_dates,
    previous_available_dates,
)


class VerifiedReaderTest(unittest.TestCase):
    def test_build_partition_paths_for_real_2026_partition(self) -> None:
        paths = build_partition_paths("verified_trades", ["2026-03-13"])
        self.assertEqual(len(paths), 1)
        self.assertIsInstance(paths[0], Path)
        self.assertTrue(paths[0].exists())

    def test_next_available_dates_uses_verified_manifest_order(self) -> None:
        mapping = next_available_dates("verified_trades", ["2026-01-05", "2026-03-13"])
        self.assertEqual(mapping["2026-01-05"], "2026-01-06")
        if "2026-03-13" in mapping:
            self.assertGreater(mapping["2026-03-13"], "2026-03-13")

    def test_previous_available_dates_uses_verified_order(self) -> None:
        mapping = previous_available_dates("verified_trades", ["2026-01-05", "2026-03-13"])
        self.assertEqual(mapping["2026-01-05"], "2026-01-02")
        self.assertIn("2026-03-13", mapping)
        self.assertLess(mapping["2026-03-13"], "2026-03-13")

    def test_load_verified_lazy_filters_target_universe(self) -> None:
        with TemporaryDirectory() as tmpdir:
            data_path = Path(tmpdir) / "verified.parquet"
            profile_path = Path(tmpdir) / "instrument_profile.parquet"
            pl.DataFrame(
                {
                    "date": ["2026-03-13", "2026-03-13"],
                    "source_file": ["trade/00001.csv", "trade/00002.csv"],
                    "Price": [10.0, 20.0],
                }
            ).write_parquet(data_path)
            pl.DataFrame(
                {
                    "instrument_key": ["00002"],
                    "stock_research_candidate": [True],
                }
            ).write_parquet(profile_path)

            with (
                patch("harness.verified_reader.build_partition_paths", return_value=[data_path]),
                patch("harness.instrument_universe.INSTRUMENT_PROFILE_PATH", profile_path),
            ):
                out = load_verified_lazy(
                    "verified_trades",
                    ["2026-03-13"],
                    ["date", "Price"],
                    target_instrument_universe="stock_research_candidate",
                ).collect()

        self.assertEqual(out.columns, ["date", "Price", "instrument_key"])
        self.assertEqual(out.to_dicts(), [{"date": "2026-03-13", "Price": 20.0, "instrument_key": "00002"}])


if __name__ == "__main__":
    unittest.main()
