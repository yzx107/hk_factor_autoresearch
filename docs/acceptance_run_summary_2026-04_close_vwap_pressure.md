# Acceptance Run Summary (2026-04, Second Family: close_vwap_pressure)

## Judgment

`yes`

当前这套 `hk_factor_autoresearch` 在第二个 non-extension family 上也完成了真实闭环确认：

`candidate selection -> verified factor run -> pre-eval -> scoreboard -> auto-triage -> minimal backtest`

这次判断可以升到 `yes`，原因是：
- 默认股票主线在第二个 family 上仍然干净，未出现 universe 污染
- `factor_profile.json` / `family_profile.json` / `data_run_summary.json` 在真实 run 中完整落盘
- repaired `sign-aware readiness` 在 `close_vwap_pressure` 这个容易 sign-flip 的 family 上仍然有效
- `baseline redundancy` 在 challenger 候选上稳定落盘，不再只在上一轮 family 上成立
- minimal backtest 与 pre-eval / triage 叙事一致，没有出现“scoreboard 看起来 ready，但 backtest 完全反着来”的失配

本次 confirmation 依赖一个最小必要修复：
- `registry/lineage.json` 的容错读取与自愈写回
- 这个修复是为了恢复 append-only registry 的可写状态，不属于 scope 扩张

## Run Scope

- confirmation family: `close_vwap_pressure`
- why this family:
  - 与第一轮 `order_trade_interaction_pressure` 机制明显不同
  - 是默认 `phase_a_core`、`stock_research_candidate`、`target_only` 主线 family
  - family metadata 明确写了“方向可能反向，容易需要 sign flip”，适合验证 repaired `sign-aware readiness`
- selected candidates:
  - `close_vwap_gap_intensity`
  - `close_vwap_gap_intensity_change`
- target universe: `stock_research_candidate`
- source universe: `target_only`
- contains_cross_security_source: `false`
- excluded from this confirmation:
  - transfer entropy
  - cross-security source lane
  - extension-lane routing

## Executed Steps

1. Environment and input readiness
   - `python3 harness/bootstrap_universe.py`
   - reused shared labels: `runs/labels_2026_20260407T054938Z/forward_labels.parquet`
2. Candidate selection
   - selected the two existing family variants already tracked in repo
   - no new prototype generation was needed because this task was confirmation, not candidate expansion
3. Verified factor runs
   - `python3 harness/run_verified_factor.py --card research_cards/examples/close_vwap_gap_intensity_2026.md --factor close_vwap_gap_intensity --dates 2026-01-05 2026-02-24 2026-03-13 --notes "second-family confirmation close_vwap level"`
   - `python3 harness/run_verified_factor.py --card research_cards/examples/close_vwap_gap_intensity_change_2026.md --factor close_vwap_gap_intensity_change --dates 2026-01-05 2026-02-24 2026-03-13 --notes "second-family confirmation close_vwap change"`
4. Fixed pre-eval
   - `python3 harness/run_pre_eval.py --factor close_vwap_gap_intensity --experiment exp_20260407T064104Z_rc_20260329_close_vwap_gap_intensity_2026 --labels-path runs/labels_2026_20260407T054938Z/forward_labels.parquet --notes "second-family confirmation close_vwap level pre-eval"`
   - `python3 harness/run_pre_eval.py --factor close_vwap_gap_intensity_change --experiment exp_20260407T064104Z_rc_20260329_close_vwap_gap_intensity_change_2026 --labels-path runs/labels_2026_20260407T054938Z/forward_labels.parquet --notes "second-family confirmation close_vwap change pre-eval"`
5. Scoreboard
   - `python3 harness/scoreboard.py --factors close_vwap_gap_intensity close_vwap_gap_intensity_change --notes "second-family confirmation close_vwap scoreboard"`
6. Auto-triage
   - `python3 harness/run_auto_triage.py --scoreboard-summary runs/score_20260407T064127Z/scoreboard_summary.json --labels-path runs/labels_2026_20260407T054938Z/forward_labels.parquet --notes "second-family confirmation close_vwap triage"`
7. Minimal backtest sanity checks
   - `python3 harness/run_minimal_backtest.py --run-dir runs/exp_20260407T064104Z_rc_20260329_close_vwap_gap_intensity_2026 --labels-path runs/labels_2026_20260407T054938Z/forward_labels.parquet --notes "second-family confirmation close_vwap level backtest"`
   - `python3 harness/run_minimal_backtest.py --run-dir runs/exp_20260407T064104Z_rc_20260329_close_vwap_gap_intensity_change_2026 --labels-path runs/labels_2026_20260407T054938Z/forward_labels.parquet --notes "second-family confirmation close_vwap change backtest"`

## Key Artifacts

Primary confirmation artifacts:
- scoreboard summary: `runs/score_20260407T064127Z/scoreboard_summary.json`
- scoreboard report: `runs/score_20260407T064127Z/scoreboard_report.md`
- triage summary: `runs/triage_20260407T064137Z_score_20260407T064127Z/triage_summary.json`
- triage report: `runs/triage_20260407T064137Z_score_20260407T064127Z/triage_report.md`
- minimal backtest summary (level): `runs/bt_20260407T064241Z_close_vwap_gap_intensity/minimal_backtest_summary.json`
- minimal backtest report (level): `runs/bt_20260407T064241Z_close_vwap_gap_intensity/minimal_backtest_report.md`
- minimal backtest summary (change): `runs/bt_20260407T064241Z_close_vwap_gap_intensity_change/minimal_backtest_summary.json`
- minimal backtest report (change): `runs/bt_20260407T064241Z_close_vwap_gap_intensity_change/minimal_backtest_report.md`

Representative run artifacts:
- level factor profile: `runs/exp_20260407T064104Z_rc_20260329_close_vwap_gap_intensity_2026/factor_profile.json`
- level family profile: `runs/exp_20260407T064104Z_rc_20260329_close_vwap_gap_intensity_2026/family_profile.json`
- level data run summary: `runs/exp_20260407T064104Z_rc_20260329_close_vwap_gap_intensity_2026/data_run_summary.json`
- change factor profile: `runs/exp_20260407T064104Z_rc_20260329_close_vwap_gap_intensity_change_2026/factor_profile.json`
- change family profile: `runs/exp_20260407T064104Z_rc_20260329_close_vwap_gap_intensity_change_2026/family_profile.json`
- change data run summary: `runs/exp_20260407T064104Z_rc_20260329_close_vwap_gap_intensity_change_2026/data_run_summary.json`

Context and prior acceptance:
- first-family acceptance reference: `docs/acceptance_run_summary_2026-04.md`

## Result Snapshot

Profile completeness check:
- checked `close_vwap_gap_intensity` and `close_vwap_gap_intensity_change`
- confirmed fields were present in real `factor_profile.json`:
  - `factor_name`
  - `family_name`
  - `mechanism_hypothesis`
  - `target_universe_scope`
  - `source_universe_scope`
  - `contains_cross_security_source`
  - `universe_filter_version`
  - `required_data_lane`
  - `required_year_grade`
  - `time_grade_requirement`
  - `contains_caveat_fields`
  - `supports_default_lane`
  - `supports_extension_lane`
  - `label_definition`
  - `evaluation_horizons`
  - `known_failure_modes`
  - `baseline_comparators`
  - `requires_cross_security_mapping`

Scoreboard snapshot:
- candidate_count: `2`
- scoreboard readiness distribution:
  - ready: `0`
  - watch: `2`
  - reject: `0`
- both candidates were classified as:
  - `promotion_readiness = watch`
  - `primary_reject_reason = inverse_candidate_only`
- scoreboard stability checks passed:
  - `promotion_readiness` present
  - `primary_reject_reason` present
  - `mean_nmi` present
  - `baseline_redundancy_score` present for challenger candidate
  - `universe_scope` present
  - `contains_caveat_fields` present
  - `entropy_regime_dispersion` present
- baseline redundancy details:
  - `close_vwap_gap_intensity` is the registered baseline anchor for this family, so `baseline_redundancy_score = null` is expected by design
  - `close_vwap_gap_intensity_change` is a challenger candidate and produced `baseline_redundancy_score = 0.2441`
- sign-aware readiness check:
  - `close_vwap_gap_intensity`: `mean_rank_ic = -0.1310`, `mean_abs_rank_ic = 0.1310`, `mean_top_bottom_spread = -0.0136`
  - `close_vwap_gap_intensity_change`: `mean_rank_ic = -0.1051`, `mean_abs_rank_ic = 0.1051`, `mean_top_bottom_spread = -0.0131`
  - both were correctly kept out of `ready`

Auto-triage snapshot:
- shortlisted: `0`
- watch: `0`
- rejected: `2`
- rejected candidates:
  - `close_vwap_gap_intensity`
  - `close_vwap_gap_intensity_change`
- primary reject reasons:
  - both `weak_ic`
- secondary reject reasons:
  - both `inverse_candidate_only`
  - both `unstable_across_dates`
- reject reason histogram:
  - `weak_ic`: `2`
  - `inverse_candidate_only`: `2`
  - `unstable_across_dates`: `2`
- family-level summary:
  - `candidate_count = 2`
  - `shortlisted_count = 0`
  - `rejected_count = 2`
  - `shortlist_rate = 0.0`
  - `average_redundancy_profile = 0.2441`
  - `entropy_regime_sensitivity = 0.0595`
  - `significance_quality = 1.0`
- recommended next batch directions:
  - `Retire weak variants and reframe the family mechanism hypothesis.`
  - `Review negative-signed variants as explicit inverse candidates before promoting them.`

Minimal backtest snapshot:
- `close_vwap_gap_intensity`
  - `spread_return = -0.0139460178`
  - `hit_rate = 0.0`
  - `turnover_proxy = 0.5543`
  - `stability_proxy = 1.0`
  - `coverage_ratio = 0.9305`
- `close_vwap_gap_intensity_change`
  - `spread_return = -0.0133147940`
  - `hit_rate = 0.0`
  - `turnover_proxy = 0.5596`
  - `stability_proxy = 1.0`
  - `coverage_ratio = 0.9544`
- interpretation:
  - minimal backtest supports the reject narrative
  - there was no case where scoreboard looked `ready` but backtest contradicted it

## Universe Hygiene

- target universe in confirmed run artifacts: `stock_research_candidate`
- source universe in confirmed run artifacts: `target_only`
- `contains_cross_security_source` remained `false`
- no cross-security source lane artifact entered scoreboard, triage, or minimal backtest
- no TE / extension artifact entered this confirmation flow
- conclusion: 本次 confirmation run 未发现默认主线 universe 污染

## Acceptance Notes

Cross-family stability conclusion:
- repaired `sign-aware readiness` is stable across families
  - first-family acceptance proved it on `order_trade_interaction_pressure`
  - this second-family confirmation proved it again on `close_vwap_pressure`, a family whose own metadata warns about sign flip risk
- repaired `baseline redundancy` is stable across families
  - previous acceptance showed populated redundancy on challengers in `order_trade_interaction_pressure`
  - this confirmation again produced a non-null challenger redundancy score on `close_vwap_gap_intensity_change`
  - the baseline anchor remaining null is expected and contract-consistent, not a regression
- auto-triage now looks more credible across families
  - family 1 confirmed the positive shortlist path
  - family 2 confirmed the negative sign-flip reject path

Minimal repair made during this confirmation:
- files:
  - `harness/run_phase_a.py`
  - `tests/test_harness_smoke.py`
  - `registry/lineage.json`
- repair:
  - made lineage loading tolerate trailing garbage and rewrite clean JSON on the next append
  - cleaned the existing `registry/lineage.json` so append-only runs could continue
- why required:
  - the confirmation run was blocked before verified factor materialization because `append_lineage()` failed on malformed JSON
- why this is not scope expansion:
  - it only restores existing registry write behavior
  - it does not change research semantics, gating policy, or harness outputs

## Next-Stage Follow-Ups

- Run one more small confirmation on a family with at least three candidates, so the watch/reject distribution is exercised on a broader batch.
- Keep an eye on registry health for append-only artifacts beyond `lineage.json`, especially after interrupted runs.
- Revisit whether inverse-candidate handling should stay `watch` at scoreboard stage or graduate into a more explicit, still non-promoting action label in future policy work.
