"""Semantic-aware scoreboard wrapper.

This wrapper keeps the existing scoreboard implementation intact and adds a
conservative semantic gating pass on top of the generated payload.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import harness.scoreboard as scoreboard_module
from harness.semantic_bridge import (
    STATUS_BLOCKED,
    STATUS_MANUAL_REVIEW,
    STATUS_NOT_LOADED,
    STATUS_SESSION_SPLIT,
    STATUS_UNRESOLVED,
    append_semantic_gate_log,
    evaluate_semantic_gate,
)


def _override_readiness(row: dict[str, Any]) -> None:
    status = str(row.get("semantic_gate_status", ""))
    if status == STATUS_BLOCKED:
        row["promotion_readiness"] = "reject"
        row["primary_reject_reason"] = "semantic_blocked"
        row["secondary_reject_reasons"] = [
            item for item in list(row.get("secondary_reject_reasons", [])) if item != "semantic_blocked"
        ]
        return
    if status in {STATUS_MANUAL_REVIEW, STATUS_UNRESOLVED, STATUS_NOT_LOADED}:
        original_primary = str(row.get("primary_reject_reason", "none"))
        secondary = [item for item in list(row.get("secondary_reject_reasons", [])) if item != original_primary]
        if original_primary not in {"", "none", "semantic_manual_review_required"}:
            secondary = [original_primary] + secondary
        row["promotion_readiness"] = "watch"
        row["primary_reject_reason"] = "semantic_manual_review_required"
        row["secondary_reject_reasons"] = secondary
        return
    if status == STATUS_SESSION_SPLIT:
        original_primary = str(row.get("primary_reject_reason", "none"))
        secondary = [item for item in list(row.get("secondary_reject_reasons", [])) if item != original_primary]
        if original_primary not in {"", "none", "semantic_requires_session_split"}:
            secondary = [original_primary] + secondary
        row["promotion_readiness"] = "watch"
        row["primary_reject_reason"] = "semantic_requires_session_split"
        row["secondary_reject_reasons"] = secondary


def apply_semantic_gate_to_payload(
    payload: dict[str, Any],
    *,
    notes: str,
    semantic_dqa_root: Path | None = None,
) -> dict[str, Any]:
    scoreboard_id = str(payload["scoreboard_id"])
    factor_board = list(payload.get("factor_board", []))
    semantic_counts: Counter[str] = Counter()
    for row in factor_board:
        gate_payload = evaluate_semantic_gate(
            row,
            factor_profile=dict(row.get("factor_profile", {})),
            family_profile=dict(row.get("family_profile", {})),
            semantic_dqa_root=semantic_dqa_root,
        )
        row.update(gate_payload)
        _override_readiness(row)
        append_semantic_gate_log(
            scoreboard_id=scoreboard_id,
            factor_name=str(row.get("factor_name", "")),
            family_name=str(row.get("family_name", row.get("factor_family", ""))),
            gate_payload=row,
            notes=notes,
        )
        semantic_counts[str(row.get("semantic_gate_status", ""))] += 1
    payload["factor_board"] = factor_board
    payload["semantic_gate_status_counts"] = dict(semantic_counts)
    return payload


def _render_report_zh(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 语义门控候选板")
    lines.append("")
    lines.append(f"- 候选板ID：`{payload['scoreboard_id']}`")
    lines.append(f"- 因子数量：`{payload['factor_count']}`")
    lines.append(f"- 比较数量：`{payload['comparison_count']}`")
    lines.append(f"- 语义状态统计：`{json.dumps(payload.get('semantic_gate_status_counts', {}), ensure_ascii=False)}`")
    lines.append("")
    lines.append("## 候选摘要")
    lines.append("")
    for row in payload.get("factor_board", []):
        lines.append(
            f"- `{row.get('factor_name', '')}` 家族=`{row.get('family_name', row.get('factor_family', ''))}` "
            f"readiness=`{row.get('promotion_readiness', 'unknown')}` "
            f"主拒绝原因=`{row.get('primary_reject_reason', 'none')}` "
            f"语义状态=`{row.get('semantic_gate_status', '')}` "
            f"语义模块=`{','.join(row.get('semantic_gate_modules', [])) or 'none'}` "
            f"人工复核=`{row.get('semantic_requires_manual_review', False)}` "
            f"需要session拆分=`{row.get('semantic_requires_session_split', False)}`"
        )
    lines.append("")
    lines.append("## 说明")
    lines.append("")
    lines.append("- 本报告是在原始 scoreboard 结果之上，额外叠加上游 semantic/admissibility 结论后生成。")
    lines.append("- 若语义状态为 `semantic_blocked`，该候选会被直接降为 reject。")
    lines.append("- 若语义状态为 `semantic_requires_manual_review` / `semantic_unresolved_mapping` / `semantic_not_loaded`，该候选会被保守降为 watch。")
    lines.append("- 若语义状态为 `semantic_requires_session_split`，该候选会被保守降为 watch，并提示必须做 session 级拆分。")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a semantic-aware scoreboard from latest factor runs.")
    parser.add_argument("--factors", nargs="+", required=True, help="Factor names to include.")
    parser.add_argument("--notes", default="", help="Short scoreboard note.")
    parser.add_argument("--semantic-dqa-root", default="", help="Optional upstream semantic dqa root.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _, payload, summary_path = scoreboard_module.build_scoreboard(args.factors, notes=args.notes)
    semantic_root = Path(args.semantic_dqa_root) if args.semantic_dqa_root else None
    payload = apply_semantic_gate_to_payload(payload, notes=args.notes, semantic_dqa_root=semantic_root)
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report_path = summary_path.parent / "scoreboard_semantic_report_zh.md"
    report_path.write_text(_render_report_zh(payload), encoding="utf-8")
    print(
        f"{payload['scoreboard_id']} factors={payload['factor_count']} comparisons={payload['comparison_count']} semantic={json.dumps(payload.get('semantic_gate_status_counts', {}), ensure_ascii=False)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
