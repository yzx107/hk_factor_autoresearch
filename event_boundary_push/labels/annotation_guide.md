# Annotation Guide

## 标注目标

这一步的目标，是把模型抓出来的 `event case` 人工判断成：
- 像不像“入港股通前事件”
- 更像哪一种路径
- 判断依据是什么

这里的“入港股通前事件”指的是：
- 在潜在纳入窗口前后
- 盘面上出现控盘形成、边界接近、价格推进等协同特征
- 值得后续拿去和真实纳入样本做对照的案例

这不是法律判断，也不是官方纳入规则重建。

## 基本原则

- 不要求标注人给出“真相”，而是给出可复核的研究判断
- 不确定时优先保守，允许标 `unclear`
- 评论尽量描述盘面路径和研究理由，不要写成执法结论
- 单日异动不等于完整事件，优先看整个事件窗

## 推荐观察点

- `control proxy` 是否持续高位或逐步抬升
- 标的是否逐步靠近 `boundary proxy` 区间
- 价格是否在回撤受控的情况下连续推进
- 事件末段是否已经出现松动、抢跑结束或派发迹象
- 这条案例是否和“潜在入港股通前抢跑/准备”叙事一致

## 字段说明

- `annotator`
  - 填标注人姓名、缩写或固定 ID
  - 例：`yx`、`research_1`

- `expert_suspect_flag`
  - 这条案例整体上像不像目标事件
  - 建议值：`yes / no / unclear`
  - `yes`：较像“入港股通前事件”
  - `no`：不太像，或更像普通行情/消息驱动
  - `unclear`：证据不足，暂不下结论

- `perceived_path_type`
  - 你主观判断这条案例更像哪一种路径
  - 建议值：
    - `full_path_like`
    - `control_then_push`
    - `boundary_only`
    - `momentum_only`
    - `distribution`
    - `unclear`
  - 解释：
    - `full_path_like`：控盘、边界接近、价格推进三者都比较完整
    - `control_then_push`：更像控盘形成后开始推进，但边界信号一般
    - `boundary_only`：更像边界接近，但盘面结构支撑不够
    - `momentum_only`：主要是价格趋势，不像目标事件
    - `distribution`：事件后段更像派发、松动、撤退
    - `unclear`：看不出稳定路径

- `confidence`
  - 你对本次判断的把握
  - 建议值：`low / medium / high`

- `reason_code_1`
- `reason_code_2`
- `reason_code_3`
  - 填 1 到 3 个最核心原因即可
  - 建议短代码：
    - `persistent_control_proxy`
    - `near_boundary_band`
    - `suppressed_drawdown`
    - `steady_price_push`
    - `late_stage_distribution`
    - `news_driven_spike`
    - `weak_control_evidence`
    - `weak_boundary_fit`
    - `not_southbound_like`
  - 原则：
    - 优先写最影响你判断的原因
    - 不必追求完整枚举

- `operator_fingerprint_guess`
  - 记录你对盘面资金行为的主观猜测
  - 仅作研究用途，不代表真实主体识别
  - 可写示例：
    - `single_operator_accumulation`
    - `event_funds_front_run`
    - `momentum_chasers`
    - `unclear`

- `comment`
  - 自由备注
  - 建议写：
    - 哪几天最关键
    - 为什么像或不像“入港股通前事件”
    - 是否更像消息驱动、主题炒作或普通趋势
    - 有无明显派发、失败推进、抢跑过头等现象

## 一条推荐打标流程

1. 先看整条 `event case` 的起止时间和强度，不要只看单日。
2. 判断这条案例是否整体像“入港股通前事件”。
3. 再判断它更像哪一种路径类型。
4. 用 1 到 3 个 `reason_code` 固定住判断依据。
5. 最后在 `comment` 里补充上下文和犹豫点。

## 不要做的事

- 不要把标注结果写成违法操纵结论
- 不要把 proxy 指标等同于官方真值
- 不要因为单日拉升就自动判断为完整路径事件
- 不要为了凑满字段而强行下判断，不确定就标 `unclear`
