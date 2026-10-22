"""scene_check.py FILE VIEWID : build the viewer scene JSON of a view (drawings.scene_text) and count prims by layer / with pts3"""
import sys, os, time, json, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.drawings import Model, scene_text
m = Model(os.path.abspath(sys.argv[1])); m.start()
while m.state in ('idle', 'loading'): time.sleep(0.5)
m.decoder(); d = json.loads(scene_text(m, int(sys.argv[2]), {}))
c = collections.Counter((p.get('layer'), 'pts3' in p) for p in d['prims'])
print('prims', len(d['prims']), dict(c)); [print(p['elem'], p.get('pts3'), p.get('pts')) for p in d['prims'] if 'pts3' in p][:3]
