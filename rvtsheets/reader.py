"""Read-only adapter over the ~/rvt-research reader (session 176). Every access to reader internals goes through here.
Override the reader location with RVT_READER_DIR."""
import os, sys, json, functools

READER_DIR = os.environ.get('RVT_READER_DIR', os.path.expanduser('~/rvt-research'))
if READER_DIR not in sys.path: sys.path.insert(0, READER_DIR)
os.environ.setdefault('RVT_GEOM', '1')

INVALID = -1


def _memoise_get_x():
    """rvt_xcache.get_x unpickles the whole record cache on every call and several reader helpers call it (materials, params, geometry
    contexts): one copy per file per process (238 MB saved per extra call on 2020 Residential). Patched in this process only."""
    import rvt_xcache
    if getattr(rvt_xcache.get_x, '_rvtsheets_memo', False): return
    orig = rvt_xcache.get_x; memo = {}
    def get_x(path):
        k = os.path.realpath(path)
        try: st = os.stat(k); k = (k, st.st_size, int(st.st_mtime))
        except OSError: return orig(path)
        if k not in memo:
            if len(memo) >= 2: memo.clear()                  # one or two files per process
            memo[k] = orig(path)
        return memo[k]
    get_x._rvtsheets_memo = True
    rvt_xcache.get_x = get_x


try: _memoise_get_x()
except Exception: pass


class Rec(dict):
    """record fields with helpers; .id .cls"""
    __slots__ = ('id', 'cls')


def ob(x):
    """pointer slot {'handle','ptr','obj'} -> obj"""
    return x.get('obj', x) if isinstance(x, dict) and 'obj' in x and 'ptr' in x else x


def path(f, *keys, default=None):
    for k in keys:
        f = ob(f)
        if isinstance(f, dict): f = f.get(k)
        elif isinstance(f, (list, tuple)) and isinstance(k, int) and -len(f) <= k < len(f): f = f[k]
        else: return default
        if f is None: return default
    return ob(f)


class File:
    """one .rvt: records by id, class names, id width, saved graphics on demand"""
    def __init__(self, fn):
        import rvt_xcache, rvt_scan
        self.fn = os.path.abspath(fn)
        try: x = rvt_xcache.get_x(self.fn)
        except Exception as ex:                       # reader's optional Rust fast path can be mid-update: fall back to its pure-Python path
            os.environ['RVT_NOFAST'] = '1'
            x = rvt_xcache.get_x(self.fn)
        self.eh = x.get('eh', {})
        self.W = x.get('W')
        self.classes = [c['name'] for c in rvt_scan.load(self.fn)[1]]
        self.byid = {}; self.bycls = {}
        for (eid, c), r in x['recs'].items():
            self.byid.setdefault(eid, []).append(r)
            self.bycls.setdefault(c, []).append(r)
        self.idbits = 64 if (self.W or 4) == 8 else 32
        self._g = None

    # ---- ids
    def eid(self, v):
        """ElementId (EID / int / u32 / u64) -> signed int, -1 for invalid"""
        if v is None: return INVALID
        try: v = int(v)
        except Exception: return INVALID
        if v >= 1 << 63: v -= 1 << 64
        elif self.idbits == 32 and v >= 1 << 31: v -= 1 << 32
        elif v >= 1 << 31 and v < 1 << 32 and v > (1 << 32) - 10_000_000: v -= 1 << 32       # 8-byte files that still store u32 negatives in some fields
        return v

    def tagname(self, tag):
        try: return self.classes[int(tag) - 12]
        except Exception: return None

    def rec(self, eid, cls=None):
        for r in self.byid.get(eid, []):
            if cls is None or r['class'] == cls or (isinstance(cls, tuple) and r['class'] in cls): return r
        return None

    def recs(self, *classes):
        out = []
        for c in classes: out += self.bycls.get(c, [])
        return sorted(out, key=lambda r: r['id'])

    def recs_prefix(self, prefix):
        return sorted((r for c, rs in self.bycls.items() if c.startswith(prefix) for r in rs), key=lambda r: r['id'])

    # ---- saved graphics (partition channel 103)
    @property
    def g(self):
        if self._g is None:
            import rvt_elemmesh
            self._g = rvt_elemmesh.Doc(self.fn)
        return self._g

    def graphics(self, eid):
        try: return self.g.rec(eid)
        except Exception: return None

    def params(self):
        import rvt_params
        return rvt_params.params(self.fn)


@functools.lru_cache(None)
def names(kind):
    """category_names / param_names (derived from Revit VM dumps by the reader session): str(id) -> name"""
    return json.load(open(os.path.join(READER_DIR, kind + '_names.json')))
