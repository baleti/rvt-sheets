import os, sys, tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.vg import linkdraw as LD


def test_resolve_path_prefix_and_scene_names():
    with tempfile.TemporaryDirectory() as d:
        for n in ('46_Snowdon_Towers_Sample_Facades.rvt', '2026_vg_link_target.rvt', '2026_vg_links.rte'): open(os.path.join(d, n), 'w').close()
        host = os.path.join(d, '43_Snowdon_Towers_Sample_Structural.rvt'); open(host, 'w').close()
        assert LD.resolve_path(host, 'Snowdon Towers Sample Facades.rvt').endswith('46_Snowdon_Towers_Sample_Facades.rvt')
        assert LD.resolve_path(os.path.join(d, '2026_vg_links.rte'), 'C:\\wl\\vg_link_target.rvt').endswith('2026_vg_link_target.rvt')
        assert LD.resolve_path(host, 'Missing.rvt') is None


def test_host_frame_maps_to_same_view_coordinates():
    th = 0.7; R = np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0], [0, 0, 1.0]]); t = np.array([5.0, -3.0, 2.0])
    v = {'origin': [1.0, 2.0, 0.0], 'right': [1, 0, 0], 'up': [0, 1, 0], 'dir': [0, 0, 1], 'crop': {}}
    w = LD.host_to_link_view(v, R, t, {'range': {'cut': 3.0, 'levels': []}})
    pL = np.array([4.0, 1.0, 0.5]); pH = R @ pL + t
    uvH = [(pH - v['origin']) @ np.array(v[k]) for k in ('right', 'up')]
    uvL = [(pL - np.array(w['origin'])) @ np.array(w[k]) for k in ('right', 'up')]
    assert np.allclose(uvH, uvL)


def test_halftone_mixes_with_white():
    p = LD._halftone({'style': {'rgb': [0, 100, 200], 'halftone': False}, 'fill': [0, 0, 0]})
    assert p['style']['rgb'] == [128, 178, 228] and p['style']['halftone'] and p['fill'] == [128, 128, 128]


def test_by_host_moves_range_and_takes_host_settings():
    R = np.eye(3); t = np.array([0.0, 0.0, 10.0])
    v = {'origin': [0, 0, 0], 'right': [1, 0, 0], 'up': [0, 1, 0], 'dir': [0, 0, 1], 'crop': {}, 'range': {'cut': 14.0, 'top': 20.0, 'bottom': 8.0, 'depth': 8.0, 'plan_view_type': 1}}
    base = {'range': {'cut': 4.0, 'levels': [1, 2]}, 'phase': 1, 'detail_level': 1}
    w = LD.host_to_link_view(v, R, t, base, by_host=True, ev={'phase': 7, 'detail_level': 3})
    assert (w['range']['cut'], w['range']['top'], w['range']['bottom']) == (4.0, 10.0, -2.0)      # host z minus the link's z offset
    assert w['range']['plan_view_type'] == 1 and w['range']['levels'] == [1, 2] and w['phase'] == 7 and w['detail_level'] == 3
    assert LD.host_to_link_view(v, R, t, base)['range'] == base['range'] and LD.host_to_link_view(v, R, t, base)['phase'] == 1


def test_crop_basis_rotated():
    R = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1.0]]); t = np.array([1.0, 0.0, 0.0])
    v = {'origin': [0, 0, 0], 'right': [1, 0, 0], 'up': [0, 1, 0], 'dir': [0, 0, 1], 'crop': {'origin': [2.0, 0.0, 0.0], 'basis': [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}}
    w = LD.host_to_link_view(v, R, t, {})
    assert np.allclose(w['crop']['origin'], [0, -1, 0]) and np.allclose(w['crop']['basis'][0], [0, -1, 0])


def test_pick_view_closest_cut_plane():
    mk = lambda cut: {'kind': 'plan', 'class': 'DBViewPlan', 'range': {'cut': cut}}
    doc = {'views': {1: mk(4.0), 2: mk(14.0), 3: dict(mk(12.0), template=True), 4: {'kind': 'section'}}}
    assert LD._pick_view(doc, {'range': {'cut': 13.0}}, 10.0) == 1       # link cut + 10 = 14 and 24 ... 1 -> 14.0: |14-13| ; 2 -> 24
    assert LD._pick_view(doc, {'range': {'cut': 25.0}}, 10.0) == 2


def test_nested_links_compose_frames(monkeypatch):
    import collections
    from rvtsheets.vg import links as L
    th = 0.5; R1 = np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0], [0, 0, 1.0]]); t1 = np.array([10.0, 0, 0])
    R2 = np.eye(3); t2 = np.array([0.0, 4.0, 0])
    seen = {}

    class Rec:
        def __init__(s, fn): s.fn = fn
        def rec(s, vid): return {'fields': {}}
    class Drw:
        def __init__(s, name, doc): s.f = Rec(name); s.stats = collections.Counter(); s.name = name; s.doc = doc; s.vis = type('V', (), {'effective': staticmethod(lambda v: v)})()
        def _draw(s, lvid):
            seen[s.name] = s.doc['views'][lvid]['origin']
            return {'prims': [{'layer': 'cut', 'src': s.name}]}
    plan = lambda: {'kind': 'plan', 'class': 'DBViewPlan', 'range': {'cut': 4.0, 'levels': []}, 'origin': [0, 0, 0], 'right': [1, 0, 0], 'up': [0, 1, 0], 'dir': [0, 0, 1], 'crop': {}}
    docs = {'A': {'views': {1: plan()}}, 'B': {'views': {1: plan()}}}
    drws = {'A': Drw('A', docs['A']), 'B': Drw('B', docs['B'])}
    insts = {'host': {101: {'symbol': 11, 'rot': R1.tolist(), 'origin': t1.tolist()}}, 'A': {201: {'symbol': 21, 'rot': R2.tolist(), 'origin': t2.tolist()}}, 'B': {}}
    monkeypatch.setattr(L, 'link_types', lambda f: {11: {'name': 'A', 'path': 'A'}, 21: {'name': 'B', 'path': 'B'}})
    monkeypatch.setattr(L, 'link_instances', lambda f: insts[f.fn])
    monkeypatch.setattr(L, 'view_links', lambda f, fl: {11: {'visible': True, 'halftone': False, 'instances': {}}, 21: {'visible': True, 'halftone': False, 'instances': {}}})
    monkeypatch.setattr(LD, 'resolve_path', lambda hp, lp: lp)
    monkeypatch.setattr(LD, '_linked', lambda path: (None, docs[path], drws[path]))
    host = Drw('host', {}); host.f = Rec('host'); host.f.fn = 'host'
    host.f.rec = lambda vid: {'fields': {}}
    class F2(Rec): pass
    hf = F2('host'); host.f = hf
    out = LD.link_prims(host, 1, plan(), {'prims': []})
    assert {p['link'] for p in out} == {101, 201} and {p['src'] for p in out} == {'A', 'B'}
    oA = R1.T @ (np.zeros(3) - t1); oB = R2.T @ (oA - t2)
    assert np.allclose(seen['A'], oA) and np.allclose(seen['B'], oB)
