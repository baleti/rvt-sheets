"""2D saved graphics (partition channel 103 GElement trees) -> drawing primitives in the element's own coordinates (feet).
Primitive dicts:
  {'t':'line','pts':[[x,y,z],...],'gs':gstyle}            polyline (lines, arcs sampled, polylines)
  {'t':'fill','loops':[[[x,y,z],...]],'pattern':id,'color':rgb|None,'gs':gstyle}
  {'t':'text','text':str,'origin','x','y','size','font','halign','valign','bold','italic','box':(w,h) ft,'gs'}
  {'t':'image','symbol':id,'transform':(R,o),'scale':(sx,sy)}
Each primitive also carries 'cond': list of view conditions met on the way down (GConditionDir/Int...), evaluated by the caller."""
import math, re
import numpy as np
from .reader import ob

ARC_SEG = math.radians(5)


def rtf_text(raw):
    """minimal RTF -> plain text (\\par -> newline, \\'xx, \\uN, groups for font/colour tables dropped)"""
    if raw is None: return ''
    if isinstance(raw, (bytes, bytearray)): s = raw.decode('latin1', 'replace')
    else:
        s = str(raw)
        if s.startswith("b'") or s.startswith('b"'):
            try:
                import ast; s = ast.literal_eval(s).decode('latin1', 'replace')
            except Exception: pass
    s = s.replace('\x00', '')
    out = []; i = 0; depth = 0; skip_depth = None; n = len(s)
    while i < n:
        ch = s[i]
        if ch == '{':
            depth += 1
            m = re.match(r'\{\\(\*|fonttbl|colortbl|stylesheet|info)', s[i:])
            if m and skip_depth is None: skip_depth = depth
            i += 1; continue
        if ch == '}':
            if skip_depth == depth: skip_depth = None
            depth -= 1; i += 1; continue
        if skip_depth is not None: i += 1; continue
        if ch == '\\':
            m = re.match(r"\\'([0-9a-fA-F]{2})", s[i:])
            if m: out.append(bytes([int(m.group(1), 16)]).decode('cp1252', 'replace')); i += 4; continue
            m = re.match(r'\\u(-?\d+) ?\??', s[i:])
            if m: out.append(chr(int(m.group(1)) % 65536)); i += len(m.group(0)); continue
            m = re.match(r'\\([a-z]+)(-?\d+)? ?', s[i:])
            if m:
                w = m.group(1)
                if w in ('par', 'line'): out.append('\n')
                elif w == 'tab': out.append('\t')
                i += len(m.group(0)); continue
            if i + 1 < n and s[i + 1] in '\\{}': out.append(s[i + 1]); i += 2; continue
            i += 2; continue
        if ch in '\r\n': i += 1; continue
        out.append(ch); i += 1
    return ''.join(out).rstrip('\n ')


def rtf_runs(raw):
    """font size of the first run in half-points (\\fsN), bold/italic flags (best effort)"""
    s = raw.decode('latin1', 'replace') if isinstance(raw, (bytes, bytearray)) else str(raw)
    fs = re.search(r'\\fs(\d+)', s)
    return {'fs': int(fs.group(1)) if fs else None, 'bold': '\\b ' in s or '\\b\\' in s, 'italic': '\\i ' in s}


def arc_pts(c, r, x, y, t0, t1, rx=None):
    c = np.asarray(c, float); x = np.asarray(x, float); y = np.asarray(y, float)
    ry = r; rx = r if rx is None else rx
    n = max(2, int(math.ceil(abs(t1 - t0) / ARC_SEG)) + 1)
    return [(c + rx * math.cos(t) * x + ry * math.sin(t) * y).tolist() for t in np.linspace(t0, t1, n)]


_IDX = [False, None]


def _index_fn():
    """Rust handle indexer (rvt_fast.index_handles: same dict, same node objects, 3.5x), None when unavailable"""
    if not _IDX[0]:
        _IDX[0] = True
        try:
            import os, sys
            p = os.path.expanduser('~/src/rvt-core/python')
            if os.path.isdir(p) and p not in sys.path: sys.path.append(p)
            import rvt_fast
            _IDX[1] = rvt_fast.index_handles
        except Exception: _IDX[1] = None
    return _IDX[1]


class Collector:
    def __init__(self, f, cond_ok=None):
        self.f = f; self.prims = []; self.unknown = {}
        self.cond_ok = cond_ok or (lambda conds: True)

    def collect(self, rec):
        fields = rec['fields'] if isinstance(rec, dict) and 'fields' in rec else rec
        self.handles = {}
        self._index(fields)
        for n in fields.get('m_subNodes') or []: self.node(n, [], None)
        return self.prims

    def _index(self, x):
        fn = _index_fn()
        if fn is not None:
            try: self.handles.update(fn(x)); return
            except Exception: pass
        self._index_py(x)

    def _index_py(self, x):
        if isinstance(x, dict):
            if 'handle' in x and 'obj' in x and isinstance(x.get('handle'), int) and x['handle'] != 0xFFFFFFFF: self.handles[x['handle']] = x
            for v in x.values(): self._index_py(v)
        elif isinstance(x, list):
            for v in x: self._index_py(v)

    def deref(self, x):
        if isinstance(x, dict) and set(x) == {'ref'}: return self.handles.get(x['ref'])
        return x

    def node(self, n, conds, gs):
        n = self.deref(n)
        if not isinstance(n, dict) or 'obj' not in n: return
        cls = self.f.tagname(n.get('ptr')); o = n['obj']
        if not isinstance(o, dict): return
        gi = o.get('m_GInfo') or {}
        g = gi.get('m_categoryId')
        g = self.f.eid(g) if g is not None else -1
        if g == -1: g = gs
        if cls in ('GFilter', 'GGroup', 'GNode'):
            cs = conds + [dict(ob(c), _class=self.f.tagname(c.get('ptr'))) for c in (o.get('m_oConditions') or []) if isinstance(c, dict)]
            if not self.cond_ok(cs): return
            for s in o.get('m_subNodes') or []: self.node(s, cs, g)
            return
        p = {'cond': conds, 'gs': g, 'tag': gi.get('m_tag'), 'flags': gi.get('m_flags')}
        if cls == 'GLine':
            orr = np.asarray(o['m_origin'], float); d = np.asarray(o['m_dirVec'], float); t0, t1 = o['m_endParams']
            self.prims.append(dict(p, t='line', pts=[(orr + d * t0).tolist(), (orr + d * t1).tolist()]))
        elif cls == 'GArc':
            t0, t1 = o['m_endParams']
            if abs(t1 - t0) < 1e-12: t1 = t0 + 2 * math.pi             # unbounded arc = full circle (elevation marker body '12.5mm Circle')
            pts = arc_pts(o['m_center'], o['m_radius'], o['m_xVec'], o['m_yVec'], t0, t1)
            self.prims.append(dict(p, t='fill' if o.get('m_bFilled') else 'line', pts=pts, loops=[pts] if o.get('m_bFilled') else None))
        elif cls == 'GEllipse':
            t0, t1 = o.get('m_endParams', [0, 2 * math.pi])
            if abs(t1 - t0) < 1e-12: t1 = t0 + 2 * math.pi
            pts = arc_pts(o['m_center'], o.get('m_radiusY', o.get('m_radius')), o['m_xVec'], o['m_yVec'], t0, t1, rx=o.get('m_radiusX'))
            self.prims.append(dict(p, t='line', pts=pts))
        elif cls == 'GPolyLine':
            pts = [list(map(float, q)) for q in o['m_coord']]
            if o.get('m_bFilled'): self.prims.append(dict(p, t='fill', loops=[pts], pattern=None, color=None))
            else: self.prims.append(dict(p, t='line', pts=pts))
        elif cls == 'GRichText':
            raw = o.get('m_arrRtfRawData')
            x = (o.get('m_modelXUnitVec') or {}).get('m_xyz'); y = (o.get('m_modelYUnitVec') or {}).get('m_xyz')
            self.prims.append(dict(p, t='text', text=rtf_text(raw), rtf=rtf_runs(raw) if raw is not None else {}, origin=(o.get('m_modelOrigin') or {}).get('m_xyz'), x=x, y=y,
                                   size=o.get('m_defaultFontSize'), font=o.get('m_defaultFontName'), halign=o.get('m_defaultHorizontalTextAlignment'), valign=o.get('m_defaultVerticalTextAlignment'),
                                   bold=o.get('m_isDefaultFontBold'), italic=o.get('m_isDefaultFontItalic'), width_scale=o.get('m_widthScale'), color=o.get('m_defaultTextColor'),
                                   box=[(o.get('m_layoutWidthHimetric') or 0) / 1e5 / 0.3048, (o.get('m_layoutHeightHimetric') or 0) / 1e5 / 0.3048],
                                   text_box=[(o.get('m_textWidthHimetric') or 0) / 1e5 / 0.3048, (o.get('m_textHeightHimetric') or 0) / 1e5 / 0.3048],
                                   text_off=[(o.get('m_textHorzOffsetHimetric') or 0) / 1e5 / 0.3048, (o.get('m_textVertOffsetHimetric') or 0) / 1e5 / 0.3048],
                                   model_to_sheet=o.get('m_modelToSheetScale'), opaque=not o.get('m_transparentBackground', 1)))
        elif cls == 'GImage':
            ii = ob(o.get('m_imageInfo')) or {}
            t = ii.get('m_Trf') or {}
            self.prims.append(dict(p, t='image', symbol=self.f.eid(ii.get('m_symbolId')), R=t.get('m_3x3'), o=t.get('m_or'), scale=[ii.get('m_dWidthScale'), ii.get('m_dHeightScale')]))
        elif cls == 'GFilling':
            face = self.deref(o.get('m_pGFace'))
            loops = self.face_loops(face)
            self.prims.append(dict(p, t='fill', loops=loops, pattern=self.f.eid(o.get('m_patternId')), color=o.get('m_fillColor'), placer=o.get('m_placer'), fill_flags=o.get('m_flags')))
        elif cls == 'GInstance':
            ii = ob(o.get('m_instanceInfo')) or {}
            t = ii.get('m_Trf') or {}
            self.prims.append(dict(p, t='instance', symbol=self.f.eid(ii.get('m_symbolId')), R=t.get('m_3x3'), o=t.get('m_or')))
        elif cls == 'Geometry':
            return                     # B-rep holder (faces referenced by GFilling); solids handled by the 3D path
        else:
            self.unknown[cls] = self.unknown.get(cls, 0) + 1

    def face_loops(self, face):
        """planar face (Face -> EdgeLoops -> Edges) -> 3D loops via the reader's planar B-rep helper"""
        if not isinstance(face, dict): return []
        try:
            import rvt_brep
            h = face.get('handle')
            # find the Geometry node holding this face
            for gh, gn in self.handles.items():
                if self.f.tagname(gn.get('ptr')) != 'Geometry': continue
                g = gn['obj']
                if any(isinstance(fc, dict) and fc.get('handle') == h for fc in g.get('m_pFaces') or []):
                    for fr in rvt_brep.planar_faces(g):
                        if fr['handle'] == h: return fr['loops']
        except Exception: pass
        return []


def transform_pts(pts, R, o):
    """world = R_cols @ local + o (reader convention: columns of m_3x3 are the basis vectors)"""
    if R is None: return pts
    M = np.asarray(R, float); o = np.asarray(o, float)
    return (np.asarray(pts, float) @ M.T + o).tolist()
