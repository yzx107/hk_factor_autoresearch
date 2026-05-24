# Universe Layering Research Contract

This document defines the first research contract for Hong Kong stock
universe layering in `hk_factor_autoresearch`.

It is a research and evaluation contract only. It does not widen Gate A, does
not change the default `phase_a_core` input surface, and does not replace the
current `stock_research_candidate` target universe.

## Decision

Do not mine the Hong Kong universe as one homogeneous pool.

The default all-candidate pool remains useful as a benchmark, but factor
selection must be layer-aware because Hong Kong securities differ materially
by liquidity, investor clientele, listing lifecycle, listing regime, index
flow, auction mechanics, and low-liquidity risk.

The first implementation should tag instruments with objective, lagged, and
source-traced layers, then re-summarize existing factor runs by layer before
adding new factor families.

## Evidence Summary

Market structure changed enough in 2025 to justify a new segmentation layer:

- HKEX reported 2025 Southbound Stock Connect ADT of HKD 121.1bn, versus
  HKD 48.2bn in 2024, and Southbound turnover at 23.0% of Hong Kong cash
  equities turnover at the end of Q4 2025.
- HKEX Monthly Market Highlights reported 2025 securities-market ADT of
  HKD 249.8bn, up 90% from 2024; ETF ADT of HKD 33.3bn, up 108%; 119 newly
  listed companies; and IPO funds raised of HKD 285.8bn, up 225%.
- HKEX's 2025 ECM recap said Southbound net flows increased 74% year over
  year in 2025.
- The SFC Q4 2025 quarterly report placed Southbound trading at 24.2% of
  Hong Kong market turnover in 2025 and cumulative Southbound net inflows
  above HKD 5.1tn.

The mechanism evidence also supports segmentation:

- Southbound eligibility is not arbitrary. HKEX's investor book ties eligible
  SEHK stocks to Hang Seng Composite LargeCap/MidCap constituents,
  SmallCap constituents above HKD 5bn market cap, and eligible A+H shares,
  with exclusions for non-HKD shares and risk-alert/delisting arrangements.
- Stock Connect research finds market-opening effects on bid-ask spread,
  effective spread, depth, price impact, and short-term volatility. Other
  research finds Southbound and Northbound flows have different implications
  for connected stocks, and that Stock Connect turnover Granger-causes
  market realized volatility and market volume.
- Hang Seng Index methodology explicitly evaluates candidates by
  representativeness, market capitalisation, turnover, and financial
  performance, with quarterly review/rebalancing. Index inclusion is therefore
  a flow and liquidity regime, not only a label.
- Chapter 18A and Chapter 18C create distinct listed ecosystems. HKEX now
  describes biotech as a multi-asset ecosystem with benchmarks, ETFs,
  structured products, futures, and event-driven trading; Chapter 18C creates
  a dedicated path for specialist technology companies with different
  revenue, R&D, disclosure, and IPO allocation characteristics.
- Hong Kong IPO literature links underpricing and aftermarket liquidity, so
  newly listed names should be evaluated separately from mature names.
- SFC ramp-and-dump guidance explicitly calls out thinly traded small-cap
  stocks with highly concentrated shareholding and unexplained sustained
  price increases as a risk pattern. This should become an observable
  low-liquidity risk proxy, not a subjective label.
- HKEX CAS rules create a distinct closing-auction mechanism with reference
  price, two-stage price limits, no-cancellation/random closing periods, and
  special short-selling constraints. Close-heavy factors need a CAS overlay.

## Layering Principles

- Use ex-ante information only. A layer tag must be generated from sources
  available no later than the research date, with `source_asof_date` recorded.
- Separate primary layers from overlays. Primary layers are mutually
  exclusive tradability buckets. Overlays are non-exclusive mechanism tags.
- Keep the labels mechanical. Avoid labels such as `old_dealer_stock`; use
  observable proxy names such as `legacy_illiquid_risk_proxy`.
- Fail closed. Missing source evidence means `unknown`, not silent promotion
  into a cleaner bucket.
- Keep sample-size discipline. A layer-level metric is diagnostic unless it
  meets minimum date and instrument counts.
- Do not import caveat fields through the back door. Top-of-book, active
  order, broker, full-depth, queue, and fill-realism fields remain governed by
  `data_contracts/upstream_surfaces.md`.

## Phase A Primary Layer

The first version should define one mutually exclusive field:

`primary_tradability_layer`

Allowed values:

| value | intent | initial rule sketch |
| --- | --- | --- |
| `new_or_recent_listing` | isolate IPO seasoning and newly listed flow | `listing_age_days <= 365`, with a stricter diagnostic bucket for `<= 90` days |
| `large_liquid_core` | large, institutionally tradable names | high float market cap and high recent ADT, or index/core connect membership |
| `mid_liquid_tradable` | normal research pool | stock candidate with adequate observations and not assigned above/below |
| `small_illiquid_special` | sparse/capacity-constrained names | low float market cap, low recent ADT, sparse observations, or wide microstructure proxy |
| `unknown` | fail-closed source gap | insufficient reference data |

Do not hard-code numeric cutoffs in factor code. Put cutoffs in a versioned
layer config, then write them to run artifacts.

Recommended initial thresholds for empirical calibration, not yet policy:

- `large_liquid_core`: top 20% by lagged 60-day ADT or float market cap among
  `stock_research_candidate`, plus major index names if reliable membership
  data is present.
- `small_illiquid_special`: bottom 30% by lagged 60-day ADT or float market
  cap, or insufficient active trading days.
- `mid_liquid_tradable`: remaining stock candidates.
- `new_or_recent_listing`: override the above while listing age is within
  365 calendar days.

## Phase A Overlays

The first version should allow these non-exclusive boolean/string overlays:

| overlay | type | purpose | source priority |
| --- | --- | --- | --- |
| `southbound_eligible` | bool | Mainland investor access and flow regime | `instrument_profile.southbound_eligible`, HKEX Stock Connect list |
| `southbound_active_proxy` | enum | stronger flow participation if holdings/turnover data is present | future Stock Connect turnover/holding source |
| `listing_age_bucket` | enum | IPO and seasoning behavior | `listing_date` from instrument profile or newly listed reference |
| `chapter_18a_biotech` | bool | biotech event/liquidity ecosystem | HKEX listing regime/reference seed |
| `chapter_18c_specialist_tech` | bool | specialist tech listing regime | HKEX listing regime/reference seed |
| `index_flow_bucket` | enum | passive/index rebalance and derivative-linked flow | Hang Seng/HKEX index constituents |
| `cas_eligible` | bool | close auction mechanics | HKEX CAS eligible list |
| `shortsell_or_options_eligible` | bool | hedging/derivative participant regime | HKEX short-sell/options lists |
| `legacy_illiquid_risk_proxy` | bool | low-liquidity manipulation-risk proxy | lagged price/liquidity/sparsity/concentration inputs |
| `top_of_book_bounded_ready` | bool | future extension lane only | upstream top-of-book handoff, not default |

## Current Local Source Inventory

Available now:

- `/Volumes/Data/港股Tick数据/reference/instrument_profile/latest/instrument_profile.parquet`
  - rows: 27278
  - `stock_research_candidate`: 2693
  - `southbound_eligible` known among stock candidates: 601
  - `circulating_mktcap_hkd` known among stock candidates: 2669
  - `latest_turnover_hkd` known among stock candidates: 2669
  - useful fields: `instrument_key`, `listing_date`, `float_mktcap_hkd`,
    `total_mktcap_hkd`, `circulating_mktcap_hkd`, `latest_turnover_hkd`,
    `southbound_eligible`, `southbound_as_of_date`, `instrument_family`,
    `stock_research_candidate`, `as_of_date`
  - boundary: `circulating_mktcap_hkd` / `total_mktcap_hkd` are reference
    size proxies, not `float_mktcap_hkd` or verified fact truth.
- `/Volumes/Data/港股Tick数据/reference/newly_listed_hk/year=2026/newly_listed_hk_2026.parquet`
  - rows: 7720
  - `universe_status=included`: 54
  - listing date range: 2026-01-02 to 2026-05-13
  - caveat: reference/caveat handoff, not verified semantic layer
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/References/normalized/hkex_southbound_seed.csv`
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/References/normalized/instrument_profile_seed.csv`

Missing or not yet normalized:

- current Hang Seng constituent history and rebalance dates;
- HKEX CAS eligible-security history;
- short-sell/options eligibility history;
- official 18A/18C issuer tags by instrument and date;
- Southbound holdings/turnover by instrument and date; current eligibility is
  present only as a point-in-time reference snapshot;
- free-float/holding concentration history for a stronger
  `legacy_illiquid_risk_proxy`.

## Required Output Contract

A future builder should materialize:

`cache/universe_layers/year=<YYYY>/universe_layers_<YYYY>.parquet`

Required columns:

- `instrument_key`
- `layer_date`
- `primary_tradability_layer`
- `listing_age_bucket`
- `southbound_eligible`
- `southbound_eligible_known`
- `southbound_active_proxy`
- `chapter_18a_biotech`
- `chapter_18c_specialist_tech`
- `index_flow_bucket`
- `cas_eligible`
- `shortsell_or_options_eligible`
- `legacy_illiquid_risk_proxy`
- `top_of_book_bounded_ready`
- `source_asof_date`
- `layer_version`
- `source_trace_json`
- `tradability_proxy_hkd`
- `liquidity_proxy_hkd`
- `liquidity_proxy_source`
- `size_proxy_hkd`
- `size_proxy_source`

Minimum companion manifest:

- `generated_at`
- `year`
- `layer_version`
- `source_paths`
- `threshold_config`
- `row_count`
- `coverage_by_layer`
- `coverage_by_overlay`
- `unknown_counts`

## Evaluation Contract

Before mining new factors, re-evaluate existing candidates by layer:

- Keep current all-candidate metrics as the benchmark.
- Add layer-level summaries to pre-eval/scoreboard artifacts.
- Report `rank_ic`, `abs_rank_ic`, `top_bottom_spread`, `nmi`,
  `mi_p_value`, coverage ratio, instrument count, and date count per layer.
- Mark layer metrics as `diagnostic_only` unless they meet minimum coverage.
- Treat `small_illiquid_special` separately for turnover, capacity, and
  slippage. A factor that only works there is not automatically promotable.
- Treat `new_or_recent_listing`, `chapter_18a_biotech`, and
  `chapter_18c_specialist_tech` as mechanism discovery lanes until sample
  counts are sufficient.

Promotion language should change from "factor works" to:

```text
factor works / fails / is untested in layer X under layer_version Y
```

## First Implementation Plan

1. Add `configs/universe_layers_phase_a.toml` with the first threshold policy.
2. Add `harness/build_universe_layers.py` to create the layer map from
   `instrument_profile`, newly listed reference data, and safe daily aggregate
   liquidity proxies when available.
3. Add a smoke test that asserts:
   - all `stock_research_candidate` instruments receive exactly one primary
     layer or `unknown`;
   - overlays are nullable/fail-closed where source data is absent;
   - the builder does not read caveat/top-of-book objects.
4. Add a layer-aware pre-eval summary that joins factor outputs to the layer
   map and writes `layered_pre_eval_summary.json`.
5. Re-run the current accepted factors first. Only after reading layer response
   should new factor specs be added.

## Source Links

- HKEX Stock Connect 2025 Review:
  https://www.hkexgroup.com/media-centre/insight/insight/2026/hkex-insight/stock-connect-2025-review?sc_lang=en
- HKEX Monthly Market Highlights:
  https://www.hkex.com.hk/Market-Data/Statistics/Consolidated-Reports/HKEX-Monthly-Market-Highlights?sc_lang=en
- HKEX 2025 ECM recap:
  https://www.hkexgroup.com/Media-Centre/Insight/Insight/2026/HKEX-Insight/ECM-performance-in-2025?sc_lang=en
- SFC Quarterly Report, Oct-Dec 2025:
  https://www.sfc.hk/-/media/EN/files/COM/QR-Reports/202510-12/3---Oct-Dec-2025-QR---Eng---Enhancing-Hong-Kong-market-competitiveness-and-appeal.pdf
- HKEX Stock Connect information book:
  https://www.hkex.com.hk/-/media/HKEX-Market/Mutual-Market/Stock-Connect/Getting-Started/Information-Booklet-and-FAQ/Information-Book-for-Investors/Investor_Book_En.pdf
- Hang Seng Index methodology:
  https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/methodologies/IM_hsie.pdf
- HKEX Chapter 18A rulebook:
  https://en-rules.hkex.com.hk/entiresection/5193
- HKEX Chapter 18C explainer:
  https://www.hkexgroup.com/Media-Centre/Insight/Insight/2026/HKEX-Insight/18C-Explained?sc_lang=en
- HKEX biotech ecosystem:
  https://www.hkexgroup.com/Media-Centre/Insight/Insight/2026/HKEX-Insight/The-Rise-of-Hong-Kong-Multi-Asset-Biotech-Ecosystem?sc_lang=en
- HKEX CAS FAQ:
  https://www.hkex.com.hk/Global/Exchange/FAQ/Securities-Market/Trading/CAS?sc_lang=en
- Stock Market Openness and Market Quality:
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3543713
- Cross-Border Equity Flows and Information Transmission:
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3562001
- Stock Connect turnover and volatility:
  https://www.mdpi.com/1911-8074/11/4/76
- Hong Kong IPO aftermarket liquidity:
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=975054
- SFC ramp-and-dump circular:
  https://apps.sfc.hk/edistributionWeb/api/circular/openFile?lang=EN&refNo=21EC26
