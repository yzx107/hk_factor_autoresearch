+++
card_id = "rc_20260406_session_activity_shift_2026"
name = "盘内活跃度迁移 (Session Activity Shift 2026)"
owner = "agent"
status = "draft"
factor_family = "intraday_distribution"
years = ["2026"]
universe = "phase_a_core"
target_instrument_universe = "stock_research_candidate"
source_instrument_universe = "target_only"
holding_horizon = "30m_to_1d"
research_modules = ["order_trade_coverage_profile"]
required_fields = ["date", "source_file", "Time", "Price", "Volume"]
horizon_scope = "30m_to_1d"
hypothesis = "早盘 vs 午盘的成交额分布差异，能代理盘内注意力迁移方向，捕捉尾盘压力预兆。"
mechanism = "港股上午09:30-12:00和下午13:00-16:00的成交份额比例变化反映了资金的盘内择时偏好，这种截面差异可能预示后续波动。"
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；只使用 verified 的 Time 和 Price*Volume 计算的盘内分段成交额，不使用任何 caveat-only 字段。"
observable_proxies = ["afternoon_turnover_share", "morning_vs_afternoon_ratio"]
baseline_refs = ["structural_activity_proxy"]
promotion_target = "family screening"
failure_modes = ["可能退化为 turnover 或 volume 的简单代理。", "盘中休市分割可能引入结构性偏差。", "不同时区或半日交易日会打破分段假设。"]
expected_risks = ["与 activity baseline 共线。", "午盘回来后成交量不可比。", "异常交易日影响。"]

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

港股的上午和下午时段有天然的中午休市分割。如果某只股票当日成交量异常向尾盘迁移，可能暗示收盘竞价前的方向性压力。

## Mechanism

计算 (afternoon_turnover - morning_turnover) / total_turnover 的截面排名。这个指标对同一日内不同股票的时段结构差异进行量化。

## Observable Proxies

- afternoon_turnover_share: 下午成交额占比
- session_shift: 早盘 vs 午盘的相对位移

## Holding Horizon

三十分钟到一天。

## Required Fields

`date`, `source_file`, `Time`, `Price`, `Volume`

## Info Boundary

不使用 TradeDir、BrokerNo、queue 或 vendor code 语义。只使用安全结构字段。

## Expected Winning Regimes

高波动日、尾盘有大资金流入流出的日子。

## Expected Failure Regimes

半日交易日、成交极为稀疏的日子。

## Why Incremental vs Baselines

现有因子全部是日级聚合，完全丢弃了时段结构信息。本因子捕捉的是 "活跃度在一天中的分布形状"，而不是总量。

## Forbidden Semantic Assumptions

不使用 signed-side truth、broker identity truth、queue semantics。

## Promotion Target

family screening

## Expected Risks

与 activity baseline 的 turnover 维度共线。休市后的回归效应。
