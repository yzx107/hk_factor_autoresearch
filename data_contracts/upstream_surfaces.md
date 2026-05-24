# Upstream Research Surfaces

This file records how `hk_factor_autoresearch` reads the current downstream
research contract exported by `Hshare_Lab_v2`.

It is a documentation sync only. It does not add loaders, widen Gate A, or
change the default Phase A factor lane.

## Upstream Anchors

- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/downstream_research_surface_contract_2026-05-24.md`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/manifests/downstream_research_surface_contract.json`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/l2_field_semantics_evidence_matrix_2026-05-24.md`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/orderbook_research_handoff_2026-05.md`

## Surface Mapping

| upstream surface | upstream status | current status in this repo |
| --- | --- | --- |
| `verified_default` | default formal input through `verified_orders` and `verified_trades` | default Phase A input surface |
| `explicit_caveat_research` | explicit caveat objects such as `Dir`, `Type`, `OrderTypeLifecycleEventCode`, `OrderSideVendor`, active-order linkage evidence, and prior-volume checks | partially represented only by existing `phase_a_caveat_lane`; no new loader or namespace is wired |
| `top_of_book_bounded` | bounded top-of-book replay objects with quality gates | future extension lane only; not consumed by default harness |
| `blocked_keep_out` | blocked objects such as `BrokerNo`, `Level`, full `Ext`, full depth, queue, and fill realism | blocked |

## Default Lane

The default factor lane remains `phase_a_core`.

It may read only `verified_default` objects:

- `verified_orders`
- `verified_trades`
- repo-local `verified_*_daily` aggregates derived from those tables

The default lane must continue to record:

- `target_instrument_universe = "stock_research_candidate"`
- `source_instrument_universe = "target_only"`
- `contains_cross_security_source = false`

## Caveat Lane

The upstream contract now names a broader `explicit_caveat_research` surface.
This repo does not automatically inherit all of it.

Current `phase_a_caveat_lane` still only admits the fields already checked by
Gate A:

- `TradeDir` / `Dir`
- `Type`
- `OrderType`
- `OrderSideVendor`

Active-order linkage evidence, `PriorActiveVolumeCheck`, and any materialized
caveat namespace need a separate loader, research card wording, Gate A rule,
and output metadata before they can enter this repo.

## Top-Of-Book Extension

The upstream `top_of_book_bounded` surface exposes:

- `BestBidReplay`
- `BestAskReplay`
- `ReplaySpread`
- `ReplayMid`
- `TradeInsideBestBookFlag`
- `TopOfBookValidFlag`
- `ReplayQualityScore`
- replay quality flags

The upstream default consumption filter is:

```text
TopOfBookValidFlag = true
ReplayQualityScore = 1.0
CrossedWindowFlag = false
ReplayResidueFlag = false
ReplayWindowExcludedFlag = false
SameMillisecondBatchRiskFlag = false
```

This repo currently has no `top_of_book_bounded` loader. Future work must add a
named extension lane instead of mixing these objects into `verified_default` or
`verified_*_daily`.

## OpenD Caveat Handoff

`Hshare_Lab_v2` also documents a caveated handoff namespace:

- `/Volumes/Data/港股Tick数据/caveat/orderbook_replay__top_of_book_with_size_caveat`

This surface is not a default research input. Bid/ask size remains caveated
active-order replay volume, not executable queue size, full-depth reconstruction,
or fill realism.

Any future adapter must fail closed unless the physical parquet schema matches
the current handoff contract. The current contract names
`CaveatHandoffReadyFlag`; older materializations may still carry legacy
readiness field names.

## Blocked Objects

The following remain outside default and caveat research in this repo:

- `BrokerNo`
- `Level`
- full `Ext`
- `BidVolume`
- `AskVolume`
- `FullReconstructedDepth`
- queue position / queue depletion
- fill priority / execution realism
- broker alpha

They may appear in upstream stage, DQA, or blocker reports, but not as formal
factor inputs without a new upstream release plus a local contract update.
