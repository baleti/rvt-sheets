# rvt-sheets

Revit sheets and views drawn from the .rvt file alone (no Revit): title blocks, viewports, plans, sections/elevations,
drafting views, legends, orthographic 3D, annotations (text, dimensions, tags, grids/levels), view filters/overrides/templates,
phases, line weights/patterns, fill patterns. Uses the reader in ~/rvt-research (read-only). Fidelity numbers: PROGRESS.md; coverage: COVERAGE.md.

## Demo (any .rvt / .rte, Revit 2020-2026)
Standalone (fallback; prints the URL, opens nothing):

    ~/src/rvt-sheets/rvt-sheets serve ~/rvt-research/corpus/2020/20_Residential_Sample_Project.rvt --port 8810
    # then open http://127.0.0.1:8810/sheets/#local

Other examples:

    ~/src/rvt-sheets/rvt-sheets serve ~/rvt-research/corpus/2020/18_rst_basic_sample_project.rvt --port 8811
    ~/src/rvt-sheets/rvt-sheets serve ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt --port 8812

Caching: every rendered sheet/view is stored in ~/.cache/rvt-sheets/<key>/ (key = file content hash + rvtsheets drawing-code version;
the reader version is recorded but not in the key, so the cache survives reader edits). The first open of a sheet renders it (seconds;
e.g. Residential A-2 10.7 s), every later open - also after restarting the server - is served from disk (A-2: 0.002 s) and the model is
not even decoded when the requested drawings are cached.

Demo prep (pre-render every sheet and view; the viewer's `bin/rvt-view --prepare FILE` calls this):

    ~/src/rvt-sheets/rvt-sheets warm FILE.rvt [FILE...] [--mem 3G] [--workers N] [--refresh] [--host1]

Parallel workers (<= 4, as many as fit in --mem; the whole job runs in a systemd scope with that memory cap, nice 19), one progress line per
drawing, final line `warmed N sheets, M views`. --host1 runs it on host1 via h1run and pulls the cache back (big files). --refresh redraws
(after reader changes). Results: ~/.cache/rvt-sheets/READY.json (per file: counts, failures, demo command). Re-run warm after changing
rvtsheets drawing code (the key changes; warm deletes the old cache directory of the same file). `tools/smoke.sh FILE` = headless demo check,
`tools/timing.py FILE...` = first-render vs cached table.

View primitives as JSON (viewer control panel, CONTROL-API.md): `GET /sheets/api/{mid}/view/{id}.json?scale=&detail=&template=0&filters=0&cut=&phase=&phaseFilter=` (cached next to the SVGs).

QA against Revit's own exports: `~/src/rvt-qa/qa-view FILE VIEWID --svg OURS.svg`, `tools/compare_dxf.py FILE VIEWID REVIT.dxf --register`, `tools/check_elements.py FILE [VIEWID]`; per-feature status: FEATURE-AUDIT.md.

PDF: the page has 'PDF: this sheet / all sheets' links (GET /sheets/api/{mid}/sheet/{id}.pdf, /sheets/api/{mid}/sheets.pdf).

Page keys: left/right (or PageUp/PageDown/space) previous/next drawing, f fit, i sheet index with thumbnails, p present mode (full screen,
no side bar), Esc. Green dots = cached; the 'cached' badge shows when a drawing came from the cache. The page prefetches the neighbouring
drawings in the background (the server draws page requests before prefetches).

The page shows a progress card (stage + percentage) while the reader parses the file (seconds for small files, a few minutes for the
first open of a 50 MB model; later opens use the reader's cache), then the sheet list (or the view list for files without sheets) and the
first sheet. Click any sheet or view; mouse wheel zooms, drag pans. Drawn SVGs are cached in ~/.cache/rvt-sheets/.

Inside the viewer (session 187 mounts the sub-app, see HOOKS.md): `/sheets/#<model id>` on the viewer's own port.

Batch / files:

    .venv/bin/python tools/sheet_full.py FILE.rvt OUTDIR [SHEET_NUMBER...]   # sheets -> OUTDIR/<number>.svg
    .venv/bin/python tools/view_svg.py FILE.rvt VIEW_ID OUT.svg               # one view
    ./rvt-sheets pdf FILE.rvt OUT.pdf [SHEET_NUMBER...]                     # sheets -> multi-page vector PDF (uses the cache)

## Setup
    python3 -m venv --system-site-packages .venv && .venv/bin/pip install shapely numba ezdxf olefile mapbox_earcut

## Layout
rvtsheets/reader.py (reader adapter) / decode.py (views, sheets, styles, filters, overrides) / visibility.py (element set per view) /
scene.py (saved graphics walked per view) / viewdraw.py (cut + projection + HLR) / hlr.py / patterns.py / style.py / filters.py / datums.py /
annot.py (dimensions, tags) / units.py / sheet.py (title blocks, viewport titles) / compose.py (sheet SVG) / server.py (aiohttp sub-app) / web/index.html.
Validation tools: tools/check_settings.py, check_elements.py, compare_img.py, compare_dxf.py, fid_images.py, robust.py. Oracle jobs: oracle/.
