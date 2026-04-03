# event_boundary_push

`event_boundary_push` 是一个 event-driven special situations module。
它不是普通单因子，也不是 production trading system。

模块目标：
- 在 IPO / 次新股扫描池里检测 `control_build -> boundary_approach -> push_regime` 这类可疑路径事件
- 生成稳定的事件案例表（event cases）
- 导出面向人工复核的 review pack

模块不做什么：
- 不接入现有 `factor_defs/`
- 不改写 `Phase A / pre_eval / gate_b / registry` 主线
- 不做 production backtest / execution
- 不伪装成完整指数历史边界重建

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
- `control proxy = order_trade_event_ratio + order_trade_notional_ratio + churn_ratio`

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

更多口径说明见 [event_spec.md](/Users/yxin/AI_Workstation/hk_factor_autoresearch/event_boundary_push/event_spec.md)。
