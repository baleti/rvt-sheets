#!/usr/bin/env python3
"""Inspect caches and optionally remove stale cache directories."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys

# Allow direct execution from a source checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rvtsheets import cachereport


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", default=os.environ.get(
            "RVT_SHEETS_CACHE", os.path.expanduser("~/.cache/rvt-sheets")
        ),
    )
    parser.add_argument("--json", action="store_true", help="print JSON records")
    parser.add_argument("--stale", action="store_true", help="list only stale caches")
    parser.add_argument("--prune", action="store_true", help="remove stale caches")
    parser.add_argument("--yes", action="store_true", help="actually perform pruning")
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    entries = cachereport.scan(root)
    obsolete = cachereport.stale(entries)
    shown = obsolete if args.stale else entries
    if args.json:
        print(json.dumps(shown, indent=2))
    else:
        print(cachereport.format_table(shown))
        print(
            f"{len(shown)} caches, "
            f"{cachereport.total_bytes(shown) / 1024 ** 2:.1f} MB, "
            f"{len(obsolete)} stale"
        )
    if args.prune:
        # Keep JSON stdout parseable when pruning and JSON are combined.
        stream = sys.stderr if args.json else sys.stdout
        if not args.yes:
            print("dry run: pass --yes to delete stale caches", file=stream)
        for entry in obsolete:
            key = entry["key"]
            directory = root / key
            if (
                not re.fullmatch(r"[0-9a-fA-F]{16}", key)
                or directory.is_symlink()
                or not directory.is_dir()
                or directory.resolve().parent != root
            ):
                continue
            print(f"{'Removing' if args.yes else 'Would remove'} {directory}",
                  file=stream, flush=True)
            if args.yes:
                shutil.rmtree(directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
