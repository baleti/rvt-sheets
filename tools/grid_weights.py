import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
fn, vid, dxf = sys.argv[1], int(sys.argv[2]), sys.argv[3]
L=open(dxf,errors='ignore').read().split('\n'); pairs=[(L[i].strip(),L[i+1].strip()) for i in range(0,len(L)-1,2)]
ents=[];cur=None
for c,v in pairs:
    if c=='0':
        if cur: ents.append(cur)
        cur={'type':v}
    elif cur is not None: cur.setdefault(c,[]).append(v)
rv=collections.Counter()
for e in ents:
    if e['type'] in ('LINE','LWPOLYLINE') and e.get('8',[''])[0] in ('S-GRID','A-GRID'): rv[e.get('370',['bylayer'])[0]]+=1
print('REVIT S-GRID/A-GRID lineweights (1/100 mm):', dict(rv))
dec=Decoder(fn); doc=dec.doc(); dr=ViewDrawer(dec,doc).draw(vid)
c=collections.Counter()
for p in dr['prims']:
    if p.get('layer')=='datum' and p.get('part')=='line' and p.get('t')=='line': st=p['style']; c[(st['w'], 'dash' if st.get('dash') else 'solid')]+=1
print('OURS grid/level lines (w mm, dash):', dict(c))
