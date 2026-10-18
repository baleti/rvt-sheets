"""vg_scene_check.py SCENE.rte -> V/G oracle scene vs our model: element-list P/R per VG view, ORDERED_FILTERS vs decoded filter order,
PHASEELEM vs phase_status, HIDDEN vs our hidden set (rows from jobs/vgdump.cs, ~/rvt-research/gt_views/<year>_vg_<name>.rte.vg)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; ofn = oracle.find(fn); o = oracle.load(ofn); dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc); I = vis.info.info
rows = collections.defaultdict(list)
for ln in open(ofn.replace('.views', '.vg'), errors='replace'):
    p = ln.rstrip('\n').split('\t'); rows[p[0]].append(p[1:])
print('row types', {k: len(v) for k, v in rows.items()})
tot = collections.Counter()
for vid, ids in sorted(o['viewelems'].items()):
    v = doc['views'].get(vid)
    if not v or not v['name'].startswith('VG') or v['kind'] in ('schedule', 'sheet'): continue
    pred, why = vis.elements(vid, explain=True); P = set(pred); G = set(ids)
    tp = len(P & G); fp = len(P - G); fn_ = len(G - P); tot.update(tp=tp, fp=fp, fn=fn_)
    cls = lambda i: (I.get(i) or {}).get('cls')
    print('%8d %-34s gt %4d pred %4d P %.3f R %.3f' % (vid, v['name'][:34], len(G), len(P), tp / max(len(P), 1), tp / max(len(G), 1)), 'FP', collections.Counter(cls(i) for i in P - G).most_common(3), 'FN', collections.Counter((cls(i), why.get(i)) for i in G - P).most_common(3))
print('ALL P %.4f R %.4f' % (tot['tp'] / max(tot['tp'] + tot['fp'], 1), tot['tp'] / max(tot['tp'] + tot['fn'], 1)))
# filter order
ok = bad = 0
for r in rows['ORDERED_FILTERS']:
    vid = int(r[0]); want = [int(x) for x in r[1].split(',') if x]
    got = [f['filter'] for f in (doc['views'].get(vid) or {}).get('filters') or []]
    if got == want: ok += 1
    else:
        bad += 1
        if bad <= 5: print('FILTER ORDER view', vid, 'revit', want, 'stored', got)
print('filter order: stored list order == Revit GetOrderedFilters in %d / %d views' % (ok, ok + bad))
# phase status
c = collections.Counter(); ex = []
for r in rows['PHASEELEM']:
    vid, eid, st = int(r[0]), int(r[1]), r[2]
    v = doc['views'].get(vid)
    if not v or eid not in I: continue
    mine = vis.phase_status(I[eid], v.get('phase')); m = {None: 'None', 'new': 'New', 'existing': 'Existing', 'demolished': 'Demolished', 'temporary': 'Temporary', 'past': 'Past', 'future': 'Future'}.get(mine, str(mine))
    c[(st, m)] += 1
print('phase status (revit, ours):', sorted(c.items()))
# hidden
hid = collections.defaultdict(set)
for r in rows['HIDDEN']: hid[int(r[0])].add(int(r[1]))
for vid, s in hid.items():
    v = doc['views'].get(vid); pred, why = vis.elements(vid, explain=True)
    print('hidden view', vid, v and v['name'], 'revit hidden', len(s), 'ours excluded among them', sum(1 for e in s if e not in pred), 'ours in v.hidden_elements', len(s & set(v.get('hidden_elements') or [])))
