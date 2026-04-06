+++
card_id = "rc_20260406_trade_dir_buy_ratio_2026"
name = "买入比率 (Trade Dir Buy Ratio 2026)"
owner = "agent"
status = "draft"
factor_family = "directional_proxy"
years = ["2026"]
universe = "phase_a_caveat_lane"
holding_horizon = "30m_to_1d"
research_modules = ["trade_dir_candidate_signal_profile"]
required_fields = ["date", "source_file", "Price", "Volume", "TradeDir"]
horizon_scope = "30m_to_1d"
hypothesis = "截面上 vendor proxy 买入占比异常偏高的股票，可能代理短周期的需求压力。"
mechanism = "计算每日每只股票被 vendor 标记为买入方向的成交笔数占总成交的比例。这只是一个 vendor-derived proxy，不是真实的 signed-side truth。"
info_boundary = "使用 TradeDir 字段作为 vendor-aggressor proxy，明确声明不做 signed-side truth 宣称。"
observable_proxies = ["buy_trade_ratio", "buy_count_vs_total"]
baseline_refs = ["structural_activity_proxy"]
promotion_target = "exploratory_only"
failure_modes = ["TradeDir 可能只是 vendor 的机械码映射，无真实方向含义。", "买卖比可能在横截面上缺乏分散性。", "vendor 定义可能跨年份不一致。"]
expected_risks = ["语义风险：TradeDir 不等于真实交易方向。", "覆盖风险：部分日期 TradeDir 可能全为同一值。", "回测偏差：vendor proxy 不应承接 signed-side 的预期收益。"]

[timing]
mode = "coarse_only"
uses_precise_lag = false
uses_strict_ordering = false
uses_queue_semantics = false

[semantics]
TradeDir = "vendor_aggressor_proxy_only"
BrokerNo = "unused"
OrderType = "unused"
Level = "unused"
VolumePre = "unused"
Type = "unused"
Ext = "unused"
+++

## Hypothesis

vendor提供的 TradeDir 虽然不能被当成 signed-side truth，但截面排名上的相对差异可能反映不同股票的方向性激进程度。

## Mechanism

每日每只股票 buy_count / total_count。这个指标反映 vendor 层面的买入偏好代理。

## Observable Proxies

- buy_trade_ratio: 被标记为买方的成交笔数比例

## Holding Horizon

三十分钟到一天。

## Required Fields

`date`, `source_file`, `Price`, `Volume`, `TradeDir`

## Info Boundary

TradeDir 只作为 vendor aggressor proxy 使用。不宣称 signed-side truth。

## Expected Winning Regimes

方向性不对称显著的日子、流动性充足日。

## Expected Failure Regimes

TradeDir 大量缺失或分布退化的日子。

## Why Incremental vs Baselines

现有因子完全没有方向性信息维度。即使是最弱的方向代理，也是全新的信息切面。

## Forbidden Semantic Assumptions

不使用 signed-side truth、aggressor truth、broker identity truth、queue semantics。

## Promotion Target

exploratory_only

## Expected Risks

核心风险是 TradeDir 语义本身不可靠。需要人工复核。
