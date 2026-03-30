# Factor Specs

这个目录放“批量候选生成”的规格文件。

定位：
- 不是替代 `research_cards/`
- 也不是替代 `factor_defs/`
- 而是把同一 family 下可批量派生的 Gate A 候选先写成结构化规格

当前用途：
- 先服务 `phase_a_core`
- 先服务已经有稳定 `daily_agg` 的 family
- 先做 level / one_day_difference 这种可批量化变体

典型工作流：
1. 在 `factor_specs/*.toml` 里定义 prototype
2. 运行 `python3 harness/generate_factor_batch.py --spec <spec>`
3. 自动生成 `research_cards/examples/*.md` 和 `factor_defs/*.py`
   默认是“一个 prototype 一个模块”，在模块内部通过 `transform` 参数支持 `level` / `one_day_difference`
4. 把正式候选接入 `configs/autoresearch_phase_a.toml`
5. 跑固定 cycle

注意：
- spec 只能生成已经被 harness 支持的安全 family
- spec 不能绕过 `program.md`、`factor_contracts/` 和 `factor_families/` 的约束
- 生成器只适合高重复、低歧义的 Gate A 候选，不适合复杂手工研究卡
