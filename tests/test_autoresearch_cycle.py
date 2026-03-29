from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from harness.autoresearch_cycle import SelectionPolicy, _recommendation, load_cycle_config


class AutoresearchCycleTest(unittest.TestCase):
    def test_load_cycle_config_reads_candidates(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cycle.toml"
            path.write_text(
                'version = "v1"\n'
                'name = "cycle"\n'
                'owner = "agent"\n'
                'anchor_dates = ["2026-01-05"]\n'
                "\n"
                "[selection]\n"
                "min_abs_rank_ic_keep = 0.05\n"
                "min_abs_rank_ic_review = 0.02\n"
                "max_mean_abs_peer_corr = 0.50\n"
                "\n"
                "[[candidates]]\n"
                'factor = "f1"\n'
                'card = "research_cards/examples/sample.md"\n',
                encoding="utf-8",
            )
            config = load_cycle_config(path)
            self.assertEqual(config.version, "v1")
            self.assertEqual(config.candidates[0].factor_name, "f1")
            self.assertEqual(config.anchor_dates, ("2026-01-05",))

    def test_recommendation_flags_negative_ic_as_inverse_candidate(self) -> None:
        action, reason = _recommendation(
            {
                "mean_rank_ic": -0.08,
                "mean_abs_rank_ic": 0.08,
                "mean_abs_peer_corr": 0.10,
            },
            SelectionPolicy(
                min_abs_rank_ic_keep=0.05,
                min_abs_rank_ic_review=0.02,
                max_mean_abs_peer_corr=0.50,
            ),
        )
        self.assertEqual(action, "consider_inverse")
        self.assertIn("negative", reason)


if __name__ == "__main__":
    unittest.main()
