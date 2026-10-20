# CONTROL-API (rvt-sheets side, c2-annot)
Contract with c2-vctl (viewer control panel). Full request list: ~/src/rvt-viewer-vctl/docs/CONTROL-API.md; answers: CONTROL-API-ANSWERS.md next to it.

## Primitive keys (ViewDrawer.draw -> prims, view coordinates, model feet)
Stable: `t` (line|segs|cut|fill|text), `elem`, `layer`, `style` {w, rgb, dash, halftone}, text keys (`text origin x size font bold italic halign valign anchor box`).
Added by `ViewDrawer._finish` (all optional for consumers, absent = unknown):
- `cat`: category id of the owner element.
- `paper`: true for layers annotation, annotation_fill, text, datum (sizes are paper sizes x view scale).
- `part`: sub-part of the element: `text` | `line` | `fill` by default; explicit: dimensions `line` `witness` `arrow`, text-note leaders `leader` `arrow`. Tags, datums, markers, spots: next.
- `anchor`: world feet point of the element's first annotation prim (tagged-element reference point later).
- `hang`: marker prims (section/elevation/callout heads) that may sit outside the model extents.

## Open (see PROGRESS.md of this branch)
element properties table, /view/{id}.json in the sheets server (c5-sheets owns server.py), `gs` on annotation prims.

## Served by the sheets server (c5-sheets, dev)
GET /sheets/api/{mid}/view/{id}.json?scale=&detail=&template=0&filters=0&cut=&phase=&phaseFilter= -> {view, prims, elements, options, stats, seconds, key} (same shape as vscene_worker; cached next to the SVGs as scene_<vid>_<opts-hash>.json; 200 ready, 202 model still loading).

## Update 2026-10-16 (c5-annot) answers to ANNOT-FINDINGS item 2 / 3
- Joist system notes ('18LH04 @ Max 4'-0"') ARE stored: class `BeamSystemTag` (cat -2005130, 7 in L2); span direction symbols ('2VLI-6" / TOS(5'-6")' + arrows) are class `SpanDirectionSymbol` (cat -2005110, 3 in L2). Both are drawn now (annot commits 'beam system tags' / 'span direction symbols'); their prims carry elem ids, cls in the elements table (PROP_CLASSES includes both), part head/text.
- Spot elevations in plans read the picked element's face under the point (Revit 7'-4 1/2" vs stored 7'-7"): 'SpotElevation' elements in L2 / L1 are those '4'-7"' / '7'-4 1/2"' strings; the 80'-1" dimension rule is still unknown.
- New element classes drawn with ids: property line segment tags (IndependentTag, rotated along the segment), ContourLabelingElem (one prim per label, `elem` = the labelling element), equality dimensions ('EQ' text, part text).

## Update 2026-10-17 (c3-annot)
- New element classes drawn with ids / parts: `AngularDim` (arc `line`, `arrow` heads + ticks, `text` degrees; in PROP_CLASSES), `SpanDirectionSymbol` and `BeamSystemTag` now use the instance's own symbol (m_actualSymbolId) so arrow lengths follow the Left/Right/Top/Bottom parameters.
- Tag leaders (`part: leader`) are now 3-point polylines (shelf start at the label block edge, elbow = head + m_elbowOffset, target); consumers must not assume 2 points.
- Wall / floor / roof layer lines and surface patterns carry `elem` of the host and layer `cut` / `cut_fill`; roof chevron cuts are layered per piece.
- Datum planes not perpendicular to a section / elevation view are not emitted (Revit omits them).

## Graphics resolution (c3-vg, 2026-10-17) for the hidden-line renderer and the control panel
`rvtsheets.vg.api.report_text(dec, doc, view_id)` (JSON; route proposal for server.py: `GET /api/{mid}/view/{id}/vg.json`) =
`{view, name, kind, scale, template {id,name,controlled[groups]}|null, detail_level, phase_filter, discipline, filters [{id,name,visible,enabled,overrides}] (view list order),
hidden_categories [ids], links [{instance, symbol, name, visible, halftone, underlay, custom{overall, modes, categories}}], excluded {reason: n}, excluded_ids {id: reason},
elements {eid: {cls, cat, phase, filters [ids matched, priority order], overrides {merged members: proj_weight/proj_color/proj_pattern/cut_*/surf_fg_pattern/surf_fg_color/surf_bg_*/cut_fg_*/cut_bg_*/*_visible/halftone/transparency/detail_level},
source {member: "category:ID"|"filter:ID"|"phase"|"element"}, proj {w (mm at the view scale), rgb, dash [mm]|null, pen, halftone}, cut {same}, halftone, transparency (0-100), phase}}}`.
Order of precedence per member: element override > filters (earlier in the view's list win) > phase-status override > category (sub-category falls back to parent) > object style.
Members absent from `overrides` come from the object style (`proj`/`cut` already contain the resolved line style). Fill patterns: `overrides.surf_fg_pattern` etc. are fill pattern ids (doc fill_patterns); when absent the material's surface pattern applies (reader materials).

## Update 2026-10-19 (c6-annot)
- Text of tags / dimensions / level heads now follows Revit's PDF word for word on the Snowdon corpus (tools/pdf_text_all.py, tools/pdf_text_regress.sh): consumers can rely on `text` strings of prims with `elem` of class IndependentTag / BeamSystemTag / LinearDimString / Level / Grid / Section / InteriorElev being what Revit prints (dimension prefix / suffix / override, alternate units `part: alt_text` with digit grouping, unplaced markers '-' / '---').
- `BeamSystemTag` text prims carry a rotation (`x` direction vector): perpendicular to the held beams of the tagged JoistSystem (Revit 'Beam System Tag Direction', not stored on the tag).
- Static RTF text notes of annotation family instances (`FamilyInstance` detail items / generic annotations) are emitted as `text` prims with the instance `elem`.
- Dimension prims whose references are link instances hidden in the view are not emitted (stat `dim_hidden_link`).
- New env switches (all default on unless noted): RVT_DIMFIELDS, RVT_BST_DIR, RVT_TAGTYPEID, RVT_TAGBYNAME, RVT_ELEMID64, RVT_ELEVFMT, RVT_UNPLACED_MARK, RVT_SYMTEXT, RVT_TAGQ, RVT_DIMLINK; off by default: RVT_DIMLINK2, RVT_DIMREF64, RVT_GRIDNORTH=1 (old plan grid head rule).

## Update 2026-10-19 (c7-annot)
- Area tags: the Area element's value follows the area scheme boundary lines at their wall-finish offsets (text now '1310 SF' / '12299 SF' per the project's area format grouping); consumers see them as ordinary `text` prims with the Area (RoomElem with m_areaSchemeId) `elem`. Env: RVT_AREA_POLY=0 off.
- Property line segments (IndependentTag-free, cls `PropertyLineSegment`, `layer: projection`) are emitted per the view's crop z bounds / site range rule (RVT_PROPLINE_Z=0 restores the range rule).
- Section markers: `part` unchanged; which ends carry a full head symbol now depends on flip / crop clipping (RVT_SECTION_TAILFLIP=0 old rule); interior elevation markers emit the body's sheet-number text once (RVT_BODY_ONCE=0).
