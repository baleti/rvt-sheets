# VG-PIPELINE (c3-vg)
Package `rvtsheets/vg/`: stage functions on decoded Doc dicts. `tests/test_vg.py` unit tests; `tools/vg_report.py FILE VIEWID [OUT.json]` = graphics resolution report.

## Measured facts
* Template control: controlled set = applicable params minus `m_nonPropagatedTemplateParamIds` (equals Revit TPLCTL noncontrolled). Applying a template COPIES its controlled settings into the view (rosetta view_h_template), so stored view values are already effective; checked in 6 files: every controlled group equals the template's (only exceptions: schedules, 3D views on plan templates, level-relative view range). `Visibility.effective` now copies only groups the template controls.
* Revit's `View.GetFilters()` lists ascending element id, not UI priority; decoded filters match as a set 54/54, visible 316/316, overrides 316/316 (Snowdon 2024; check_settings.py). Priority order (stored order, earlier wins) is unverified: needs GetOrderedFilters + overlapping-filter scene (NEEDS-FROM-ORACLE).
* View records also carry: `m_pRvtLinkOverrides` (invisible/halftone/underlay sets, display settings), `m_oWorksetVisibilityViewSettings`, `m_oDesignOptionViewSettings`, `m_pHideElementsMgr`, draw-filter classes Partition/Phasing/DesignOption/RvtLink/HideElements. Not yet decoded into the Doc.

## Resolution report (for the hidden-line renderer / control panel)
`resolve_view(dec, doc, vid)` -> {view, template, filters, hidden_categories, elements: {eid: {cls, cat, phase, filters, overrides (merged members), source (member -> category:ID | filter:ID | phase | element), proj/cut {w mm, rgb, dash, pen, halftone}, halftone, transparency}}}.
