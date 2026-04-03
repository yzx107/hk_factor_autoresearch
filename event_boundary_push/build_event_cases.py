"""Build event cases from detected daily state rows."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from event_boundary_push._core import load_config, write_event_cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build event cases for the boundary push module.")
    parser.add_argument(
        "--config",
        default="event_boundary_push/configs/boundary_push_event_v0.toml",
        help="Path to the module config TOML.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config))
    frame, summary = write_event_cases(config)
    print(f"event_cases rows={frame.height} output={config.event_case_path}")
    if summary.get("event_type_counts"):
        top = summary["event_type_counts"][0]
        print(f"top_event_type={top['event_type']} count={top['count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
