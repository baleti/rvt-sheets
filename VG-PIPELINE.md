# VG-PIPELINE (c3-vg)
Package `rvtsheets/vg/`: stage functions on decoded Doc dicts. `tests/test_vg.py` unit tests; `tools/vg_report.py FILE VIEWID [OUT.json]` = graphics resolution report.

## Measured facts
* Template control: controlled set = applicable params minus `m_nonPropagatedTemplateParamIds` (equals Revit TPLCTL noncontrolled). Applying a template COPIES its controlled settings into the view (rosetta view_h_template), so stored view values are already effective; checked in 6 files: every controlled group equals the template's (only exceptions: schedules, 3D views on plan templates, level-relative view range). `Visibility.effective` now copies only groups the template controls.
* Revit's `View.GetFilters()` lists ascending element id, not UI priority; decoded filters match as a set 54/54, visible 316/316, overrides 316/316 (Snowdon 2024; check_settings.py). Priority order (stored order, earlier wins) is unverified: needs GetOrderedFilters + overlapping-filter scene (NEEDS-FROM-ORACLE).
* View records also carry: `m_pRvtLinkOverrides` (invisible/halftone/underlay sets, display settings), `m_oWorksetVisibilityViewSettings`, `m_oDesignOptionViewSettings`, `m_pHideElementsMgr`, draw-filter classes Partition/Phasing/DesignOption/RvtLink/HideElements. Not yet decoded into the Doc.

## Resolution report (for the hidden-line renderer / control panel)
`resolve_view(dec, doc, vid)` -> {view, template, filters, hidden_categories, elements: {eid: {cls, cat, phase, filters, overrides (merged members), source (member -> category:ID | filter:ID | phase | element), proj/cut {w mm, rgb, dash, pen, halftone}, halftone, transparency}}}.

## Link content (stage 9b, c6-vg)
`vg/linkdraw.py`, `RVT_LINKS=1` (off by default). resolve_path finds the link file next to the host (corpus number prefixes ignored, RVT_LINK_DIRS); a second ViewDrawer draws the linked view copy with the host frame (X_L = R^T X_H, O_L = R^T (O_H - t)); display mode per INSTANCE id: by linked view = that view (its phase decides: oracle links scene, a phase-1 view hides phase-3 content), by host view = host phase, filter, detail, range moved into link coordinates; halftone mixes with white. Only model layers are taken (no link annotations). Verified on the oracle scene 2026_vg_links; not on Snowdon, whose Revit references were exported with the links unloaded.

## Element-list rules added by c6-vg (all with RVT_* off switches, see PROGRESS.md 2026-10-18)
RVT_GRID_CROP_PLAN, RVT_CGL_NOBBOX, RVT_CGL_EDGEON, RVT_FAMWALL, RVT_ROOM_SECTION, RVT_RCP_SWEEPS. Parked: elevation markers are per plan in Revit (no stored link found), face splitters listed per view by host face orientation (unproven), ceiling plan 36 below-cut elements.

## c7-vg additions (2026-10-19)
- RVT_ROOM_UNPLACED=0 off: unplaced rooms (empty bbox sentinel) are listed in views of the room's own phase (m_phaseId) only.
- RVT_LINK_LISTED=1 on (default off): RvtLinkInstance elements are listed in every view (Revit does this when the link was loaded at export; Snowdon's references were exported unloaded).
- Unit tests: python3 -m pytest -q tests/test_vg.py tests/test_filters.py tests/test_visibility.py tests/test_linkdraw.py (no corpus needed).
- Scene check: tools/check_elements.py SCENE.rte gt_views/SCENE.rte.views on host3 under a 3 GB cap (each ~1 min); see the FEATURE-AUDIT tail for the numbers.
