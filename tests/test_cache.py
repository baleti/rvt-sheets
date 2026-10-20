"""Characterise the persistent cache using only synthetic, temporary files."""
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets import cache


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    root = tmp_path / "cache"
    code = tmp_path / "code"
    reader = tmp_path / "reader"
    code.mkdir()
    reader.mkdir()
    monkeypatch.setenv("RVT_SHEETS_CACHE", str(root))
    monkeypatch.setenv("RVT_READER_DIR", str(reader))
    # These settings are captured at import time, so patch the globals too.
    monkeypatch.setattr(cache, "ROOT", str(root))
    monkeypatch.setattr(cache, "HERE", str(code))
    monkeypatch.setattr(cache, "READER_DIR", str(reader))


@pytest.fixture
def model(tmp_path):
    path = tmp_path / "model.rvt"
    path.write_bytes(b"synthetic model")
    return path


def test_directory_key_and_metadata(model):
    item = cache.Cache(model)
    parts = {
        "file": hashlib.sha1(b"synthetic model").hexdigest(),
        "code": hashlib.sha1(b"").hexdigest()[:12],
        "settings": cache.SETTINGS_VERSION,
    }
    key = hashlib.sha1(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:16]
    assert item.path == str(model.resolve())
    assert item.key == key
    assert item.dir == str(Path(cache.ROOT) / key)
    assert item.fn("sheet_1.svg") == str(Path(item.dir) / "sheet_1.svg")
    meta = json.loads(item.read("meta.json"))
    assert meta["path"] == item.path
    assert meta["parts"] == {**parts, "reader": hashlib.sha1(b"").hexdigest()[:12]}
    assert isinstance(meta["created"], str)
    assert set(Path(cache.ROOT).iterdir()) == {
        Path(item.dir), Path(cache.ROOT) / "filehash.json",
    }


def test_explicit_key_preserves_existing_metadata(model):
    item = cache.Cache(model, key="known-key")
    item.write("meta.json", '{"existing": true}')
    again = cache.Cache(model, key="known-key")
    assert again.key == "known-key"
    assert again.read("meta.json") == '{"existing": true}'


def test_reader_changes_parts_but_not_key(model):
    first = cache.Cache(model)
    (Path(cache.READER_DIR) / "rvt_reader.py").write_text("reader = 2\n")
    second = cache.Cache(model)
    assert second.parts["reader"] != first.parts["reader"]
    assert second.key == first.key
    assert json.loads(second.read("meta.json"))["parts"] == first.parts


@pytest.mark.parametrize("name", ["sheet_1.svg", "view_42.svg"])
def test_svg_round_trip_and_overwrite(model, name):
    item = cache.Cache(model)
    assert not item.has(name)
    svg = '<svg><polygon points="0,0 1,0 0,1"/><text>é</text></svg>'
    item.write(name, svg)
    assert item.has(name)
    assert item.read(name) == svg
    item.write(name, "<svg/>")
    assert item.read(name) == "<svg/>"


@pytest.mark.parametrize("data", ["new text", b"\x00\xffPNG"])
def test_write_replaces_only_after_temp_file_is_complete(model, monkeypatch, data):
    item = cache.Cache(model)
    item.write("artifact", "old")
    destination = Path(item.fn("artifact"))
    temporary = Path(str(destination) + ".%d.tmp" % os.getpid())
    replace = os.replace
    calls = []

    def inspect_replace(src, dst):
        assert Path(src) == temporary
        assert Path(dst) == destination
        assert destination.read_text() == "old"
        assert temporary.read_bytes() == (data if isinstance(data, bytes) else data.encode())
        calls.append((src, dst))
        replace(src, dst)

    monkeypatch.setattr(cache.os, "replace", inspect_replace)
    item.write("artifact", data)
    assert len(calls) == 1
    assert item.read("artifact", "rb" if isinstance(data, bytes) else "r") == data
    assert not temporary.exists()


@pytest.mark.parametrize("contents, expected", [
    (None, None), ("invalid json", None), ('{"sheets": []}', {"sheets": []}),
    ("[]", []),
])
def test_doc_missing_invalid_and_valid(model, contents, expected):
    item = cache.Cache(model)
    if contents is not None:
        item.write("doc.json", contents)
    assert item.doc() == expected


@pytest.mark.parametrize("contents", [b"", b"abc", b"\x00\xff\n"])
def test_file_hash_and_index(model, contents):
    model.write_bytes(contents)
    expected = hashlib.sha1(contents).hexdigest()
    assert cache.file_hash(model) == expected
    assert cache.file_hash(model) == expected
    stat = model.stat()
    key = "%s|%d|%d" % (model.resolve(), stat.st_size, int(stat.st_mtime))
    assert json.loads((Path(cache.ROOT) / "filehash.json").read_text()) == {key: expected}
    assert list(Path(cache.ROOT).iterdir()) == [Path(cache.ROOT) / "filehash.json"]


def test_file_hash_memoizes_by_size_and_integer_mtime(model):
    model.write_bytes(b"abc")
    os.utime(model, (1000, 1000))
    original = cache.file_hash(model)
    model.write_bytes(b"xyz")
    os.utime(model, (1000.5, 1000.5))
    assert cache.file_hash(model) == original
    os.utime(model, (1001, 1001))
    assert cache.file_hash(model) == hashlib.sha1(b"xyz").hexdigest()
    model.write_bytes(b"longer")
    os.utime(model, (1001, 1001))
    assert cache.file_hash(model) == hashlib.sha1(b"longer").hexdigest()


def test_file_hash_recovers_from_invalid_index(model):
    Path(cache.ROOT).mkdir()
    (Path(cache.ROOT) / "filehash.json").write_text("broken")
    assert cache.file_hash(model) == hashlib.sha1(model.read_bytes()).hexdigest()


def test_code_version_stable_and_selected_files_only():
    here = Path(cache.HERE)
    (here / "vg").mkdir()
    (here / "data").mkdir()
    files = {
        here / "render.py": b"render",
        here / "vg" / "geometry.py": b"geometry",
        here / "data" / "names.json": b"{}",
    }
    for path, contents in files.items():
        path.write_bytes(contents)
    digest = hashlib.sha1()
    for path in sorted(files):
        digest.update(path.name.encode())
        digest.update(files[path])
    expected = digest.hexdigest()[:12]
    assert cache.code_version() == cache.code_version() == expected
    for name in cache.NOT_DRAWING:
        (here / name).write_text("ignored")
    (here / "notes.txt").write_text("ignored")
    assert cache.code_version() == expected
    (here / "render.py").write_text("changed")
    assert cache.code_version() != expected


def test_best_complete_with_absent_root_and_supplied_hash(model):
    assert cache.best_complete(model, file_sha="supplied") is None
    assert not Path(cache.ROOT).exists()


@pytest.mark.parametrize("defect", [
    "no_marker", "no_doc", "wrong_path", "wrong_hash", "bad_meta",
])
def test_best_complete_rejects_ineligible_entries(model, defect):
    item = cache.Cache(model)
    item.write("doc.json", "{}")
    item.write("complete.json", "{}")
    if defect == "no_marker":
        Path(item.fn("complete.json")).unlink()
    elif defect == "no_doc":
        Path(item.fn("doc.json")).unlink()
    elif defect == "bad_meta":
        item.write("meta.json", "invalid")
    else:
        meta = json.loads(item.read("meta.json"))
        if defect == "wrong_path":
            meta["path"] = str(model.with_name("other.rvt"))
        else:
            meta["parts"]["file"] = "different"
        item.write("meta.json", json.dumps(meta))
    assert cache.best_complete(model) is None


def test_best_complete_uses_marker_mtime_and_only_requires_doc_existence(model):
    for key, marker_time, doc_time in [("older", 100, 400), ("newer", 200, 300)]:
        item = cache.Cache(model, key=key)
        item.write("doc.json", "not parsed")
        # Marker contents (including failed counts) are not inspected.
        item.write("complete.json", '{"failed": 3}')
        os.utime(item.fn("complete.json"), (marker_time, marker_time))
        os.utime(item.fn("doc.json"), (doc_time, doc_time))
    assert cache.best_complete(model) == "newer"


@pytest.mark.parametrize("failed, expected", [(None, True), (0, True), (2, False)])
def test_best_complete_legacy_ready_fallback(model, failed, expected):
    item = cache.Cache(model)
    item.write("doc.json", "{}")
    entry = {"key": item.key}
    if failed is not None:
        entry["failed"] = failed
    (Path(cache.ROOT) / "READY.json").write_text(json.dumps({item.path: entry}))
    assert cache.best_complete(model) == (item.key if expected else None)


@pytest.mark.parametrize("initial", ["missing", "invalid", "existing"])
def test_mark_ready_merges_and_updates_summary(model, initial):
    item = cache.Cache(model)
    ready_path = Path(cache.ROOT) / "READY.json"
    other = str(model.with_name("other.rvt"))
    if initial == "invalid":
        ready_path.write_text("invalid")
    elif initial == "existing":
        ready_path.write_text(json.dumps({other: {"key": "keep"}, item.path: {"old": True}}))
    cache.mark_ready(item, {"sheets": [1, 2], "views": [3]}, 1.26, port=9000, failed=2)
    ready = json.loads(ready_path.read_text())
    assert set(ready) == ({item.path, other} if initial == "existing" else {item.path})
    if initial == "existing":
        assert ready[other] == {"key": "keep"}
    entry = ready[item.path]
    assert "old" not in entry
    assert entry["key"] == item.key
    assert entry["parts"] == item.parts
    assert (entry["sheets"], entry["views"], entry["failed"], entry["warm_seconds"]) == (2, 1, 2, 1.3)
    assert entry["demo"].endswith(" %s --sheets" % item.path)
    assert entry["standalone"] == "%s serve %s --port 9000" % (
        Path(cache.HERE).parent / "rvt-sheets", item.path,
    )
    marker = json.loads(item.read("complete.json"))
    assert marker["parts"] == item.parts
    assert marker["failed"] == 2
    assert isinstance(marker["prepared"], str)
    assert isinstance(entry["prepared"], str)
    assert not list(Path(cache.ROOT).rglob("*.tmp"))
    assert not Path(str(ready_path) + ".%d" % os.getpid()).exists()
