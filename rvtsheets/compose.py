"""Full sheet: title block + every viewport's view drawing (placed with the viewport transform, clipped to the crop region) -> SVG"""
import numpy as np
from .decode import FT_MM
from .sheet import SheetComposer
from .svg import SVG
from .viewdraw import ViewDrawer
from . import shaded3d
from . import viewsvg


def crop_rect_uv(v):
    """crop region of a view in view coordinates (u0, v0, u1, v1), None when the crop is off"""
    c = v.get('crop') or {}
    if not c.get('crop_active') or not c.get('basis'): return None
    O = np.asarray(v['origin'], float); X = np.asarray(v['right'], float); Y = np.asarray(v['up'], float)
    co = np.asarray(c['origin'], float); B = np.asarray(c['basis'], float); b = c['bounds']
    pts = [co + B[0] * x + B[1] * y for x in (b[0][0], b[0][1]) for y in (b[1][0], b[1][1])]
    uv = np.array([[(p - O) @ X, (p - O) @ Y] for p in pts])
    return uv[:, 0].min(), uv[:, 1].min(), uv[:, 0].max(), uv[:, 1].max()


def datum_ids(d):
    """elements drawn on the datum layer (levels/grids: line + head symbol + head text)"""
    if '_datums' not in d: d['_datums'] = {p.get('elem') for p in d['prims'] if p.get('layer') == 'datum'}
    return d['_datums']


def _touching(prims, rc):
    """ids of the prims whose element (all its prims together) overlaps the rectangle rc = (u0, v0, u1, v1)"""
    import collections
    box = collections.defaultdict(lambda: [1e18, 1e18, -1e18, -1e18])
    def pts(p):
        out = list(p.get('pts') or []) + [q for l in p.get('loops') or [] for q in l] + [q for sg in p.get('segs') or [] for q in sg]
        if p.get('origin') is not None: out.append(p['origin'])
        return out
    for p in prims:
        b = box[p.get('elem')]
        for q in pts(p):
            b[0] = min(b[0], q[0]); b[1] = min(b[1], q[1]); b[2] = max(b[2], q[0]); b[3] = max(b[3], q[1])
    ok = {e for e, b in box.items() if b[0] <= rc[2] and b[2] >= rc[0] and b[1] <= rc[3] and b[3] >= rc[1] or b[0] > b[2]}
    return {id(p) for p in prims if p.get('elem') in ok}


def sheet_svg(dec, sheet_id, doc=None, drawer=None, log=print):
    sc = SheetComposer(dec, doc)
    doc = sc.doc
    vd = drawer or ViewDrawer(dec, doc)
    dr = sc.compose(sheet_id)
    s = SVG(dr['extent'], sc.sty)
    for p in dr['prims']: s.prim(p)
    # elements owned by the sheet itself (text notes, detail lines, symbols); title blocks, viewports and schedules are drawn above
    try:
        own = vd.draw(sheet_id, skip_classes={'Viewport', 'GCSViewport', 'ScheduleInstance'}, skip_cats={-2000280})
        f = 1.0
        for e in viewsvg.body(own['prims'], 1, lambda u, w: s.P((u, w))): s.raw(e)
    except Exception as ex: log('sheet-owned elements failed: %r' % ex)
    for k, item in enumerate(dr['viewports']):
        vp = item['vp']; v = doc['views'].get(vp['view'])
        for p in item.get('title') or []: s.prim(p)
        if v['kind'] not in ('plan', 'section', 'drafting', 'legend', '3d'):
            o = vp['offset']; s.text({'text': '[%s view not drawn yet: %s]' % (v['kind'], v['name']), 'origin': [o[0], o[1], 0], 'size': 2.5 / FT_MM}); continue
        if v['kind'] == '3d' and (v.get('crop') or {}).get('proj_method') == 2 and not (vp.get('scale') or 0) and shaded3d.is_shaded(v):
            # perspective 3D: shaded image placed in the viewport (size = crop tangents x 11.6 ft, empirical from Revit's Front Yard export:
            # viewport box 1.25 x 0.58 ft for tangents 0.1077 x 0.0500; image centre = viewport offset + 11.6 x crop centre tangents)
            try:
                import base64
                img = shaded3d.view_image(vd, v['id'], 1400)
                if img:
                    c = v['crop']; b = c['bounds']; D = 11.6
                    w = (b[0][0] - b[0][1]) * D; h = (b[1][0] - b[1][1]) * D
                    cx = vp['offset'][0] + (b[0][0] + b[0][1]) / 2 * D; cy = vp['offset'][1] + (b[1][0] + b[1][1]) / 2 * D
                    a = s.P((cx - w / 2, cy + h / 2))
                    s.raw('<image x="%.3f" y="%.3f" width="%.3f" height="%.3f" href="data:image/png;base64,%s" preserveAspectRatio="none"/>' % (a[0], a[1], w * FT_MM, h * FT_MM, base64.b64encode(img[0]).decode()))
                    continue
            except Exception as ex: log('3d view %s failed: %r' % (v['id'], ex))
        try: d = vd.draw(v['id'])
        except Exception as ex:
            log('view %s failed: %r' % (v['id'], ex)); continue
        f = vp['scale'] or 1.0 / (v.get('scale') or 100)
        ox, oy = vp['offset'][0], vp['offset'][1]
        tx = lambda u, w: s.P((ox + u * f, oy + w * f))
        cr = crop_rect_uv(v)
        clip = clip2 = clip3 = ''
        if cr:
            a = tx(cr[0], cr[3]); b = tx(cr[2], cr[1])
            s.raw('<clipPath id="vp%d"><rect x="%.3f" y="%.3f" width="%.3f" height="%.3f"/></clipPath>' % (k, a[0], a[1], b[0] - a[0], b[1] - a[1]))
            # datums (levels, grids) and their heads extend past the crop region (Revit: drawn to their extents, heads outside the crop)
            g = 70.0
            s.raw('<clipPath id="vpd%d"><rect x="%.3f" y="%.3f" width="%.3f" height="%.3f"/></clipPath>' % (k, a[0] - g, a[1] - g, b[0] - a[0] + 2 * g, b[1] - a[1] + 2 * g))
            clip = ' clip-path="url(#vp%d)"' % k; clip2 = ' clip-path="url(#vpd%d)"' % k
            # annotations (tags, dimensions, notes, legends) are clipped to the annotation crop (crop + offsets x scale), not to the model crop
            from .datums import Datums
            ar = Datums.annotation_rect(v, v.get('scale') or 100)
            if ar:
                a2 = tx(ar[0], ar[3]); b2 = tx(ar[2], ar[1])
                s.raw('<clipPath id="vpa%d"><rect x="%.3f" y="%.3f" width="%.3f" height="%.3f"/></clipPath>' % (k, a2[0], a2[1], b2[0] - a2[0], b2[1] - a2[1]))
                clip3 = ' clip-path="url(#vpa%d)"' % k
        sc = v.get('scale') or 100
        s.raw('<g data-view="%s"%s>' % (v['id'], clip))
        rest = [p for p in d['prims'] if p.get('elem') not in datum_ids(d)]
        if clip3:
            for e in viewsvg.body([p for p in rest if p.get('layer') in viewsvg.MODEL_LAYERS or p.get('layer') in ('room_fill', 'mask')], sc, tx): s.raw(e)
            s.raw('</g>')
            # annotation elements are shown whole when they touch the annotation crop region (Commercial colour legend sticks out past the crop), else dropped
            ann = [p for p in rest if not (p.get('layer') in viewsvg.MODEL_LAYERS or p.get('layer') in ('room_fill', 'mask'))]
            keep = _touching(ann, ar)
            s.raw('<g data-view="%s" data-annotations="1">' % v['id'])
            for e in viewsvg.body([p for p in ann if id(p) in keep], sc, tx): s.raw(e)
            s.raw('</g>')
        else:
            for e in viewsvg.body(rest, sc, tx): s.raw(e)
            s.raw('</g>')
        dp = [p for p in d['prims'] if p.get('elem') in datum_ids(d)]
        if dp:
            s.raw('<g data-view="%s" data-datums="1"%s>' % (v['id'], clip2))
            for e in viewsvg.body(dp, sc, tx): s.raw(e)
            s.raw('</g>')
        log('  %s %-30s %d prims %s' % (v['id'], v['name'], len(d['prims']), d['stats'].get('seconds')))
    return s.tostring()
