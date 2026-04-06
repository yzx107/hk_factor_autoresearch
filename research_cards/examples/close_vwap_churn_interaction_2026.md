+++
card_id = "rc_20260330_close_vwap_churn_interaction_2026"
name = "收盘-VWAP 与 churn 交互（Close Vwap Churn Interaction 2026）"
owner = "codex"
status = "draft"
factor_family = "order_trade_interaction_pressure"
years = ['2026']
universe = "phase_a_core"
instrument_universe = "stock_research_candidate"
holding_horizon = "30m_to_1d"
research_modules = ['order_trade_coverage_profile']
required_fields = ['date', 'source_file', 'OrderId', 'Time', 'Price', 'Volume', 'row_num_in_file']
horizon_scope = "30m_to_1d"
hypothesis = '如果 close-vwap gap 和 churn 同时抬升，可能比单独的尾盘压力或 churn 更像短周期未消化状态。'
mechanism = '把尾盘价格偏离和订单生命周期 churn 放在一起，捕捉“价格压力 × 订单摩擦”的联合状态。'
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；只使用 verified_trades_daily 与 verified_orders_daily 的安全 daily agg；不使用任何 caveat-only 字段。"
observable_proxies = ['close_like_price', 'vwap', 'churn_ratio', 'close-vwap gap x churn interaction']
baseline_refs = ['close_vwap_gap_intensity', 'order_lifecycle_churn']
promotion_target = "family screening"
failure_modes = ['可能只是 close_vwap_gap 的放大版本。', '尾盘成交稀疏时交互项容易失真。', '高 churn 但无真实价格压力的日子会制造假阳性。']
expected_risks = ['与 close-vwap family 共线。', '尾盘噪声。', '极端事件污染。']

[timing]
mode = "coarse_only"
uses_precise_lag = false
uses_strict_ordering = false
uses_queue_semantics = false

[semantics]
TradeDir = "unused"
BrokerNo = "unused"
OrderType = "unused"
Level = "unused"
VolumePre = "unused"
Type = "unused"
Ext = "unused"
+++

## Hypothesis

如果 close-vwap gap 和 churn 同时抬升，可能比单独的尾盘压力或 churn 更像短周期未消化状态。

## Mechanism

把尾盘价格偏离和订单生命周期 churn 放在一起，捕捉“价格压力 × 订单摩擦”的联合状态。

## Observable Proxies

close_like_price, vwap, churn_ratio, close-vwap gap x churn interaction

## Holding Horizon

30m_to_1d

## Required Fields

date, source_file, OrderId, Time, Price, Volume, row_num_in_file

## Info Boundary

只使用 `phase_a_core` 的日级安全缓存，不使用任何 caveat-only 字段。

## Failure Modes

可能只是 close_vwap_gap 的放大版本。 尾盘成交稀疏时交互项容易失真。 高 churn 但无真实价格压力的日子会制造假阳性。

## Expected Winning Regimes

high_vol、late_session_pressure、closing_imbalance_days

## Expected Failure Regimes

flat_close_days、low_order_activity_days、noisy_event_days

## Why Incremental vs Baselines

它把 close-vwap pressure 和 order_lifecycle pressure 做交互，不是任一单家族的 level 重复。

## Forbidden Semantic Assumptions

no_trade_side_truth、no_broker_identity_truth、no_ordertype_truth、no_queue_semantics

## Promotion Target

family screening

## Expected Risks

与 close-vwap family 共线。 尾盘噪声。 极端事件污染。
