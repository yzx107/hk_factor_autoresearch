"""Detect daily boundary-push event states."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from event_boundary_push._core import load_config, write_event_state_daily


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect boundary-push event states on the event universe.")
    parser.add_argument(
        "--config",
        default="event_boundary_push/configs/boundary_push_event_v0.toml",
        help="Path to the module config TOML.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config))
    frame, summary = write_event_state_daily(config)
    print(
        f"event_state_daily rows={frame.height} active_event_rows={summary['active_event_rows']} "
        f"output={config.event_state_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
