# Universe Rules

Phase A 使用的是保守的消费层 universe，而不是重新定义上游 data contract。

默认 universe：
- `phase_a_core` = 可以基于上游 `verified_orders` 和 `verified_trades` 当前已放行结构字段、并结合声明年份范围来研究的行和证券
- `phase_a_caveat_lane` = 只能在显式 caveat、人工复核和单独 namespace 下消费 caveat-only 字段的受限研究面

规则：
- 每张 card 都必须声明 `years` 和 `universe`
- `phase_a_core` 不得使用 `TradeDir`、`OrderType`、`Type`、`OrderSideVendor`、`BrokerNo`、`Level`、`VolumePre`、full `Ext`
- `phase_a_caveat_lane` 只允许额外使用 `TradeDir`、`OrderType`、`Type`、`OrderSideVendor`，并且必须保持上游 caveat wording
- `phase_a_caveat_lane` 仍不得把 `BrokerNo`、`Level`、`VolumePre`、`BidOrderID`、`AskOrderID` 等写成已验证因子输入真值
- 只有在 research card 明确说明后，factor code 才能基于透明结构字段做过滤
- 本 repo 不改动上游或固定 evaluator 所拥有的 corporate-action、liquidity、tradability 定义
- 任何未来更窄的 trading universe 都必须作为命名配置加入，不能在 factor code 里临时推断
