from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import polars as pl

from harness.instrument_universe import (
    apply_target_instrument_universe_filter,
    load_target_instrument_universe_lazy,
)


class InstrumentUniverseTest(unittest.TestCase):
    def test_apply_target_instrument_universe_filter_keeps_only_allowed_rows(self) -> None:
        frame = pl.DataFrame(
            {
                "instrument_key": ["00001", "00002", "00003"],
                "value": [1.0, 2.0, 3.0],
            }
        ).lazy()
        allowed = pl.DataFrame({"instrument_key": ["00002"]}).lazy()

        out = apply_target_instrument_universe_filter(
            frame,
            target_instrument_universe="stock_research_candidate",
            allowed_instruments=allowed,
        ).collect()

        self.assertEqual(out.to_dicts(), [{"instrument_key": "00002", "value": 2.0}])

    def test_load_target_instrument_universe_lazy_reads_sidecar(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "instrument_profile.parquet"
            pl.DataFrame(
                {
                    "instrument_key": ["00001", "00002", "00003"],
                    "stock_research_candidate": [True, False, True],
                }
            ).write_parquet(path)
            with patch("harness.instrument_universe.INSTRUMENT_PROFILE_PATH", path):
                out = load_target_instrument_universe_lazy("stock_research_candidate").collect()

        self.assertEqual(out["instrument_key"].to_list(), ["00001", "00003"])
