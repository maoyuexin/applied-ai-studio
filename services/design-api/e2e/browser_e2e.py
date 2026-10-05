"""Browser end-to-end test of Design Studio through the real UI (Chrome DevTools Protocol).

Clicks through the article, voice, image and video pipelines as a user would, against an offline fake API,
and checks each run completes with an output. Start the two servers first:

    DESIGN_PROVIDER_MODE=fake DESIGN_DATA_DIR=/tmp/ds-e2e DESIGN_VIDEO_POLL_SECONDS=0.5 DESIGN_CAP_VIDEO_TAKES=500 \
      .venv/bin/python -m uvicorn app.main:app --app-dir services/design-api --port 4431
    (cd apps/web && WEB_PORT=5180 services__design__http__0=http://127.0.0.1:4431 npx vite --port 5180)
    .venv/bin/python services/design-api/e2e/browser_e2e.py [article voice image video]

Needs a Chromium-based browser (E2E_BROWSER) and the `websockets` package (installed with uvicorn[standard]).
"""
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

EDGE = os.environ.get("E2E_BROWSER", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
BASE = "http://127.0.0.1:5180"
API = "http://127.0.0.1:4431/api/design"
OUT = os.environ.get("E2E_SHOTS", tempfile.gettempdir())
PORT = 9334

HELPERS = r"""
window.__t = {
  buttons: () => [...document.querySelectorAll('button, a.ds-btn')],
  click(text, nth = 0) {
    const matches = this.buttons().filter(b => b.textContent.trim().includes(text) && !b.disabled);
    if (!matches[nth]) return 'missing:' + text;
    matches[nth].click();
    return 'clicked:' + text;
  },
  has(text) { return document.body.innerText.toLowerCase().includes(text.toLowerCase()); },
  enabled(text) { return this.buttons().some(b => b.textContent.trim().includes(text) && !b.disabled); },
  type(selector, value) {
    const el = document.querySelector(selector);
    if (!el) return 'missing:' + selector;
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    return 'typed';
  },
  runId() { const m = location.pathname.match(/runs\/([^/?]+)/); return m ? m[1] : null; },
};
'ok'
"""


class Tab:
    def __init__(self, ws):
        self.ws, self.n = ws, 0

    async def call(self, method, **params):
        self.n += 1
        my = self.n
        await self.ws.send(json.dumps({"id": my, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == my:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    async def js(self, expr):
        result = await self.call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"].get("text"))
        return result.get("result", {}).get("value")

    async def go(self, path):
        await self.call("Page.navigate", url=BASE + path)
        await self.until("document.querySelector('.ds') && !document.querySelector('.route-loading')", 30, f"load {path}")
        await self.js(HELPERS)

    async def until(self, expr, timeout, label):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if await self.js(f"!!({expr})"):
                    return
            except RuntimeError:
                pass
            await asyncio.sleep(0.3)
        await self.shot(f"e2e-fail-{label.replace(' ', '_')[:30]}")
        raise AssertionError(f"timed out: {label}")

    async def click(self, text, nth=0):
        await self.js(HELPERS)
        result = await self.js(f"__t.click({json.dumps(text)}, {nth})")
        if not str(result).startswith("clicked"):
            await self.shot(f"e2e-fail-click-{text[:20]}")
            raise AssertionError(result)
        await asyncio.sleep(0.4)

    async def gate(self, timeout=60):
        await self.until("(window.__t || {}).enabled && __t.enabled('Approve & continue')", timeout, "gate ready")

    async def shot(self, name):
        data = await self.call("Page.captureScreenshot", format="png")
        with open(f"{OUT}/{name}.png", "wb") as handle:
            handle.write(base64.b64decode(data["data"]))


def run_detail(run_id):
    return json.load(urllib.request.urlopen(f"{API}/runs/{run_id}"))


async def finish(tab, label):
    run_id = await tab.js("__t.runId()")
    deadline = time.time() + 90
    while time.time() < deadline:
        detail = run_detail(run_id)
        if detail["run"]["status"] in ("completed", "failed"):
            break
        await asyncio.sleep(0.5)
    assert detail["run"]["status"] == "completed", (label, detail["run"]["status"], detail["run"]["error"])
    final = next(a for a in detail["artifacts"] if a["kind"] == "final" and a["status"] == "ready")
    await tab.until("document.querySelector('.ds-card.hl')", 20, f"{label} final card")
    await tab.shot(f"e2e-{label}")
    print(f"PASS {label}: {run_id} · {detail['run']['counters'].get('outputs')} · final {final['media_type']}")


async def article(tab):
    await tab.go("/design-studio/new/article")
    await tab.click("Load example")
    await tab.until("__t.enabled('Start run')", 10, "article start enabled")
    await tab.click("Start run")
    await tab.gate()
    await tab.click("Approve & continue")
    await tab.until("__t.has('Fact check of v1')", 30, "v1 checked")
    await tab.js(HELPERS)
    await tab.js("__t.type('textarea[aria-label=\"Revision note\"]', 'Say December 2026 explicitly.')")
    await tab.click("Make v2")
    await tab.until("__t.has('Fact check of v2') && __t.has('Show changes from v1')", 30, "v2 checked")
    await tab.gate()
    await tab.click("Approve & continue")
    await finish(tab, "article")


async def voice(tab):
    await tab.go("/design-studio/new/voice")
    await tab.until("document.querySelectorAll('select[aria-label$=\"voice\"]').length >= 2", 15, "speakers prefilled")
    await tab.click("Load example")
    await tab.click("Start run")
    await tab.gate()
    await tab.click("Approve & continue")
    await tab.until("__t.has('matches the script')", 30, "lines recorded")
    await tab.click("Again")
    await tab.until("__t.has('line 1.2')", 30, "line re-recorded")
    await tab.gate()
    await tab.click("Approve & continue")
    await finish(tab, "voice")


async def image(tab):
    await tab.go("/design-studio/new/image")
    await tab.click("Load example")
    await tab.click("Start run")
    await tab.gate()
    await tab.click("Approve & continue")
    await tab.until("document.querySelectorAll('#step-candidates .ds-take').length >= 2 && [...document.querySelectorAll('#step-candidates .ds-take')].every(t => t.querySelector('.ds-acts button'))", 30, "candidates ready")
    await tab.click("Keep")
    await tab.gate()
    await tab.click("Approve & continue")
    await tab.until("document.querySelector('#revise-note')", 30, "iterate open")
    await tab.js("__t.type('#revise-note', 'Lower the camera to road level.')")
    await tab.click("Write the prompt")
    await tab.until("document.querySelector('#draft-prompt')", 30, "draft prompt shown")
    await tab.click("Make v1 from c1")
    await tab.until("__t.has('v1 · kept') || __t.has('v1')", 30, "v1 created")
    await tab.until("[...document.querySelectorAll('.ds-node')].some(n => n.textContent.includes('v1') && n.querySelector('img'))", 30, "v1 ready")
    await tab.gate()
    await tab.click("Approve & continue")
    await finish(tab, "image")


async def video(tab):
    await tab.go("/design-studio/new/video")
    await tab.click("Load example")
    await tab.js("document.querySelectorAll('.ds-grid4 select')[0].value")
    await tab.click("Start run")
    await tab.gate()
    await tab.click("Approve & continue")
    await tab.until("document.querySelectorAll('#step-takes .ds-take').length >= 4 && [...document.querySelectorAll('#step-takes .ds-take')].every(t => t.querySelector('.ds-acts button'))", 90, "takes ready")
    shots = await tab.js("document.querySelectorAll('#step-takes .ds-shot').length")
    for index in range(shots):
        await tab.js(f"document.querySelectorAll('#step-takes .ds-shot')[{index}].querySelector('.ds-acts button').click()")
        await asyncio.sleep(0.6)
    await tab.gate()
    await tab.click("Approve & continue")
    await finish(tab, "video")


async def main():
    profile = tempfile.mkdtemp()
    proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--remote-debugging-port={PORT}",
                             f"--user-data-dir={profile}", "--window-size=1440,1000", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    failures = 0
    try:
        for _ in range(40):
            try:
                page = next(t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")) if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.25)
        async with websockets.connect(page["webSocketDebuggerUrl"], max_size=64 * 1024 * 1024) as ws:
            tab = Tab(ws)
            await tab.call("Page.enable")
            await tab.call("Emulation.setDeviceMetricsOverride", width=1440, height=1000, deviceScaleFactor=1, mobile=False)
            flows = {f.__name__: f for f in (article, voice, image, video)}
            for flow in [flows[n] for n in (sys.argv[1:] or flows)]:
                try:
                    await flow(tab)
                except Exception as error:  # noqa: BLE001
                    failures += 1
                    print(f"FAIL {flow.__name__}: {error}")
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        shutil.rmtree(profile, ignore_errors=True)
    sys.exit(1 if failures else 0)


asyncio.run(main())
