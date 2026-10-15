# rvt-sheets: design

Goal: draw Revit SHEETS and the VIEWS placed on them, from the .rvt alone, as close to what Revit itself draws as we can measure.
Own analysis only (no ODA, no code from rvt-rs or others). Autodesk sample files stay local.

## 1. Sources
* Reader (session 176, `~/rvt-research`, imported read-only): `rvt_xcache.get_x(file)` -> every record decoded schema-driven (`recs[(id, class)] = {id, class, fields, ...}`),
  element headers (`eh`: category, owner view, design option, bbox), parameters (`rvt_params`), saved graphics per element (channel 103, `g103_get`),
  meshes / B-rep (`rvt_elemmesh.element_mesh`, `rvt_geometry.element_brep`), materials (`rvt_materials`).
  The record fields already contain everything view-related as raw fields; this project gives them meaning (stage 1).
* Oracle (session 181, real Revit 2020/2024/2026 in an offline VM): `oracle/viewdump.cs` (settings + per-view element lists), `oracle/viewexport.cs`
  (Revit's PNG/DXF/PDF of every sheet and placed view). Results in `~/rvt-research/gt_views/`. Requests go through `~/rvt-research/NEEDS-FROM-ORACLE.md`.
* Rosetta: base + one-change variant files (requested: viewport move, scale, crop, view range, category/filter/element overrides, template, detail level, phase filter, annotations).

## 2. What the records say (first findings, 2020 rst_basic; to be validated against the oracle)
| concept | record / field |
|---|---|
| sheet | `DBViewDrafting` with `m_sheetNumber` (+ dates, drawn/checked by), own `DBDrawing` |
| viewport on a sheet | `Viewport` with `m_ownerDBViewId` = sheet: `m_dbViewId` (placed view), `m_offset` (sheet position, ft), `m_scale`, `m_labelOrigin`, `m_labelLength`, `m_attrId` (viewport type), `m_viewportOrientation`, `m_detailNumber`. Every view also has an internal Viewport+DBDrawing of its own (not on a sheet). |
| schedule on a sheet | `ScheduleInstance` owned by the sheet: `origin_XYZ`, `m_scheduleId`, `rotationValue` |
| view | `DBViewPlan / DBViewSection / DBView3d / DBViewDrafting / DBViewSchedule / DBViewRendering ...`: `m_viewName`, `m_scale` (1/N), `m_origin`, `m_viewDir`, `m_horzDir`, `m_vertDir`, `m_viewTemplateId`, `m_isTemplate`, `m_dbViewTypeId`, `m_genElemId` (level), `m_partsVisibility`, `m_viewerId` |
| view range | `m_pPlanViewRange2 {m_offsets[5], m_levelIds[5]}` + absolute `m_cutPlaneElev`, `m_topClipElev`, `m_bottomClipElev`, `m_levelBelowElev` (view depth), cutter planes `m_pCutter`, `m_pViewDepthCutter` |
| crop | `Viewer.m_boundedSpace {m_orig, m_basis[3], m_boundOffset[3][max,min], m_boundActive}`, annotation crop `m_pAnnotationCropOffsets`, non-rectangular `m_nonRectangularCropAreaCurvesLoops` |
| category V/G | `m_oaDrawFilters[].m_categoryIds` (+ annotations/models/imports excluded flags), `m_oGraphicOverrides` (per-category maps: gStylesProj/Cut, fill patterns/colours fg+bg proj/cut, halftones, transparency, detail levels) |
| filters in a view | `m_oFilterOverrides.m_oaSettings` |
| element overrides | `m_oAdHocOverrides {m_elementMap, m_oaSettings}`, hidden: `m_explicitlyHiddenElements`, `m_oHiddenElementsViewSettings` |
| draw order (detail) | `m_pDetailDrawOrderMgr.m_aDrawOrder` |
| design options | `m_oDesignOptionViewSettings` |
| links | `m_pRvtLinkOverrides` |
| line-work edits | `m_pRetouchTable` (linework tool) |
| display | `m_pViewDisplayMgr` (style, edges, shadows, background) |
| view-owned elements | element header / `m_ownerDBViewId` = view id |

## 3. Data model (`rvtsheets/model.py`, plain dataclasses, JSON-serialisable)
* `Doc`: file, version, units, categories (object styles: proj/cut weight, colour, pattern, material, parent), line patterns, fill patterns, line-weight table (pen -> mm per scale), phases, phase filters, design options, levels, filters, view templates, sheets, views.
* `Sheet`: id, number, name, size (from title block), title blocks (symbol id, transform, parameter text), viewports, schedule instances, revisions.
* `Viewport`: id, view id, sheet position (box centre / view origin on paper, ft), rotation, type (title shown, line weight...), label origin/length, detail number.
* `View`: id, kind (plan/ceiling/area/structural/section/elevation/3d/drafting/legend/schedule), name, scale, detail level, discipline, display style, frame (origin, right, up, dir), crop (box + shape + annotation crop, active/visible), view range (absolute elevations), phase + phase filter, template id + controlled parameters (effective settings = template where controlled), category V/G, filters (ordered, visibility, enabled, overrides), element overrides, hidden elements, underlay, far clip.
* `Override` (== OverrideGraphicSettings): projection/cut line {weight, colour, pattern}, surface/cut fill {fg/bg pattern, colour, visible}, halftone, transparency, detail level. Resolution order: element > filters (first in list wins per member) > category (sub-category falls back to parent) > object style.
* Drawing primitives (`rvtsheets/prims.py`, paper space mm after the viewport transform): `Line(pts, weight_mm, rgb, dash, halftone)`, `Region(loops, fill pattern + colour, transparency)`, `Text(str, pos, size, font, rotation, align)`, `Image`, each tagged with element id + category + layer (cut/projection/beyond/annotation) so the evaluator can compare per element.

## 4. Pipeline
```
.rvt --reader (rvt_xcache records, meshes, saved graphics)--> decode/*.py --> Doc (model.json, cached by file stamp)
Doc + view id --> content builder (build/plan.py, section.py, model3d.py, drafting.py, legend.py, schedule.py, annot.py)
   1. element set: category V/G, filters visibility, hidden elements, phase filter, design option, discipline, view range/far clip, crop, owner view
   2. geometry per element: plan/section = cut (slice of the element mesh at the cut plane) + projection (B-rep edges below the cut,
      hidden-line removal by a z-buffer pass), beyond/underlay, symbolic 2D graphics of families (saved graphics nodes with view-direction conditions);
      annotation = the element's own 2D graphics (saved graphics) or text/dimension rules
   3. style resolution (section 3 order) -> primitives
--> renderer: render/svg.py (vector, exact paper mm; default), canvas raster for big views (later WebGL)
--> sheet composer: title block symbol graphics + viewports (clip to crop, scale, rotate, translate) + viewport titles + schedules
--> export: SVG, PDF (cairosvg / own PDF writer)
```
Caching: decoded Doc per file stamp; per-view primitive lists as JSON (gz) so the browser only fetches what it shows.

## 5. Plug-in to the viewer (no edits to ~/src/rvt-viewer)
* rvt-sheets ships its own aiohttp sub-application `rvtsheets.server:make_app()` with routes `/sheets/` (page), `/sheets/api/<mid>/doc.json`, `/sheets/api/<mid>/sheet/<id>.svg|json`, `/sheets/api/<mid>/view/<id>.svg|json`.
  It finds the model file through the viewer's model dir (`~/.cache/rvt-viewer/models/<mid>/` meta) or an explicit path.
* Standalone: `./rvt-sheets serve FILE.rvt` (own port) works without the viewer.
* Hook requests to session 187 are in `HOOKS.md`: (1) mount the sub-app (`app.add_subapp('/sheets/', make_app(...))`) when importable, (2) the view/sheet browser opens `/sheets/#<mid>/sheet/<id>` (new tab/pane) for sheets and 2D views.

## 6. Validation (oracle plan)
* Per view: element-set precision/recall of our visible set vs `VIEWELEMS` (Revit's FilteredElementCollector(doc, viewId)).
* Settings: every decoded setting vs `VIEW/RANGE/CROP/CATVIS/VFILTER/EOVR/VIEWPORT/TITLEBLOCK` rows (exact or tolerance), reported as a per-field table.
* Pictures: our SVG rasterised at the PDF's paper size vs Revit's PDF (2024/2026; exact paper registration) or PNG/DXF (2020): SSIM on the full sheet and per viewport, and a symmetric edge-map distance (chamfer, mm at paper scale). Image metrics only; screenshots for the user go to `screenshots/`.
* Feature checklist (`COVERAGE.md`): per view type and per override/rule type: decoded? applied? verified (rosetta variant changes what Revit changes)?

## 7. Stages
0 design (this file) / 1 decode + settings validation / 2 sheet layout (title block, viewports, titles) / 3 plan views (range, cut/projection, weights, patterns, phases, overrides, filters, templates) /
4 sections/elevations / 5 annotations / 6 schedules, legends, 3D, drafting, links / 7 SVG/PDF export. Each stage ends with a measured table in PROGRESS.md.

## 8. Constraints
host3 is shared: heavy jobs `systemd-run --user --scope -p MemoryMax=4G -p MemorySwapMax=0 nice`, one at a time, check `free -g` first. No VM access except via session 181. Test windows only on Hyprland workspace 178.
