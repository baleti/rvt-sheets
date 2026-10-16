"""snowdon_l2_check.py : numeric invariants of the demo view Snowdon Structural L2 (124194) that earlier regressions broke:
grid heads 1-9 on the north (top) side, E-A heads on the east side, structural column symbols present, one linear dimension ('38'-7"'), CW12"/CW10" wall tags,
no joist-system sketch lines, no head leader polylines. Prints OK/FAIL per check (host3, one view, ~15 s)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
fn = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')
dec = Decoder(fn); doc = dec.doc(); vd = ViewDrawer(dec, doc); dr = vd.draw(124194); f = vd.f; info = vd.vis.info.info
P = dr['prims']; ok = True
def chk(name, cond, extra=''):
    global ok; ok &= bool(cond); print('OK  ' if cond else 'FAIL', name, extra)
bub = {}
for p in P:
    if p['layer'] == 'datum' and p['t'] == 'line' and p.get('part') == 'bubble' and len(p['pts']) > 30:
        t = f.rec(p['elem'])['fields'].get('m_text'); bub[t] = np.mean(np.asarray(p['pts'], float), 0)
lines = {f.rec(p['elem'])['fields'].get('m_text'): np.asarray(p['pts'], float) for p in P if p['layer'] == 'datum' and p['t'] == 'line' and p.get('part') == 'line' and f.rec(p['elem'], ('Grid',))}
top = [g for g in '23456789' if g in bub and g in lines and bub[g][1] > lines[g][:, 1].mean()]
chk('numbered grid heads on top', len(top) == 8, '%d/8' % len(top))
east = [g for g in 'ABCDE' if g in bub and g in lines and bub[g][0] > lines[g][:, 0].mean()]
chk('lettered grid heads east', len(east) == 5, '%d/5' % len(east))
cols = sum(1 for p in P if info.get(p['elem'], {}).get('cat') == -2001330 and p['t'] == 'line' and p['layer'] == 'symbolic')
chk('column symbol lines', cols >= 150, str(cols))
dims = {p['elem'] for p in P if info.get(p['elem'], {}).get('cls') == 'LinearDimString'}
chk('one linear dimension', len(dims) == 1, str(len(dims)))
cw = [p['text'] for p in P if p['t'] == 'text' and p['text'].startswith('CW')]
chk('CW wall tags', len(cw) == 8 and set(cw) == {'CW12"', 'CW10"'}, str(sorted(set(cw))))
chk('no joist system sketch', not any(info.get(p['elem'], {}).get('cls') == 'JoistSystem' for p in P))
chk('no datum polylines', not any(p['layer'] == 'datum' and p['t'] == 'line' and p.get('part') == 'line' and len(p['pts']) > 2 for p in P))
bst = [p['text'] for p in P if p['t'] == 'text' and info.get(p['elem'], {}).get('cls') == 'BeamSystemTag']
chk('joist system notes', len(bst) == 7 and '18LH04 @ Max 4\'-0"' in bst, str(len(bst)))
spots = {p['text'] for p in P if p['t'] == 'text' and info.get(p['elem'], {}).get('cls') == 'SpotElevation'}
chk('spot elevations read the picked face', "7'-4 1/2\"" in spots and "4'-7\"" in spots, str(sorted(spots)))
print('ALL OK' if ok else 'FAILED'); sys.exit(0 if ok else 1)
