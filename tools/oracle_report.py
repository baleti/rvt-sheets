"""Summarize precision, recall, and errors from an oracle element-list sweep."""

import re
import sys


_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_RESULT = re.compile(
    rf"^\s*(\S+)\s+(new|old)\s+ALL\s+precision\s+({_NUMBER})"
    rf"\s+recall\s+({_NUMBER})\s+\(tp\s+(\d+)\s+fp\s+(\d+)"
    r"\s+fn\s+(\d+)\)\s*$"
)


def parse(text):
    """Return scene/mode metrics, ignoring skip lines and unrelated output."""
    rows = {}
    for line in text.splitlines():
        match = _RESULT.fullmatch(line)
        if match is None:
            continue
        scene, mode, precision, recall, tp, fp, fn = match.groups()
        rows.setdefault(scene, {})[mode] = (
            float(precision), float(recall), int(tp), int(fp), int(fn)
        )
    return rows


def totals(rows, mode):
    """Return summed (tp, fp, fn) for scenes containing the requested mode."""
    tp = fp = fn = 0
    for modes in rows.values():
        if mode in modes:
            metrics = modes[mode]
            tp += metrics[2]
            fp += metrics[3]
            fn += metrics[4]
    return tp, fp, fn


def report(rows):
    """Return changed scenes ordered by old errors, followed by overall totals."""
    lines = ["scene                          old fp/fn   new fp/fn   dP     dR"]
    scenes = [
        scene for scene, modes in rows.items()
        if "old" in modes and "new" in modes
        and modes["old"][3:5] != modes["new"][3:5]
    ]
    scenes.sort(key=lambda scene: (
        -(rows[scene]["old"][3] + rows[scene]["old"][4]), scene
    ))
    for scene in scenes:
        old, new = rows[scene]["old"], rows[scene]["new"]
        old_errors = f"{old[3]}/{old[4]}"
        new_errors = f"{new[3]}/{new[4]}"
        lines.append(
            f"{scene:<30} {old_errors:<11} {new_errors:<11} "
            f"{new[0] - old[0]:+.3f} {new[1] - old[1]:+.3f}"
        )
    _, old_fp, old_fn = totals(rows, "old")
    _, new_fp, new_fn = totals(rows, "new")
    lines.append(f"TOTAL old fp {old_fp} fn {old_fn} -> new fp {new_fp} fn {new_fn}")
    return "\n".join(lines)


def main(argv):
    """Read argv[1] or stdin, print the report, and return zero."""
    if len(argv) > 1:
        with open(argv[1], encoding="utf-8") as source:
            text = source.read()
    else:
        text = sys.stdin.read()
    print(report(parse(text)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
