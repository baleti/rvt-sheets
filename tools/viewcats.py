"""viewcats.py FILE VIEWID : category histogram of the elements the view lists, with category names"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc)
c = collections.Counter(vis.info.info.get(i, {}).get('cat') for i in vis.elements(int(sys.argv[2])))
for k, n in c.most_common(): print(k, n, (doc['categories'].get(k) or {}).get('name') if isinstance(doc.get('categories'), dict) else '')
