# Schema Boundary

上游锚点：
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/verified_admission_matrix_2026-03-18.md`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/verified_field_policy_2026-03-15.json`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/field_policy_2026-03-15.json`

Phase A 的安全输入面只包含保守的结构字段核心。

默认结构字段：
- orders: `date`, `table_name`, `source_file`, `ingest_ts`, `row_num_in_file`,
  `SeqNum`, `OrderId`, `Time`, `Price`, `Volume`
- trades: `date`, `table_name`, `source_file`, `ingest_ts`, `row_num_in_file`,
  `TickID`, `Time`, `Price`, `Volume`

仅允许带 caveat 使用的字段：
- orders: `OrderType`, `Ext`
- trades: `Type`

这些字段仍然是 vendor-defined code。研究卡必须明确写出 caveat，
Gate A 不会自动放行。

默认排除：
- `TradeDir` / `Dir`
- `BrokerNo`
- `Level`
- `VolumePre`
- `BidOrderID`, `AskOrderID`, `BidVolume`, `AskVolume`

规则：
- 与 HKEX OMD-C 系列兼容，不代表字段身份与官方语义一一对应
- 本 repo 不会把 vendor field 自动升级为 verified semantics
- 除非研究卡明确写出 caveat 且 Gate A 放行，否则因子代码只能依赖默认结构核心
