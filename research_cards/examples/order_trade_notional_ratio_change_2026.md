+++
card_id = "rc_20260330_order_trade_notional_ratio_change_2026"
name = "订单-成交名义额比变化（Order Trade Notional Ratio Change 2026）"
owner = "codex"
status = "draft"
factor_family = "order_trade_interaction_pressure"
years = ["2026"]
universe = "phase_a_core"
holding_horizon = "30m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["date", "source_file", "OrderId", "Price", "Volume"]
horizon_scope = "30m_to_1d"
hypothesis = "订单 notional 相对成交 turnover 的加速度，可能比 level 更敏感地捕捉压力切换。"
mechanism = "如果订单 notional 变化快于成交吸收，说明压力结构在快速变化。"
info_boundary = "只使用 verified_trades_daily 与 verified_orders_daily 的安全 daily agg；不使用任何 caveat-only 字段。"
observable_proxies = ["one_day_difference(total_order_notional vs turnover log-ratio)"]
baseline_refs = ["order_trade_notional_ratio", "avg_trade_notional_bias_change"]
promotion_target = "family screening"
failure_modes = ["可能只是前日大单噪声的延续。", "前一日缺失会直接伤害信号。", "变化项容易放大覆盖差异。"]
expected_risks = ["与 change baselines 共线。", "前日缺失。", "事件污染。"]

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

订单 notional 相对成交 turnover 的日间加速度，可能比 level 更像短周期压力变化的触发器。

## Mechanism

用差分看压力切换，而不是静态差异。

## Observable Proxies

前后两日 `total_order_notional vs turnover` log-ratio 的差分。

## Holding Horizon

三十分钟到一天。

## Required Fields

`date`、`source_file`、`OrderId`、`Price`、`Volume`

## Info Boundary

只使用 Phase A core lane 的安全 daily agg。

## Failure Modes

如果 change 只是在大单事件后回归均值，它不会成为稳健信号。

## Expected Winning Regimes

高 vol、高 turnover、压力切换清晰的阶段。

## Expected Failure Regimes

低覆盖、低成交、平稳横盘阶段。

## Why Incremental vs Baselines

它直接押交互型 pressure 的变化，而不是已有 notional baseline 的 level 信息。

## Forbidden Semantic Assumptions

不使用 trade side truth、broker identity、ordertype truth、queue semantics。

## Promotion Target

先做 `family screening`，重点看是否优于对应 level 版与 notional change baseline。

## Expected Risks

最大风险是把覆盖变化或大单事件误读为压力切换。
