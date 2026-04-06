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

`diagnostics_summary.json` 会附带日期级 `regime_annotations`，其中包含基于 turnover distribution entropy 的 `entropy_quantile` 切片。

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

最小 family batch screen：

```bash
python3 harness/autoresearch_cycle.py \
  --config configs/order_trade_interaction_screen.toml \
  --notes "order-trade interaction entropy screen"
```

每个 scoreboard 会写出：
- `scoreboard_summary.json`
- `scoreboard_report.md`

scoreboard / cycle 默认会把 `mean_nmi`、`entropy_regime_dispersion` 和 `entropy_quantile` 切片摘要带出来做展示与比较。

每个 pre-eval 会写出：
- `pre_eval_summary.json`
- `label_preview.json`

`pre_eval_summary.json` 的正式聚合指标放在 `aggregate_metrics`，最小固定字段包括：
- `mi`
- `rank_ic`
- `top_bottom_spread`
- `nmi`
- `nmi_ic_gap`
- `mi_p_value`
- `mi_excess_over_null`
- `mi_significant_date_ratio`

日期级 mutual information 指标的 canonical 字段是：
- `per_date[*].mi`
- `per_date[*].nmi`
- `per_date[*].mi_p_value`
- `per_date[*].mi_significant`
- `per_date[*].nmi_ic_gap`

`per_date[*].mutual_info` / `per_date[*].normalized_mutual_info` 当前只保留为兼容 alias。

这里的 entropy diagnostics 当前只指 turnover distribution entropy quantile，
并且只作为 descriptive regime labeling；
不要把它理解成更宽泛的“市场熵”或全面市场复杂度，也不要直接把全样本 quantile 标签当 production regime。

transfer entropy 现在有独立的 exploratory utility：

```bash
python3 harness/find_lead_factors.py --metric rank_ic
```

它不属于 fixed pre-eval，也不直接进入当前 Gate B policy。

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
