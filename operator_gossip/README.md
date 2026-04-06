# operator_gossip

`operator_gossip` 用来研究：

`operator / seat / style gossip -> future path -> executable strategy`

它不是法律判断模块，也不是“谁一定在做庄”的事实认定工具。
它的目标是把主观 gossip 变成：

- 可记录
- 可复盘
- 可分组统计
- 可转成规则化交易研究

## 研究问题

第一版先回答三个问题：

- 哪类 `operator_guess / style_guess` 在后续有稳定路径特征
- gossip 本身有没有 edge
- `gossip prior + market confirmation` 是否优于纯 gossip

## 最小工作流

1. 在 `labels/gossip_cases_template.csv` 里记录一条 gossip
2. 用脚本读取 gossip ledger
3. 计算每条 gossip 之后的未来收益与路径特征
4. 按 `operator_guess / style_guess / confidence` 分组看表现

## 当前范围

第一版先做事件研究，不直接做完整实盘系统。

重点包括：

- future returns
- path shape
- drawdown
- up-day share
- operator/style 分组表现

## 文件

- `gossip_schema.md`
  - 字段定义与推荐填法
- `labels/gossip_cases_template.csv`
  - 手工记录模板
- `labels/gossip_cases_intake_template.csv`
  - 面向同事的友好填写模板
- `labels/gossip_cases_intake_guide.md`
  - 面向同事的简版填写说明
- `backtest_operator_gossip.py`
  - 最小事件研究脚本

## 后续扩展

后面可以继续加：

- 盘口/成交确认信号
- seat-level feature
- operator-style 子策略
- gossip-only vs confirmation-only vs combined 对比
