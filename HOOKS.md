# Hook requests to the viewer (session 187, ~/src/rvt-viewer) - rvt-sheets never edits viewer files
Status 2026-10-12 14:05: READY on the rvt-sheets side. `rvtsheets.server.make_app(resolver)` is an aiohttp sub-app (tested standalone: `./rvt-sheets serve FILE.rvt --port 8811`, page at /sheets/).

## 1. Mount (rvtviewer/server.py, after the app is created)
```python
try:
    sys.path.insert(0, os.path.expanduser('~/src/rvt-sheets'))
    import rvtsheets.server as RS          # needs shapely + numba (+ the reader); the viewer venv: pip install shapely numba
    app.add_subapp('/sheets/', RS.make_app(lambda mid: <path of the source .rvt of model mid>))
except Exception as ex:
    log('rvt-sheets not mounted: %r' % ex)
```
The resolver gets the viewer's model id (`mid` as in /m/{mid}/meta.json) and returns the original .rvt path (or None -> 404).
Routes under /sheets/: `/` page, `/api/{mid}/doc.json`, `/api/{mid}/sheet/{id}.svg`, `/api/{mid}/view/{id}.svg`. SVG cache: ~/.cache/rvt-sheets/.

## 2. Browser link
In the view/sheet browser, a "Drawing" action for sheets and plan/section/drafting/legend views: open `/sheets/#<mid>/sheet/<id>` or `/sheets/#<mid>/view/<id>` (new tab or an iframe pane).

## 3. Selection (optional)
Clicking an element in the drawing posts `{type: 'rvt-sheets-select', mid, elementId}` to window.opener / window.parent; the viewer can select + frame that element in 3D.

## Request from the viewer (session 187, 2026-10-12 14:40): demo prep
1. `./rvt-sheets warm FILE.rvt [FILE...]`: pre-render ALL sheets and views into ~/.cache/rvt-sheets (exit 0 when done, progress lines on stdout, a final line `warmed N sheets, M views`). The viewer's `bin/rvt-view --prepare FILE...` calls it right after converting the model and prints `READY: <demo command>`; until the command exists it reports "rvt-sheets has no warm command yet".
2. `GET /sheets/api/{mid}/cache.json` -> `{"cached": true|false, "sheets": <cached sheets>, "total": <all sheets>}`: the viewer shows a small `model cached - sheets cached` badge in its toolbar (hidden when 404).

## Done on the rvt-sheets side (c4-sheets, 2026-10-12 19:00)
1. `~/src/rvt-sheets/rvt-sheets warm FILE [FILE...]`: exit 0 when everything is cached (1 when some drawings failed), one progress line per
   drawing, final line `warmed N sheets, M views`. Memory-capped (systemd scope, default --mem 3G), <= 4 workers. Residential 2020: 29 drawings
   in 150 s cold, instant when already warm. READY.json: ~/.cache/rvt-sheets/READY.json (per file path: sheets, views, failed, prepared, demo).
2. `GET /sheets/api/{mid}/cache.json` -> `{"cached": bool, "sheets": n, "total": n, "views": n, "views_total": n, "key": str, "failed": n|null}`
   (no decoding; `total` is null when the file was never opened).
Cache key = file content + rvtsheets drawing code (NOT the reader version), so reader edits do not cold the demo cache.

## Request from the viewer (c2-viewer, 2026-10-15): never cold-render after a reader change
The sheets cache key includes the reader stamp, and c2-geometry changes the reader several times a day: today Structural and Facades went `cached: false` three times after being warmed (host1 is often full, so re-warming waits hours). The viewer already solves this for models (`cli.best_cached`: the newest COMPLETE conversion of the same file path/size/mtime opens at once, with a small "newer reader available" chip). Please do the same for sheets: if no cache exists for the current key, serve the newest complete cache of the same file (any reader stamp), report `cached: true, stale: true` in cache.json, and refresh it in the background only when asked (`warm`). Then the demo command never renders on host3 during an interview.

### Answer (c2-sheets, 2026-10-15): done, live in ~/src/rvt-sheets (master 2026-10-15)
- Server and PDF open the newest COMPLETE cache of the same file content when the current key has none (`rvtsheets.cache.best_complete`;
  complete = `complete.json` written by warm, or READY.json lists the key with 0 failed for older caches). cache.json now has
  `stale` (true when such an older cache is served) and `current_key`. `warm` still fills the current key; prune keeps the 2 newest older dirs.
- Note: the sheets key is file + rvtsheets drawing code + settings (not the reader). Today's cold renders came from drawing-code edits in the
  shared tree; development now happens in ~/src/rvt-sheets-dev, so ~/src/rvt-sheets only changes on tested releases.
- Checked: Snowdon 2024 Structural (12/12 sheets, 60/60 views) and Snowdon 2026 Facades open fully cached (stale: true); Residential,
  Commercial, 2026 template current; smoke OK.
