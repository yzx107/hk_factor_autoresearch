+++
card_id = "rc_20260406_trade_dir_imbalance_intensity_2026"
name = "买卖失衡强度 (Trade Dir Imbalance Intensity 2026)"
owner = "agent"
status = "draft"
factor_family = "directional_proxy"
years = ["2026"]
universe = "phase_a_caveat_lane"
instrument_universe = "stock_research_candidate"
holding_horizon = "30m_to_1d"
research_modules = ["trade_dir_candidate_signal_profile"]
required_fields = ["date", "source_file", "Price", "Volume", "TradeDir"]
horizon_scope = "30m_to_1d"
hypothesis = "vendor proxy 的成交额加权买卖失衡绝对值越大，说明当日的方向性压力越强，可能预示短期趋势延续或反转。"
mechanism = "计算 |buy_notional - sell_notional| / total_notional。这是关于方向性压力 '强度' 的因子，而不是关于 '方向' 的因子。高失衡可能来自单边流入或流出，具体方向需要配合 buy_ratio 使用。"
info_boundary = "只在上游 instrument_profile sidecar 的 stock_research_candidate 股票候选池内研究；这不是 fully verified equity universe，仍可能残留 listed_security_unclassified 低位非股票例外；使用 TradeDir 进行名义额加权的买卖分组，只做 vendor proxy 级别的强度估算。"
observable_proxies = ["volume_weighted_imbalance", "abs_net_flow_ratio"]
baseline_refs = ["structural_activity_proxy", "trade_dir_buy_ratio"]
promotion_target = "exploratory_only"
failure_modes = ["当 vendor TradeDir 编码不准确时，失衡计算失去意义。", "极端少量大单会主导 notional 加权。", "如果 vendor 方向标记高度非对称，会系统性偏移。"]
expected_risks = ["TradeDir 语义不可靠的核心风险。", "大单事件污染。", "需要人工复核 vendor 方向分布。"]

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

不管买还是卖方向，失衡 "强度" 本身就是一种信号。高失衡的日子，成交的非对称性大，可能说明有知情参与者的单边介入。

## Mechanism

|buy_notional - sell_notional| / total_notional，其中 buy/sell 按 vendor TradeDir 划分。

## Observable Proxies

- volume_weighted_imbalance: 名义额加权的买卖失衡程度
- abs_net_flow_ratio: 绝对净流比

## Holding Horizon

三十分钟到一天。

## Required Fields

`date`, `source_file`, `Price`, `Volume`, `TradeDir`

## Info Boundary

TradeDir 只作为 vendor aggressor proxy 使用。这是 caveat-only 实验。

## Expected Winning Regimes

单边资金涌入或涌出日、流动性充足使 notional 加权有意义的日子。

## Expected Failure Regimes

TradeDir 缺失严重的日子、成交极稀疏日。

## Why Incremental vs Baselines

buy_ratio 告诉你 "方向偏好"，imbalance_intensity 告诉你 "偏好有多极端"。后者是前者无法替代的互补信号。

## Forbidden Semantic Assumptions

不使用 signed-side truth、aggressor truth、broker identity truth、queue semantics。

## Promotion Target

exploratory_only

## Expected Risks

核心风险是 vendor TradeDir 的语义可信度。
