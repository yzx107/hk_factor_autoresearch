# Acceptance Run Summary (2026-04)

## Judgment

`mostly yes`

这套 `hk_factor_autoresearch` 已经在默认股票主线下跑通了：

`factor generation -> verified factor run / pre-eval -> scoreboard -> auto-triage -> minimal backtest`

本次判断是 `mostly yes`，不是 `yes`，原因很简单：
- 闭环已经真实跑通，关键产物齐全，universe hygiene 干净
- `scoreboard` 的 sign-aware readiness 和 baseline redundancy 需要在本轮验收后补一层修复才稳定
- 修复后的 rerun 结果合理，但目前只在一个 family 上完成正式 acceptance

## Run Scope

- family: `order_trade_interaction_pressure`
- spec: `factor_specs/order_trade_interaction_batch.toml`
- screen config: `configs/order_trade_interaction_screen.toml`
- target universe: `stock_research_candidate`
- source universe: `target_only`
- acceptance lane: default stock target lane only
- excluded from this acceptance: transfer entropy / cross-security extension lane

## Executed Steps

1. Universe / sidecar readiness check
   - `python3 harness/bootstrap_universe.py`
2. Factor generation
   - `python3 harness/generate_factor_batch.py --spec factor_specs/order_trade_interaction_batch.toml --overwrite`
3. Shared labels export
   - `python3 harness/export_forward_labels.py --year 2026 --notes "acceptance-run labels with universe metadata"`
4. Verified factor runs + pre-eval via fixed cycle
   - `python3 harness/autoresearch_cycle.py --config configs/order_trade_interaction_screen.toml --notes "acceptance run order_trade_interaction family" --no-reuse`
5. Repaired scoreboard rerun for acceptance freeze
   - `python3 harness/scoreboard.py --factors order_unique_trade_participation_gap order_unique_trade_participation_gap_change order_notional_vs_trade_notional_gap order_notional_vs_trade_notional_gap_change close_vwap_churn_interaction close_vwap_churn_interaction_change --notes "acceptance repair rerun sign-aware scoreboard"`
6. Auto-triage with shared labels
   - `python3 harness/run_auto_triage.py --scoreboard-summary runs/score_20260407T060710Z/scoreboard_summary.json --labels-path runs/labels_2026_20260407T054938Z/forward_labels.parquet --notes "acceptance repair rerun triage"`
7. Minimal backtest for shortlist confirmation
   - `python3 harness/run_minimal_backtest.py --run-dir runs/exp_20260407T054954Z_rc_20260330_order_notional_vs_trade_notional_gap_2026 --labels-path runs/labels_2026_20260407T054938Z/forward_labels.parquet --notes "acceptance repair rerun shortlist backtest"`

## Key Artifacts

Primary acceptance artifacts:
- scoreboard summary: `runs/score_20260407T060710Z/scoreboard_summary.json`
- scoreboard report: `runs/score_20260407T060710Z/scoreboard_report.md`
- triage summary: `runs/triage_20260407T060723Z_score_20260407T060710Z/triage_summary.json`
- triage report: `runs/triage_20260407T060723Z_score_20260407T060710Z/triage_report.md`
- minimal backtest summary: `runs/bt_20260407T060735Z_order_notional_vs_trade_notional_gap/minimal_backtest_summary.json`
- minimal backtest report: `runs/bt_20260407T060735Z_order_notional_vs_trade_notional_gap/minimal_backtest_report.md`

Representative factor run artifacts:
- shortlist factor profile: `runs/exp_20260407T054954Z_rc_20260330_order_notional_vs_trade_notional_gap_2026/factor_profile.json`
- shortlist family profile: `runs/exp_20260407T054954Z_rc_20260330_order_notional_vs_trade_notional_gap_2026/family_profile.json`
- shortlist data run summary: `runs/exp_20260407T054954Z_rc_20260330_order_notional_vs_trade_notional_gap_2026/data_run_summary.json`
- contrast factor profile: `runs/exp_20260407T054959Z_rc_20260330_close_vwap_churn_interaction_2026/factor_profile.json`
- contrast family profile: `runs/exp_20260407T054959Z_rc_20260330_close_vwap_churn_interaction_2026/family_profile.json`
- contrast data run summary: `runs/exp_20260407T054959Z_rc_20260330_close_vwap_churn_interaction_2026/data_run_summary.json`

Supporting inputs:
- labels summary: `runs/labels_2026_20260407T054938Z/labels_summary.json`
- cycle summary: `runs/auto_20260407T055005Z/cycle_summary.json`

## Result Snapshot

Scoreboard stage after repair:
- ready: `1`
- watch: `3`
- reject: `2`
- sign-aware effect: negative-signed candidates no longer default to `ready`
- baseline redundancy effect: `baseline_redundancy_score` is now populated for the full batch

Final auto-triage stage:
- shortlisted candidates: `1`
- watch candidates: `0`
- rejected candidates: `5`

Final shortlist:
- `order_notional_vs_trade_notional_gap`

Final rejected set:
- `close_vwap_churn_interaction`
- `close_vwap_churn_interaction_change`
- `order_unique_trade_participation_gap`
- `order_unique_trade_participation_gap_change`
- `order_notional_vs_trade_notional_gap_change`

Reject reason histogram:
- `weak_ic`: `5`
- `inverse_candidate_only`: `3`
- `unstable_across_dates`: `4`
- `insufficient_significance`: `2`
- `narrow_entropy_regime_only`: `1`

Family-level summary:
- family: `order_trade_interaction_pressure`
- candidate_count: `6`
- shortlisted_count: `1`
- rejected_count: `5`
- shortlist_rate: `0.1667`
- dominant failure modes: `weak_ic`, `insufficient_significance`

Minimal backtest summary:
- shortlist candidate `order_notional_vs_trade_notional_gap`
  - `spread_return = 0.0030404721`
  - `hit_rate = 0.6667`
  - `turnover_proxy = 0.5456`
  - `stability_proxy = 0.6667`
  - interpretation: supports the shortlist narrative
- contrast candidate `close_vwap_churn_interaction` was also checked during acceptance rerun
  - explicit prior backtest artifact: `runs/bt_20260407T055256Z_close_vwap_churn_interaction/minimal_backtest_summary.json`
  - `spread_return = -0.0233804070`
  - `hit_rate = 0.0`
  - interpretation: supports rejection rather than exposing a false negative in triage

## Universe Hygiene

- target universe recorded in this acceptance run: `stock_research_candidate`
- source universe recorded in this acceptance run: `target_only`
- `contains_cross_security_source` stayed `false` in the default mainline run artifacts
- no transfer-entropy or cross-security extension lane artifact was consumed by the fixed scoreboard / triage / minimal backtest flow
- conclusion: 本次闭环未发现默认主线 universe 污染

## Acceptance Notes

What clearly passed:
- `factor_profile.json` / `family_profile.json` / `data_run_summary.json` were written in real runs
- `scoreboard` emitted `mean_nmi`, `promotion_readiness`, `primary_reject_reason`, `baseline_redundancy_score`, `universe_scope`, `contains_caveat_fields`
- `auto-triage` emitted `shortlisted_candidates`, `watch_candidates`, `rejected_candidates`, `reject_reason_histogram`, `family_level_summary`, `recommended_next_batch_directions`
- `minimal backtest` ran on shortlist with unified low-freedom assumptions and correct universe metadata

What still keeps this at `mostly yes`:
- sign-aware gating only became stable after the acceptance repair rerun
- baseline redundancy is now populated, but this was first stabilized in the repaired acceptance scoreboard
- this acceptance was completed on one family, not yet repeated as a second-family confirmation run

## Next-Stage Follow-Ups

- Validate the repaired sign-aware readiness logic on at least one additional non-extension family.
- Confirm that auto-materialized baseline redundancy remains stable across more batches, not only this acceptance family.
- Revisit watch-threshold calibration so the post-backtest triage is not overly binary on small candidate batches.
