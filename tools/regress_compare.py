"""Parse and compare per-view text-diff counts using only the standard library."""

import argparse
from pathlib import Path
import re


def parse_summary(text):
    """Return view IDs and difference counts, stopping before details."""
    pattern = re.compile(r'^(\d+)\s.*onlyRevit\s+(\d+)\s+onlyOurs\s+(\d+)')
    result = {}
    for line in text.splitlines():
        if line.startswith("=== DETAILS"):
            break
        match = pattern.match(line)
        if match:
            view_id, only_revit, only_ours = map(int, match.groups())
            result[view_id] = (only_revit, only_ours)
    return result


def load_baseline(text):
    """Return keyed difference counts from lines with at least five fields."""
    result = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        result[(fields[0], fields[1])] = (int(fields[3]), int(fields[4]))
    return result


def compare(new, baseline):
    """Return sorted lists of worse, better, and missing baseline keys."""
    worse, better, missing = [], [], []
    for key, base in baseline.items():
        if key not in new:
            missing.append(key)
            continue
        current = new[key]
        if current[0] > base[0] or current[1] > base[1]:
            worse.append(key)
        elif current[0] < base[0] or current[1] < base[1]:
            better.append(key)
    return sorted(worse), sorted(better), sorted(missing)


def main(argv):
    """Compare keyed files; return 1 if any view is worse, otherwise 0."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("new_keyed_file", metavar="NEW_KEYED_FILE")
    parser.add_argument("baseline_file", metavar="BASELINE_FILE")
    args = parser.parse_args(argv)
    new = load_baseline(Path(args.new_keyed_file).read_text(encoding="utf-8"))
    baseline = load_baseline(Path(args.baseline_file).read_text(encoding="utf-8"))
    worse, better, missing = compare(new, baseline)
    for key in worse:
        print(f"WORSE {key} {baseline[key]} -> {new[key]}")
    print(
        f"views {len(new)} worse {len(worse)} "
        f"better {len(better)} missing {len(missing)}"
    )
    return 1 if worse else 0


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
