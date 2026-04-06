+++
card_id = "rc_20260330_order_unique_trade_participation_gap_2026"
name = "订单-成交参与广度差（Order Unique Trade Participation Gap 2026）"
owner = "codex"
status = "draft"
factor_family = "order_trade_interaction_pressure"
years = ['2026']
universe = "phase_a_core"
target_instrument_universe = "stock_research_candidate"
source_instrument_universe = "target_only"
contains_cross_security_source = false
universe_filter_version = "stock_research_candidate_filter_v1"
holding_horizon = "30m_to_1d"
research_modules = ['order_trade_coverage_profile']
required_fields = ['date', 'source_file', 'OrderId', 'Price', 'Volume']
horizon_scope = "30m_to_1d"
hypothesis = '当 unique order breadth 相对 trade_count 异常抬升时，可能代理更强的未成交压力或更慢的成交吸收。'
mechanism = '比较唯一订单参与广度与成交笔广度，捕捉“挂单参与”和“实际成交实现”之间的落差。'
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；只使用 verified_trades_daily 与 verified_orders_daily 的安全 daily agg；不使用任何 caveat-only 字段。"
observable_proxies = ['unique_order_ids', 'trade_count', 'unique-order-vs-trade-count log gap']
baseline_refs = ['order_trade_event_ratio', 'structural_activity_proxy']
promotion_target = "family screening"
failure_modes = ['可能只是 order_event_ratio 的低信息量变体。', '低覆盖日中 breadth 信号容易被噪声主导。', '不同股票的文件切分差异可能影响广度代理。']
expected_risks = ['与 activity baseline 共线。', '订单覆盖偏差。', '低成交日不稳定。']

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

当 unique order breadth 相对 trade_count 异常抬升时，可能代理更强的未成交压力或更慢的成交吸收。

## Mechanism

比较唯一订单参与广度与成交笔广度，捕捉“挂单参与”和“实际成交实现”之间的落差。

## Observable Proxies

unique_order_ids, trade_count, unique-order-vs-trade-count log gap

## Holding Horizon

30m_to_1d

## Required Fields

date, source_file, OrderId, Price, Volume

## Info Boundary

只使用 `phase_a_core` 的日级安全缓存，不使用任何 caveat-only 字段。

## Failure Modes

可能只是 order_event_ratio 的低信息量变体。 低覆盖日中 breadth 信号容易被噪声主导。 不同股票的文件切分差异可能影响广度代理。

## Expected Winning Regimes

high_turnover、high_vol、quote_heavy_days

## Expected Failure Regimes

low_turnover、sparse_order_days、coverage_shift_days

## Why Incremental vs Baselines

它比较的是订单参与广度和成交实现广度，不是单看 activity，也不是单看 order_event_count。

## Forbidden Semantic Assumptions

no_trade_side_truth、no_broker_identity_truth、no_ordertype_truth、no_queue_semantics

## Promotion Target

family screening

## Expected Risks

与 activity baseline 共线。 订单覆盖偏差。 低成交日不稳定。
