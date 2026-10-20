import os, sys, json, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets import cachereport as cr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mk(root, key, path, sha, sheets=1, views=2, complete=True, failed=0, age=0):
    d = root / key; d.mkdir()
    (d / 'meta.json').write_text(json.dumps({'path': path, 'parts': {'file': sha}, 'created': '2026-10-20 10:00:00'}))
    (d / 'doc.json').write_text('{}')
    for i in range(sheets): (d / ('sheet_%d.svg' % i)).write_text('<svg/>' * 10)
    for i in range(views): (d / ('view_%d.svg' % i)).write_text('<svg/>' * 5)
    if complete: (d / 'complete.json').write_text(json.dumps({'failed': failed, 'prepared': 'x', 'parts': {}}))
    t = time.time() - age
    os.utime(d, (t, t))


def test_scan_counts_and_skips(tmp_path):
    mk(tmp_path, 'a' * 16, '/x/Model.rvt', 's1', sheets=2, views=3)
    (tmp_path / ('b' * 16)).mkdir()                       # no meta.json: skipped
    (tmp_path / 'READY.json').write_text(json.dumps({'/x/Model.rvt': {'key': 'a' * 16}}))
    e = cr.scan(str(tmp_path))
    assert len(e) == 1 and e[0]['sheets'] == 2 and e[0]['views'] == 3 and e[0]['complete'] and e[0]['ready'] and e[0]['failed'] == 0
    assert e[0]['bytes'] > 0 and e[0]['file_sha'] == 's1'
    assert cr.scan(str(tmp_path / 'missing')) == []


def test_stale_rules(tmp_path):
    mk(tmp_path, '1' * 16, '/x/A.rvt', 'h', age=300)               # old complete
    mk(tmp_path, '2' * 16, '/x/A.rvt', 'h', age=200)               # newest complete: kept
    mk(tmp_path, '3' * 16, '/x/A.rvt', 'h', complete=False, age=100)  # incomplete, newer than the complete one but not complete
    mk(tmp_path, '4' * 16, '/x/B.rvt', 'k', complete=False)        # only entry of its group: kept
    e = cr.scan(str(tmp_path)); st = {x['key'] for x in cr.stale(e)}
    assert '1' * 16 in st and '2' * 16 not in st and '4' * 16 not in st
    assert '3' * 16 in st


def test_ready_entries_are_never_stale(tmp_path):
    mk(tmp_path, '1' * 16, '/x/A.rvt', 'h', age=300); mk(tmp_path, '2' * 16, '/x/A.rvt', 'h', age=200)
    (tmp_path / 'READY.json').write_text(json.dumps({'/x/A.rvt': {'key': '1' * 16}}))
    assert {x['key'] for x in cr.stale(cr.scan(str(tmp_path)))} == set()


def test_table_and_total(tmp_path):
    mk(tmp_path, 'c' * 16, '/x/Some Model.rvt', 's')
    e = cr.scan(str(tmp_path)); t = cr.format_table(e)
    assert t.splitlines()[0].split() == ['KEY', 'PATH', 'SHEETS', 'VIEWS', 'SIZE', 'COMPLETE', 'READY'] or t.splitlines()[0].startswith('KEY')
    assert 'Some Model.rvt' in t and '/x/' not in t
    assert cr.total_bytes(e) == e[0]['bytes']


def test_cli_dry_run_then_prune(tmp_path):
    mk(tmp_path, '1' * 16, '/x/A.rvt', 'h', age=300); mk(tmp_path, '2' * 16, '/x/A.rvt', 'h', age=200)
    cli = os.path.join(REPO, 'tools', 'cache_report.py')
    r = subprocess.run([sys.executable, cli, '--root', str(tmp_path), '--prune'], capture_output=True, text=True)
    assert 'dry run' in r.stdout and (tmp_path / ('1' * 16)).exists()
    r = subprocess.run([sys.executable, cli, '--root', str(tmp_path), '--prune', '--yes'], capture_output=True, text=True)
    assert not (tmp_path / ('1' * 16)).exists() and (tmp_path / ('2' * 16)).exists()
    j = subprocess.run([sys.executable, cli, '--root', str(tmp_path), '--json'], capture_output=True, text=True)
    assert len(json.loads(j.stdout)) == 1
