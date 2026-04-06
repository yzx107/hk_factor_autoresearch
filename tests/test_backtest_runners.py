from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import polars as pl

import harness.run_auto_triage as run_auto_triage_module
import harness.run_minimal_backtest as run_minimal_backtest_module
import harness.triage as triage_module


class BacktestRunnerTest(unittest.TestCase):
    def _sample_factor_frame(self) -> pl.DataFrame:
        return pl.DataFrame(
            {
                "date": [
                    "2026-01-02",
                    "2026-01-02",
                    "2026-01-02",
                    "2026-01-02",
                    "2026-01-03",
                    "2026-01-03",
                    "2026-01-03",
                    "2026-01-03",
                ],
                "instrument_key": ["A", "B", "C", "D", "A", "B", "C", "D"],
                "score": [4.0, 3.0, 2.0, 1.0, 1.0, 4.0, 2.0, 3.0],
            }
        )

    def _sample_label_frame(self) -> pl.DataFrame:
        return pl.DataFrame(
            {
                "date": [
                    "2026-01-02",
                    "2026-01-02",
                    "2026-01-02",
                    "2026-01-02",
                    "2026-01-03",
                    "2026-01-03",
                    "2026-01-03",
                    "2026-01-03",
                ],
                "instrument_key": ["A", "B", "C", "D", "A", "B", "C", "D"],
                "forward_return_1d_close_like": [0.08, 0.05, -0.01, -0.04, 0.02, 0.07, -0.02, -0.05],
            }
        )

    def test_minimal_backtest_runner_writes_summary_json(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_minimal_backtest_module.RUN_ROOT = tmp / "runs"

            run_dir = tmp / "factor_run"
            run_dir.mkdir(parents=True)
            self._sample_factor_frame().write_parquet(run_dir / "factor_output.parquet")
            (run_dir / "data_run_summary.json").write_text(
                json.dumps(
                    {
                        "factor_name": "demo_factor",
                        "score_column": "score",
                        "transform_name": "1d",
                        "target_instrument_universe": "stock_research_candidate",
                        "source_instrument_universe": "target_only",
                        "contains_cross_security_source": False,
                        "universe_filter_version": "stock_target_only_v1",
                        "factor_profile": {"family_name": "demo_family"},
                        "family_profile": {"family_name": "demo_family"},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            labels_path = tmp / "labels.parquet"
            self._sample_label_frame().write_parquet(labels_path)

            backtest_id, payload, summary_path = run_minimal_backtest_module.run_minimal_backtest_for_factor(
                run_dir=run_dir,
                labels_path=labels_path,
                top_fraction=0.25,
                cost_bps=5.0,
            )

            self.assertTrue(backtest_id.startswith("bt_"))
            self.assertTrue(summary_path.exists())
            self.assertEqual(payload["result"]["policy_version"], "minimal_backtest_lane_v1")
            self.assertEqual(payload["target_instrument_universe"], "stock_research_candidate")
            self.assertIn("spread_return", payload)
            self.assertIn("turnover_proxy", payload)

    def test_auto_triage_runner_shortlists_ready_candidate(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_auto_triage_module.ROOT = tmp
            run_minimal_backtest_module.RUN_ROOT = tmp / "runs"
            triage_module.REJECT_REASON_LOG = tmp / "registry" / "reject_reason_log.tsv"
            triage_module.FAMILY_PERFORMANCE_SUMMARY = tmp / "registry" / "family_performance_summary.tsv"

            run_dir = tmp / "factor_run"
            run_dir.mkdir(parents=True)
            self._sample_factor_frame().write_parquet(run_dir / "factor_output.parquet")
            (run_dir / "data_run_summary.json").write_text(
                json.dumps(
                    {
                        "factor_name": "demo_factor",
                        "module_name": "demo_factor",
                        "score_column": "score",
                        "transform_name": "1d",
                        "target_instrument_universe": "stock_research_candidate",
                        "source_instrument_universe": "target_only",
                        "contains_cross_security_source": False,
                        "universe_filter_version": "stock_target_only_v1",
                        "factor_profile": {"family_name": "demo_family"},
                        "family_profile": {"family_name": "demo_family"},
                        "dates": ["2026-01-02", "2026-01-03"],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            (run_dir / "factor_profile.json").write_text(
                json.dumps(
                    {
                        "factor_name": "demo_factor",
                        "factor_id": "demo_factor",
                        "family_name": "demo_family",
                        "target_universe_scope": "stock_research_candidate",
                        "source_universe_scope": "target_only",
                        "contains_cross_security_source": False,
                        "universe_filter_version": "stock_target_only_v1",
                        "contains_caveat_fields": False,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            (run_dir / "family_profile.json").write_text(
                json.dumps(
                    {
                        "family_name": "demo_family",
                        "mechanism_hypothesis": "demo mechanism",
                        "allowed_input_lane": "phase_a_core_only",
                        "current_best_variants": ["demo_factor"],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            labels_path = tmp / "labels.parquet"
            self._sample_label_frame().write_parquet(labels_path)

            scoreboard_path = tmp / "scoreboard_summary.json"
            scoreboard_path.write_text(
                json.dumps(
                    {
                        "scoreboard_id": "board_demo",
                        "factor_board": [
                            {
                                "factor_name": "demo_factor",
                                "factor_family": "demo_family",
                                "run_dir": str(run_dir),
                                "score_column": "score",
                                "pre_eval_id": "pre_demo",
                                "mean_rank_ic": 0.08,
                                "mean_abs_rank_ic": 0.08,
                                "mean_nmi": 0.02,
                                "mean_coverage_ratio": 1.0,
                                "mi_significant_date_ratio": 1.0,
                                "mean_mi_p_value": 0.01,
                                "mean_abs_baseline_corr": 0.1,
                                "sign_consistency": 1.0,
                                "entropy_regime_summary": [
                                    {"slice_value": "low", "mean_abs_rank_ic": 0.03},
                                    {"slice_value": "mid", "mean_abs_rank_ic": 0.04},
                                    {"slice_value": "high", "mean_abs_rank_ic": 0.05},
                                ],
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            triage_id, payload, summary_path = run_auto_triage_module.run_auto_triage(
                scoreboard_summary_path=scoreboard_path,
                labels_path=labels_path,
                notes="demo",
            )

            self.assertTrue(triage_id.startswith("triage_"))
            self.assertTrue(summary_path.exists())
            self.assertEqual(payload["candidate_count"], 1)
            self.assertEqual(len(payload["shortlisted_candidates"]), 1)
            self.assertEqual(payload["rejected_candidates"], [])
            self.assertTrue(payload["recommended_next_batch_directions"])


if __name__ == "__main__":
    unittest.main()
