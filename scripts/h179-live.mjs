#!/usr/bin/env node
/**
 * H-179 live proof: drive the isolated Coursebook window through the create flow, capture
 * steps 1/2/3 at 1049/900/460 in light and dark, at 200% text, with a keyboard pass and a
 * reduced-motion pass, then submit once on the real draft path and print what the DOM says.
 *
 * `--probe` prints the create flow's current DOM state and exits; no screenshots, no submits.
 * `--phase before|after` only changes the output directory name; the driver reads data
 * attributes, so it runs against the pre-H-179 flow and the new one without a rewrite.
 */
import { writeFileSync, mkdirSync, readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'

const PORT = process.env.CB013_CDP_PORT || '9391'
const PHASE = process.env.H179_PHASE || 'after'
const OUT = resolve(process.env.H179_SHOTS || `audit/visual/h179-create/${PHASE}`)
const PROBE = process.argv.includes('--probe')
const SUBMIT = process.argv.includes('--submit')

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target on the isolated window')

const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => {
  socket.addEventListener('open', res, { once: true })
  socket.addEventListener('error', rej, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const { res, rej } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) rej(new Error(JSON.stringify(message.error)))
    else res(message.result)
  }
})
const send = (method, params = {}, timeout = 20000) =>
  new Promise((res, rej) => {
    const id = nextId++
    const timer = setTimeout(() => {
      pending.delete(id)
      rej(new Error(`CDP timeout: ${method}`))
    }, timeout)
    pending.set(id, {
      res: (value) => { clearTimeout(timer); res(value) },
      rej: (error) => { clearTimeout(timer); rej(error) }
    })
    socket.send(JSON.stringify({ id, method, params }))
  })
const evalJs = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
  return result.result?.value ?? null
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const waitFor = async (expr, ms = 20000) => {
  const end = Date.now() + ms
  while (Date.now() < end) {
    if (await evalJs(expr)) return true
    await wait(200)
  }
  return false
}
const shot = async (name) => {
  const png = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }, 40000)
  const path = `${OUT}/${name}.png`
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, Buffer.from(png.data, 'base64'))
  console.log(`shot ${path}`)
  return path
}

/** This Electron build runs the page at ~0.896 zoom, so calibrate until innerWidth is the target. */
const setWidth = async (target, height = 1000) => {
  let override = target
  for (let i = 0; i < 8; i += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height, deviceScaleFactor: 1, mobile: false })
    await wait(320)
    const measured = await evalJs('window.innerWidth')
    if (Math.abs(measured - target) <= 1) return measured
    override = Math.round((override * target) / measured)
  }
  return evalJs('window.innerWidth')
}
/** Open the route's settings sheet, press one option in a control, close the sheet. */
const chooseSetting = async (control, optionText) => {
  const opened = await evalJs(`(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.getAttribute('aria-label') === 'Open Coursebook settings')
    if (!b) return false
    b.click()
    return true
  })()`)
  if (!opened) throw new Error('no settings button on the route header')
  await wait(450)
  const picked = await evalJs(`(() => {
    const root = document.querySelector('[data-cb-settings-control="${control}"]')
    if (!root) return 'no-control'
    const btn = [...root.querySelectorAll('button')].find((b) => b.innerText.trim().toLowerCase() === ${JSON.stringify(optionText.toLowerCase())})
    if (!btn) return 'no-option:' + root.innerText.replace(/\\s+/g, ' ').slice(0, 120)
    btn.click()
    return 'clicked'
  })()`)
  if (picked !== 'clicked') throw new Error(`setting ${control}=${optionText}: ${picked}`)
  await wait(350)
  await evalJs(`document.querySelector('[data-cb-settings-close]')?.click()`)
  await wait(400)
  return picked
}

const setAppearance = async (mode) => {
  await chooseSetting('appearance', mode === 'dark' ? 'Dark' : 'Light')
  const painted = await evalJs("document.querySelector('[data-cb-route]')?.getAttribute('data-cb-scope') || null")
  if (painted !== mode) throw new Error(`appearance did not repaint: wanted ${mode}, painted ${painted}`)
}
const setMotion = async (reduce) => {
  await chooseSetting('reduced-motion', reduce ? 'Reduce motion' : 'Follow system')
  await send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-motion', value: reduce ? 'reduce' : 'no-preference' }]
  })
  await wait(300)
}
const text200 = async (on) => {
  if (on) await evalJs("document.documentElement.style.setProperty('font-size','32px','important')")
  else await evalJs("document.documentElement.style.removeProperty('font-size')")
  await wait(400)
}

const state = () => evalJs(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const q = (sel) => document.querySelector(sel)
  const buttons = [...document.querySelectorAll('[data-cb-route] button')]
  const primaries = buttons.filter((b) => b.dataset.cbAction === 'primary' || (b.className || '').includes('bg-primary'))
  const card = (el) => ({
    id: el.getAttribute('data-cb-scope-option'),
    selected: el.getAttribute('aria-selected'),
    text: el.innerText.replace(/\\s+/g, ' ').trim(),
    box: (() => { const r = el.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height) } })()
  })
  return {
    hash: location.hash,
    step: q('[data-cb-create-step][aria-current="step"]')?.dataset.cbCreateStep || null,
    spine: [...document.querySelectorAll('[data-cb-create-step]')].map((n) => n.textContent.trim()),
    next: q('[data-cb-create-next]')?.textContent || null,
    heading: q('[data-cb-create-spine]') ? q('[data-cb-route] h2')?.textContent || null : null,
    cards: [...document.querySelectorAll('[data-cb-scope-option]')].map(card),
    goalValue: q('#cb-goal') ? q('#cb-goal').value : null,
    titleValue: q('#cb-title') ? q('#cb-title').value : null,
    titleInDisclosure: q('#cb-title') ? Boolean(q('#cb-title').closest('details')) : null,
    useChoice: q('[data-cb-use-choice]') ? q('[data-cb-use-choice]').innerText.replace(/\\s+/g, ' ').trim() : null,
    tuneOpen: q('[data-cb-tune]') ? q('[data-cb-tune]').open : null,
    primaryLabels: primaries.map((b) => b.innerText.trim()),
    continueDisabled: (() => { const b = buttons.find((x) => x.innerText.trim() === 'Continue'); return b ? b.disabled : null })(),
    describedBy: (() => { const b = buttons.find((x) => x.innerText.trim() === 'Continue'); return b ? b.getAttribute('aria-describedby') : null })(),
    preview: q('[data-cb-create-preview]') ? q('[data-cb-create-preview]').innerText.replace(/\\s+/g, ' ').trim() : null,
    confirm: q('[data-cb-create-facts]') ? q('[data-cb-create-facts]').innerText.replace(/\\s+/g, ' ').trim() : null,
    statusRows: document.querySelectorAll('[data-cb-route] div.border-b').length,
    overflowX: route ? route.scrollWidth - route.clientWidth : null,
    routeWidth: route ? route.clientWidth : null,
    docOverflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    innerWidth: window.innerWidth,
    rootFont: getComputedStyle(document.documentElement).fontSize,
    scope: document.querySelector('[data-cb-route]')?.getAttribute('data-cb-scope') || null
  }
})()`)

const setValue = (selector, value) => evalJs(`(() => {
  const el = document.querySelector(${JSON.stringify(selector)})
  if (!el) return false
  const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(value)})
  el.dispatchEvent(new Event('input', { bubbles: true }))
  return true
})()`)
const clickText = (text, scope = 'button') => evalJs(`(() => {
  const el = [...document.querySelectorAll(${JSON.stringify(scope)})].find((b) => b.innerText.trim() === ${JSON.stringify(text)})
  if (!el) return false
  el.click()
  return true
})()`)

await send('Page.enable')
await send('Runtime.enable')

// Open a *fresh* create flow: the flow keeps its own state per mount, so a window left on step 2
// would otherwise have its step-2 DOM captured as "step 1".
const openCreate = async () => {
  await evalJs("location.hash = '#/'")
  await wait(700)
  await evalJs("location.hash = '#/coursebook'")
  await wait(1400)
  if (await evalJs("!!document.querySelector('#cb-goal')")) return true
  for (const label of ['New course', 'Start with a goal', 'Create a course', 'Start a course']) {
    if (await clickText(label)) {
      await waitFor("!!document.querySelector('#cb-goal')", 8000)
      break
    }
  }
  return evalJs("!!document.querySelector('#cb-goal')")
}

if (!PROBE) {
  const fresh = await openCreate()
  if (!fresh) throw new Error('could not open a fresh create flow')
}

if (PROBE) {
  console.log(JSON.stringify(await state(), null, 2))
  socket.close()
  process.exit(0)
}

const report = { phase: PHASE, steps: [] }

// ── step 1 ────────────────────────────────────────────────────────────────
await setWidth(1049)
await wait(500)
report.steps.push({ label: 'step1-empty', ...(await state()) })
await setValue('#cb-goal', 'Order coffee and ask for the bill in Kyoto, politely')
await wait(500)
report.steps.push({ label: 'step1-goal', ...(await state()) })

for (const [mode, suffix] of [['light', 'light'], ['dark', 'dark']]) {
  await setAppearance(mode)
  await wait(400)
  for (const width of [1049, 900, 460]) {
    const measured = await setWidth(width, width <= 460 ? 1500 : 1000)
    await wait(450)
    await shot(`step1-goal-${width}-${suffix}`)
    report.steps.push({ label: `step1-goal-${width}-${suffix}`, measured, ...(await state()) })
  }
}
await setAppearance('light')
await wait(300)
for (const width of [1049, 460]) {
  await setWidth(width, width <= 460 ? 1900 : 1300)
  await text200(true)
  await shot(`step1-goal-${width}-text200`)
  report.steps.push({ label: `step1-goal-${width}-text200`, ...(await state()) })
  await text200(false)
}

// ── step 2 ────────────────────────────────────────────────────────────────
await setWidth(1049)
await wait(400)
report.continueStep1 = await clickText('Continue')
await waitFor("!!document.querySelector('[data-cb-scope-option]')")
await wait(500)
report.steps.push({ label: 'step2-ask', ...(await state()) })

for (const [mode, suffix] of [['light', 'light'], ['dark', 'dark']]) {
  await setAppearance(mode)
  await wait(400)
  for (const width of [1049, 900, 460]) {
    const measured = await setWidth(width, width <= 460 ? 2200 : 1200)
    await wait(450)
    await shot(`step2-ask-${width}-${suffix}`)
    report.steps.push({ label: `step2-ask-${width}-${suffix}`, measured, ...(await state()) })
  }
}
await setAppearance('light')
await setWidth(1049)
await wait(300)

// Pick the middle route by clicking its card, exactly as a pointer would.
const picked = await evalJs(`(() => {
  const el = document.querySelector('[data-cb-scope-option="short"]')
  if (!el) return false
  el.click()
  return true
})()`)
report.pickedShort = picked
await wait(600)
report.steps.push({ label: 'step2-chosen', ...(await state()) })

// Keyboard: Tab into the cards, move with arrows, confirm selection and the focus ring.
await evalJs("document.querySelector('[data-cb-scope-option=\"short\"]')?.focus()")
await wait(200)
const ringBefore = await evalJs(`(() => { const el = document.activeElement; const s = getComputedStyle(el); return { tag: el.tagName, id: el.getAttribute('data-cb-scope-option'), outline: s.outlineStyle + ' ' + s.outlineWidth + ' ' + s.outlineColor } })()`)
for (let i = 0; i < 2; i += 1) {
  await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39 })
  await wait(250)
}
const ringAfter = await evalJs(`(() => { const el = document.activeElement; const s = getComputedStyle(el); return { tag: el.tagName, id: el.getAttribute('data-cb-scope-option'), outline: s.outlineStyle + ' ' + s.outlineWidth + ' ' + s.outlineColor, selected: el.getAttribute('aria-selected') } })()`)
report.keyboard = { ringBefore, ringAfter, selected: await evalJs("document.querySelectorAll('[data-cb-scope-option][aria-selected=\"true\"]').length") }
await shot('step2-keyboard-card-focus-1049')

// Put the choice back on the short course for the remaining frames.
await evalJs(`document.querySelector('[data-cb-scope-option="short"]')?.click()`)
await wait(400)
report.steps.push({ label: 'step2-chosen-after-keyboard', ...(await state()) })

for (const [mode, suffix] of [['light', 'light'], ['dark', 'dark']]) {
  await setAppearance(mode)
  await wait(400)
  for (const width of [1049, 900, 460]) {
    const measured = await setWidth(width, width <= 460 ? 2200 : 1200)
    await wait(450)
    await shot(`step2-chosen-${width}-${suffix}`)
    report.steps.push({ label: `step2-chosen-${width}-${suffix}`, measured, ...(await state()) })
  }
}
await setAppearance('light')
await setWidth(460, 1900)
await text200(true)
await shot('step2-chosen-460-text200')
report.steps.push({ label: 'step2-chosen-460-text200', ...(await state()) })
await text200(false)

// Reduced motion: the flow must carry no animation at all.
await setMotion(true)
await wait(600)
report.reducedMotion = await evalJs(`(() => {
  const anims = document.getAnimations ? document.getAnimations() : []
  const own = [...document.querySelectorAll('[data-cb-action], [data-cb-scope-option]')]
  return {
    animations: anims.length,
    running: anims.filter((a) => a.playState === 'running').length,
    // Coursebook's own controls must carry no beat; host chrome (SDK buttons elsewhere on the
    // route) is the host's business and is counted separately.
    ownControls: own.length,
    ownWithTransition: own.filter((n) => {
      const d = getComputedStyle(n).transitionDuration
      // This build reports a zero duration as 1e-05s; anything at or below 10 ms is no beat.
      return d && d.split(',').some((part) => parseFloat(part) > 0.01)
    }).length,
    ownWithAnimation: own.filter((n) => getComputedStyle(n).animationName !== 'none').length
  }
})()`)
await shot('step2-chosen-460-reduced-motion')
await setMotion(false)

// ── step 3 ────────────────────────────────────────────────────────────────
await setWidth(1049)
await wait(400)
report.continueStep2 = await clickText('Continue')
await waitFor("!!document.querySelector('[data-cb-create-preview]') || !!document.querySelector('#cb-goal')")
await wait(700)
report.steps.push({ label: 'step3-preview', ...(await state()) })

for (const [mode, suffix] of [['light', 'light'], ['dark', 'dark']]) {
  await setAppearance(mode)
  await wait(400)
  for (const width of [1049, 900, 460]) {
    const measured = await setWidth(width, width <= 460 ? 1800 : 1100)
    await wait(450)
    await shot(`step3-preview-${width}-${suffix}`)
    report.steps.push({ label: `step3-preview-${width}-${suffix}`, measured, ...(await state()) })
  }
}
await setAppearance('light')
await setWidth(460, 2200)
await text200(true)
await shot('step3-preview-460-text200')
report.steps.push({ label: 'step3-preview-460-text200', ...(await state()) })
await text200(false)
await setWidth(1049)

if (SUBMIT) {
  // One press on the real draft path: course.create -> enrollment.create -> jobs.create.
  const before = await evalJs('performance.now()')
  report.submitClicked = await clickText('Create course')
  const appeared = await waitFor("!!document.querySelector('[data-cb-create-receipt]') || !!document.querySelector('[data-cb-create-preview]') === false", 60000)
  await wait(1500)
  report.submit = {
    appeared,
    elapsedMs: Math.round((await evalJs('performance.now()')) - before),
    receipt: await evalJs(`(() => { const el = document.querySelector('[data-cb-create-receipt]'); return el ? el.innerText.replace(/\\s+/g, ' ').trim() : null })()`),
    lead: await evalJs(`(() => { const h = document.querySelector('[data-cb-route] h2'); return h ? h.innerText.trim() : null })()`),
    body: await evalJs(`(() => { const ps = [...document.querySelectorAll('[data-cb-route] p')]; return ps.slice(0, 3).map((p) => p.innerText.trim()) })()`),
    primaries: await evalJs(`[...document.querySelectorAll('[data-cb-route] button')].filter((b) => b.dataset.cbAction === 'primary').map((b) => b.innerText.trim())`)
  }
  await shot('step3-created-1049-light')
}

mkdirSync(OUT, { recursive: true })
writeFileSync(`${OUT}/h179-live.json`, JSON.stringify(report, null, 2))
console.log(JSON.stringify({ phase: PHASE, steps: report.steps.length, out: OUT, submit: report.submit || null }, null, 2))
socket.close()
