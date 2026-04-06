+++
card_id = "rc_20260406_trade_size_concentration_2026"
name = "成交额集中度 (Trade Size Concentration 2026)"
owner = "agent"
status = "draft"
factor_family = "intraday_distribution"
years = ["2026"]
universe = "phase_a_core"
target_instrument_universe = "stock_research_candidate"
source_instrument_universe = "target_only"
contains_cross_security_source = false
universe_filter_version = "stock_research_candidate_filter_v1"
holding_horizon = "30m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["date", "source_file", "Price", "Volume"]
horizon_scope = "30m_to_1d"
hypothesis = "单笔成交额分布的集中度（Gini系数）反映大单 vs 散单的组成结构，高集中度可能代理机构大单介入。"
mechanism = "计算每日每只股票所有成交笔的名义额 Gini 系数，高 Gini 意味着少数大笔成交主导了当日总成交，这种截面差异可能预示短期方向性。"
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；只使用 Price*Volume 计算的单笔名义额分布，不依赖任何被阻断字段。"
observable_proxies = ["gini_of_trade_notional", "top_trade_share"]
baseline_refs = ["avg_trade_notional_bias", "structural_activity_proxy"]
promotion_target = "family screening"
failure_modes = ["Gini 可能退化为 avg_trade_size 的单调变换。", "极端大单事件污染。", "低成交日 Gini 缺乏统计意义。"]
expected_risks = ["与 notional bias baseline 共线。", "大单事件噪声。", "低流动性股票覆盖差。"]

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

成交额的离散度比均值包含更多信息。少数大笔成交是否主导了当日交易，这种结构性差异可能反映了机构参与度。

## Mechanism

Gini 系数量化了单笔成交额分布的不平等程度。值越接近 1，越集中在少量大成交；越接近 0，越均匀分布。

## Observable Proxies

- gini_of_trade_notional: Price×Volume 逐笔的 Gini 系数
- top_trade_share: 最大单笔成交占比（补充切面）

## Holding Horizon

三十分钟到一天。

## Required Fields

`date`, `source_file`, `Price`, `Volume`

## Info Boundary

不使用 TradeDir、BrokerNo、queue 或 vendor code 语义。

## Expected Winning Regimes

大单频繁出现的日子、机构博弈活跃日。

## Expected Failure Regimes

极低成交量日（样本不足难以计算 Gini）、事件驱动的异常大单日。

## Why Incremental vs Baselines

avg_trade_notional_bias 只看均值，完全忽略了分布形态。本因子捕捉的是 "成交不平等程度" 而非 "平均规模"。

## Forbidden Semantic Assumptions

不使用 signed-side truth、broker identity truth、queue semantics。

## Promotion Target

family screening

## Expected Risks

与 notional 均值高度共线的风险。大单事件污染。
