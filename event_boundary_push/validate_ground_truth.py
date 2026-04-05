"""Validate detected event cases against historical inclusion/event ground truth."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from event_boundary_push._ground_truth import load_ground_truth_config, write_ground_truth_validation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate boundary-push events against ground-truth windows.")
    parser.add_argument(
        "--config",
        default="event_boundary_push/configs/boundary_push_ground_truth_v0.toml",
        help="Path to the ground-truth validation config TOML.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_ground_truth_config(Path(args.config))
    matches, noise_cases, summary = write_ground_truth_validation(config)
    print(
        f"ground_truth_count={summary['ground_truth_count']} matched={summary['matched_truth_count']} "
        f"hit_rate={summary['hit_rate']:.4f} output={config.summary_path}"
    )
    print(
        f"noise_case_count={summary['noise_case_count']} "
        f"matches_output={config.matches_path} noise_output={config.noise_cases_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
