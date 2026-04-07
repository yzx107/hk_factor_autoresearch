from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import harness.scoreboard as scoreboard_module
from harness.instrument_universe import UNIVERSE_FILTER_VERSION
from harness.scoreboard import _pre_eval_row


class ScoreboardTest(unittest.TestCase):
    def test_scoreboard_payload_shape(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            payload = {
                "scoreboard_id": "score_x",
                "factor_count": 2,
                "comparison_count": 1,
                "missing_comparisons": [],
            }
            path = tmp / "scoreboard_summary.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["factor_count"], 2)
            self.assertEqual(loaded["comparison_count"], 1)

    def test_pre_eval_row_prefers_aggregate_metrics_and_entropy_slice_summary(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            summary_path = tmp / "pre_eval_summary.json"
            summary_path.write_text(
                json.dumps(
                    {
                        "label_name": "forward_return_1d_close_like",
                        "labeled_dates": ["2026-03-13"],
                        "skipped_dates": [],
                        "joined_rows": 10,
                        "aggregate_metrics": {
                            "rank_ic": 0.02,
                            "abs_rank_ic": 0.12,
                            "mi": 0.01,
                            "nmi": 0.03,
                            "nmi_ic_gap": 0.01,
                            "mi_p_value": 0.04,
                            "mi_significant_date_ratio": 1.0,
                            "top_bottom_spread": 0.01,
                            "coverage_ratio": 1.0,
                        },
                        "mean_rank_ic": 999.0,
                        "mean_abs_rank_ic": 999.0,
                        "mean_mutual_info": 999.0,
                        "mean_normalized_mutual_info": 999.0,
                        "mean_top_bottom_spread": 999.0,
                        "mean_coverage_ratio": 999.0,
                        "per_date": [
                            {"date": "2026-03-13", "rank_ic": 0.02},
                            {"date": "2026-03-14", "rank_ic": 0.01},
                        ],
                        "regime_metadata": {"label_mode": "descriptive_only"},
                        "regime_slices": {
                            "entropy_quantile": [
                                {"slice_value": "q1_low_entropy", "mean_abs_rank_ic": 0.12, "mean_nmi": 0.03},
                                {"slice_value": "q3_high_entropy", "mean_abs_rank_ic": 0.04, "mean_nmi": 0.01},
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            row = _pre_eval_row(
                {
                    "pre_eval_id": "pre_x",
                    "experiment_id": "exp_x",
                    "factor_name": "f1",
                    "summary_path": str(summary_path),
                }
            )
            assert row is not None
            self.assertAlmostEqual(row["mean_nmi"], 0.03)
            self.assertAlmostEqual(row["mean_abs_rank_ic"], 0.12)
            self.assertAlmostEqual(row["mean_nmi_ic_gap"], 0.01)
            self.assertAlmostEqual(row["mi_significant_date_ratio"], 1.0)
            self.assertAlmostEqual(row["entropy_regime_dispersion"], 0.08)
            self.assertEqual(row["entropy_regime_strongest_slice"], "q1_low_entropy")
            self.assertAlmostEqual(row["sign_consistency"], 1.0)

    def test_build_scoreboard_materializes_baseline_comparison_for_default_baseline_set(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_root = tmp / "runs"
            registry = tmp / "registry"
            registry.mkdir(parents=True)
            run_root.mkdir(parents=True)

            original_experiment_log = scoreboard_module.EXPERIMENT_LOG
            original_pre_eval_log = scoreboard_module.PRE_EVAL_LOG
            original_comparison_log = scoreboard_module.COMPARISON_LOG
            original_scoreboard_log = scoreboard_module.SCOREBOARD_LOG
            original_run_root = scoreboard_module.RUN_ROOT
            original_load_baseline_registry = scoreboard_module.load_baseline_registry
            original_run_factor_comparison = scoreboard_module.run_factor_comparison

            try:
                scoreboard_module.EXPERIMENT_LOG = registry / "experiment_log.tsv"
                scoreboard_module.PRE_EVAL_LOG = registry / "pre_eval_log.tsv"
                scoreboard_module.COMPARISON_LOG = registry / "comparison_log.tsv"
                scoreboard_module.SCOREBOARD_LOG = registry / "scoreboard_log.tsv"
                scoreboard_module.RUN_ROOT = run_root

                candidate_run = run_root / "candidate_run"
                baseline_run = run_root / "baseline_run"
                candidate_run.mkdir(parents=True)
                baseline_run.mkdir(parents=True)

                def _write_run_artifacts(run_dir: Path, *, factor_name: str, family_name: str) -> None:
                    (run_dir / "data_run_summary.json").write_text(
                        json.dumps(
                            {
                                "module_name": factor_name,
                                "transform_name": "level",
                                "target_instrument_universe": "stock_research_candidate",
                                "source_instrument_universe": "target_only",
                                "contains_cross_security_source": False,
                                "universe_filter_version": UNIVERSE_FILTER_VERSION,
                                "table_name": "verified_trades_daily",
                                "score_column": "score",
                                "dates": ["2026-03-13"],
                                "output_rows": 8,
                                "factor_profile": {
                                    "factor_name": factor_name,
                                    "factor_id": f"{factor_name}_v1",
                                    "family_name": family_name,
                                    "mechanism_hypothesis": "demo mechanism",
                                    "target_universe_scope": "stock_research_candidate",
                                    "source_universe_scope": "target_only",
                                    "required_data_lane": "phase_a_core_only",
                                    "required_year_grade": ["2026"],
                                    "time_grade_requirement": "level",
                                    "contains_caveat_fields": False,
                                    "supports_default_lane": True,
                                    "supports_extension_lane": False,
                                    "label_definition": "forward_return_1d_close_like",
                                    "evaluation_horizons": ["1d"],
                                    "known_failure_modes": [],
                                    "baseline_comparators": ["structural_activity_proxy"],
                                    "requires_cross_security_mapping": False,
                                    "contains_cross_security_source": False,
                                    "universe_filter_version": UNIVERSE_FILTER_VERSION,
                                },
                                "family_profile": {
                                    "family_name": family_name,
                                    "mechanism_hypothesis": "demo mechanism",
                                    "allowed_input_lane": "phase_a_core_only",
                                    "current_best_variants": [factor_name],
                                    "redundancy_pattern": "demo",
                                    "regime_sensitivity": ["entropy_quantile"],
                                    "whether_to_expand_further": "selective",
                                },
                                "data_source_mode": "phase_a_core_only",
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    (run_dir / "diagnostics_summary.json").write_text(
                        json.dumps(
                            {
                                "distinct_instruments": 4,
                                "overall_score_summary": {
                                    "mean": 0.0,
                                    "min": -1.0,
                                    "max": 1.0,
                                },
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    (run_dir / "factor_profile.json").write_text(
                        json.dumps(
                            {
                                "factor_name": factor_name,
                                "factor_id": f"{factor_name}_v1",
                                "family_name": family_name,
                                "mechanism_hypothesis": "demo mechanism",
                                "target_universe_scope": "stock_research_candidate",
                                "source_universe_scope": "target_only",
                                "required_data_lane": "phase_a_core_only",
                                "required_year_grade": ["2026"],
                                "time_grade_requirement": "level",
                                "contains_caveat_fields": False,
                                "supports_default_lane": True,
                                "supports_extension_lane": False,
                                "label_definition": "forward_return_1d_close_like",
                                "evaluation_horizons": ["1d"],
                                "known_failure_modes": [],
                                "baseline_comparators": ["structural_activity_proxy"],
                                "requires_cross_security_mapping": False,
                                "contains_cross_security_source": False,
                                "universe_filter_version": UNIVERSE_FILTER_VERSION,
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    (run_dir / "family_profile.json").write_text(
                        json.dumps(
                            {
                                "family_name": family_name,
                                "mechanism_hypothesis": "demo mechanism",
                                "allowed_input_lane": "phase_a_core_only",
                                "current_best_variants": [factor_name],
                                "redundancy_pattern": "demo",
                                "regime_sensitivity": ["entropy_quantile"],
                                "whether_to_expand_further": "selective",
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )

                _write_run_artifacts(
                    candidate_run,
                    factor_name="order_unique_trade_participation_gap",
                    family_name="order_trade_interaction_pressure",
                )
                _write_run_artifacts(
                    baseline_run,
                    factor_name="structural_activity_proxy",
                    family_name="activity_pressure",
                )

                scoreboard_module.EXPERIMENT_LOG.write_text(
                    "\n".join(
                        [
                            "experiment_id\tcreated_at\tfactor_name\trun_dir\tnotes",
                            "\t".join(
                                [
                                    "exp_candidate",
                                    "2026-04-07T00:00:00+00:00",
                                    "order_unique_trade_participation_gap",
                                    str(candidate_run),
                                    "demo",
                                ]
                            ),
                            "\t".join(
                                [
                                    "exp_baseline",
                                    "2026-04-07T00:00:01+00:00",
                                    "structural_activity_proxy",
                                    str(baseline_run),
                                    "demo",
                                ]
                            ),
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
                scoreboard_module.PRE_EVAL_LOG.write_text(
                    "\n".join(
                        [
                            "pre_eval_id\tcreated_at\texperiment_id\tfactor_name\tsummary_path\tnotes",
                            "\t".join(
                                [
                                    "pre_candidate",
                                    "2026-04-07T00:00:02+00:00",
                                    "exp_candidate",
                                    "order_unique_trade_participation_gap",
                                    str(tmp / "pre_eval_summary.json"),
                                    "demo",
                                ]
                            ),
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
                (tmp / "pre_eval_summary.json").write_text(
                    json.dumps(
                        {
                            "label_name": "forward_return_1d_close_like",
                            "labeled_dates": ["2026-03-13"],
                            "skipped_dates": [],
                            "joined_rows": 10,
                            "aggregate_metrics": {
                                "rank_ic": 0.05,
                                "abs_rank_ic": 0.05,
                                "nmi": 0.02,
                                "mi_p_value": 0.01,
                                "mi_significant_date_ratio": 1.0,
                                "top_bottom_spread": 0.01,
                                "coverage_ratio": 1.0,
                            },
                            "per_date": [{"date": "2026-03-13", "rank_ic": 0.05}],
                            "regime_metadata": {"label_mode": "descriptive_only"},
                            "regime_slices": {},
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                scoreboard_module.COMPARISON_LOG.write_text(
                    "comparison_id\tcreated_at\tleft_experiment_id\tright_experiment_id\tleft_factor\tright_factor\tcommon_dates\tcommon_rows\tsummary_path\tnotes\n",
                    encoding="utf-8",
                )

                scoreboard_module.load_baseline_registry = lambda: {
                    "default_baselines": ["structural_activity_proxy"],
                    "groups": {},
                }
                comparison_calls: list[tuple[str, str, str, str, str]] = []

                def _fake_run_factor_comparison(
                    *,
                    left_factor: str,
                    right_factor: str,
                    left_experiment: str = "",
                    right_experiment: str = "",
                    top_n: int = 20,
                    notes: str = "",
                ) -> tuple[str, dict[str, object], Path]:
                    comparison_calls.append((left_factor, right_factor, left_experiment, right_experiment, notes))
                    payload = {
                        "comparison_id": "cmp_demo",
                        "left": {"factor_name": left_factor, "score_column": "score"},
                        "right": {"factor_name": right_factor, "score_column": "score"},
                        "common_dates": ["2026-03-13"],
                        "common_rows": 10,
                        "per_date": [
                            {
                                "date": "2026-03-13",
                                "common_rows": 10,
                                "pearson_corr": 0.42,
                            }
                        ],
                        "top_overlap": [{"date": "2026-03-13", "top_overlap_count": 3}],
                    }
                    summary_path = tmp / "cmp_demo.json"
                    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                    return "cmp_demo", payload, summary_path

                scoreboard_module.run_factor_comparison = _fake_run_factor_comparison

                _, payload, _ = scoreboard_module.build_scoreboard(
                    ["order_unique_trade_participation_gap"],
                    notes="demo",
                )

                self.assertEqual(len(comparison_calls), 1)
                self.assertEqual(payload["baseline_comparison_count"], 1)
                self.assertEqual(payload["missing_baseline_comparisons"], [])
                self.assertAlmostEqual(payload["factor_board"][0]["baseline_redundancy_score"], 0.42)
            finally:
                scoreboard_module.EXPERIMENT_LOG = original_experiment_log
                scoreboard_module.PRE_EVAL_LOG = original_pre_eval_log
                scoreboard_module.COMPARISON_LOG = original_comparison_log
                scoreboard_module.SCOREBOARD_LOG = original_scoreboard_log
                scoreboard_module.RUN_ROOT = original_run_root
                scoreboard_module.load_baseline_registry = original_load_baseline_registry
                scoreboard_module.run_factor_comparison = original_run_factor_comparison


if __name__ == "__main__":
    unittest.main()
