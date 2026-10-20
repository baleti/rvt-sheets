import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.oracle_report import parse, totals, report

TEXT = """skip scene_skip.rte
scene_a.rte new ALL        precision 1.0000 recall 1.0000  (tp 193 fp 0 fn 0)
scene_a.rte old ALL        precision 0.8457 recall 0.7668  (tp 148 fp 27 fn 45)
scene_same.rte new ALL        precision 1.0000 recall 1.0000  (tp 10 fp 0 fn 0)
scene_same.rte old ALL        precision 1.0000 recall 1.0000  (tp 10 fp 0 fn 0)
scene_b.rte new ALL        precision 1.0000 recall 1.0000  (tp 321 fp 0 fn 0)
scene_b.rte old ALL        precision 0.6842 recall 0.9720  (tp 312 fp 144 fn 9)
scene_new.rte new ALL        precision 0.5000 recall 1.0000  (tp 1 fp 1 fn 0)
DONE
"""


def test_parse():
    r = parse(TEXT)
    assert set(r) == {'scene_a.rte', 'scene_same.rte', 'scene_b.rte', 'scene_new.rte'}
    assert r['scene_a.rte']['old'] == (0.8457, 0.7668, 148, 27, 45)
    assert 'old' not in r['scene_new.rte']


def test_totals():
    r = parse(TEXT)
    assert totals(r, 'new') == (193 + 10 + 321 + 1, 1, 0)
    assert totals(r, 'old') == (148 + 10 + 312, 27 + 144, 45 + 9)


def test_report():
    rep = report(parse(TEXT)).splitlines()
    assert rep[0].startswith('scene') and 'old fp/fn' in rep[0]
    body = [l for l in rep[1:-1]]
    assert len(body) == 2                       # same scene and the new-only scene are not listed
    assert body[0].startswith('scene_b.rte')   # old fp+fn 153 > 72
    assert body[1].startswith('scene_a.rte')
    assert '+0.316' in body[0] and '+0.028' in body[0]
    assert rep[-1] == 'TOTAL old fp 171 fn 54 -> new fp 1 fn 0'
