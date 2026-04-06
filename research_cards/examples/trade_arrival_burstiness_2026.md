+++
card_id = "rc_20260406_trade_arrival_burstiness_2026"
name = "成交到达脉冲度 (Trade Arrival Burstiness 2026)"
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
required_fields = ["date", "source_file", "Time", "Price", "Volume", "row_num_in_file"]
horizon_scope = "30m_to_1d"
hypothesis = "成交到达时间间隔的变异系数（CV）能区分稳态噪声流和脉冲式信息驱动交易，高脉冲度可能代理信息到达。"
mechanism = "计算连续成交之间的时间间隔序列的 CV。CV 高意味着交易节奏不均匀、聚集出现，这可能与事件驱动交易或知情交易者的短窗口介入行为一致。"
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；只使用 Time 字段排序并计算间隔，不使用任何 caveat-only 字段。"
observable_proxies = ["inter_trade_interval_cv", "burstiness_index"]
baseline_refs = ["structural_activity_proxy", "order_lifecycle_churn"]
promotion_target = "family screening"
failure_modes = ["极低成交日间隔计算不可靠。", "同一秒内多笔成交无法计算有效间隔。", "开盘抢筹和收盘竞价窗口会系统性拉升 CV。"]
expected_risks = ["与 trade_count 可能存在非线性关联。", "Time 字段精度限制可能影响间隔计算。", "异常交易日大幅波动。"]

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

"成交什么时候到达"比"成交了多少"包含更多微观结构信息。成交到达的节奏是稳定的还是脉冲式的，反映了市场参与者的行为模式。

## Mechanism

使用成交记录的时间戳排序后计算相邻成交的时间间隔，然后计算间隔列表的 CV（标准差/均值）。高 CV → 脉冲式 → 可能是信息到达；低 CV → 匀速流 → 可能是做市或噪声。

## Observable Proxies

- inter_trade_interval_cv: 成交间隔的变异系数
- burstiness_index: 归一化后的脉冲指数

## Holding Horizon

三十分钟到一天。

## Required Fields

`date`, `source_file`, `Time`, `Price`, `Volume`, `row_num_in_file`

## Info Boundary

只使用 Time 字段排序和间隔计算。不依赖 TradeDir 或 BrokerNo。

## Expected Winning Regimes

信息驱动日、异常成交集中的日子。

## Expected Failure Regimes

极低成交量日（间隔样本不足）、高频相同时间戳的精度限制。

## Why Incremental vs Baselines

activity proxy 和 churn 量化的是 "交易了多少" 或 "撤了多少单"，完全忽视了 "到达节奏"。本因子捕捉的是时间维度的形态信息。

## Forbidden Semantic Assumptions

不使用 signed-side truth、broker identity truth、queue semantics。

## Promotion Target

family screening

## Expected Risks

Time 精度限制。与 trade_count 的非线性共线风险。
