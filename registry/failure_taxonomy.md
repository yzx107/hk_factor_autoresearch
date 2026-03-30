# Failure Taxonomy

这个 taxonomy 用来把“失败”从一句随手备注，变成可累积的研究知识。

## 使用原则

- 一个实验可以命中多个失败标签
- failure 标签描述的是失败原因，不是情绪判断
- 失败标签应该和 gate 位置对应
- 失败实验不能删除，只能被标记、归类、保留

## A 类：数据与边界

- `data_invalid`
  research card 或输入字段本身不合法
- `semantic_boundary_violation`
  越过 `TradeDir`、`BrokerNo`、queue 等边界
- `coverage_too_sparse`
  样本覆盖不足，无法支持比较

## B 类：统计有效性

- `signal_too_weak`
  固定 pre-eval 下统计关系过弱
- `sign_unstable`
  不同日期或切片下方向不稳定
- `nonlinear_evidence_absent`
  线性和非线性证据都很弱

## C 类：稳健性

- `unstable_by_year`
  按年份切片时不稳定
- `unstable_by_bucket`
  bucket 间结构不稳定
- `regime_specific_only`
  只在极窄 regime 下成立
- `event_polluted`
  明显被事件驱动或异常样本污染

## D 类：增量性

- `redundant_to_existing_factor`
  与已有候选高度重合
- `redundant_to_baseline`
  只是 baseline 的轻微改写
- `family_member_dominates`
  同家族已有更强版本，这个版本没有额外价值

## E 类：可交易性

- `not_tradable`
  即使有关系也不适合进入交易层
- `turnover_too_high`
  信号依赖过高换手
- `concentration_too_high`
  暴露过度集中在少量标的或单一子集

## 假设层失败

- `hypothesis_falsified`
  结果明确与原始机制叙事不一致
- `mechanism_unclear`
  有统计关系，但机制无法自洽
- `proxy_only`
  因子最终只是在重复表达体量、流动性或价格水平

## 当前推荐写法

在 notes、review 或未来 gate 输出里，优先使用：

```text
failure_tags=redundant_to_baseline,proxy_only
```

而不是只写：

```text
this factor is not good
```

## 维护原则

- 先保持 taxonomy 稳定，再增加新标签
- 新标签应当是新信息，而不是旧标签换个说法
- 如果两个标签总是一起出现，应考虑合并
