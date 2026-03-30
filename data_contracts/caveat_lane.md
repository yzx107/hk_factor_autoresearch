# Caveat Lane

这个文件把 `Phase A` 里允许显式声明的 `caveat-only` 输入面固定下来。

它不改变默认 `verified v1`：
- 默认安全面仍然只包含 `admit_now` 结构字段
- `caveat-only` 字段必须走单独的 `phase_a_caveat_lane`
- `phase_a_caveat_lane` 只代表“可研究但必须带 caveat”，不代表字段已经毕业为 verified truth

当前与上游对齐的 `caveat-only` 输入：

- trades:
  - `TradeDir` / `Dir`
    - wording: `vendor-derived aggressor proxy`
    - status: `requires_manual_review`
    - forbidden: signed-side truth / aggressor truth
  - `Type`
    - wording: `vendor public-trade-type bucket`
    - status: `allow_with_caveat`

- orders:
  - `OrderType`
    - wording: `stable vendor event code`
    - status: `allow_with_caveat`
  - `OrderSideVendor`
    - source: derived from `Ext.bit0`
    - wording: `vendor order-side proxy`
    - status: `allow_with_caveat`

当前仍不进入 caveat lane 的字段：
- `BrokerNo`
- `Level`
- `VolumePre`
- full `Ext`
- `BidOrderID`, `AskOrderID`, `BidVolume`, `AskVolume`

规则：
- research card 必须声明 `universe = "phase_a_caveat_lane"`
- Gate A 结果至少是 `allow_with_caveat`
- 不得把 caveat-only 字段混写成默认 `verified` 字段
- 不得把 caveat-only 字段写成官方原生字段语义
- 若要真正接入 runner / daily_agg，必须单独新增受限 namespace，而不是偷偷混进当前 `verified_*_daily`
