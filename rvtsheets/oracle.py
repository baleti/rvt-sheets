"""parser for the oracle's viewdump output (oracle/VIEWDUMP_FORMAT.md)"""
import os, glob

GT_DIR = os.path.expanduser('~/rvt-research/gt_views')


def kv(cols):
    d = {}; rest = []
    for c in cols:
        if '=' in c and not c.startswith('='):
            k, v = c.split('=', 1); d[k] = v
        else: rest.append(c)
    return d, rest


def vec(s):
    try: return [float(a) for a in s.split(',')]
    except Exception: return None


def load(fn):
    o = {'views': {}, 'crop': {}, 'range': {}, 'catvis': {}, 'vfilter': {}, 'eovr': {}, 'viewelems': {}, 'owned': {}, 'viewports': {}, 'sheets': {},
         'titleblocks': {}, 'tbparams': {}, 'filters': {}, 'frules': [], 'cats': {}, 'gstyles': {}, 'lpat': {}, 'fpat': {}, 'phases': [], 'phasefilters': {},
         'tplctl': {}, 'vparams': {}, 'schedinst': {}, 'schedrows': {}, 'levels': {}, 'err': []}
    for line in open(fn, encoding='utf-8', errors='replace'):
        c = line.rstrip('\n').split('\t'); t = c[0]
        if t == 'VIEW':
            d, _ = kv(c[6:]); d.update(id=int(c[1]), api_class=c[2], view_type=c[3], name=c[4], template=c[5].endswith('True')); o['views'][int(c[1])] = d
        elif t == 'CROP':
            d, _ = kv(c[2:]); o['crop'][int(c[1])] = d
        elif t == 'RANGE':
            d, _ = kv(c[3:]); o['range'].setdefault(int(c[1]), {})[c[2]] = (int(d['level']), float(d['offset']))
        elif t == 'CATVIS':
            d, rest = kv(c[3:5]); ov = {}
            for part in (c[5] if len(c) > 5 else '').split(';'):
                if '=' in part: k, v = part.split('=', 1); ov[k] = v
            o['catvis'].setdefault(int(c[1]), {})[int(c[2])] = dict(hidden=d.get('hidden') == 'True', can_hide=d.get('canHide') == 'True', ov=ov)
        elif t == 'VFILTER':
            d, _ = kv(c[3:5]); ov = {}
            for part in (c[5] if len(c) > 5 else '').split(';'):
                if '=' in part: k, v = part.split('=', 1); ov[k] = v
            o['vfilter'].setdefault(int(c[1]), []).append(dict(filter=int(c[2]), visible=d.get('visible') == 'True', enabled=d.get('enabled'), ov=ov))
        elif t == 'EOVR':
            ov = {}
            for part in c[3].split(';'):
                if '=' in part: k, v = part.split('=', 1); ov[k] = v
            o['eovr'].setdefault(int(c[1]), {})[int(c[2])] = ov
        elif t == 'VIEWELEMS':
            o['viewelems'][int(c[1])] = [int(x) for x in c[3].split(',') if x] if len(c) > 3 else []
        elif t == 'OWNED':
            d, rest = kv(c[4:]); d.update(cls=c[3]); o['owned'].setdefault(int(c[1]), {})[int(c[2])] = d
        elif t == 'VIEWPORT':
            d, _ = kv(c[2:]); d['id'] = int(c[1]); o['viewports'][int(c[1])] = d
        elif t == 'SHEET':
            d, _ = kv(c[2:]); d['id'] = int(c[1]); o['sheets'][int(c[1])] = d
        elif t == 'TITLEBLOCK':
            d, _ = kv(c[2:]); d['id'] = int(c[1]); o['titleblocks'][int(c[1])] = d
        elif t == 'TBPARAM':
            o['tbparams'].setdefault(int(c[1]), {})[c[2]] = c[4] if len(c) > 4 else ''
        elif t == 'FILTER':
            d, _ = kv(c[3:]); o['filters'][int(c[1])] = dict(name=c[2], cats=[int(x) for x in d.get('cats', '').split(',') if x])
        elif t == 'FRULE': o['frules'].append(c[1:])
        elif t == 'CAT':
            d, _ = kv(c[4:]); d.update(parent=int(c[2]), name=c[3]); o['cats'][int(c[1])] = d
        elif t == 'GSTYLE':
            d, _ = kv(c[4:]); d.update(name=c[2], type=c[3]); o['gstyles'][int(c[1])] = d
        elif t == 'LPAT': o['lpat'][int(c[1])] = (c[2], c[3] if len(c) > 3 else '')
        elif t == 'FPAT':
            d, rest = kv(c[3:]); d.update(name=c[2], grids=rest); o['fpat'][int(c[1])] = d
        elif t == 'PHASE': o['phases'].append((int(c[1]), c[2]))
        elif t == 'PHASEFILTER': o['phasefilters'][int(c[1])] = (c[2], c[3] if len(c) > 3 else '')
        elif t == 'TPLCTL':
            d, _ = kv(c[2:]); o['tplctl'][int(c[1])] = d
        elif t == 'VPARAM':
            o['vparams'].setdefault(int(c[1]), {})[int(c[2])] = dict(bip=c[3], name=c[4], storage=c[5], raw=c[6], text=c[7] if len(c) > 7 else '')
        elif t == 'SCHEDINST':
            d, _ = kv(c[2:]); o['schedinst'][int(c[1])] = d
        elif t == 'SCHEDROW': o['schedrows'].setdefault(int(c[1]), []).append((c[2], int(c[3]), c[4].split('\x1f') if len(c) > 4 else []))
        elif t == 'LEVEL':
            d, _ = kv(c[3:]); o['levels'][int(c[1])] = (c[2], float(d['elev']))
        elif t == 'ERR': o['err'].append(c[1:])
    return o


def find(rvt_path):
    """oracle file for a corpus/rosetta path: <year>_<basename>.views"""
    b = os.path.basename(rvt_path)
    for fn in glob.glob(os.path.join(GT_DIR, '*.views')):
        n = os.path.basename(fn)[:-6]
        if n.endswith(b) and n[:4].isdigit(): return fn
    return None
