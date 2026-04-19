# 语义门控说明

这次改动没有重写原有 harness，而是新增一层保守包装器。

## 上游依赖

默认读取上游 semantic 输出：

- `semantic/year=<year>/semantic_yearly_summary.parquet`
- `semantic/year=<year>/semantic_admissibility_bridge.parquet`

默认根目录可由以下环境变量控制：

- `HK_SEMANTIC_UPSTREAM_ROOT`
- `HK_SEMANTIC_DQA_ROOT`

## 新增文件

- `harness/semantic_bridge.py`
- `harness/run_semantic_scoreboard.py`
- `registry/semantic_gate_log.tsv`（运行时 append-only）

## 候选板命令

```bash
python3 harness/run_semantic_scoreboard.py \
  --factors structural_activity_proxy avg_trade_notional_bias \
  --notes "semantic gating smoke"
```

如需显式指定上游 semantic dqa 根目录：

```bash
python3 harness/run_semantic_scoreboard.py \
  --factors structural_activity_proxy avg_trade_notional_bias \
  --semantic-dqa-root /path/to/Hshare_Lab_v2/data/dqa \
  --notes "semantic gating smoke"
```

## 语义状态

当前会输出：

- `semantic_allowed`
- `semantic_allow_with_caveat`
- `semantic_blocked`
- `semantic_requires_manual_review`
- `semantic_requires_session_split`
- `semantic_unresolved_mapping`
- `semantic_not_loaded`

## 当前策略

- `semantic_blocked` -> 候选板里保守降为 `reject`
- `semantic_requires_manual_review` / `semantic_unresolved_mapping` / `semantic_not_loaded` -> 保守降为 `watch`
- `semantic_requires_session_split` -> 保守降为 `watch`

## 输出

运行后会补充：

- `scoreboard_summary.json` 中的 semantic 字段
- `scoreboard_semantic_report_zh.md`
- `registry/semantic_gate_log.tsv`
