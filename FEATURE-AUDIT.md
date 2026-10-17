# FEATURE-AUDIT: view-dependence hierarchy (c5-sheets, 2026-10-15)
done = decoded + drawn + checked against a Revit export; partial = drawn, known gaps; missing = not drawn.
Evidence: tools/check_elements.py (element sets vs FilteredElementCollector), tools/compare_dxf.py (DXF layer P/R), tools/fid_images.py (SSIM), ~/src/rvt-qa/qa-view.

| area | status | notes |
|---|---|---|
| view template (V/G, filters, detail level, phase filter, discipline taken from template) | partial | settings decoded + applied; TPLCTL used (rvtsheets/vg/template.py, equals Revit's noncontrolled list); stored view values are the effective ones (6 files) |
| category visibility (hidden categories, annotation/model/analytical/import flags) | done | element sets P/R 0.95-0.99 |
| category overrides (weights, colours, patterns, halftone, transparency, cut/surface fill) | done | rosettas e |
| subcategory overrides | partial | via category parent lookup |
| element overrides, hidden elements | done / partial | m_explicitlyHiddenElements read; hidden dims of Snowdon L2 (595385/6) are hidden by an unknown mechanism |
| view filters (rules, enabled, visibility, overrides) | done | 2026-10-15: inverse rules decoded, 'Family and Type' resolved, filters now also hide annotation + marker elements (Sections/Callouts/Elevations categories); missing-parameter inverse rule = no match |
| phase / phase filter | partial | visibility + presentation overrides; demolished/new graphics partial |
| discipline | partial | marker rules by discipline (coordination hides markers); no other effect modelled |
| view range (cut/top/bottom/depth) | done | plus underlay (halftone), stair/floor exceptions; structural framing above the cut plane hidden (Snowdon L2, one data point) |
| crop region, annotation crop | done / partial | crop clip, datums clipped to the annotation crop (crop + offsets x scale) when a 3D-extent grid has no per-view extent |
| scale-dependent line weights / patterns | done | model pens per scale, pattern scale |
| detail level (coarse/medium/fine) | done | conditions in family graphics |
| underlay | done (plans) | |
| linked models (RvtLinkInstance) | missing | Snowdon Structural has 6 links; needs reader support for link documents |
| worksets | partial | visibility not modelled (all worksets shown) |
| design options | partial | primary = DesignOptionSet.m_mainDesignOption (2026-10-17 fix, it never matched before), per-view option choice decoded (unverified: no sample view has one) |
| grids | done | 2D/3D extents along -axis (Snowdon, Commercial), bubble end, annotation-crop clip, heads at paper size; multi-segment grids missing |
| levels | partial | extents/heads in sections done; plan hidden; head symbol with cross + NW/SE black quadrants (2020 families) |
| colour scheme legends | done | alphabetical entries, wrap, title; 'Calculating...' placeholder row not reproduced |
| property lines, stairs path text | done | property lines inside the primary view range; UP/DN at start/end riser |
| tags (independent, room, space, area) | partial | symbol graphics + labels + rotation (orientation 1/2); label-visibility rules (family label parameters), leaders missing; 'Structural Framing Tag' frame suppressed (Revit shows bare text) |
| dimensions | partial | linear done (ticks, witness, text, units 2022+); angular/radial/arc missing; alternate units missing; dimension hide rule unknown |
| spot elevations / slopes | partial | values verified by reading Revit's sheet (5'-0", 7'-7"); Revit draws the text without target/leader here: placement rule unknown |
| text notes, keynotes | partial | text notes done; keynote tags/legends partial |
| section / callout / elevation markers | done (plans), partial (sections) | filters + discipline + range + scale + crop rules |
| detail components, filled regions, masking regions, repeating details | done | |
| surface patterns (projection) | missing | cut patterns done |
| reinforcement (rebar sets, area/path reinforcement bar by bar) | done (release 4) | bars from rvt_rebar.rebar_centerlines; rst_basic S-RBAR recall 1.0 in sections/plans; wall reinforcement in sections not checked; fabric sheets missing |
| graphical column schedules | missing | |
| revision clouds, revision schedules | missing | no corpus samples |
| schedules / legends | partial | values + groups; legends components partial |
| 3D views | partial | software shaded; perspective empirical; no section box/crop frame |
| sheets (title block, viewports, rotation) | done | |
| PDF export | done | rvt-sheets pdf |

## Fonts (c3-sheets, 2026-10-17)
Cause of "grid bubble glyphs differ": checked on Snowdon L2 against Revit's own PDF (pdffonts / pdftohtml): Revit embeds **TrebuchetMS** (grid bubbles, beam-system / joist notes, level tags 'W18x55') and **ArialMT** (column tags 'W14x109'). Our SVG asks for the same families (font name from the TextElemType / family label font id). At 12000 px the bubble '1' has digit height / circle diameter 0.3746 (Revit PDF 0.3744), width 0.126 (0.128), ink share 0.0219 (0.0215): glyph shape, size and weight are the same. What the user sees at screen size is renderer anti-aliasing (Revit PNG = GDI grey-scale, browser / rsvg = different hinting) and, on a machine without Trebuchet MS, the browser's fallback.
Fonts in the demo corpus (doc['fonts']): Residential Arial only; Commercial Arial + Arial Black (1); Snowdon Structural Arial 1018, Trebuchet MS 84, ARchitxt 45, Arial Narrow 19, Georgia 2, Swis721 Lt BT 1; Facades Arial 428, Trebuchet 252, ARchitxt 2, Georgia 1.
| Revit font | host3 (fc-match) | host1 before | host1 now | width error of the host1-before fallback vs the real font | free substitute (measured) |
|---|---|---|---|---|---|
| Arial | Arial (MS) | Liberation Sans (metric-compatible) | Arial | 0.0 % | Liberation Sans / Arimo |
| Arial Black | Arial Black | DejaVu Sans | Arial Black | -6.8 % (sd 3.4) | DejaVu Sans Bold x1.03 (sd 2.2 %) |
| Trebuchet MS | Trebuchet MS | DejaVu Sans | Trebuchet MS | +16.7 % (sd 3.7) | Noto Sans x1.068 (sd 2.7 %), Open Sans x1.06 |
| Georgia | Georgia | DejaVu Serif | Georgia | +15.8 % (sd 7.4) | Liberation Serif x1.045 (sd 6.7 %) |
| Verdana | Verdana | DejaVu Sans | Verdana | n/a | DejaVu Sans x1.013 (sd 1.6 %) |
| Arial Narrow | Nimbus Sans Narrow | Liberation Sans Narrow (compatible) | same | not measured (no real file) | Liberation Sans Narrow |
| ARchitxt, Swis721 Lt BT (Snowdon) | Noto Sans | DejaVu Sans | same | not measurable (no file; ARchitxt is a hand-lettering font, Swis721 = Helvetica Light) | Arial / Liberation Sans |
Revit PDF text widths (pdftohtml) / (advance of the real font x size): Trebuchet 1.014 (sd 0.4 %), Arial 1.0 on unrotated runs: the installed Microsoft fonts reproduce Revit's text extents.
Real consequence found: text measured by fc-match drives wrapping (text notes), leader shelf lengths and tag layout, so the host1 warm (DejaVu for Trebuchet / Georgia) laid out different geometry than host3. Fix 1: the user's own Microsoft font files were copied to host1 ~/.local/share/fonts/ms-local (outside every repo, local use only, fc-cache run). Fix 2 (viewdraw._font): when fontconfig has no real match for a Revit font, measure with the measured substitute scaled to the real widths (RVT_FONT_SUBST=0 disables). Open: SVG / viewer font-family stacks with open fallbacks and shipped open fonts (c3-annot, svg.py / viewsvg.py emit 'Name, sans-serif'); the proprietary files must not be shipped.

## Fonts and text baselines (c3-annot, 2026-10-17): measured against Revit's own PDFs
Method: pymupdf span origin (= baseline), font name and size of the Snowdon view / sheet PDFs (gt_views/2024_43*/<id>.pdf) vs our SVG text (tools in out/annot/font/: fontcmp.py size ratios, baseoff.py baseline offsets in em, basecmp.py residuals; the sheet pages coincide with ours so offsets are absolute, view PDFs are registered by a linear fit).
- Font identity: Revit prints exactly the type's family (TrebuchetMS grid bubbles / beam tags, ArialMT, Arial-BoldItalicMT dimension text); our SVG asks for the same families and the Microsoft fonts are installed on host3 / host1 (see the table above): glyphs agree. **Arial Narrow is printed as plain Arial** by the reference machines (dimension text widths in Snowdon L4 equal Arial Bold Italic, ours with the narrow face were 18 % too narrow): svg.font_stack and viewdraw._font map it to Arial (RVT_ARIAL_NARROW=real keeps the narrow face).
- Size: the em printed by Revit = type size x 1/0.72 snapped half-up to 0.5 pt below 30 pt and to 1 pt above (3/32" 9.375 -> 9.5 pt, 3/16" 18.75 -> 19.0, 3/8" 37.5 -> 38.0, 1/8" 12.5 and 1/4" 25.0 exact): svg.revit_pt; size ratio vs Revit 0.986 -> 1.000 (RVT_PTSNAP=0 disables).
- Baseline vs anchor (em of the printed size), Revit: top-aligned +0.98 (titleblock labels), middle +0.335..0.338 ((ascent - descent) / 2), bottom -0.225 (Arial: viewport titles sit 0.88 mm = 0.2 em ABOVE their title line) / -0.247 (Trebuchet). Ours before: +0.90 / +0.45 / 0.0 (the title baseline lay on the line, ~1 mm too low). svg.first_baseline / BASE_OFF now implement the measured numbers (RVT_TEXTBASE=0 restores the old rule); dimension texts, which sat 0.3 size above the line to compensate, now sit on the line (DIM_TXT_OFF 0). Residual after: view L4 grid digits +0.11 mm, dimension text -0.11 mm; sheets S101 / S600 groups within 0.01 em (schedule header cells 'No.' / 'Description' +0.22 em still different: table cell alignment, open).
- Table: Revit font | installed host3 | installed host1 | width error: see the earlier table (c3-sheets): Arial 0 %, Trebuchet / Georgia / Arial Black real fonts present on both hosts (0 %), Arial Narrow not available in Revit's references (Arial), ARchitxt / Swis721 Lt BT not installed anywhere (fallback Arial, no reference text to measure).

## Cover sheet 206143 (Commercial), audit table (c3-sheets, from c3-qa AUDIT-206143.md + own measurements, 2026-10-17)
Reference: Revit PNG (3000 px) and, since 2026-10-17, PDF 206143.pdf (gt_views). Status = state of dev f523bdb.
| item | Revit | ours | status / owner |
|---|---|---|---|
| titleblock hairlines | 1 px black | 0.076 mm pens anti-alias light grey | min width 0.13 mm for sheet-level lines (svg.SHEET_MIN_W, RVT_SHEET_MIN_W): done, needs a warm to show in cached sheets; outer frame is a single black frame in Revit, ours double thin: open |
| revision table header separator | present | missing | open (c3-sheets) |
| text baselines (fields, Owner / Pharmacy / Cover Sheet, A - 00) | PDF | 4-10 px low, A - 00 35 px low | c3-annot baseline rule merged (within 0.2 mm of the PDFs); re-measure after the warm |
| right-aligned values keep a ~1 mm margin | yes | flush to the frame | open |
| Sheet List (gridless): em, pitch, 'Approved By' column | em 8.93 mm, pitch 12.07 mm, JLH column, blank row after the title | 7.59 / 9.88 mm, no column | em + pitch + column fixed (schedule.py); blank spacer row open |
| How Do I / revision table grid weights, row pitch | black 1 px | grey 2-3 px, pitch drift | grid weights as titleblock; pitch open |
| rotated date stamp | present | present (current date) | ok |
| logo, consultant blocks | ok | ok | within 3 dE |
| 3D viewport 1 (realistic render: brick / stucco textures, green roof, red 3D sign, sky, ground) | realistic | flat colours | open: needs the shading model (c3-viewer), textures / materials from c3-geometry (530/530 materials validated), our software shaded3d has no texture or sky |
| 3D viewport 2 (shaded white building on sky blue) | shaded + sky | hidden-line wireframe, white background | open (c3-viewer hidden-line default branch hl / shaded3d + a sky gradient behind shaded 3D viewports) |
| site plan (white paving, drive aisles, parking stripes, car symbol, colour trees, property line) | see left | grey / green fills over the whole site | open: toposurface subregions / materials and site-component z-order (c3-geometry reply in NEEDS-FROM-READER.md tail), planting symbols done |
| help icons, view titles / bubbles | ok | ok ('?' icon drawn) | ok |
