// CP-TEXT-GATE browser driver: photograph a page once with each lettering run painted and once
// with only that run's glyphs killed, so the ink mask is the pixel difference between the two.
//
// Usage: node measure.mjs <page-path> <units-json> <out-dir>
//   units-json: [{"name","object","centre","runs":[css-selector-or-""]}]
//   "" means the object element's own text (the object is its own lettering surface).
//
// Writes <out-dir>/base.png and <out-dir>/without-<n>.png, prints one JSON object on stdout.
//
// Notes that matter for the measurement:
//   * Glyphs are killed with `color: transparent`, not `visibility: hidden`: the object's own
//     background image and every box stay exactly where they were, so only paint changes.
//   * Chromium does not implement Element.getBoxQuads. Four zero-size absolutely positioned
//     probes at 0/100% of the object's padding box give the object's corner points after every
//     ancestor/self transform; the caller turns those into a homography (a rotated board is
//     measured in its own frame, so its axis-aligned bounding box cannot hide spill).
//   * A style mutation can re-raster a rotated layer's antialiased edge by a subpixel, which is
//     not lettering. Each run's text rects (Range.getClientRects) are reported so the caller can
//     restrict the ink mask to the area the run actually paints.
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const [pagePath, unitsJson, outDir] = process.argv.slice(2)
if (!pagePath || !unitsJson || !outDir) {
  console.error('usage: node measure.mjs <page-path> <units-json> <out-dir>')
  process.exit(2)
}
const unitsIn = JSON.parse(unitsJson)
const width = 1344
const height = 768
const port = 16000 + Math.floor(Math.random() * 800)
const profileDir = path.join(outDir, `chromium-${process.pid}-${Date.now()}`)
const chromium = spawn('chromium', [
  '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
  '--force-device-scale-factor=1',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profileDir}`, 'about:blank'
], { stdio: 'ignore' })
const sleep = (ms) => new Promise((done) => setTimeout(done, ms))

const stop = () => {
  try { chromium.kill('SIGKILL') } catch (error) { /* already gone */ }
}

try {
  let targets = null
  for (let attempt = 0; attempt < 120; attempt += 1) {
    try {
      targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
      if (targets.length) break
    } catch (error) { targets = null }
    await sleep(250)
  }
  if (!targets || !targets.length) throw new Error('chromium CDP did not open')
  const page = targets.find((entry) => entry.type === 'page')
  if (!page) throw new Error('chromium exposed no page target')
  const socket = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((done, fail) => {
    socket.addEventListener('open', done, { once: true })
    socket.addEventListener('error', fail, { once: true })
  })
  let nextId = 1
  const pending = new Map()
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    if (message.id && pending.has(message.id)) {
      const entry = pending.get(message.id)
      pending.delete(message.id)
      if (message.error) entry.fail(new Error(JSON.stringify(message.error)))
      else entry.done(message.result)
    }
  })
  const send = (method, params = {}) => new Promise((done, fail) => {
    const id = nextId++
    pending.set(id, { done, fail })
    socket.send(JSON.stringify({ id, method, params }))
  })
  const evaluate = async (expression) => {
    const answer = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (answer.exceptionDetails) throw new Error(JSON.stringify(answer.exceptionDetails))
    return answer.result.value
  }

  await send('Page.enable')
  await send('Runtime.enable')
  await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false })
  await send('Page.navigate', { url: `file://${pagePath}` })
  await sleep(900)
  await evaluate('document.fonts.ready.then(() => true)')
  await evaluate('new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(() => done(true))))')

  const setup = `(() => {
    const units = ${JSON.stringify(unitsIn)};
    const out = [];
    window.__cbProbeRuns = [];
    const cornerOf = (object, fx, fy) => {
      const marker = document.createElement('span');
      marker.setAttribute('data-cb-probe-corner', '');
      marker.style.cssText = 'position:absolute;width:0;height:0;margin:0;padding:0;border:0;' +
        'left:' + (fx * 100) + '%;top:' + (fy * 100) + '%;visibility:hidden;pointer-events:none;';
      object.appendChild(marker);
      const rect = marker.getBoundingClientRect();
      marker.remove();
      return [rect.left, rect.top];
    };
    for (const unit of units) {
      const object = document.querySelector(unit.object);
      if (!object) { out.push({ name: unit.name, missing: true }); continue; }
      const box = object.getBoundingClientRect();
      const style = getComputedStyle(object);
      const corners = [cornerOf(object, 0, 0), cornerOf(object, 1, 0), cornerOf(object, 1, 1), cornerOf(object, 0, 1)];
      const runs = [];
      for (const sel of unit.runs) {
        const nodes = sel ? [...object.querySelectorAll(sel)] : [object];
        for (const node of nodes) {
          const index = window.__cbProbeRuns.push(node) - 1;
          const cs = getComputedStyle(node);
          let rects = [];
          try {
            const range = document.createRange();
            range.selectNodeContents(node);
            rects = [...range.getClientRects()].map((r) => [r.left, r.top, r.width, r.height]);
          } catch (error) { rects = []; }
          if (!rects.length) {
            const r = node.getBoundingClientRect();
            rects = [[r.left, r.top, r.width, r.height]];
          }
          // Clipped overflow is invisible to a pixel mask (the object's overflow:hidden removes
          // the glyphs), so walk the run and its ancestors up to the object and report any box
          // whose text is wider than its client area. Width only: a block's scrollHeight routinely
          // exceeds clientHeight by a few px of descender/leading, which is not clipping.
          const overflow = [];
          for (let walk = node; walk; walk = walk.parentElement) {
            if (walk.nodeType === 1) {
              const dx = walk.scrollWidth - walk.clientWidth;
              if (dx > 1) overflow.push({ tag: walk.tagName, dx });
            }
            if (walk === object) break;
          }
          runs.push({
            selector: sel || '(self)',
            index,
            text: (node.textContent || '').trim().replace(/[ \\t\\n\\r]+/g, ' ').slice(0, 80),
            textAlign: cs.textAlign,
            color: cs.color,
            visibility: cs.visibility,
            rects,
            overflow
          });
        }
      }
      out.push({
        name: unit.name,
        missing: false,
        centre: Boolean(unit.centre),
        object: {
          width: box.width,
          height: box.height,
          quad: corners,
          overflowX: style.overflowX,
          overflowY: style.overflowY
        },
        runs
      });
    }
    return { units: out };
  })()`
  const info = await evaluate(setup)

  const shot = async (name) => {
    const answer = await send('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: false })
    const file = path.join(outDir, `${name}.png`)
    fs.writeFileSync(file, Buffer.from(answer.data, 'base64'))
    return file
  }

  const base = await shot('base')
  const shots = []
  for (const unit of info.units) {
    if (unit.missing) continue
    for (const run of unit.runs) {
      await evaluate(`(() => { window.__cbProbeRuns[${run.index}].style.color = 'transparent'; return true })()`)
      await evaluate('new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(() => done(true))))')
      const file = await shot(`without-${run.index}`)
      await evaluate(`(() => { window.__cbProbeRuns[${run.index}].style.color = ''; return true })()`)
      await evaluate('new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(() => done(true))))')
      shots.push({ unit: unit.name, selector: run.selector, index: run.index, file })
    }
  }

  socket.close()
  process.stdout.write(JSON.stringify({ width, height, info, base, shots }))
} finally {
  stop()
}
