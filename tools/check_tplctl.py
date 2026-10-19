"""check_tplctl.py FILE.rte GT.views : our template non-controlled parameter set (m_nonPropagatedTemplateParamIds) vs the TPLCTL rows of Revit (gt_views)"""
import sys,re
sys.path.insert(0,'/home/user1/src/rvt-sheets-vg')
from rvtsheets.decode import Decoder
from rvtsheets.vg import template as T
fn,gt=sys.argv[1:3]
gtm={}
for l in open(gt,errors='replace'):
    if l.startswith('TPLCTL\t'):
        p=l.rstrip('\n').split('\t'); m=re.search(r'noncontrolled=([-\d,]*)',l); c=re.search(r'controlled=([-\d,]*)',l)
        gtm[int(p[1])]=({int(x) for x in m.group(1).split(',') if x},{int(x) for x in c.group(1).split(',') if x})
doc=Decoder(fn).doc(); ok=bad=0
for vid,(nc,c) in gtm.items():
    v=doc['views'].get(vid)
    if not v: print(vid,'missing'); continue
    ours=T.excluded_ids(v)
    if ours==nc: ok+=1
    else: bad+=1; print(vid,v['name'],'only ours',sorted(ours-nc),'only revit',sorted(nc-ours))
print('templates equal',ok,'differ',bad)
