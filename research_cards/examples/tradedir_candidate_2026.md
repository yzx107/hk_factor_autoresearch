+++
card_id = "rc_20260326_tradedir_candidate_2026"
name = "TradeDir 候选对比（TradeDir Candidate Contrast 2026）"
owner = "codex"
status = "draft"
years = ["2026"]
universe = "phase_a_caveat_lane"
holding_horizon = "5m_to_30m"
research_modules = ["trade_dir_candidate_signal_profile"]
required_fields = ["TickID", "Time", "Price", "Volume", "TradeDir"]
hypothesis = "带 caveat 的 TradeDir 对比，在 2026 年可能携带较弱的短周期方向信息。"
mechanism = "vendor 方向代码可能与短周期流量失衡相关，但它不是 signed-side truth。"
info_boundary = "使用上游 admissibility 输出。TradeDir 只被当作需要人工复核的 vendor-derived aggressor proxy。"
failure_modes = ["考虑成本后对比消失。", "信号只是事件污染。", "vendor 方向语义漂移。"]
expected_risks = ["必须人工复核。", "不是 signed-flow truth。", "可能只是 vendor 导出伪影。"]

[timing]
mode = "fine_ok"
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

研究 2026 年 TradeDir 对比在短持有后是否还有较弱预测力。

## Mechanism

只把这个代码当作 vendor-derived aggressor proxy，不宣称官方 signed-side truth。

## Holding Horizon

五到三十分钟。

## Required Fields

`TickID`、`Time`、`Price`、`Volume`、`TradeDir`

## Info Boundary

不宣称 signed-side truth，不使用 queue 或 latency 语义。

## Failure Modes

观察到的对比可能不具备因果性，也可能在摩擦后消失。

## Expected Risks

这个例子带有很强的 vendor 语义 caveat。
