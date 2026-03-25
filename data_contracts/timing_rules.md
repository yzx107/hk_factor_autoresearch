# Timing Rules

Upstream anchors:
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Audits/research_admissibility_matrix.md`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/verified_admission_matrix_2026-03-18.md`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/tradedir_validation_2025.md`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/tradedir_validation_2026.md`

Year grades:
- `2025 = coarse_only`
- `2026 = fine_ok`

Hard rules:
- `2025` may do coverage, same-second sanity, event-count lifecycle shape, and
  coarse post-trade windows only.
- `2025` may not do precise lag, latency, queue, strict ordering, or execution
  realism studies.
- `2026` may do fine timing only when the field semantics used are still within
  verified or caveated scope.
- queue and depth semantics stay blocked in both years.
- signed-side and aggressor truth stay blocked in both years.

Field-specific timing boundary:
- `TradeDir`: `2025 = stable_code_structure_only`
- `TradeDir`: `2026 = candidate_directional_signal_only`
- `TradeDir` is never confirmed signed side.
- `BrokerNo` is `reference_lookup_only` in both years.
- `Level` and `VolumePre` stay blocked.
- `Type`, `Ext`, and `OrderType` remain vendor codes with manual-review caveat.
