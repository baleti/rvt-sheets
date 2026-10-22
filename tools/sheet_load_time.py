"""sheet_load_time.py FILE.rvt SHEETID... : headless Chromium (CDP helper of rvt-viewer, caps 3 cores / 3 GB) time from navigation to the sheet SVG painted in the
standalone /sheets/ page, per sheet (cache must be warm: the timing is the display cost, not the render). Prints one line per sheet."""
import asyncio, sys, os, subprocess, time, json
sys.path.insert(0, os.path.expanduser('~/src/rvt-viewer/tools')); import cdp
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

async def main(f, sheets, port=29601):
    srv = subprocess.Popen([os.path.join(ROOT, 'rvt-sheets'), 'serve', f, '--port', str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cdp.wait_http('http://127.0.0.1:%d/sheets/' % port, 60); b = cdp.Browser(size=(1280, 720)); await b.start()
    try:
        await b.goto('http://127.0.0.1:%d/sheets/%s#local' % (port, os.environ.get('Q', '')))
        for _ in range(200):
            if await b.ev("typeof items !== 'undefined' && items.length > 0"): break
            await asyncio.sleep(0.25)
        for s in sheets:
            t0 = time.time()
            await b.ev("(async()=>{await show(items.findIndex(x => x.k=='sheet' && x.i==%s)); window.__done=1})(); 0" % s)
            for _ in range(1200):
                if await b.ev("window.__done===1"): break
                await asyncio.sleep(0.1)
            await b.ev("window.__done=0; 0")
            await asyncio.sleep(0.2); n = await b.ev("document.querySelectorAll('#paper svg *').length"); txt = await b.ev("document.querySelector('#status').innerText")
            print('sheet', s, 'svg nodes', n, '%.1f s' % (time.time() - t0), '|', txt, flush=True)
    finally: await b.close(); srv.terminate()

if __name__ == '__main__': asyncio.run(main(os.path.abspath(sys.argv[1]), sys.argv[2:]))
