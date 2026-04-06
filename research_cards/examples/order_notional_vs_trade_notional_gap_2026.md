+++
card_id = "rc_20260330_order_notional_vs_trade_notional_gap_2026"
name = "订单-成交平均名义额差（Order Notional Vs Trade Notional Gap 2026）"
owner = "codex"
status = "draft"
factor_family = "order_trade_interaction_pressure"
years = ['2026']
universe = "phase_a_core"
target_instrument_universe = "stock_research_candidate"
source_instrument_universe = "target_only"
holding_horizon = "30m_to_1d"
research_modules = ['order_trade_coverage_profile']
required_fields = ['date', 'source_file', 'OrderId', 'Price', 'Volume']
horizon_scope = "30m_to_1d"
hypothesis = '当订单侧平均名义额相对成交侧平均名义额异常偏高时，可能说明大额意图未被成交充分吸收。'
mechanism = '比较平均订单名义额与平均成交名义额，捕捉显示出来的订单规模和真正成交规模之间的落差。'
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；只使用 verified_trades_daily 与 verified_orders_daily 的安全 daily agg；不使用任何 caveat-only 字段。"
observable_proxies = ['total_order_notional', 'unique_order_ids', 'turnover', 'trade_count', 'average-order-vs-trade-notional gap']
baseline_refs = ['order_trade_notional_ratio', 'avg_trade_notional_bias']
promotion_target = "family screening"
failure_modes = ['可能退化为 notional baseline 的换皮表达。', '极端大单事件会污染平均 notional 差。', '订单覆盖变化可能被误读成经济信号。']
expected_risks = ['与 notional baseline 共线。', '大单事件污染。', '低流动性失真。']

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

当订单侧平均名义额相对成交侧平均名义额异常偏高时，可能说明大额意图未被成交充分吸收。

## Mechanism

比较平均订单名义额与平均成交名义额，捕捉显示出来的订单规模和真正成交规模之间的落差。

## Observable Proxies

total_order_notional, unique_order_ids, turnover, trade_count, average-order-vs-trade-notional gap

## Holding Horizon

30m_to_1d

## Required Fields

date, source_file, OrderId, Price, Volume

## Info Boundary

只使用 `phase_a_core` 的日级安全缓存，不使用任何 caveat-only 字段。

## Failure Modes

可能退化为 notional baseline 的换皮表达。 极端大单事件会污染平均 notional 差。 订单覆盖变化可能被误读成经济信号。

## Expected Winning Regimes

high_vol、large_order_days、late_session_pressure

## Expected Failure Regimes

thin_turnover、single-block-event_days、coverage_shift_days

## Why Incremental vs Baselines

它比较的是两侧平均 notional 的相对差，而不是只看 turnover、avg_trade_notional 或 total_order_notional。

## Forbidden Semantic Assumptions

no_trade_side_truth、no_broker_identity_truth、no_ordertype_truth、no_queue_semantics

## Promotion Target

family screening

## Expected Risks

与 notional baseline 共线。 大单事件污染。 低流动性失真。
