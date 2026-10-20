import os, sys, subprocess, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.regress_compare import parse_summary, load_baseline, compare

SUMMARY = """101    PlanA                         revit   19 ours   19 onlyRevit   1 onlyOurs   1  (5s)
600158    3D                                 revit    0 ours    8 onlyRevit   0 onlyOurs   2  (1s)
garbage line
=== DETAILS
700000    ignored                            revit    1 ours    1 onlyRevit   9 onlyOurs   9  (1s)
"""


def test_parse_summary():
    d = parse_summary(SUMMARY)
    assert d == {101: (1, 1), 600158: (0, 2)}


def test_load_baseline():
    b = load_baseline("fileA 101 x 2 0\nshort line\nfileB 1 x 0 0\n")
    assert b == {('fileA', '101'): (2, 0), ('fileB', '1'): (0, 0)}


def test_compare():
    base = {'a': (2, 0), 'b': (0, 0), 'c': (1, 1), 'd': (3, 3)}
    new = {'a': (1, 1), 'b': (0, 0), 'c': (0, 1), 'x': (5, 5)}
    worse, better, missing = compare(new, base)
    assert worse == ['a'] and better == ['c'] and missing == ['d']


def test_cli_exit_codes():
    with tempfile.TemporaryDirectory() as t:
        n = os.path.join(t, 'new'); b = os.path.join(t, 'base')
        open(b, 'w').write("f 1 x 0 0\nf 2 x 1 1\n")
        open(n, 'w').write("f 1 x 0 0\nf 2 x 1 0\n")
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'regress_compare.py'), n, b], capture_output=True, text=True)
        assert r.returncode == 0 and 'worse 0' in r.stdout and 'better 1' in r.stdout
        open(n, 'w').write("f 1 x 1 0\nf 2 x 1 1\n")
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'regress_compare.py'), n, b], capture_output=True, text=True)
        assert r.returncode == 1 and 'WORSE' in r.stdout
