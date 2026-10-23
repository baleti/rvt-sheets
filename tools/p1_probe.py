import sys; sys.path.insert(0,'.')
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
d=Decoder('/home/user1/rvt-research/corpus/2020/18_rst_basic_sample_project.rvt'); doc=d.doc(); vd=ViewDrawer(d,doc)
for e in (1417422,1417426,1176611,1404374):
    r=d.f.rec(e); i=vd.vis.info.info[e]; bb=vd.vis.info.bbox(e)
    print("P",e,r['class'],i.get('type'),i.get('fam'),bb, 'hdr' ,i.get('has_header'), [k for k in r['fields'] if 'Sym' in k or 'sym' in k][:4])
