from __future__ import annotations

from pathlib import Path
import unittest

from harness.verified_reader import build_partition_paths, next_available_dates


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


if __name__ == "__main__":
    unittest.main()
