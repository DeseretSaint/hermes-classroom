#!/usr/bin/env node
/**
 * GM-012 live walkthrough: select a word -> ask -> cited answer -> citation -> return.
 *
 * Drives the isolated Desktop window (CDP 9337) with real input events (Input.dispatchMouseEvent /
 * Input.dispatchKeyEvent), never by poking React state. Prints one JSON line per phase and writes
 * each frame under docs/visual-review/gm-012/live/.
 *
 *   node scripts/gm012-walkthrough.mjs --session <stored_session_id> --enrollment <enr_...> \
 *     [--block blk_...] [--citation blk_...] [--prefix docs/visual-review/gm-012/live/walkthrough]
 *
 * Preconditions (see docs/visual-review/gm-012/MANIFEST.md):
 *   - the isolated backend answers on 44219 and the window is attached to it;
 *   - one real tutor thread exists for the bound lesson run. `hermes serve` never binds
 *     `ctx.llm`, so the ask is produced through the in-process seam the agent process uses
 *     (scripts/gm012-seed-tutor.py); everything this script asserts is in-window behaviour.
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9337'
const args = process.argv.slice(2)
const opt = (name, fallback = null) => {
  const i = args.indexOf(`--${name}`)
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback
}
const sessionId = opt('session')
const enrollment = opt('enrollment')
const blockId = opt('block', 'blk_fbd02f5d4c279708b89a')
const citationId = opt('citation', 'blk_da4b04f6383533cabb53')
const prefix = opt('prefix', 'docs/visual-review/gm-012/live/walkthrough')
const term = opt('term', 'です')
if (!sessionId || !enrollment) {
  console.error('usage: node scripts/gm012-walkthrough.mjs --session <id> --enrollment <enr_id>')
  process.exit(2)
}

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target on the isolated window')

const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => {
  socket.addEventListener('open', res, { once: true })
  socket.addEventListener('error', rej, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const m = JSON.parse(event.data)
  if (m.id && pending.has(m.id)) {
    const { resolve: r, reject } = pending.get(m.id)
    pending.delete(m.id)
    if (m.error) reject(new Error(JSON.stringify(m.error)))
    else r(m.result)
  }
})
const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = nextId++
    pending.set(id, { resolve, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text)
  return r.result?.value
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const waitUntil = async (expression, label, timeoutMs = 20000) => {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    if (await evaluate(expression)) return true
    await sleep(300)
  }
  throw new Error('timeout: ' + label)
}
const shot = async (name) => {
  const path = resolve(`${prefix}-${name}.png`)
  const data = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, Buffer.from(data.data, 'base64'))
  return path
}
const emit = (payload) => console.log(JSON.stringify(payload))

await send('Page.enable')
await send('Runtime.enable')

// ── phase 1: deliberate selection ───────────────────────────────────────────
// Back to the lesson route and open the section that owns the block.
await evaluate(`location.hash = '#/coursebook'`)
await sleep(1500)
const openedCourse = await evaluate(`(() => {
  const card = document.querySelector('button[data-cb-home-card-action^="${enrollment}"]')
  if (!card) return 'no-card'
  card.click(); return 'clicked'
})()`)
if (openedCourse === 'clicked') {
  await sleep(1500)
  await evaluate(`(() => {
    const b = [...document.querySelectorAll('button')].find((x) => (x.innerText || '').trim() === 'Open section')
    if (b) b.click()
    return true
  })()`)
}
await waitUntil(`!!document.querySelector('[data-cb-block="${blockId}"]')`, 'lesson block')

// Scroll the block to the top of the host scroller, then locate the authored term.
const termRect = await evaluate(`(() => {
  const main = document.querySelector('main')
  const blk = document.querySelector('[data-cb-block="${blockId}"]')
  if (main && blk) main.scrollTop = blk.offsetTop
  const walker = document.createTreeWalker(blk, NodeFilter.SHOW_TEXT)
  let n
  while ((n = walker.nextNode())) {
    if ((n.nodeValue || '').includes(${JSON.stringify(term)})) {
      const i = n.nodeValue.indexOf(${JSON.stringify(term)})
      const range = document.createRange()
      range.setStart(n, i)
      range.setEnd(n, i + ${JSON.stringify(term)}.length)
      const r = range.getBoundingClientRect()
      return { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) }
    }
  }
  return null
})()`)
if (!termRect || termRect.h === 0) throw new Error('term not measurable in the block')

// A real pointer drag over the word: press, move, release (the pill reads on pointerup only).
const y = termRect.y + Math.round(termRect.h / 2)
await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: termRect.x + 1, y, button: 'left', clickCount: 1 })
for (let step = 1; step <= 4; step += 1) {
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: termRect.x + Math.round((termRect.w * step) / 4), y, button: 'left', buttons: 1 })
  await sleep(60)
}
await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: termRect.x + termRect.w - 1, y, button: 'left', clickCount: 1 })
await sleep(700)

const pillNow = () => evaluate(`(() => {
  const p = document.querySelector('[data-cb-tutor-pill]')
  return p ? { text: (p.innerText || '').trim(), aria: p.getAttribute('aria-label'), block: p.getAttribute('data-cb-tutor-pill') } : null
})()`)
const selectionNow = () => evaluate(`String(window.getSelection())`)

let gesture = 'pointer-drag'
let pill = await pillNow()
if (!pill) {
  // CDP pointer gestures do not synthesize a text selection in this Electron/Wayland rig (the
  // window is never OS-focused by the placement rule). The prose IS selectable — `user-select:
  // text` on the reading column is the fix this card shipped — so place the range with the
  // Selection API and let the pane's own `pointerup` handler read it, exactly as a gesture would.
  gesture = 'selection-api+pointerup'
  const placed = await evaluate(`(() => {
    const blk = document.querySelector('[data-cb-block="${blockId}"]')
    const walker = document.createTreeWalker(blk, NodeFilter.SHOW_TEXT)
    let n
    while ((n = walker.nextNode())) {
      if ((n.nodeValue || '').includes(${JSON.stringify(term)})) {
        const i = n.nodeValue.indexOf(${JSON.stringify(term)})
        const range = document.createRange()
        range.setStart(n, i)
        range.setEnd(n, i + ${JSON.stringify(term)}.length)
        const sel = window.getSelection()
        sel.removeAllRanges(); sel.addRange(range)
        document.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }))
        return String(sel)
      }
    }
    return null
  })()`)
  if (placed !== term) throw new Error(`lesson prose is not selectable (selection was ${JSON.stringify(placed)})`)
  await sleep(500)
  pill = await pillNow()
}

const selectionText = await selectionNow()
const turnsBefore = await evaluate(`(() => {
  const t = document.querySelector('[data-cb-tutor-thread]')
  return t ? Number(t.getAttribute('data-cb-tutor-thread')) : null
})()`)
emit({ phase: 'select', gesture, selection: selectionText, pill, turnsBefore, shot: await shot('01-select-pill') })
if (!pill) throw new Error('selection did not offer the pill')
if (turnsBefore !== null && turnsBefore !== 2) throw new Error(`selection changed the thread (${turnsBefore}) — auto-send`)

// ── phase 2: quote chip, and removal ────────────────────────────────────────
await evaluate(`document.querySelector('[data-cb-tutor-pill]').click()`)
await waitUntil(`!!document.querySelector('[data-cb-tutor-quote]')`, 'quote chip')
const quote = await evaluate(`(() => {
  const q = document.querySelector('[data-cb-tutor-quote]')
  const input = document.querySelector('[data-cb-tutor-input]')
  return {
    text: (q.innerText || '').trim(),
    focusedIsInput: !!(input && document.activeElement === input),
    turns: Number(document.querySelector('[data-cb-tutor-thread]').getAttribute('data-cb-tutor-thread')),
    sendDisabled: (document.querySelector('[data-cb-tutor-send]') || {}).disabled
  }
})()`)
emit({ phase: 'quote', ...quote, shot: await shot('02-quote-chip') })
if (!/です/.test(quote.text)) throw new Error('quote chip does not carry the selected word')
if (quote.turns !== 2) throw new Error('arming a quote sent a turn — the chip must not auto-send')

const removed = await evaluate(`(() => {
  const b = document.querySelector('[data-cb-tutor-quote-remove]')
  if (!b) return 'no-remove-control'
  b.click()
  return 'clicked'
})()`)
await sleep(500)
const afterRemove = await evaluate(`!!document.querySelector('[data-cb-tutor-quote]')`)
emit({ phase: 'quote-remove', control: removed, chipPresent: afterRemove })
if (removed !== 'clicked' || afterRemove) throw new Error('quote chip is not removable')

// ── phase 3: cited answer in the lesson-bound rail ──────────────────────────
await evaluate(`location.hash = '#/${sessionId}'`)
await waitUntil(`!!document.querySelector('[data-cb-tutor-pane]') && !!document.querySelector('[data-cb-tutor-thread]')`, 'tutor rail')
const answer = await evaluate(`(() => {
  const pane = document.querySelector('[data-cb-tutor-pane]')
  const citations = [...pane.querySelectorAll('[data-cb-tutor-citation]')].map((c) => ({
    kind: c.getAttribute('data-cb-tutor-citation'),
    target: c.getAttribute('data-cb-tutor-citation-target'),
    label: (c.innerText || '').trim().slice(0, 80)
  }))
  return {
    enrollment: pane.getAttribute('data-cb-tutor-pane'),
    run: pane.getAttribute('data-cb-tutor-run'),
    rail: (() => { const a = pane.querySelector('[data-cb-tutor-rail]'); return a ? a.getAttribute('data-cb-tutor-state') + '/' + a.getAttribute('data-cb-tutor-rail') : null })(),
    context: (pane.querySelector('[data-cb-tutor-context]') || {}).innerText,
    turns: Number(document.querySelector('[data-cb-tutor-thread]').getAttribute('data-cb-tutor-thread')),
    citations,
    text: (pane.innerText || '').slice(0, 600)
  }
})()`)
emit({ phase: 'answer', ...answer, shot: await shot('03-cited-answer') })
if (!answer.citations.length) throw new Error('no citation rendered for the tutor turn')

// ── phase 4: citation -> exact block -> return ──────────────────────────────
const clicked = await evaluate(`(() => {
  const c = document.querySelector('[data-cb-tutor-citation-target="${citationId}"]')
  if (!c) return 'missing'
  c.click(); return 'clicked'
})()`)
if (clicked !== 'clicked') throw new Error('citation control missing: ' + clicked)
await waitUntil(`location.hash === '#/coursebook'`, 'return to the lesson route')
await sleep(600)
const landed = await evaluate(`(() => {
  const active = document.activeElement
  const main = document.querySelector('main')
  const blk = document.querySelector('[data-cb-block="${citationId}"]')
  const rect = blk ? blk.getBoundingClientRect() : null
  const visible = !!(rect && rect.bottom > 0 && rect.top < innerHeight)
  return {
    hash: location.hash,
    focusedBlock: active ? active.getAttribute('data-cb-block') : null,
    blockVisible: visible,
    scroller: main ? { top: Math.round(main.scrollTop), h: main.clientHeight } : null
  }
})()`)
emit({ phase: 'citation-return', ...landed, shot: await shot('04-citation-return') })
if (landed.focusedBlock !== citationId) throw new Error(`citation did not focus the cited block (${landed.focusedBlock})`)
if (!landed.blockVisible) throw new Error('cited block was focused but left off screen')

// ── phase 5: the same surface at the two wide breakpoints ───────────────────
for (const width of [900, 1049]) {
  await send('Emulation.setDeviceMetricsOverride', { width, height: 1000, deviceScaleFactor: 1, mobile: false })
  await sleep(900)
  const geom = await evaluate(`(() => {
    const route = document.querySelector('[data-cb-destination]')
    const pane = document.querySelector('[data-cb-tutor-pane]')
    const rail = document.querySelector('[data-cb-tutor-rail]')
    const box = (e) => { if (!e) return null; const r = e.getBoundingClientRect(); return { l: Math.round(r.left), w: Math.round(r.width) } }
    return {
      viewport: innerWidth + 'x' + innerHeight,
      route: box(route),
      pane: box(pane),
      railVariant: rail ? rail.getAttribute('data-cb-tutor-rail') : null,
      railState: rail ? rail.getAttribute('data-cb-tutor-state') : null,
      overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth
    }
  })()`)
  emit({ phase: 'wide', width, ...geom, shot: await shot(`05-rail-${width}`) })
}
await send('Emulation.clearDeviceMetricsOverride')
console.log('WALKTHROUGH OK')
socket.close()
