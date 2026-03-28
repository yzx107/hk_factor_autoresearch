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

Why this exists:
- keep experiment setup comparable
- reduce token waste by emitting compact summaries
- make keep, caveat, and discard decisions explicit
