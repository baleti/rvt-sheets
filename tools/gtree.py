"""gtree.py FILE id [maxdepth] -> compact saved-graphics tree: node class, conditions, leaf counts, GInfo category"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.reader import File
f = File(sys.argv[1]); r = f.graphics(int(sys.argv[2])); md = int(sys.argv[3]) if len(sys.argv) > 3 else 8
print(r['class'])
def cond_s(c):
    o = c.get('obj') or {}; cls = f.tagname(c.get('ptr'))
    if 'm_dir' in o: return '%s%d%s(%s)%s' % (cls[10:13], o.get('m_comp'), '!' if o.get('m_negateDirCondition') else '', ','.join('%.2g' % a for a in o['m_dir']), (' [%.3g..%.3g]' % (o['m_rangeLo'], o['m_rangeHi'])) if 'm_rangeLo' in o else '')
    return '%s%d p%s=%s' % (cls[10:13], o.get('m_comp'), o.get('m_param'), o.get('m_value', o.get('m_dbViewId')))
def walk(n, d):
    if not isinstance(n, dict) or 'obj' not in n: return
    o = n['obj']; cls = f.tagname(n.get('ptr'))
    if not isinstance(o, dict): return
    subs = o.get('m_subNodes') or []
    gi = o.get('m_GInfo') or {}
    cat = f.eid(gi.get('m_categoryId')) if gi.get('m_categoryId') is not None else None
    leaf = collections.Counter(f.tagname(s.get('ptr')) for s in subs if isinstance(s, dict) and not (isinstance(s.get('obj'), dict) and s['obj'].get('m_subNodes')))
    if cls in ('GFilter', 'GGroup', 'GNode', 'GElement') or subs:
        print('  ' * d + '%s gs=%s flags=%x conds=[%s] leaves=%s' % (cls, cat, gi.get('m_flags') or 0, '; '.join(cond_s(c) for c in o.get('m_oConditions') or []), dict(leaf)))
        if d < md:
            for s in subs: walk(s, d + 1)
    elif cls == 'GInstance':
        print('  ' * d + 'GInstance sym=%s' % f.eid((o.get('m_instanceInfo') or {}).get('obj', {}).get('m_symbolId')))
walk({'obj': r['fields'], 'ptr': 0}, 0)
