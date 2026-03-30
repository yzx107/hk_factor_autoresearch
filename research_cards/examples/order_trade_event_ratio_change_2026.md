+++
card_id = "rc_20260330_order_trade_event_ratio_change_2026"
name = "订单-成交事件强度比变化（Order Trade Event Ratio Change 2026）"
owner = "codex"
status = "draft"
factor_family = "order_trade_interaction_pressure"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "30m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["date", "source_file", "OrderId", "Price", "Volume"]
horizon_scope = "30m_to_1d"
hypothesis = "订单相对成交的压力如果快速加速，可能比 level 本身更能捕捉短期摩擦变化。"
mechanism = "压力水平的加速度，比静态水平更像新信息或库存变化的触发器。"
info_boundary = "只使用 verified_trades_daily 与 verified_orders_daily 的安全 daily agg；不使用任何 caveat-only 字段。"
observable_proxies = ["one_day_difference(order_event_count vs trade_count log-ratio)"]
baseline_refs = ["order_trade_event_ratio", "order_lifecycle_churn_change"]
promotion_target = "family screening"
failure_modes = ["可能只是在复制 level 版的噪声。", "前一日覆盖不足会直接伤害 change 信号。", "极端日跳变可能是事件污染。"]
expected_risks = ["与 change baselines 共线。", "前日缺失。", "高波动事件污染。"]

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

订单-成交相对强度的日间加速度，可能比静态强度更适合捕捉短周期摩擦变化。

## Mechanism

用 one-day difference 看交互压力是否突然抬升，而不是只看常态水平。

## Observable Proxies

前后两日 `order_event_count vs trade_count` log-ratio 的差分。

## Holding Horizon

三十分钟到一天。

## Required Fields

`date`、`source_file`、`OrderId`、`Price`、`Volume`

## Info Boundary

只使用 Phase A core lane 的安全 daily agg。

## Failure Modes

如果 change 版只是把 level 版噪声差分化，它不会提供稳定增量。

## Expected Winning Regimes

高 turnover、高 vol、压力切换明显的阶段。

## Expected Failure Regimes

低覆盖、低成交、连续平稳无切换的阶段。

## Why Incremental vs Baselines

它直接押“交互压力变化”，不是 activity、notional 或 churn 的静态水平换皮。

## Forbidden Semantic Assumptions

不使用 trade side truth、broker identity、ordertype truth、queue semantics。

## Promotion Target

先做 `family screening`，重点看它是否优于对应 level 版。

## Expected Risks

最大风险是把前后两日覆盖差异误当成经济变化。
