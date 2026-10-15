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
