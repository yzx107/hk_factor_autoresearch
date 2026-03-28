from __future__ import annotations

import unittest

import polars as pl

from evaluation.diagnostics import build_signal_diagnostics


class DiagnosticsTest(unittest.TestCase):
    def test_build_signal_diagnostics_returns_fixed_summary_shape(self) -> None:
        frame = pl.DataFrame(
            {
                "date": ["2026-03-13", "2026-03-13", "2026-03-14"],
                "instrument_key": ["00001", "00002", "00001"],
                "signal": [1.0, 2.0, -1.0],
            }
        )
        diagnostics = build_signal_diagnostics(frame, score_column="signal", top_n=1)
        self.assertEqual(diagnostics["row_count"], 3)
        self.assertEqual(diagnostics["date_count"], 2)
        self.assertEqual(diagnostics["distinct_instruments"], 2)
        self.assertEqual(len(diagnostics["per_date"]), 2)
        self.assertEqual(len(diagnostics["top_by_date"]), 2)
        self.assertEqual(len(diagnostics["bottom_by_date"]), 2)


if __name__ == "__main__":
    unittest.main()
