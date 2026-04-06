from __future__ import annotations

import unittest

from evaluation.transfer_entropy import transfer_entropy
from harness.find_lead_factors import build_lead_factor_summary


class TransferEntropyTest(unittest.TestCase):
    def test_transfer_entropy_prefers_true_direction(self) -> None:
        source = [0.0, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0]
        target = [0.0] + source[:-1]

        forward = transfer_entropy(source, target, lag=1, bins=2)
        reverse = transfer_entropy(target, source, lag=1, bins=2)

        self.assertGreater(forward, reverse)

    def test_build_lead_factor_summary_ranks_larger_lead_gap_first(self) -> None:
        series_by_factor = {
            "leader": {
                "2026-01-01": 0.0,
                "2026-01-02": 1.0,
                "2026-01-03": 1.0,
                "2026-01-04": 0.0,
                "2026-01-05": 1.0,
                "2026-01-06": 0.0,
                "2026-01-07": 0.0,
                "2026-01-08": 1.0,
                "2026-01-09": 1.0,
                "2026-01-10": 0.0,
            },
            "follower": {
                "2026-01-01": 0.0,
                "2026-01-02": 0.0,
                "2026-01-03": 1.0,
                "2026-01-04": 1.0,
                "2026-01-05": 0.0,
                "2026-01-06": 1.0,
                "2026-01-07": 0.0,
                "2026-01-08": 0.0,
                "2026-01-09": 1.0,
                "2026-01-10": 1.0,
            },
        }

        summary = build_lead_factor_summary(
            series_by_factor,
            metric="rank_ic",
            lag=1,
            bins=2,
            min_overlap=6,
        )

        self.assertEqual(summary["ranked_edges"][0]["source_factor"], "leader")
        self.assertEqual(summary["ranked_edges"][0]["target_factor"], "follower")


if __name__ == "__main__":
    unittest.main()
