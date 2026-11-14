// Legibility audit driver (card t_60ef62f7). Derived from CP-TEXT-GATE's measure.mjs, kept outside
// the repo so the audit does not edit tests or product code.
//
// Usage: node legibility.mjs <page-path> <units-json> <out-dir> <viewport-width>
//
// For every declared text run on every declared object it writes:
//   base.png              the page as shipped
//   without-<n>.png       only run n's glyph paint killed (`color: transparent`; no layout change)
//   cap-<n>.png           run n's text replaced by "H" in the same computed font, so the cap
//                         height can be measured from pixels instead of inferred
// and prints one JSON object describing geometry, computed type and every file it wrote.
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const [pagePath, unitsJson, outDir, widthArg] = process.argv.slice(2)
if (!pagePath || !unitsJson || !outDir || !widthArg) {
  console.error('usage: node legibility.mjs <page-path> <units-json> <out-dir> <viewport-width>')
  process.exit(2)
}
const unitsIn = JSON.parse(unitsJson)
const width = Number(widthArg)
const height = 768
const port = 16000 + Math.floor(Math.random() * 800)
const profileDir = path.join(outDir, `chromium-${process.pid}-${Date.now()}`)
const chromium = spawn('chromium', [
  '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
  '--force-device-scale-factor=1',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profileDir}`, 'about:blank'
], { stdio: 'ignore' })
const sleep = (ms) => new Promise((done) => setTimeout(done, ms))
const stop = () => { try { chromium.kill('SIGKILL') } catch (error) { /* gone */ } }

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
  await sleep(1000)
  await evaluate('document.fonts.ready.then(() => true)')
  await evaluate('new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(() => done(true))))')

  // Geometry + computed type + canvas cap metric for every run.
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
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const sceneRoot = document.querySelector('[data-cb-home-scene]');
    const sceneCssWidth = sceneRoot ? parseFloat(getComputedStyle(sceneRoot).width) : 0;
    const sceneScale = sceneRoot && sceneCssWidth
      ? sceneRoot.getBoundingClientRect().width / sceneCssWidth : 1;
    const capOf = (cs) => {
      const style = (cs.fontStyle || 'normal') + ' ' + (cs.fontWeight || '400') + ' ' +
        (cs.fontSize || '16px') + ' ' + (cs.fontFamily || 'sans-serif');
      ctx.font = style;
      const font = ctx.font;
      const cap = ctx.measureText('H');
      const ex = ctx.measureText('x');
      const zero = ctx.measureText('0');
      const full = ctx.measureText('Hx');
      // Chromium rounds actualBoundingBox* to whole CSS px, which is too coarse to separate a
      // 10.5 px cap from an 11 px floor. Measure the same face at 200 px to recover the exact cap
      // ratio (0.25% quantisation) and scale it back.
      const bigStyle = (cs.fontStyle || 'normal') + ' ' + (cs.fontWeight || '400') + ' 200px ' +
        (cs.fontFamily || 'sans-serif');
      ctx.font = bigStyle;
      const bigCap = ctx.measureText('H');
      const bigX = ctx.measureText('x');
      return {
        requested: style,
        resolved: font,
        capAscent: cap.actualBoundingBoxAscent,
        capDescent: cap.actualBoundingBoxDescent,
        xAscent: ex.actualBoundingBoxAscent,
        zeroAscent: zero.actualBoundingBoxAscent,
        baselineAscent: full.actualBoundingBoxAscent,
        capAscent200: bigCap.actualBoundingBoxAscent,
        xAscent200: bigX.actualBoundingBoxAscent,
        capRatio: bigCap.actualBoundingBoxAscent / 200,
        xRatio: bigX.actualBoundingBoxAscent / 200
      };
    };
    for (const unit of units) {
      const object = document.querySelector(unit.object);
      if (!object) { out.push({ name: unit.name, missing: true }); continue; }
      const box = object.getBoundingClientRect();
      const style = getComputedStyle(object);
      const corners = [cornerOf(object, 0, 0), cornerOf(object, 1, 0), cornerOf(object, 1, 1), cornerOf(object, 0, 1)];
      // Rendered scale: the scene plate is one transform; the object's own offset box is authored px.
      const scaleX = object.offsetWidth ? box.width / object.offsetWidth : 1;
      const scaleY = object.offsetHeight ? box.height / object.offsetHeight : 1;
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
          const overflow = [];
          for (let walk = node; walk; walk = walk.parentElement) {
            if (walk.nodeType === 1) {
              const dx = walk.scrollWidth - walk.clientWidth;
              const dy = walk.scrollHeight - walk.clientHeight;
              const ws = getComputedStyle(walk);
              const clips = ws.overflowX !== 'visible' || ws.overflowY !== 'visible';
              if (clips && (dx > 1 || dy > 1)) {
                overflow.push({ tag: walk.tagName, dx, dy, cls: String(walk.className || '').slice(0, 40) });
              }
            }
            if (walk === object) break;
          }
          runs.push({
            selector: sel || '(self)',
            index,
            text: (node.textContent || '').trim().replace(/[ \\t\\n\\r]+/g, ' ').slice(0, 80),
            textAlign: cs.textAlign,
            color: cs.color,
            opacity: cs.opacity,
            visibility: cs.visibility,
            fontFamily: cs.fontFamily,
            fontSize: cs.fontSize,
            fontWeight: cs.fontWeight,
            fontStyle: cs.fontStyle,
            letterSpacing: cs.letterSpacing,
            lineHeight: cs.lineHeight,
            cap: capOf(cs),
            rects,
            overflow
          });
          // Kept in the page for the cap probe: the probe paints an absolutely positioned "H"
          // with the run's computed font while the run's own glyphs are transparent, so nothing
          // reflows and the diff against the glyph-less capture is exactly one capital.
          window.__cbProbeStyle = window.__cbProbeStyle || {};
          window.__cbProbeObject = window.__cbProbeObject || [];
          window.__cbProbeObject[index] = object;
          window.__cbProbeStyle[index] = {
            color: cs.color,
            fontSize: cs.fontSize,
            fontFamily: cs.fontFamily,
            fontWeight: cs.fontWeight,
            fontStyle: cs.fontStyle,
            lineHeight: cs.lineHeight,
            letterSpacing: cs.letterSpacing
          };
        }
      }
      out.push({
        name: unit.name,
        missing: false,
        centre: Boolean(unit.centre),
        object: {
          width: box.width,
          height: box.height,
          offsetWidth: object.offsetWidth,
          offsetHeight: object.offsetHeight,
          scaleX,
          scaleY,
          quad: corners,
          overflowX: style.overflowX,
          overflowY: style.overflowY,
          backgroundImage: style.backgroundImage,
          backgroundColor: style.backgroundColor
        },
        runs
      });
    }
    return { units: out, devicePixelRatio: window.devicePixelRatio, sceneScale, sceneCssWidth };
  })()`
  const info = await evaluate(setup)

  const shot = async (name) => {
    const answer = await send('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: false })
    const file = path.join(outDir, `${name}.png`)
    fs.writeFileSync(file, Buffer.from(answer.data, 'base64'))
    return file
  }
  const settle = () => evaluate('new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(() => done(true))))')

  const base = await shot('base')
  await settle()
  const baseAgain = await shot('base-again')

  const shots = []
  for (const unit of info.units) {
    if (unit.missing) continue
    for (const run of unit.runs) {
      await evaluate(`(() => { window.__cbProbeRuns[${run.index}].style.color = 'transparent'; return true })()`)
      await settle()
      const without = await shot(`without-${run.index}`)
      // Cap probe: paint one capital H in the run's computed font, absolutely positioned over the
      // run's text rect, while the run's own glyphs stay transparent. An absolutely positioned
      // child cannot reflow the scene, which is what a textContent swap did (it narrowed the hero
      // panel and moved the card body, inflating the measured "cap" to a line box).
      await evaluate(`(() => {
        const n = window.__cbProbeRuns[${run.index}];
        const s = window.__cbProbeStyle[${run.index}];
        // The run's own text rect (Range.getClientRects), not the element's box: a centred or
        // right-aligned run paints away from its box origin.
        const target = ${JSON.stringify(run.rects[0])};
        const r = { left: target[0], top: target[1] };
        const span = document.createElement('span');
        span.setAttribute('data-cb-cap-probe', String(${run.index}));
        span.textContent = 'H';
        span.style.cssText = 'position:absolute;left:0;top:0;margin:0;padding:0;border:0;' +
          'font-family:' + s.fontFamily + ';font-size:' + s.fontSize + ';font-weight:' + s.fontWeight +
          ';font-style:' + s.fontStyle + ';line-height:' + s.lineHeight + ';letter-spacing:' + s.letterSpacing +
          ';color:' + s.color + ';white-space:nowrap;text-align:left;pointer-events:none;';
        n.appendChild(span);
        // Adding a child must not move the run's own text; if it does (a grid or button parent
        // could re-lay it out), measure the live text position and use that instead.
        const kids = [...n.childNodes].filter((node) => node !== span);
        let live = null;
        if (kids.length) {
          const range = document.createRange();
          range.setStartBefore(kids[0]);
          range.setEndAfter(kids[kids.length - 1]);
          const q = range.getClientRects()[0];
          if (q) live = { left: q.left, top: q.top };
        }
        const targetLeft = live ? live.left : r.left;
        const targetTop = live ? live.top : r.top;
        // A scene element can be scaled (the 1200 px fit) and rotated (cards, tag), so a viewport
        // delta is not a local delta. Measure the local->viewport linear map with three probes and
        // solve for the local offset that lands the H on the run's text origin.
        const at = (l, t) => {
          span.style.left = l + 'px';
          span.style.top = t + 'px';
          const q = span.getBoundingClientRect();
          return [q.left, q.top];
        };
        const p0 = at(0, 0);
        const p1 = at(100, 0);
        const p2 = at(0, 100);
        const ax = (p1[0] - p0[0]) / 100, ay = (p1[1] - p0[1]) / 100;
        const bx = (p2[0] - p0[0]) / 100, by = (p2[1] - p0[1]) / 100;
        const det = ax * by - bx * ay;
        const dx = targetLeft - p0[0], dy = targetTop - p0[1];
        const localLeft = (dx * by - bx * dy) / det;
        const localTop = (ax * dy - dx * ay) / det;
        span.style.left = localLeft + 'px';
        span.style.top = localTop + 'px';
        const landed = span.getBoundingClientRect();
        window.__cbProbeResidual = window.__cbProbeResidual || {};
        window.__cbProbeResidual[${run.index}] = [landed.left - targetLeft, landed.top - targetTop];
        return true;
      })()`)
      await settle()
      const landedBefore = await evaluate(`(() => {
        const span = document.querySelector('[data-cb-cap-probe="${run.index}"]');
        const q = span.getBoundingClientRect();
        const target = ${JSON.stringify(run.rects[0])};
        return [q.left - target[0], q.top - target[1]];
      })()`)
      const cap = await shot(`cap-${run.index}`)
      await evaluate(`(() => {
        window.__cbProbeResidual2 = window.__cbProbeResidual2 || {};
        window.__cbProbeResidual2[${run.index}] = ${JSON.stringify(landedBefore)};
        return true;
      })()`)
      await evaluate(`(() => {
        const span = document.querySelector('[data-cb-cap-probe="${run.index}"]');
        if (span) span.remove();
        window.__cbProbeRuns[${run.index}].style.color = '';
        return true;
      })()`)
      await settle()
      shots.push({ unit: unit.name, selector: run.selector, index: run.index, without, cap })

      // Floor probe: raise this run to the font size that would give it an 11 px cap (same face,
      // same line-height ratio) and observe whether the object absorbs it — a card that clips or a
      // shelf that has to widen is a measured answer, not an estimate.
      const needed = run.cap && run.cap.capRatio ? 11 / run.cap.capRatio : null
      if (needed && parseFloat(run.fontSize) < needed - 0.01) {
        const raised = await evaluate(`(() => {
          const n = window.__cbProbeRuns[${run.index}];
          const s = window.__cbProbeStyle[${run.index}];
          const size = parseFloat(s.fontSize);
          const needed = ${needed};
          const lh = s.lineHeight && s.lineHeight.endsWith('px') ? parseFloat(s.lineHeight) : size * 1.2;
          const object = window.__cbProbeObject[${run.index}];
          const before = object.getBoundingClientRect();
          const elBefore = n.getBoundingClientRect();
          n.style.fontSize = needed + 'px';
          n.style.lineHeight = (lh * needed / size) + 'px';
          const after = object.getBoundingClientRect();
          const elAfter = n.getBoundingClientRect();
          const rects = [];
          const range = document.createRange();
          const kids = [...n.childNodes].filter((node) => node.nodeType !== 1);
          if (kids.length) {
            range.setStartBefore(kids[0]);
            range.setEndAfter(kids[kids.length - 1]);
            for (const r of range.getClientRects()) rects.push([r.left, r.top, r.width, r.height]);
          }
          if (!rects.length) { const r = n.getBoundingClientRect(); rects.push([r.left, r.top, r.width, r.height]); }
          const clipping = [];
          for (let walk = n; walk; walk = walk.parentElement) {
            if (walk.nodeType === 1) {
              const ws = getComputedStyle(walk);
              const clips = ws.overflowX !== 'visible' || ws.overflowY !== 'visible';
              const dx = walk.scrollWidth - walk.clientWidth;
              const dy = walk.scrollHeight - walk.clientHeight;
              if (clips && (dx > 1 || dy > 1)) clipping.push({ tag: walk.tagName, dx, dy, cls: String(walk.className || '').slice(0, 40) });
            }
            if (walk === object) break;
          }
          const corner = (fx, fy) => {
            const marker = document.createElement('span');
            marker.style.cssText = 'position:absolute;width:0;height:0;margin:0;padding:0;border:0;' +
              'left:' + (fx * 100) + '%;top:' + (fy * 100) + '%;visibility:hidden;pointer-events:none;';
            object.appendChild(marker);
            const r = marker.getBoundingClientRect();
            marker.remove();
            return [r.left, r.top];
          };
          return {
            applied: true,
            needed_font_px: needed,
            line_height_px: lh * needed / size,
            object: { width: before.width, height: before.height, after_width: after.width, after_height: after.height },
            element: { width: elBefore.width, height: elBefore.height, after_width: elAfter.width, after_height: elAfter.height },
            object_quad: [corner(0, 0), corner(1, 0), corner(1, 1), corner(0, 1)],
            rects,
            clipping,
            scroll: { dx: n.scrollWidth - n.clientWidth, dy: n.scrollHeight - n.clientHeight }
          };
        })()`).catch(async (error) => ({ applied: false, error: String(error) }))
        await settle()
        raised.file = await shot(`raised-${run.index}`)
        await evaluate(`(() => {
          const n = window.__cbProbeRuns[${run.index}];
          n.style.fontSize = '';
          n.style.lineHeight = '';
          return true;
        })()`)
        await settle()
        shots[shots.length - 1].raised = raised
      } else {
        shots[shots.length - 1].raised = { applied: false, reason: 'already at or above the 11 px cap floor' }
      }
    }
  }
  // Restored state must equal the original base capture byte for byte; if it does not, the probes
  // mutated the page and every later measurement is suspect.
  const restored = await shot('restored')
  const residuals = await evaluate('({ placed: window.__cbProbeResidual || {}, before_shot: window.__cbProbeResidual2 || {} })')

  socket.close()
  process.stdout.write(JSON.stringify({ width, height, info, base, baseAgain, restored, residuals, shots }))
} finally {
  stop()
}
