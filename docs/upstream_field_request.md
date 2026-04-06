# 上游字段放行需求文档

本文档由下游研究工厂 `hk_factor_autoresearch` 编写，目的是向上游 `Hshare_Lab_v2` 团队说明当前因子原材料的瓶颈，以及我们希望申请的字段放行范围。

本文档不构成对上游的任何修改要求，仅作为沟通信息。

---

## 1. 当前原材料瓶颈

下游目前所有因子（含即将上线的 10 个新因子）都只能使用以下核心字段：

```
verified_trades: Price × Volume × Time × TickID
verified_orders: Price × Volume × Time × SeqNum × OrderId
```

这意味着：
- ✅ 我们知道市场的 **体量和形态**
- ❌ 我们完全不知道 **方向**（谁在买谁在卖）
- ❌ 我们完全不知道 **参与者结构**（是谁在交易）

这两个盲区使得所有因子集中在 activity / pressure / churn 类，相互之间的独立性很低。

---

## 2. 字段放行申请（优先级排序）

### P0: BrokerNo → caveat-only aggregation

**需要上游验证的内容：**
- BrokerNo 在 2026 年数据中编号是否一致（同一 broker 在不同日期的编号不变）
- 是否存在系统性的 missing / placeholder 值

**我们打算怎么用：**
- 只做日级聚合层的 HHI 集中度（broker 数量和集中度）
- 不做 broker 身份推断
- 不做跨日的 broker 追踪或网络分析
- 不 claim direct alpha

**我们能接受的约束：**
- 只用 2026 年数据
- 只在日级聚合后使用（不进入 tick 级因子）
- 走 caveat lane + 人工复核

**潜在的因子方向：**
- broker_hhi: 当日 broker 集中度
- broker_diversity: 活跃 broker 数量
- top_broker_share: 最大 N 家 broker 的成交占比

### P1: TradeDir → 稳定性升级

**当前状态：** 2026 已在 caveat-only 范围，可用但只作 vendor_aggressor_proxy_only。

**我们希望上游验证的内容：**
- 2026 年内 TradeDir 的编码规则是否保持一致
- 是否存在明显的 direction 分布异常日期
- vendor 层 BUY/SELL 标记与实际价格走势的弱一致性

**目的：** 不是要求升级为 verified truth，只是希望得到一个正式的"2026 年 vendor proxy 稳定性评估"文档，让下游使用 caveat lane 时更有信心。

### P2: OrderType → event code 稳定性确认

**当前状态：** caveat-only，仅限 stable vendor event code。

**我们希望上游验证的内容：**
- OrderType 的不同取值在 2026 年内是否稳定（比如 "new order" vs "cancel" vs "amend" 的编码不变）
- 是否有日期级别的编码异常

**我们打算怎么用：**
- 区分撤单 vs 修改单 vs 新增单的比例
- 构建 "cancel pressure" 类因子

---

## 3. 信息增量预估

| 字段 | 当前所有因子能观测的维度 | 放行后新增维度 |
|------|------------------------|---------------|
| BrokerNo | 无 | 参与者结构（谁在交易） |
| TradeDir (升级) | 弱方向 | 更可靠的买卖失衡代理 |
| OrderType | 无 | 订单类型组成（撤 vs 改 vs 新） |

---

## 4. 不会做的事情

无论上游是否放行，下游承诺：
- ❌ 不把 BrokerNo 做直接 alpha（如"跟踪某 broker 的交易模式"）
- ❌ 不把 TradeDir 当成 signed-side truth
- ❌ 不使用任何字段的方式超出上游放行的语义范围
- ❌ 不反向修改上游的任何内容

---

## 5. 联系方式

如果上游团队对上述需求有任何问题，可以直接联系下游研究负责人。

本文档仅陈述现状和需求，所有技术决定权归上游团队。
