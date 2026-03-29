# Timing Rules

上游锚点：
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Audits/research_admissibility_matrix.md`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/verified_admission_matrix_2026-03-18.md`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/tradedir_validation_2025.md`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/tradedir_validation_2026.md`

年份等级：
- `2025 = coarse_only`
- `2026 = fine_ok`

硬规则：
- `2025` 只允许做 coverage、same-second sanity、按事件数统计的生命周期形态，以及粗粒度 post-trade 窗口。
- `2025` 不允许做 precise lag、latency、queue、strict ordering 或 execution realism 研究。
- `2026` 只有在所用字段语义仍处于 verified 或 caveated 范围内时，才允许做 fine timing。
- queue 和 depth semantics 在两年中都保持阻断。
- signed-side 和 aggressor truth 在两年中都保持阻断。

字段级 timing 边界：
- `TradeDir`: `2025 = stable_code_structure_only`
- `TradeDir`: `2026 = candidate_directional_signal_only`
- `TradeDir` 永远不能当 confirmed signed side。
- `BrokerNo` 在两年里都只能 `reference_lookup_only`。
- `Level` 和 `VolumePre` 持续阻断。
- `Type`、`Ext`、`OrderType` 仍然是需要人工复核 caveat 的 vendor code。
