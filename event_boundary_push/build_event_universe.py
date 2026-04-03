"""Build the event scanning universe for the boundary push module."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from event_boundary_push._core import load_config, write_event_universe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the event-driven boundary push universe.")
    parser.add_argument(
        "--config",
        default="event_boundary_push/configs/boundary_push_event_v0.toml",
        help="Path to the module config TOML.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config))
    frame, summary = write_event_universe(config)
    print(
        f"event_universe rows={frame.height} included={summary['included_count']} "
        f"output={config.event_universe_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
