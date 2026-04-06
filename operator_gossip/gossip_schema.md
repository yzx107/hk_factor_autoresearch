# Gossip Schema

## 目标

每一行代表一条在当时真实存在的 gossip 记录。

要求：

- 先记录，再验证
- 不允许事后根据走势回填方向和置信度

## 必填字段

- `asof_date`
  - 听到 gossip 或形成交易观察的日期

- `ticker`
  - 五位股票代码

- `operator_guess`
  - 你认为可能的操盘者/资金类型
  - 例：`operator_a`、`family_office_cluster`、`unknown_small_cap_group`

- `seat_guess`
  - 你认为更可能出现的席位、通道或成交通路
  - 例：`seat_x`、`southbound_channel_like`、`broker_cluster_b`

- `style_guess`
  - 主观风格标签
  - 建议值：
    - `slow_grind`
    - `washout_then_push`
    - `gap_up_momentum`
    - `intraday_support`
    - `distribution_after_spike`
    - `news_assisted_push`
    - `unclear`

- `direction`
  - 预期方向
  - 建议值：`long / short / unclear`

- `confidence`
  - 这条 gossip 的主观把握
  - 建议值：`low / medium / high`

- `expected_horizon_days`
  - 你觉得 edge 更可能在几天内兑现

## 可选字段

- `seat_style_notes`
  - 关于席位与风格的补充说明

- `catalyst_guess`
  - 你怀疑背后的催化
  - 例：`placement`、`southbound_inclusion`、`index_flow`、`fundraising`、`none`

- `live_confirmation_needed`
  - 是否需要盘面确认后才会下单
  - 建议值：`yes / no`

- `notes`
  - 自由备注

## 研究原则

- `operator_guess` 可以错，关键是它是否带来统计上有用的条件收益
- `seat_guess` 可以模糊，但要尽量稳定命名
- `style_guess` 要少而稳，不要每条都发明新标签

## 第一版推荐问题

先看：

- 哪类 `style_guess` 最有 edge
- 哪类 `confidence` 最可靠
- 哪些 `operator_guess` 有明显 path dependency
- 是否存在明显的“高胜率但高回撤”类型

## 给同事填写时的建议

如果是非技术同事填写，优先使用：

- `labels/gossip_cases_intake_template.csv`

这份 intake 模板做了三件事：

- 列名更直白
- 示例值更贴近日常表达
- 允许先用自然语言记录，再由研究侧映射成标准字段
