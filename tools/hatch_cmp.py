"""hatch_cmp.py FILE.rvt GTDIR OUT.tsv [view ids] : per view, Revit's DXF HATCH entities by layer vs our cut_fill / surface_fill prims by category
(host job; tsv columns: view, name, kind, detail, revit 'layer:n ...', ours 'cat:n ...' (n = distinct elements with pattern lines))"""
import sys, os, collections, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
fn, gt, out = sys.argv[1:4]; only = set(int(x) for x in sys.argv[4:])
dec = Decoder(fn); doc = dec.doc(); vd = ViewDrawer(dec, doc)
with open(out, 'w') as o:
    for dxf in sorted(glob.glob(os.path.join(gt, '*.dxf'))):
        vid = int(os.path.basename(dxf)[:-4])
        if vid not in doc['views'] or (only and vid not in only): continue
        v = doc['views'][vid]
        try:
            rv = collections.Counter(e.dxf.layer for e in ezdxf.readfile(dxf).modelspace() if e.dxftype() == 'HATCH')
            dr = vd.draw(vid)
        except Exception as ex:
            o.write('%d\terror %s\n' % (vid, ex)); o.flush(); continue
        ours = collections.defaultdict(set)
        for p in dr['prims']:
            if p.get('layer') in ('cut_fill', 'surface_fill') and p.get('t') == 'segs' and p.get('elem') is not None: ours[(p['layer'], p.get('cat'))].add(p['elem'])
        o.write('%d\t%s\t%s\t%s\t%s\t%s\n' % (vid, v.get('name'), v.get('kind'), v.get('detail_level') or (v.get('display') or {}).get('detail'), ' '.join('%s:%d' % kv for kv in sorted(rv.items())),
                                          ' '.join('%s/%s:%d' % (k[0][:3], k[1], len(s)) for k, s in sorted(ours.items(), key=str))))
        o.flush()
