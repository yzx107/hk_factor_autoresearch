# hk_factor_autoresearch

This repo is a research-factory repo for Hong Kong factor work. It is not the
data-base repo and it is not a production trading stack.

Current scope is `Phase A / semi-auto`:
- freeze Layer 0 boundaries
- require research cards before implementation
- keep a fixed backtest and evaluation interface
- automate only Gate A data admissibility
- keep experiment lineage append-only
- run experiments through a lightweight harness, not ad hoc shell steps

Relationship to `Hshare_Lab_v2`:
- upstream repo: `/Users/yxin/AI_Workstation/Hshare_Lab_v2`
- this repo reads upstream verified and admissibility conclusions as read-only
- this repo must not redefine upstream field semantics or feed conclusions back
  into upstream Layer 0

What is here now:
- `data_contracts/` for fixed field and timing rules
- `research_cards/` for the card template and smoke examples
- `gatekeeper/gate_a_data.py` for minimal admissibility checks
- `configs/baseline_phase_a.toml` for a frozen baseline config
- `harness/run_phase_a.py` for the minimal autoresearch-style loop
- `registry/` for append-only experiment skeletons

What is not here:
- no multi-agent search factory
- no production backtester
- no heavy paper-trading stack
- no broker alpha, signed-flow truth, or queue semantics by default

Quick smoke:

```bash
python3 -m unittest tests/test_gate_a_smoke.py
```

Minimal harness run:

```bash
python3 harness/run_phase_a.py \
  --card research_cards/examples/structural_activity_proxy_2026.md \
  --factor structural_activity_proxy
```
