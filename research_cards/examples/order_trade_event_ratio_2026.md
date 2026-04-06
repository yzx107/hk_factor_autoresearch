+++
card_id = "rc_20260330_order_trade_event_ratio_2026"
name = "订单-成交事件强度比（Order Trade Event Ratio 2026）"
owner = "codex"
status = "draft"
factor_family = "order_trade_interaction_pressure"
years = ["2026"]
universe = "phase_a_core"
target_instrument_universe = "stock_research_candidate"
source_instrument_universe = "target_only"
contains_cross_security_source = false
universe_filter_version = "stock_research_candidate_filter_v1"
holding_horizon = "30m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["date", "source_file", "OrderId", "Price", "Volume"]
horizon_scope = "30m_to_1d"
hypothesis = "当订单事件强度相对成交事件强度异常抬升时，可能代理未消化的成交摩擦与报价压力。"
mechanism = "如果订单消息增长快于实际成交，往往说明报价与撮合之间出现摩擦或未成交压力积累。"
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；只使用 verified_trades_daily 与 verified_orders_daily 的安全 daily agg；不使用任何 caveat-only 字段。"
observable_proxies = ["order_event_count", "trade_count", "order_event_count log-ratio vs trade_count"]
baseline_refs = ["structural_activity_proxy", "order_lifecycle_churn"]
promotion_target = "family screening"
failure_modes = ["可能只是 activity baseline 与 churn baseline 的线性组合。", "低成交日 ratio 容易被噪声放大。", "订单覆盖不完整时解释力会下降。"]
expected_risks = ["与活跃度代理共线。", "低流动性放大。", "日级聚合可能掩盖更细颗粒度结构。"]

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

订单事件相对成交事件的异常抬升，可能对应更高的未成交压力或成交摩擦。

## Mechanism

该信号把订单侧和成交侧的强度放到同一日级坐标里比较，不依赖任何方向或队列语义。

## Observable Proxies

`order_event_count`、`trade_count`、两者的 log-ratio。

## Holding Horizon

三十分钟到一天，主要用于短周期压力延续的筛查。

## Required Fields

`date`、`source_file`、`OrderId`、`Price`、`Volume`

## Info Boundary

只使用 Phase A core lane 的安全 daily agg。

## Failure Modes

如果它只是活跃度或 churn 的重写版本，就不应晋级。

## Expected Winning Regimes

高 turnover、高 vol、订单消息增长快于成交实现的日子。

## Expected Failure Regimes

低成交、低订单覆盖、纯事件噪声日。

## Why Incremental vs Baselines

它不是单看 activity，也不是单看 churn，而是明确比较订单消息和成交实现之间的相对张力。

## Forbidden Semantic Assumptions

不使用 trade side truth、broker identity、ordertype truth、queue semantics。

## Promotion Target

先做 `family screening`，检验交互型压力是否比单表 baseline 更有增量。

## Expected Risks

最大风险是与已有 baseline 共线，以及低覆盖日的噪声放大。
