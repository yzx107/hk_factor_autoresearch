# Schema Boundary

上游锚点：
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/verified_admission_matrix_2026-03-18.md`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/verified_field_policy_2026-03-15.json`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/field_policy_2026-03-15.json`

Phase A 当前分成两层输入面：
- 默认 `verified v1` 安全面
- 显式声明后的 `caveat-only` 受限输入面

默认结构字段：
- orders: `date`, `table_name`, `source_file`, `ingest_ts`, `row_num_in_file`,
  `SeqNum`, `OrderId`, `Time`, `Price`, `Volume`
- trades: `date`, `table_name`, `source_file`, `ingest_ts`, `row_num_in_file`,
  `TickID`, `Time`, `Price`, `Volume`

仅允许带 caveat 使用的字段：
- orders: `OrderType`
- orders derived: `OrderSideVendor`（由 `Ext.bit0` 派生）
- trades: `TradeDir` / `Dir`
- trades: `Type`

这些字段必须满足：
- 只能进入单独声明的 `phase_a_caveat_lane`
- 研究卡必须明确写出 caveat
- Gate A 只会给 `allow_with_caveat`，不会自动转成默认 verified surface
- `TradeDir` 只能写成 vendor-derived aggressor proxy，不是 signed-side truth
- `OrderType` 只能写成 stable vendor event code，不是官方 event semantics
- `Type` 只能写成 vendor public-trade-type bucket
- `OrderSideVendor` 只能写成 `Ext.bit0` 派生的 vendor order-side proxy

默认排除：
- `BrokerNo`
- `Level`
- `VolumePre`
- `BidOrderID`, `AskOrderID`, `BidVolume`, `AskVolume`
- full `Ext`

规则：
- 与 HKEX OMD-C 系列兼容，不代表字段身份与官方语义一一对应
- 本 repo 不会把 vendor field 自动升级为 verified semantics
- 默认 `phase_a_core` 只能依赖安全结构核心
- 只有显式进入 `phase_a_caveat_lane` 且 Gate A 放行后，才允许消费 caveat-only 字段
