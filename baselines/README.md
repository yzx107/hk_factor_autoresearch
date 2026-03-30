# Baselines

这里放固定 baseline benchmark set。

目标：
- 禁止新 factor 脱离 baseline 独立自夸
- 让 scoreboard 能回答“有没有增量”，而不只是“有没有信号”
- 固定每轮研究默认要对比的 baseline anchors

当前 baseline registry 在：
- `baselines/baseline_registry.toml`

当前默认 baseline set：
- `structural_activity_proxy`
- `avg_trade_notional_bias`
- `order_lifecycle_churn`
- `close_vwap_gap_intensity`

原则：
- level 版优先作为 baseline anchor
- change 版优先作为 challenger
- baseline 不是“最好”的同义词，而是“默认必须比较”的参考物
