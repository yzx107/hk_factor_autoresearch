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

Why this exists:
- keep experiment setup comparable
- reduce token waste by emitting compact summaries
- make keep, caveat, and discard decisions explicit
