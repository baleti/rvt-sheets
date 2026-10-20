import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.viewrules import property_line_candidate as f


def test_deep_crop_plan_lists():
    assert f('plan', 1, 7.5, 1000.0)
    assert f('plan', 2, 1e9, 1000.0)          # ceiling plan with unbounded top (Commercial Mezzanine RCP)


def test_shallow_crop_plan_does_not():
    assert not f('plan', 1, 7.5, 100.0)
    assert not f('plan', 2, 17.5, 100.0)
    assert not f('plan', 1, 9.0, 0.0) and not f('plan', 1, 9.0, None)


def test_site_plan():
    assert f('plan', 1, 200.0, 100.0)
    assert not f('plan', 2, 200.0, 100.0)      # a ceiling plan is never a site plan
    assert not f('plan', 1, 1e9, 100.0)        # unbounded top is not a site range


def test_other_kinds():
    assert not f('section', 1, 200.0, 1000.0)
    assert not f('3d', None, None, 1000.0)


def test_legacy_rule():
    assert f('plan', 1, 7.5, 0.0, legacy=True, bbox_z=0.0, range_bottom=0.0, range_depth=0.0)
    assert not f('plan', 1, 7.5, 1000.0, legacy=True, bbox_z=-1.0, range_bottom=0.0, range_depth=0.0)
    assert not f('plan', 2, 7.5, 1000.0, legacy=True, bbox_z=0.0, range_bottom=0.0)
    assert not f('plan', 1, None, 1000.0, legacy=True, bbox_z=0.0)
    assert not f('plan', 1, 7.5, 1000.0, legacy=True, bbox_z=None, range_bottom=0.0)
    assert f('plan', 1, 7.5, 0.0, legacy=True, bbox_z=7.5 + 1e-7, range_bottom=0.0)
    assert f('plan', 1, 7.5, 0.0, legacy=True, bbox_z=-8.0, range_bottom=0.0, range_depth=-8.0)
