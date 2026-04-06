# event_boundary_push

`event_boundary_push` 是一个 event-driven special situations module。
它不是普通单因子，也不是 production trading system。

模块目标：
- 研究“入港股通前窗口”可能出现的市场行为事件，而不是直接重建官方纳入规则
- 在 IPO / 次新股扫描池里检测 `control_build -> boundary_approach -> push_regime` 这类可疑路径事件
- 生成稳定的事件案例表（event cases）
- 导出面向人工复核的 review pack

模块不做什么：
- 不接入现有 `factor_defs/`
- 不改写 `Phase A / pre_eval / gate_b / registry` 主线
- 不做 production backtest / execution
- 不伪装成完整指数历史边界重建
- 不声称等价于官方港股通纳入判定

## 输入依赖

第一版默认只依赖本仓库已有的本地 daily agg：
- `cache/daily_agg/verified_trades_daily`
- `cache/daily_agg/verified_orders_daily`

可选输入：
- `instrument_profile_csv`
  - 若提供，可补 `listing_date / float_mktcap / southbound_eligible`
- `control_feature_csv`
  - 若提供，可补 `broker_hhi / broker_netflow_persistence` 等 broker 聚合特征

若可选输入不存在，模块会自动退回 proxy：
- `listing_date_effective = first_seen_in_cache_proxy`
- `boundary proxy = turnover_median_lookback`
- `control proxy = weighted(order_trade_event_ratio_lookback_pct, order_trade_notional_ratio_lookback_pct, churn_ratio_lookback_pct)`

## 主要脚本

- `build_event_universe.py`
  - 构建 IPO / 次新股事件扫描池，输出 `event_universe.parquet`
- `detect_boundary_push_events.py`
  - 构建每日状态面板，输出 `event_state_daily.parquet`
- `build_event_cases.py`
  - 把日状态压成事件案例窗，输出 `event_cases.parquet`
- `export_event_review_pack.py`
  - 导出人工复核 CSV，输出 `event_review_pack.csv`

## 最小运行流程

```bash
python3 event_boundary_push/build_event_universe.py \
  --config event_boundary_push/configs/boundary_push_event_v0.toml

python3 event_boundary_push/detect_boundary_push_events.py \
  --config event_boundary_push/configs/boundary_push_event_v0.toml

python3 event_boundary_push/build_event_cases.py \
  --config event_boundary_push/configs/boundary_push_event_v0.toml

python3 event_boundary_push/export_event_review_pack.py \
  --config event_boundary_push/configs/boundary_push_event_v0.toml
```

## 当前默认规则

- `control_proxy`
  - 默认是加权横截面 percentile 合成：
    - `0.30 * order_trade_event_ratio_lookback_pct`
    - `0.50 * order_trade_notional_ratio_lookback_pct`
    - `0.20 * churn_ratio_lookback_pct`
  - 若 broker 聚合特征存在，则按 `control_broker_blend_weight` 混入 broker proxy
- `boundary_approach`
  - 默认目标分位是 `0.85`
  - 默认 band 是 `+/- 0.04`
- `push_regime`
  - 默认要求 `10` 日窗口内正收益日占比至少 `0.70`
  - 默认要求 `10` 日累计涨幅至少 `0.08`
- `event case` 合并
  - `max_gap_sessions` 按交易日序列计，不按自然日计

## 输出说明

默认输出目录：`event_boundary_push/outputs/`

主要产物：
- `event_universe.parquet`
- `event_state_daily.parquet`
- `event_cases.parquet`
- `event_review_pack.csv`

同时会写固定 summary：
- `event_universe_summary.json`
- `event_state_daily_summary.json`
- `event_cases_summary.json`
- `event_review_pack_summary.json`

## review pack 说明

review pack 是事件案例视角，不是单日 candidate 视角。
每行代表一个事件案例，至少包含：
- `event_id`
- `ticker`
- `event_type`
- `start_date / end_date`
- `control / boundary / push` 核心指标快照
- 人工标注空列

更多口径说明见 `event_spec.md`。

## Ground-Truth Validation

模块附带一个轻量 `ground-truth validation harness`，用于把 `event_cases` 和历史港股通纳入 / 特殊事件样本对齐，输出：
- `ground_truth_matches.parquet`
- `ground_truth_noise_cases.parquet`
- `ground_truth_validation_summary.json`

默认配置：
- `event_boundary_push/configs/boundary_push_ground_truth_v0.toml`
- `event_boundary_push/labels/ground_truth_template.csv`

最小运行：

```bash
python3 event_boundary_push/validate_ground_truth.py \
  --config event_boundary_push/configs/boundary_push_ground_truth_v0.toml
```

这一步不是交易回测，而是事件命中验证：
- 看历史港股通纳入 / 事件样本是否被模块提前捕捉
- 看提前量（lead days）
- 看哪些 event cases 没有对应 ground truth，可作为噪音 proxy

## Instrument Profile Integration

如果暂时没有稳定的 `instrument_profile_csv`，可以先导出一个可回填 seed：

```bash
python3 event_boundary_push/build_instrument_profile_seed.py \
  --config event_boundary_push/configs/boundary_push_event_v0.toml \
  --included-only
```

默认输出：
- `event_boundary_push/outputs/instrument_profile_seed.csv`
- `event_boundary_push/outputs/instrument_profile_seed.summary.json`

这个 seed 会把当前事件 universe 中的：
- `instrument_key / ticker`
- `first_seen_date`
- `listing_date_seed`
- `float_mktcap_seed`
- `southbound_seed`
导出来，并留空以下可回填列：
- `listing_date`
- `float_mktcap`
- `southbound_eligible`

回填完成后，把 enriched CSV 路径写回 `boundary_push_event_v0.toml` 的 `instrument_profile_csv`，再重新跑事件模块。

重新运行后，summary JSON 里会带 `profile_coverage`，可以直接看到当前有多少行已经脱离 proxy。
