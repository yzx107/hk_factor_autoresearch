# Factor Definitions

这里只放因子定义。

应该做：
- 优先把高重复候选写进 `factor_specs/`
- 实现信号公式
- 保持逻辑纯净、易测试
- 每个定义都配一张 research card
- 每个正式候选都导出统一 factor contract metadata
- 同一原型的 `level` / `change` 这类变体优先做成 `transform` 参数，而不是独立文件
- 每轮实验只对应一个小的因子改动

不要做：
- 修改 evaluator 规则
- 修改成本假设
- 修改 universe 定义
- 重新解释被阻断字段
- 在做因子时顺手改 harness 文件

正式候选推荐导出的 metadata：
- `FACTOR_ID`
- `FACTOR_FAMILY`
- `MECHANISM`
- `INPUT_DEPENDENCIES`
- `RESEARCH_UNIT`
- `HORIZON_SCOPE`
- `VERSION`
- `TRANSFORM_CHAIN`
- `EXPECTED_REGIME`
- `FORBIDDEN_SEMANTIC_ASSUMPTIONS`

具体说明见：
- `factor_contracts/schema.md`
- `registry/factor_families.tsv`
