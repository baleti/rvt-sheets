"""Read-only inspection of persistent drawing caches."""

import json
import os
from pathlib import Path


def _read_object(path):
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def scan(root):
    """Return cache records in descending directory-mtime order."""
    root = Path(root)
    ready = _read_object(root / "READY.json") or {}
    try:
        directories = list(root.iterdir())
    except OSError:
        return []
    records = []
    for directory in directories:
        try:
            if not directory.is_dir():
                continue
            mtime = directory.stat().st_mtime_ns
            meta = _read_object(directory / "meta.json")
            if meta is None:
                continue
            files = list(directory.iterdir())
        except OSError:
            continue
        size = sheets = views = 0
        for file in files:
            try:
                if not file.is_file():
                    continue
                size += file.stat().st_size
            except OSError:
                continue
            sheets += file.match("sheet_*.svg")
            views += file.match("view_*.svg")
        path = meta.get("path")
        parts = meta.get("parts")
        ready_entry = ready.get(path) if isinstance(path, str) else None
        completion = _read_object(directory / "complete.json") or {}
        records.append((mtime, {
            "key": directory.name,
            "path": path,
            "created": meta.get("created"),
            "sheets": sheets,
            "views": views,
            "bytes": size,
            "complete": (directory / "complete.json").exists(),
            "failed": completion.get("failed"),
            "ready": isinstance(ready_entry, dict)
            and ready_entry.get("key") == directory.name,
            "file_sha": parts.get("file") if isinstance(parts, dict) else None,
        }))
    records.sort(key=lambda record: (-record[0], record[1]["key"]))
    return [record for _, record in records]


def stale(entries):
    """Select unprotected entries, assuming newest-first ordering from scan."""
    entries = list(entries)
    keep = {}
    for index, entry in enumerate(entries):
        group = (entry["path"], entry["file_sha"])
        previous = keep.get(group)
        if previous is None or (
            entry["complete"] and not entries[previous]["complete"]
        ):
            keep[group] = index
    return [
        entry for index, entry in enumerate(entries)
        if not entry["ready"]
        and keep[(entry["path"], entry["file_sha"])] != index
    ]


def _human_size(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024


def format_table(entries):
    """Render aligned columns, displaying only source-file basenames."""
    rows = [["KEY", "PATH", "SHEETS", "VIEWS", "SIZE", "COMPLETE", "READY"]]
    for entry in entries:
        rows.append([
            entry["key"], os.path.basename(entry["path"] or ""),
            str(entry["sheets"]), str(entry["views"]),
            _human_size(entry["bytes"]),
            "yes" if entry["complete"] else "no",
            "yes" if entry["ready"] else "no",
        ])
    widths = [max(len(row[i]) for row in rows) for i in range(7)]
    return "\n".join(
        " ".join(value.ljust(width) for value, width in zip(row, widths)).rstrip()
        for row in rows
    )


def total_bytes(entries):
    """Sum the recorded file sizes."""
    return sum(entry["bytes"] for entry in entries)
