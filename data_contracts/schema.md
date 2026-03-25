# Schema Boundary

Upstream anchors:
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/verified_admission_matrix_2026-03-18.md`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/verified_field_policy_2026-03-15.json`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/field_policy_2026-03-15.json`

Phase A safe input surface is the conservative structural core only.

Default structural columns:
- orders: `date`, `table_name`, `source_file`, `ingest_ts`, `row_num_in_file`,
  `SeqNum`, `OrderId`, `Time`, `Price`, `Volume`
- trades: `date`, `table_name`, `source_file`, `ingest_ts`, `row_num_in_file`,
  `TickID`, `Time`, `Price`, `Volume`

Caveat-only fields:
- orders: `OrderType`, `Ext`
- trades: `Type`

These remain vendor-defined codes. A card must state the caveat explicitly and
Gate A will not auto-pass them.

Keep out by default:
- `TradeDir` / `Dir`
- `BrokerNo`
- `Level`
- `VolumePre`
- `BidOrderID`, `AskOrderID`, `BidVolume`, `AskVolume`

Rules:
- compatibility with HKEX OMD-C family does not mean 1:1 official field
  identity
- this repo does not promote vendor fields to verified semantics
- factor code may depend on only the default structural core unless a card is
  explicitly caveated and Gate A says so
