# Event Spec

## 模块目标

`event_boundary_push` 的目标不是生成普通 alpha rank，而是识别一类特殊路径事件：

`control_build -> boundary_approach -> push_regime`

这里的研究对象是：
- IPO / 次新股
- 小中盘边界附近标的
- 在一段时间窗里出现控盘形成、边界接近和价格推进协同的案例

第一版的核心输出是：
- 事件状态日表
- 事件案例表
- 人工复核包

## 非目标

第一版明确不做：
- 生产交易系统
- 执行引擎
- 完整官方指数边界重建
- 复杂 ML / LLM / sequence model
- 法律意义上的操纵认定

## 输入依赖

默认输入：
- `verified_trades_daily`
- `verified_orders_daily`

可选输入：
- `instrument_profile_csv`
  - `instrument_key`
  - `listing_date`
  - `float_mktcap`
  - `southbound_eligible`
- `control_feature_csv`
  - `date`
  - `instrument_key`
  - 可选 `broker_hhi`
  - 可选 `broker_netflow_persistence`

## Universe 定义

第一版 universe 采用 instrument-level filter：
- `listing_age_days_at_end <= max_listing_age_days`
- `observed_days >= min_observed_days`
- `boundary_proxy_reference_percentile` 位于小中盘区间
- 若启用 `require_non_southbound_proxy`，则要求 `southbound_eligible_effective = false`

### listing_date fallback

若无 instrument profile：
- `listing_date_effective = first_seen_in_cache_proxy`

这意味着第一版的 IPO / 次新定义是宽松 proxy，适合扫描，不适合正式市场定义。

## 事件状态定义

### 1. `control_build`

含义：
- 控盘形成迹象开始持续出现

第一版默认使用以下 proxy 组合：
- `order_trade_event_ratio_lookback`
- `order_trade_notional_ratio_lookback`
- `churn_ratio_lookback`

若提供 broker 聚合特征，可额外纳入：
- `broker_hhi`
- `broker_netflow_persistence`

状态规则：
- `control_proxy >= control_build_threshold`
- `control_proxy_sustain >= control_build_sustain_threshold`

注意：
第一版用“持续高位”近似“形成过程”，不是严格重建 broker 控盘路径。

### 2. `boundary_approach`

含义：
- 标的接近一个 size / connect / index boundary proxy

优先 proxy：
- `float_mktcap_effective`

默认 fallback：
- `turnover_median_lookback`

第一版定义：
- 在 event universe 内，对 `boundary_proxy_value` 做当日横截面 percentile
- 若 percentile 落在 `boundary_target_percentile +/- boundary_band_width` 内，记为 `boundary_approach`

### 3. `push_regime`

含义：
- 价格持续推进且回撤受控

规则：
- `positive_return_share_lookback >= push_positive_share_min`
- `rolling_return_lookback >= push_return_min`
- `drawdown_from_high_lookback >= push_drawdown_floor`

## 事件触发逻辑

第一版按优先级生成每日 `event_type`：
1. `full_path_signal`
   - `control_build & boundary_approach & push_regime`
2. `boundary_control_setup`
   - `control_build & boundary_approach`
3. `control_push`
   - `control_build & push_regime`
4. `boundary_push`
   - `boundary_approach & push_regime`

这样做的目的，是把一日状态压成清晰的事件语义，而不是导出一堆日级分数。

## Event case building

对每个 `instrument_key + event_type`：
- 找出 trigger 为真的日期
- 允许 `max_gap_sessions` 个交易日间隔
- 把连续或近连续触发日压成一个 `event case`

每个 case 至少包含：
- `event_id`
- `ticker`
- `event_type`
- `start_date`
- `end_date`
- `status`
- `control_build_days`
- `boundary_approach_days`
- `push_regime_days`
- `peak_event_strength`
- `price_return_during_event`
- `max_drawdown_during_event`

## boundary proxy 的限制

第一版 boundary 不是官方恒生指数或港股通边界重建。
它是一个 event harness proxy，目标是：
- 找出“接近边界”的可疑推进案例
- 方便人工 review

因此它适合：
- 初筛
- 事件案例归档
- 专题复核

不适合：
- 直接当作官方边界真值
- 直接做 production eligibility assertion

## 输出产物

- `event_universe.parquet`
- `event_state_daily.parquet`
- `event_cases.parquet`
- `event_review_pack.csv`

## 人工 review 的角色

人工 review 不是可选装饰，而是模块的一部分。

机器负责：
- 定 universe
- 定状态
- 生成事件案例
- 整理 review pack

人工负责：
- 判断事件窗内是否真的存在明显路径特征
- 区分控盘形成、洗筹、推进、派发或不明确情形
- 保留分歧意见和不确定判断
