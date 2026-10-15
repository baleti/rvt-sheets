# Coverage (2026-10-12 14:00) - what is decoded / drawn / verified against Revit
Legend: decoded = read from the file; drawn = used by the renderer; verified = compared with the Revit oracle (gt_views) - numbers in PROGRESS.md.

| feature | decoded | drawn | verified |
|---|---|---|---|
| sheets: number/name/params, title block instance | yes | yes (symbol saved graphics + static text + labels with sheet/project params) | settings 100%; image pending |
| viewports: placement (offset + scale), type, title, detail number, label origin/length | yes | yes (view title family + stretched extension line) | centre formula 100% (2020, 2026); image pending |
| viewport rotation, schedule instances on sheets, revision schedules in title blocks | decoded (orientation, ScheduleInstance origin) | no | - |
| view scale, frame, template link, detail level, discipline, phase, phase filter | yes | detail level -> saved-graphics conditions; template V/G | 100% |
| view range (cut/top/bottom/depth/underlay), crop box + annotation crop, far clip | yes | cut plane, depth clip, crop clip on sheets | 100% |
| category V/G hidden, category overrides (lines/patterns/halftone/transparency) | yes | hidden + line overrides + cut fill overrides | 100% / rosetta e drawn |
| view filters (rules) + overrides, element overrides, hidden elements | yes (rule trees) | rules evaluated on element params; overrides applied | 100% / rosetta f, g |
| view templates (controlled params) | link + template settings | V/G, filters, detail level, phase filter, discipline taken from template | rosetta h decoded; drawing not verified |
| phases / phase filters | yes (presentation table) | visibility only; phase graphic overrides (existing/demolished styles) NOT drawn | element sets |
| design options | primary only | visibility | partial |
| element sets per view | - | - | P 0.82-0.97 / R 0.95-0.98 on sample projects |
| plan cut/projection linework | from saved-graphics solids | cut outlines (join cleanup), projection edges with z-buffer HLR, symbolic family lines (view-direction / cut conditions) | images pending |
| line weights (model pens per scale, annotation pens), line patterns, colours | yes | yes | pens/patterns 100% decoded |
| cut patterns (coarse fill, material cut patterns), surface patterns | coarse fill + material cut; surface patterns not yet | cut hatches exact (shapely) | - |
| sections / elevations | same pipeline | yes (near plane cut, far clip) | images pending |
| drafting views, detail lines/arcs, filled regions, detail components | yes | yes | element sets 0.96-1.0 |
| text notes | RTF text, type font/size, alignment flags (hypothesis) | yes | - |
| linear dimensions | refs, line, values, type | witness/ticks/text, project units | - |
| tags / room tags | tag symbol + tagged element params | symbol graphics + labels (label visibility rules missing) | - |
| grids / levels | datum planes, per-view extents (partly), head families | lines + heads | - |
| section/elevation/callout markers, spot elevations, revision clouds, keynotes | no | no | - |
| 3D views, legends (components), schedules, rendering views | no | no (placeholder text) | - |
| linked models | no | no | - |
| SVG export | yes | sheets + views | - |
| PDF export | - | no (rsvg-convert can convert the SVG) | - |
