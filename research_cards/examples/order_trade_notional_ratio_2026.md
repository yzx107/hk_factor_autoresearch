+++
card_id = "rc_20260330_order_trade_notional_ratio_2026"
name = "订单-成交名义额比（Order Trade Notional Ratio 2026）"
owner = "codex"
status = "draft"
factor_family = "order_trade_interaction_pressure"
years = ["2026"]
universe = "phase_a_core"
instrument_universe = "stock_research_candidate"
holding_horizon = "30m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["date", "source_file", "OrderId", "Price", "Volume"]
horizon_scope = "30m_to_1d"
hypothesis = "当订单名义额相对成交名义额异常偏高时，可能代理未被成交吸收的报价压力。"
mechanism = "如果显示出来的订单 notional 增长快于真实成交 turnover，可能意味着执行摩擦或未成交压力。"
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；只使用 verified_trades_daily 与 verified_orders_daily 的安全 daily agg；不使用任何 caveat-only 字段。"
observable_proxies = ["total_order_notional", "turnover", "order notional log-ratio vs turnover"]
baseline_refs = ["avg_trade_notional_bias", "order_lifecycle_churn"]
promotion_target = "family screening"
failure_modes = ["可能只是 turnover 或 liquidity proxy 的变体。", "极端大单事件可能污染 ratio。", "订单覆盖变化会影响解释。"]
expected_risks = ["与 notional baseline 共线。", "大单噪声。", "低流动性失真。"]

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

订单 notional 相对成交 turnover 的异常扩张，可能对应更强的未成交压力。

## Mechanism

该信号比较“想成交的 notional”和“已经成交的 notional”，仍然完全停留在安全字段层。

## Observable Proxies

`total_order_notional`、`turnover`、两者的 log-ratio。

## Holding Horizon

三十分钟到一天。

## Required Fields

`date`、`source_file`、`OrderId`、`Price`、`Volume`

## Info Boundary

只使用 Phase A core lane 的安全 daily agg。

## Failure Modes

如果它只是 turnover baseline 的重写版本，就不应晋级。

## Expected Winning Regimes

高成交、高波动、订单 notional 快速堆积但成交吸收不足的阶段。

## Expected Failure Regimes

低 turnover、极端大单日、订单覆盖变化日。

## Why Incremental vs Baselines

它比较的是订单 notional 与成交 turnover 的相对关系，不是单看成交尺寸或 churn。

## Forbidden Semantic Assumptions

不使用 trade side truth、broker identity、ordertype truth、queue semantics。

## Promotion Target

先做 `family screening`，看它是否提供超出成交类 baseline 的交互增量。

## Expected Risks

最大风险是与 notional/turnover 基线强共线。
