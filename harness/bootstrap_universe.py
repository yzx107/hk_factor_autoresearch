"""Check whether the stock target-universe sidecar is ready for this repo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.instrument_universe import (
    INSTRUMENT_PROFILE_PATH,
    bootstrap_instrument_universe_status,
    ensure_instrument_profile_sidecar,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether the stock target-universe sidecar is available.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    status = bootstrap_instrument_universe_status(INSTRUMENT_PROFILE_PATH)
    try:
        ensure_instrument_profile_sidecar(INSTRUMENT_PROFILE_PATH)
    except FileNotFoundError as exc:
        status["status"] = "missing"
        status["message"] = str(exc)
        if args.json:
            print(json.dumps(status, indent=2, ensure_ascii=False))
        else:
            print(status["message"])
        return 1

    status["status"] = "ready"
    status["message"] = f"Instrument profile sidecar ready: {status['instrument_profile_path']}"
    if args.json:
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        print(status["message"])
        print(f"summary_path={status['summary_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
