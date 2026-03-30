# Harness

这个目录放的是 Phase A 的固定实验 harness。

基本规则：
- 研究员和 agent 可以改 idea
- 普通实验不可以改 harness
- 每次 run 都必须走 harness runner，并留下 registry 记录

默认 run：

```bash
python3 harness/run_phase_a.py \
  --card research_cards/examples/structural_activity_proxy_2026.md \
  --factor structural_activity_proxy
```

真实 verified 数据 run：

```bash
python3 harness/run_verified_factor.py \
  --card research_cards/examples/structural_activity_proxy_2026.md \
  --factor structural_activity_proxy \
  --dates 2026-03-13
```

构建本地逐日聚合缓存：

```bash
python3 harness/build_daily_agg.py --table all --year 2026
```

查看进度：

```bash
python3 harness/status.py
```

建议的 anchor run：

```bash
python3 harness/run_verified_factor.py \
  --card research_cards/examples/structural_activity_proxy_2026.md \
  --factor structural_activity_proxy \
  --dates 2026-01-05 2026-02-24 2026-03-13 \
  --notes "three-anchor verified run"
```

每次 run 会写出：
- `result.json`
- `data_run_summary.json`
- `diagnostics_summary.json`
- `preview.json`
- `factor_output.parquet`

比较最近一次 run：

```bash
python3 harness/compare_factors.py \
  --left-factor structural_activity_proxy \
  --right-factor avg_trade_notional_bias \
  --notes "safe factor comparison"
```

生成候选板：

```bash
python3 harness/scoreboard.py \
  --factors structural_activity_proxy avg_trade_notional_bias \
  --notes "safe candidate board"
```

固定 pre-eval：

```bash
python3 harness/run_pre_eval.py \
  --factor structural_activity_proxy \
  --notes "fixed forward-return pre-eval"
```

最小正式 Gate B：

```bash
python3 harness/run_gate_b.py \
  --factor close_vwap_gap_intensity_change close_vwap_churn_interaction_change \
  --notes "initial gate b shortlist"
```

导出共享 labels：

```bash
python3 harness/export_forward_labels.py --year 2026
```

固定 autoresearch cycle：

```bash
python3 harness/autoresearch_cycle.py \
  --notes "daily cycle"
```

每个 scoreboard 会写出：
- `scoreboard_summary.json`
- `scoreboard_report.md`

每个 pre-eval 会写出：
- `pre_eval_summary.json`
- `label_preview.json`

每个 Gate B run 会写出：
- `gate_b_summary.json`

每个 cycle 会写出：
- `cycle_summary.json`
- `cycle_report.md`

为什么要有这一层：
- 保证实验设置可比较
- 用紧凑摘要减少 token 浪费
- 把 keep、caveat、discard 决策显式化
- 在固定 pre-eval 规则下同时保留线性和非线性信号证据
