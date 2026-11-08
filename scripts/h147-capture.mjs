#!/usr/bin/env node
/**
 * H-147 evidence capture: the Home settings sheet and the default learning view.
 *
 * Drives the isolated Electron window over CDP (never the operator's window). It records, from the
 * running plugin rather than from a fixture:
 *
 *   - the Home defaults line before anything is opened, and the one click that opens the sheet;
 *   - every section, its current value and its own Reset;
 *   - an immediate change (no Save) and the value it wrote to the profile's store;
 *   - a classroom override beating the home default, and clearing it restoring the default;
 *   - Escape closing the sheet and returning focus to the Settings control;
 *   - the reduced-motion setting painting `data-cb-motion`;
 *   - frames at 1049 and 460 in both painted modes.
 *
 *   CB009_CDP_PORT=9381 node scripts/h147-capture.mjs docs/h147-shots
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9381'
const OUT = resolve(process.argv[2] || 'docs/h147-shots')
mkdirSync(OUT, { recursive: true })

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page =
  targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) ||
  targets.find((entry) => entry.type === 'page')
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
    const { resolve: res, reject } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) reject(new Error(JSON.stringify(message.error)))
    else res(message.result)
  }
})
const send = (method, params = {}) =>
  new Promise((res, rej) => {
    const id = nextId++
    pending.set(id, { resolve: res, reject: rej })
    socket.send(JSON.stringify({ id, method, params }))
    setTimeout(() => {
      if (pending.has(id)) {
        pending.delete(id)
        rej(new Error(`timeout: ${method}`))
      }
    }, 20000)
  })
const evaluate = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
  return result.result.value
}
const sleep = (ms) => new Promise((res) => setTimeout(res, ms))
const shot = async (name) => {
  const data = await send('Page.captureScreenshot', { format: 'png' })
  writeFileSync(resolve(OUT, `${name}.png`), Buffer.from(data.data, 'base64'))
}

await send('Page.enable')
await send('Runtime.enable')
await evaluate(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
// Start from a clean document for this card so every number below belongs to this run.
await evaluate(`Object.keys(localStorage).filter((key) => key.startsWith('hermes.plugin.coursebook.home-preferences.')).forEach((key) => localStorage.removeItem(key))`)
await evaluate(`location.hash = '#/'`)
await sleep(500)
await evaluate(`location.hash = '#/coursebook'`)
await sleep(2200)

const facts = { port: PORT, startedAt: new Date().toISOString() }

/** Calibrate the device-metrics override to the CSS width we actually want (skill pitfall). */
const setWidth = async (target) => {
  let override = target
  for (let attempt = 0; attempt < 4; attempt += 1) {
    await send('Emulation.setDeviceMetricsOverride', {
      width: Math.round(override),
      height: 900,
      deviceScaleFactor: 1,
      mobile: false
    })
    await sleep(320)
    const inner = await evaluate(`window.innerWidth`)
    if (inner === target) return { target, override: Math.round(override), inner }
    override = Math.round((override * target) / inner)
  }
  return { target, override: Math.round(override), inner: await evaluate(`window.innerWidth`) }
}
const clearWidth = () => send('Emulation.clearDeviceMetricsOverride')

const read = () =>
  evaluate(`(() => {
    const route = document.querySelector('[data-cb-route]')
    const line = document.querySelector('[data-cb-home-defaults]')
    const sheet = document.querySelector('[data-cb-settings-sheet]')
    const trigger = document.querySelector('[data-cb-settings-open]')
    const active = document.activeElement
    const describe = (node) => node ? {
      tag: node.tagName ? node.tagName.toLowerCase() : null,
      label: node.getAttribute && node.getAttribute('aria-label'),
      text: (node.textContent || '').trim().slice(0, 48)
    } : null
    const controls = {}
    for (const node of document.querySelectorAll('[data-cb-settings-control]')) {
      controls[node.getAttribute('data-cb-settings-control')] = node.getAttribute('data-cb-settings-value')
    }
    const toggles = {}
    for (const node of document.querySelectorAll('[data-cb-settings-toggle]')) {
      const box = node.querySelector('input, [role="switch"], button[aria-checked]')
      toggles[node.getAttribute('data-cb-settings-toggle')] = box
        ? String(box.getAttribute('aria-checked') || (box.checked ? 'true' : 'false'))
        : null
    }
    return {
      mounted: Boolean(route),
      pageTitle: (document.querySelector('[data-cb-page-title]') || {}).textContent || null,
      homeDefaults: line ? line.getAttribute('data-cb-home-defaults') : null,
      homeEffective: line ? line.getAttribute('data-cb-home-effective') : null,
      homeOverride: document.querySelector('[data-cb-home-override]')
        ? document.querySelector('[data-cb-home-override]').getAttribute('data-cb-home-override')
        : null,
      lineText: line ? (line.textContent || '').replace(/\\s+/g, ' ').trim() : null,
      trigger: trigger ? {
        label: trigger.getAttribute('aria-label'),
        haspopup: trigger.getAttribute('aria-haspopup'),
        minHeight: getComputedStyle(trigger).minHeight,
        height: Math.round(trigger.getBoundingClientRect().height)
      } : null,
      sheetOpen: Boolean(sheet),
      sheetRole: sheet ? sheet.getAttribute('role') : null,
      sheetModal: sheet ? sheet.getAttribute('aria-modal') : null,
      sheetWidth: sheet ? Math.round(sheet.getBoundingClientRect().width) : null,
      sheetMaxWidth: sheet ? getComputedStyle(sheet).maxWidth : null,
      sections: [...document.querySelectorAll('[data-cb-settings-section]')].map((node) =>
        node.getAttribute('data-cb-settings-section')),
      sectionHeadingIds: [...document.querySelectorAll('[data-cb-settings-section]')].map((node) => {
        const heading = node.querySelector('h3')
        return { labelledBy: node.getAttribute('aria-labelledby'), headingId: heading ? heading.id : null }
      }),
      scopeLabel: (document.querySelector('[data-cb-settings-scope]') || {}).textContent || null,
      scope: route ? route.getAttribute('data-cb-scope') : null,
      motion: route ? route.getAttribute('data-cb-motion') : null,
      controls,
      toggles,
      resetButtons: [...document.querySelectorAll('[data-cb-settings-reset]')].map((node) => ({
        section: node.getAttribute('data-cb-settings-reset'),
        label: node.getAttribute('aria-label'),
        disabled: Boolean(node.disabled),
        height: Math.round(node.getBoundingClientRect().height)
      })),
      saveButtons: [...document.querySelectorAll('button')].filter((node) => /^save$/i.test((node.textContent || '').trim())).length,
      horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      focus: describe(active),
      focusInSheet: Boolean(active && active.closest && active.closest('[data-cb-settings-sheet]')),
      stored: Object.fromEntries(
        Object.keys(localStorage)
          .filter((key) => key.startsWith('hermes.plugin.coursebook.home-preferences.'))
          .map((key) => [key, JSON.parse(localStorage.getItem(key))])
      ),
      sheetText: sheet ? (sheet.innerText || '').replace(/\\s+/g, ' ').trim() : null
    }
  })()`)

const click = async (selector) => {
  const ok = await evaluate(`(() => {
    const node = document.querySelector(${JSON.stringify(selector)})
    if (!node) return false
    node.click()
    return true
  })()`)
  if (!ok) throw new Error(`missing control: ${selector}`)
  await sleep(500)
}

const LABELS = {
  appearance: { system: 'System', light: 'Light', dark: 'Dark' },
  'default-view': { game: 'Game', guided: 'Guided', textbook: 'Textbook' },
  classroom: { default: 'Home default', game: 'Game', guided: 'Guided', textbook: 'Textbook' },
  'reduced-motion': { system: 'Follow system', reduce: 'Reduce motion' }
}

const clickOption = async (section, value) => {
  const label = (LABELS[section] || {})[value] || value
  const ok = await evaluate(`(() => {
    const scope = document.querySelector('[data-cb-settings-control="${section}"]')
    if (!scope) return false
    const button = [...scope.querySelectorAll('button')].find(
      (node) => (node.textContent || '').trim() === ${JSON.stringify(label)}
    )
    if (!button) return false
    button.click()
    return true
  })()`)
  if (!ok) throw new Error(`missing option: ${section}=${value}`)
  await sleep(450)
}

console.log('initial', JSON.stringify(await read()).slice(0, 600))
facts.homeInitial = await read()
if (!facts.homeInitial.mounted) {
  facts.error = 'the /coursebook route did not mount'
  writeFileSync(resolve(OUT, 'h147-facts.json'), JSON.stringify(facts, null, 2))
  socket.close()
  throw new Error('route did not mount; see h147-facts.json')
}

// ── one interaction opens the sheet ─────────────────────────────────────────────────────────────
await click('[data-cb-settings-open]')
facts.sheetOpen = await read()

// ── immediate change: default view → Textbook, no Save ──────────────────────────────────────────
await clickOption('default-view', 'textbook')
facts.afterDefaultTextbook = await read()

// ── classroom override beats the home default; clearing restores it ─────────────────────────────
await clickOption('classroom', 'guided')
facts.afterClassroomGuided = await read()
await click('[data-cb-settings-reset="classroom"]')
facts.afterClassroomReset = await read()

// ── sound applies immediately (default off) ─────────────────────────────────────────────────────
await click('[data-cb-settings-toggle="sound"] [role="switch"], [data-cb-settings-toggle="sound"] input, [data-cb-settings-toggle="sound"] button')
facts.afterSoundOn = await read()
await click('[data-cb-settings-reset="sound"]')
facts.afterSoundReset = await read()

// ── reduced motion: the setting paints the route ────────────────────────────────────────────────
await clickOption('reduced-motion', 'reduce')
facts.afterReducedMotion = await read()
await clickOption('reduced-motion', 'system')

// ── Escape closes and returns focus to the invoking control ─────────────────────────────────────
await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
await sleep(600)
facts.afterEscape = await read()

// ── frames: 1049 and 460, in each painted mode, with the sheet open ─────────────────────────────
facts.frames = []
const emulated = await evaluate(`(() => {
  const route = document.querySelector('[data-cb-route]')
  return route ? route.getAttribute('data-cb-scope') : null
})()`)
const modes = emulated === 'dark' ? ['dark', 'light'] : ['light', 'dark']
for (const mode of modes) {
  // The plugin's own appearance control is the honest way to paint a mode; the host theme is the
  // fallback when the system emulation does not reach its store.
  await click('[data-cb-settings-open]')
  await clickOption('appearance', mode)
  await sleep(300)
  for (const width of [1049, 460]) {
    const calibrated = await setWidth(width)
    await sleep(420)
    const frame = await read()
    await shot(`h147-${mode}-${width}`)
    facts.frames.push({ mode, width, calibrated, ...frame })
  }
  await clearWidth()
  await click('[data-cb-settings-close]')
  await sleep(300)
}

// ── the stored document is the profile's own ───────────────────────────────────────────────────
facts.final = await read()
writeFileSync(resolve(OUT, 'h147-facts.json'), JSON.stringify(facts, null, 2))
console.log(JSON.stringify({
  homeDefaults: facts.homeInitial.homeDefaults,
  trigger: facts.homeInitial.trigger,
  opened: facts.sheetOpen.sheetOpen,
  sections: facts.sheetOpen.sections,
  afterDefaultTextbook: facts.afterDefaultTextbook.controls,
  override: facts.afterClassroomGuided.homeOverride,
  afterReset: facts.afterClassroomReset.homeOverride,
  motion: facts.afterReducedMotion.motion,
  escapeFocus: facts.afterEscape.focus,
  frames: facts.frames.map((frame) => ({
    mode: frame.mode,
    width: frame.width,
    inner: frame.calibrated.inner,
    scope: frame.scope,
    sheetWidth: frame.sheetWidth,
    overflow: frame.horizontalOverflow
  })),
  stored: Object.keys(facts.final.stored)
}, null, 2))
socket.close()
