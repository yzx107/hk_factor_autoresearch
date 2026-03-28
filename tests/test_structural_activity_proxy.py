from __future__ import annotations

import unittest

import polars as pl

from factor_defs.structural_activity_proxy import compute_signal


class StructuralActivityProxyTest(unittest.TestCase):
    def test_compute_signal_groups_by_date_and_instrument_key(self) -> None:
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
        self.assertIn("structural_activity_score", result.columns)


if __name__ == "__main__":
    unittest.main()
