# hk_factor_autoresearch

这个 repo 是港股因子研究工厂（research factory）repo。
它不是数据底座 repo，也不是 production 交易系统。

当前范围是 `Phase A / 半自动`：
- 冻结 Layer 0 边界
- 先写 research card，再落因子实现
- 固定回测与评估接口，不在普通实验里漂移
- 只自动化 Gate A 数据合法性检查
- lineage 和 experiment registry 采用 append-only
- 实验必须走固定 harness，不允许临时 shell 拼装流程

与 `Hshare_Lab_v2` 的关系：
- 上游 repo：`/Users/yxin/AI_Workstation/Hshare_Lab_v2`
- 本 repo 只读消费上游 verified 和 admissibility 结论
- 本 repo 不得重定义上游字段语义，也不能反向改写上游 Layer 0

现在 repo 里有什么：
- `data_contracts/`：固定字段、年份、timing 边界
- `factor_contracts/`：单因子 metadata 合同
- `gates/`：研究晋级门和 promotion policy
- `research_cards/`：研究卡模板和 smoke 示例
- `gatekeeper/gate_a_data.py`：最小 Gate A 合法性检查
- `configs/baseline_phase_a.toml`：冻结 baseline 配置
- `configs/autoresearch_phase_a.toml`：固定候选池配置
- `cache/daily_agg/`：从上游 verified 生成的本地逐日聚合缓存
- `harness/run_phase_a.py`：最小 autoresearch 风格实验入口
- `harness/run_pre_eval.py`：固定 forward-return pre-eval
- `harness/autoresearch_cycle.py`：端到端 cycle runner
- `registry/`：append-only 实验留痕骨架

新增的研究工厂控制层：
- `factor_contracts/schema.md`：统一说明每个因子必须声明什么
- `registry/factor_families.tsv`：把候选按机制家族登记，而不是只看单次实验
- `registry/failure_taxonomy.md`：统一失败分类，避免 registry 变成墓地
- `gates/promotion_policy.md`：把 Gate A/B/C/D/E 的目标和输出固定下来

固定 pre-eval 当前输出：
- rank IC
- top-bottom spread
- 在固定分箱规则下计算的 normalized mutual information（NMI）

这里没有什么：
- 没有多 agent 搜索工厂
- 没有 production backtester
- 没有重型 paper-trading 系统
- 默认不做 broker alpha、signed-flow truth、queue semantics

最小 smoke：

```bash
python3 -m unittest tests/test_gate_a_smoke.py
```

最小 harness run：

```bash
python3 harness/run_phase_a.py \
  --card research_cards/examples/structural_activity_proxy_2026.md \
  --factor structural_activity_proxy
```

真实 `2026 verified` 数据 run：

```bash
python3 harness/run_verified_factor.py \
  --card research_cards/examples/structural_activity_proxy_2026.md \
  --factor structural_activity_proxy \
  --dates 2026-03-13
```

构建本地逐日聚合缓存：

```bash
python3 harness/build_daily_agg.py --table all --year 2026
```

查看项目进度：

```bash
python3 harness/status.py
```

比较最近两条因子 run：

```bash
python3 harness/compare_factors.py \
  --left-factor structural_activity_proxy \
  --right-factor avg_trade_notional_bias
```

生成候选板：

```bash
python3 harness/scoreboard.py \
  --factors structural_activity_proxy avg_trade_notional_bias
```

对最新因子实验跑固定 pre-eval：

```bash
python3 harness/run_pre_eval.py \
  --factor structural_activity_proxy
```

导出共享 labels 供 pre-eval 复用：

```bash
python3 harness/export_forward_labels.py --year 2026
```

运行一轮固定 autoresearch cycle：

```bash
python3 harness/autoresearch_cycle.py
```

候选板会额外写出：

```text
runs/<scoreboard_id>/scoreboard_report.md
```

每个 verified 因子 run 也会写固定 diagnostics：

```text
runs/<experiment_id>/diagnostics_summary.json
```

每个固定 pre-eval run 会写：

```text
runs/<pre_eval_id>/pre_eval_summary.json
```

每个 autoresearch cycle 会写：

```text
runs/<cycle_id>/cycle_summary.json
```
