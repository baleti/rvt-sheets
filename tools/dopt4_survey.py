import sys, collections
sys.path.insert(0, '/home/user1/src/rvt-sheets-vg')
from rvtsheets.decode import Decoder
from rvtsheets import oracle
fn = sys.argv[1]; o = oracle.load(oracle.find(fn)); dec = Decoder(fn); f = dec.f
listed = {e for ids in o['viewelems'].values() for e in ids}
c = collections.Counter()
for eid, rs in f.byid.items():
    d = f.eid(rs[0]['fields'].get('m_designOptionId'))
    if d == -4: c[(rs[0]['class'], eid in listed)] += 1
print(sorted(c.items(), key=lambda x: -x[1])[:15])
