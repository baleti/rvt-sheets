# FEATURE-AUDIT: view-dependence hierarchy (c5-sheets, 2026-10-15)
done = decoded + drawn + checked against a Revit export; partial = drawn, known gaps; missing = not drawn.
Evidence: tools/check_elements.py (element sets vs FilteredElementCollector), tools/compare_dxf.py (DXF layer P/R), tools/fid_images.py (SSIM), ~/src/rvt-qa/qa-view.

| area | status | notes |
|---|---|---|
| view template (V/G, filters, detail level, phase filter, discipline taken from template) | partial | settings decoded + applied; template-controlled-parameter list (TPLCTL) not used to decide what a view keeps of its own; drawing verified only on Snowdon L2 |
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
| design options | partial | primary option only |
| grids | done | 2D/3D extents along -axis (Snowdon, Commercial), bubble end, annotation-crop clip, heads at paper size; multi-segment grids missing |
| levels | partial | extents/heads in sections done; plan hidden; datum head symbol quadrant fill missing |
| tags (independent, room, space, area) | partial | symbol graphics + labels + rotation (orientation 1/2); label-visibility rules (family label parameters), leaders missing; 'Structural Framing Tag' frame suppressed (Revit shows bare text) |
| dimensions | partial | linear done (ticks, witness, text, units 2022+); angular/radial/arc missing; alternate units missing; dimension hide rule unknown |
| spot elevations / slopes | partial | values verified by reading Revit's sheet (5'-0", 7'-7"); Revit draws the text without target/leader here: placement rule unknown |
| text notes, keynotes | partial | text notes done; keynote tags/legends partial |
| section / callout / elevation markers | done (plans), partial (sections) | filters + discipline + range + scale + crop rules |
| detail components, filled regions, masking regions, repeating details | done | |
| surface patterns (projection) | missing | cut patterns done |
| reinforcement (area/path/wall, bar by bar) | missing | gt_rebar exists for rst files |
| graphical column schedules | missing | |
| revision clouds, revision schedules | missing | no corpus samples |
| schedules / legends | partial | values + groups; legends components partial |
| 3D views | partial | software shaded; perspective empirical; no section box/crop frame |
| sheets (title block, viewports, rotation) | done | |
| PDF export | done | rvt-sheets pdf |
