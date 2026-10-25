"""ViewDrawer._rebar_plan_visible: hidden-line plans hide bar sets wholly below the cut plane (unless a cell lists the view), wireframe plans draw all"""
import numpy as np
from types import SimpleNamespace
from rvtsheets.viewdraw import ViewDrawer


def make(bbox, cells=None):
    rec = {'fields': {'m_cellList': {'obj': {'m_cells': [{'obj': c} for c in (cells or [])]}}}}
    d = SimpleNamespace(vis=SimpleNamespace(info=SimpleNamespace(bbox=lambda e: bbox)), f=SimpleNamespace(rec=lambda e: rec))
    return d


def view(surfaces, vid=10):
    return {'id': vid, 'range': {'cut': -3.0, 'top': -2.0, 'bottom': -8.0, 'depth': -9.0}, 'display': {'m_model': {'m_surfaces': surfaces}}}


def vis(d, v): return ViewDrawer._rebar_plan_visible(d, 1, v)


def test_set_reaching_the_cut_is_drawn():
    assert vis(make(np.array([[0, 0, -9.0], [1, 1, 6.0]])), view(2))


def test_set_below_cut_hidden_in_hidden_line_plan():
    assert not vis(make(np.array([[0, 0, -4.0], [1, 1, -3.4]])), view(2))


def test_set_below_cut_drawn_in_wireframe_plan():
    assert vis(make(np.array([[0, 0, -4.0], [1, 1, -3.4]])), view(1))


def test_listed_view_draws_set_below_cut():
    bb = np.array([[0, 0, -4.0], [1, 1, -3.4]])
    d = make(bb, [{'m_detailViewIds': ['EID(10)'], 'm_showSolidViewIds': []}])
    assert vis(d, view(2, 10)) and not vis(d, view(2, 11))
