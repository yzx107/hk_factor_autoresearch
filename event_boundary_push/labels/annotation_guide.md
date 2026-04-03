# Annotation Guide

## 标注目标

标注目标不是判断“是否违法操纵”。

本模块的人工标注目标是：
- 判断给定事件窗内，是否存在明显的
  - 控盘形成
  - 洗筹
  - 市值推进
  - 派发
  - 或不明确（`unclear`）
  等路径特征。

## 基本原则

- 允许不同标注人意见不一致
- 不确定时优先标 `unclear`
- 评论应尽量描述路径特征，而不是给法律结论

## 推荐观察点

- 事件窗内 control proxy 是否持续抬升
- 标的是否逐步靠近 boundary proxy 区间
- 价格是否在回撤受控的情况下持续推进
- 事件末段是否出现明显松动或派发迹象

## 字段说明

- `expert_suspect_flag`
  - 建议值：`yes / no / unclear`
- `perceived_path_type`
  - 建议值：`control_build / washout / boundary_push / distribution / unclear`
- `confidence`
  - 建议值：`low / medium / high`
- `reason_code_*`
  - 可写简短原因代码，例如：`persistent_control_proxy`、`near_boundary_band`、`suppressed_drawdown`
- `operator_fingerprint_guess`
  - 仅作研究记录，不代表真实主体识别

## 不要做的事

- 不要把标注结果写成执法结论
- 不要把 proxy 指标等同于官方真值
- 不要因为单日拉升就自动判断为完整路径事件
