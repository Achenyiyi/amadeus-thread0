from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from amadeus_thread0.runtime_audit import audit_runtime_layout, audit_runtime_layout_json, render_runtime_audit_report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect shared/isolated runtime data layout.")
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Runtime data root to inspect. Default: data",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON instead of the human-readable report.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    data_dir = Path(args.data_dir)
    if args.json:
        print(audit_runtime_layout_json(data_dir))
        return
    print(render_runtime_audit_report(audit_runtime_layout(data_dir)))


if __name__ == "__main__":
    main()
