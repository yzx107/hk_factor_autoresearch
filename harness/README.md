# Harness

This directory holds the fixed experiment harness for Phase A.

Rules:
- researchers and agents may change ideas
- ordinary experiments may not change the harness
- every run must go through the harness runner and leave a registry record

Default run:

```bash
python3 harness/run_phase_a.py \
  --card research_cards/examples/structural_activity_proxy_2026.md \
  --factor structural_activity_proxy
```

Verified-data run:

```bash
python3 harness/run_verified_factor.py \
  --card research_cards/examples/structural_activity_proxy_2026.md \
  --factor structural_activity_proxy \
  --dates 2026-03-13
```

Build local daily aggregate cache:

```bash
python3 harness/build_daily_agg.py --table all --year 2026
```

Progress view:

```bash
python3 harness/status.py
```

Suggested anchor run:

```bash
python3 harness/run_verified_factor.py \
  --card research_cards/examples/structural_activity_proxy_2026.md \
  --factor structural_activity_proxy \
  --dates 2026-01-05 2026-02-24 2026-03-13 \
  --notes "three-anchor verified run"
```

Each run writes:
- `result.json`
- `data_run_summary.json`
- `diagnostics_summary.json`
- `preview.json`
- `factor_output.parquet`

Latest-run comparison:

```bash
python3 harness/compare_factors.py \
  --left-factor structural_activity_proxy \
  --right-factor avg_trade_notional_bias \
  --notes "safe factor comparison"
```

Candidate scoreboard:

```bash
python3 harness/scoreboard.py \
  --factors structural_activity_proxy avg_trade_notional_bias \
  --notes "safe candidate board"
```

Fixed pre-eval:

```bash
python3 harness/run_pre_eval.py \
  --factor structural_activity_proxy \
  --notes "fixed forward-return pre-eval"
```

Export shared labels:

```bash
python3 harness/export_forward_labels.py --year 2026
```

Fixed autoresearch cycle:

```bash
python3 harness/autoresearch_cycle.py \
  --notes "daily cycle"
```

Each scoreboard writes:
- `scoreboard_summary.json`
- `scoreboard_report.md`

Each pre-eval writes:
- `pre_eval_summary.json`
- `label_preview.json`

Each cycle writes:
- `cycle_summary.json`
- `cycle_report.md`

Why this exists:
- keep experiment setup comparable
- reduce token waste by emitting compact summaries
- make keep, caveat, and discard decisions explicit
- capture both linear and non-linear signal evidence under fixed pre-eval rules
