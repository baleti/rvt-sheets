# FEATURE-AUDIT: view-dependence hierarchy (c5-sheets, 2026-10-15)
done = decoded + drawn + checked against a Revit export; partial = drawn, known gaps; missing = not drawn.
Evidence: tools/check_elements.py (element sets vs FilteredElementCollector), tools/compare_dxf.py (DXF layer P/R), tools/fid_images.py (SSIM), ~/src/rvt-qa/qa-view.

| area | status | notes |
|---|---|---|
| view template (V/G, filters, detail level, phase filter, discipline taken from template) | partial | settings decoded + applied; TPLCTL used (rvtsheets/vg/template.py, equals Revit's noncontrolled list); stored view values are the effective ones (6 files) |
| category visibility (hidden categories, annotation/model/analytical/import flags) | done | element sets P/R 0.95-0.99 |
| category overrides (weights, colours, patterns, halftone, transparency, cut/surface fill) | done | rosettas e |
| subcategory overrides | partial | via category parent lookup |
| element overrides, hidden elements | done / partial | m_explicitlyHiddenElements read; Snowdon L2 dims 595385/6 are not hidden: Revit has no bounding box for them (references to elements outside the view, oracle dimprobe) and lists none; the dimension-reference rule in visibility.py drops them (P .9941 on Snowdon) |
| view filters (rules, enabled, visibility, overrides) | done | 2026-10-15: inverse rules decoded, 'Family and Type' resolved, filters now also hide annotation + marker elements (Sections/Callouts/Elevations categories); missing-parameter inverse rule = no match |
| phase / phase filter | done (lists + resolved overrides) | oracle scene 2024_vg_phases: element phase status = Revit's ElementOnPhaseStatus 213/213; per-filter presentation (ByCategory / Overridden / DontShow) resolved: 'VG custom' view (Existing = Overridden: grey 127 pen 2, no cut fill; Temporary = Overridden blue; New ByCategory black; Demolished not shown) equals Revit's PNG; DXF/image numbers not measured |
| discipline | partial | marker rules by discipline (coordination hides markers); no other effect modelled |
| view range (cut/top/bottom/depth) | done | plus underlay (halftone), stair/floor exceptions; structural framing above the cut plane hidden (Snowdon L2, one data point) |
| crop region, annotation crop | done / partial | crop clip, datums clipped to the annotation crop (crop + offsets x scale) when a 3D-extent grid has no per-view extent |
| scale-dependent line weights / patterns | done | model pens per scale, pattern scale |
| detail level (coarse/medium/fine) | done | conditions in family graphics |
| underlay | done (plans) | |
| linked models (RvtLinkInstance) | partial | per-view display settings decoded, mode 1 = by linked view confirmed by the oracle links scene (vg/links.py: visible, halftone, underlay, custom per-category; mode names by host / by linked view / custom unverified); report lists them; link CONTENT not drawn (needs the linked documents: the 6 Snowdon targets are in the corpus, multi-file loading missing). Revit never lists link instances in view lists (0 of 1035 view/link pairs) |
| worksets | done (element lists) | per-view workset visibility + element workset (rvt_worksets, Global/ElemTable + PartitionTable) + default-hidden worksets: Revit scene 2024_vg_worksets lists matched with recall 1.0 and no non-marker FP in all 3 views (A-walls/B-furn hidden = 3 elements, C-cols default hidden = 13); closed worksets not testable |
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
- Size: the em printed by Revit = type size x 1/0.72 rounded UP to the next 0.5 pt, exact half points staying (1/8" 12.5, 1/4" 25.0, Arial 3/8" 37.5) except from 45 pt up where they move up 0.5 (1/2" 50.5, 5/8" 63.0, 1" 100.5); 3/32" 9.375 -> 9.5, 3/16" 18.75 -> 19.0: svg.revit_pt. Ratio ours/Revit 1.000 on Snowdon, Commercial 206124 and 206143 PDFs
- Baseline vs anchor (em of the printed size), Revit: top-aligned +0.98 (titleblock labels), middle +0.335..0.338 ((ascent - descent) / 2), bottom -0.225 (Arial: viewport titles sit 0.88 mm = 0.2 em ABOVE their title line) / -0.247 (Trebuchet). Ours before: +0.90 / +0.45 / 0.0 (the title baseline lay on the line, ~1 mm too low). svg.first_baseline / BASE_OFF now implement the measured numbers (RVT_TEXTBASE=0 restores the old rule); dimension texts, which sat 0.3 size above the line to compensate, now sit on the line (DIM_TXT_OFF 0). Residual after: view L4 grid digits +0.11 mm, dimension text -0.11 mm; sheets S101 / S600 groups within 0.01 em (schedule header cells 'No.' / 'Description' +0.22 em still different: table cell alignment, open).
- Final constants (annot 4f4db50; schedule lines: inner grid 0.24 pt = 0.085 mm black, outline 1.3 pt = 0.457 mm, widths in the Revit PDF are in pt; Revit PDFs Snowdon S000 921485, Commercial 206143 / 206124): Arial top 0.90 / middle 0.338 / bottom 0.225 em, rich-text label boxes Arial 0.90 / Trebuchet 0.99 em, Trebuchet top 0.95 / middle 0.335 / bottom 0.222 em; line pitch Arial 1.22 em, Trebuchet 1.26 em; residuals: titleblock labels 0.0-0.1 mm, Trebuchet titles 0.06 mm, address blocks 0.1-0.3 mm. Schedules: em = type size / 0.72 in all years, row pitch 1.917 x type size (4.565 / 6.09 / 12.17 mm), headings wider than their column wrap and grow the row, gridless lists keep the hidden heading row; ARchitxt (weld symbol text) printed as Arial; Help Button '?' (Arial Bold) is real in Revit's PDFs but absent from its DXF exports
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

## c3-vg measured list agreement (2026-10-17, element lists vs Revit's FilteredElementCollector, tools/check_elements.py)
Snowdon 2024/2026 P .9939 R .9984; Residential P .949 R .983; Commercial P .962 R .995; rst_basic P .986 R .982. Mechanisms added: design options (primary from DesignOptionSet), perpendicular + in-crop datums in sections, 3D grids/levels clipped by section box (2022+), view meta elements (extent, active section boxes), rooms across the cut, ceiling-plan volume, dimension reference rules, scope boxes not in sections. Open: elevation markers in template rosetta plan, CoordinateSystemDisplayElem rule, property lines outside range, hidden-line transparency semantics (needs Revit PNG compare).

## c6-sheets update (2026-10-19)
| area | status | notes |
|---|---|---|
| filter rule parameters (framing 'z Offset Value') | partial | Snowdon 600158: 364 of 942 framing instances have no decoded value; Revit colours 100+ beams, we match 18 (NOT = 0) / 12 (< -0.5): reader question open (NEEDS-FROM-SHEETS.md tail, tools/filter_probe.py, zoff_probe.py) |
| grids in plans (Snowdon Parapet 2 876061) | done | black dash-dot, bubbles at Revit's ends (the 10-17 review pair was stale); line weight a little lighter than Revit's |
| section cut of structural framing / columns / foundations (Snowdon Longitudinal 579975) | missing | only 5 elements are cut (4 walls + 1 floor); Revit fills cut steel dark red-brown and cut concrete grey; materials carry cut patterns (Steel 1121, Concrete 748) but framing/column solids never reach the cut path (family pieces with non-drawable or hidden graphics styles are kept as occluders only, viewdraw.py pieces['solids'] loop); tools/cutfill_probe.py, prim_probe.py (host1) |
| section marker colour | missing | Revit draws the Longitudinal section flags red (view-specific line colour), ours black |
| shaded 3D DXF tier | n/a | Revit's DXF of shaded views has datums only; score on the image tier |

### c7-vg measured evidence on the Revit-authored V/G scenes (2026-10-19, tools/check_elements.py vs gt_views, element lists of Revit's FilteredElementCollector per view; identical on the 2024 and 2026 builds)
| scene | precision | recall | what the false positives / misses are |
|---|---|---|---|
| vg_worksets | .832 | 1.000 | FP = per-plan elevation markers only |
| vg_phases | .689 | 1.000 | FP = per-plan markers (145); unplaced room phase rule fixed R .972 -> 1.0 |
| vg_discipline | .828 | 1.000 | FP = markers |
| vg_hide | .766 | 1.000 | FP = markers |
| vg_filters | .873 | 1.000 | FP = markers |
| vg_templates / templates_var | .840 / .842 | 1.000 | FP = markers |
| vg_markers | .794 | .9625 | marker 301634 (API-created) is listed only in the plan it was created for; no stored link marker -> plan found (arrows, viewer, section view, all plan records searched) |
| vg_links | .877 (RVT_LINK_LISTED=1; .846 / .767 without) | 1.000 | link instances are listed when the link was loaded at export; not derivable from the file |
| view templates, TPLCTL | non-controlled set identical to Revit's TPLCTL list for 7 of 7 templates in 4 scene files (2024/2026 templates, templates_var) |

## c7-sheets update (2026-10-20)
| area | status | notes |
|---|---|---|
| filter rule parameters (framing 'z Offset Value') | done | derived reader values live under typed keys (name|Double): FilterEval.value prefers them; Snowdon 600158 'Z Offset' filter matches 165 (Revit's dump: 165 non-zero); yellow rim beams drawn |
| section marker colour (Snowdon Longitudinal) | done | head fill = colour of the region's graphic style (red), black fills / outlines hidden |
| section cut fills of Snowdon Longitudinal 579975 | done (fills) | m_surfaces 7 accepted for shaded sections, standalone views draw the section image under the linework; piles' mesh shorter than their linework |
| dimension colour | done | dimension type's line category colours line + text (orange level dims) |
| solid surface fills of overrides (section / 3D) | done | depth-tested flat colour image under the linework (columns by level in 600158); plans not enabled |
| 3D levels | partial | envelope edges at the far corner with the view's filter colours (magenta); frame offset vs Revit's DXF unresolved |
| structural framing tags | done | tags of straight framing run along the beam (L1 offsets 7 mm -> 1 mm) |
| spot elevations without leader | partial | placement frame / alignment depends on the picked beam's direction sign: fits L1, not L2 (RVT_SPOT_OFFFRAME / RVT_SPOT_LEFT experiments, default off) |
