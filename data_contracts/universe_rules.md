# Universe Rules

Phase A 使用的是保守的消费层 universe，而不是重新定义上游 data contract。
这里的 `universe` 有两层边界，不能混写：

- 字段输入边界：哪些字段可以进入 `phase_a_core` 或 `phase_a_caveat_lane`
- 证券池选择边界：是否显式使用上游 `instrument_profile` sidecar 做股票候选池筛选

上游参考：
- `/Users/yxin/AI_Workstation/Hshare_Lab_v2/Research/Validation/instrument_universe_classification_boundary_2026-04-06.md`

默认 universe：
- `phase_a_core` = 可以基于上游 `verified_orders` 和 `verified_trades` 当前已放行结构字段、并结合声明年份范围来研究的行和证券
- `phase_a_caveat_lane` = 只能在显式 caveat、人工复核和单独 namespace 下消费 caveat-only 字段的受限研究面

重要说明：
- `phase_a_core` 只定义字段安全面，不等于“纯股票池”
- 默认 `phase_a_core` 研究对象仍可能包含全 tick universe 中的非普通股票 / ETF / REIT / structured products / debt / 其他上市证券
- 如果策略、卡片或报告需要“股票研究池”，必须显式说明使用了上游 `instrument_profile` sidecar 的 `stock_research_candidate` lane
- `stock_research_candidate` 只是保守候选池，不是 `fully verified equity universe`
- `listed_security_unclassified` 不能被自动写成 `common_equity`

规则：
- 每张 card 都必须声明 `years`、`universe` 和 `instrument_universe`
- `phase_a_core` 不得使用 `TradeDir`、`OrderType`、`Type`、`OrderSideVendor`、`BrokerNo`、`Level`、`VolumePre`、full `Ext`
- `phase_a_caveat_lane` 只允许额外使用 `TradeDir`、`OrderType`、`Type`、`OrderSideVendor`，并且必须保持上游 caveat wording
- `phase_a_caveat_lane` 仍不得把 `BrokerNo`、`Level`、`VolumePre`、`BidOrderID`、`AskOrderID` 等写成已验证因子输入真值
- 只有在 research card 明确说明后，factor code 才能基于透明结构字段做过滤
- 如果 factor code 或 card 需要排除明显非股票 / 特殊证券，过滤逻辑必须显式引用上游 `instrument_profile` sidecar，而不是默认把低位代码或全 universe 当股票
- 当前本 repo 固定要求 `instrument_universe = stock_research_candidate`
- 如果 card 使用 `stock_research_candidate`，必须在 `info_boundary` 中明确写出“这不是 pure common-equity proof，低位非股票例外仍可能残留”
- 本 repo 不改动上游或固定 evaluator 所拥有的 corporate-action、liquidity、tradability 定义
- 任何未来更窄的 trading universe 都必须作为命名配置加入，不能在 factor code 里临时推断
