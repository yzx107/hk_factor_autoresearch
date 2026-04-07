"""Run the minimal formal backtest lane for one shortlisted factor."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest_engine.minimal_lane import run_minimal_backtest

RUN_ROOT = ROOT / "runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the minimal formal backtest lane for one factor.")
    parser.add_argument("--run-dir", required=True, help="Materialized factor run directory.")
    parser.add_argument("--labels-path", required=True, help="Forward-label parquet path.")
    parser.add_argument("--score-column", default="", help="Optional score column override.")
    parser.add_argument("--label-column", default="forward_return_1d_close_like", help="Label column name.")
    parser.add_argument("--top-fraction", type=float, default=0.1, help="Long/short bucket fraction.")
    parser.add_argument("--cost-bps", type=float, default=0.0, help="Conservative one-way cost in bps.")
    parser.add_argument("--notes", default="", help="Short backtest note.")
    parser.add_argument("--json", action="store_true", help="Emit summary JSON only.")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSON artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def run_minimal_backtest_for_factor(
    *,
    run_dir: Path,
    labels_path: Path,
    score_column: str = "",
    label_column: str = "forward_return_1d_close_like",
    top_fraction: float = 0.1,
    cost_bps: float = 0.0,
    notes: str = "",
) -> tuple[str, dict[str, object], Path]:
    data_summary = _load_json(run_dir / "data_run_summary.json")
    factor_path = run_dir / "factor_output.parquet"
    if not factor_path.exists():
        raise FileNotFoundError(f"Missing factor output parquet: {factor_path}")
    if not labels_path.exists():
        raise FileNotFoundError(f"Missing labels parquet: {labels_path}")

    factor_df = pl.read_parquet(factor_path)
    labels_df = pl.read_parquet(labels_path)
    resolved_score_column = score_column or str(data_summary["score_column"])
    result = run_minimal_backtest(
        factor_df,
        labels_df,
        factor_name=str(data_summary["factor_name"]),
        score_column=resolved_score_column,
        label_column=label_column,
        target_instrument_universe=str(data_summary.get("target_instrument_universe", "")),
        source_instrument_universe=str(data_summary.get("source_instrument_universe", "")),
        contains_cross_security_source=bool(data_summary.get("contains_cross_security_source", False)),
        universe_filter_version=str(data_summary.get("universe_filter_version", "")),
        horizon=str(data_summary.get("transform_name", "1d")),
        top_fraction=top_fraction,
        cost_bps=cost_bps,
    )

    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backtest_id = f"bt_{stamp}_{data_summary['factor_name']}"
    run_root = RUN_ROOT / backtest_id
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "minimal_backtest_summary.json"
    report_path = run_root / "minimal_backtest_report.md"

    payload = {
        **result.as_dict(),
        "backtest_id": backtest_id,
        "created_at": created_at,
        "notes": notes,
        "source_factor_run_dir": str(run_dir),
        "source_factor_name": data_summary["factor_name"],
        "score_column": resolved_score_column,
        "label_column": label_column,
        "labels_path": str(labels_path),
        "factor_profile": data_summary.get("factor_profile", {}),
        "family_profile": data_summary.get("family_profile", {}),
    }
    result_payload = result.as_dict()
    result_payload["backtest_id"] = backtest_id
    payload["result"] = result_payload
    summary_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Minimal Backtest",
                "",
                f"- backtest_id: `{backtest_id}`",
                f"- factor_name: `{data_summary['factor_name']}`",
                f"- spread_return: `{payload['spread_return']}`",
                f"- cost_adjusted_spread_return: `{payload['cost_adjusted_spread_return']}`",
                f"- turnover_proxy: `{payload['turnover_proxy']}`",
                f"- hit_rate: `{payload['hit_rate']}`",
                f"- stability_proxy: `{payload['stability_proxy']}`",
                f"- coverage_ratio: `{payload['coverage_ratio']}`",
                "",
                "## Universe",
                "",
                f"- target_instrument_universe: `{payload['target_instrument_universe']}`",
                f"- source_instrument_universe: `{payload['source_instrument_universe']}`",
                f"- contains_cross_security_source: `{payload['contains_cross_security_source']}`",
                f"- universe_filter_version: `{payload['universe_filter_version']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return backtest_id, payload, summary_path


def main() -> int:
    args = parse_args()
    backtest_id, payload, _ = run_minimal_backtest_for_factor(
        run_dir=Path(args.run_dir),
        labels_path=Path(args.labels_path),
        score_column=args.score_column,
        label_column=args.label_column,
        top_fraction=args.top_fraction,
        cost_bps=args.cost_bps,
        notes=args.notes,
    )
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(
            f"{backtest_id} factor={payload['source_factor_name']} "
            f"spread_return={payload['spread_return']} "
            f"hit_rate={payload['hit_rate']} "
            f"turnover_proxy={payload['turnover_proxy']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
