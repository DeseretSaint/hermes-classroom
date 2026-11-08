#!/usr/bin/env node
/**
 * H-150 evidence capture for the Library shelf.
 *
 * Drives the isolated Electron window over CDP and records what the card must prove on the real
 * installed plugin: one page h1 "Library", one lead, no repeated plate label, correct filter
 * labels, the whole-row target with keyboard Enter, a visible (non-colour-only) Selected cue, no
 * raw revision/pack_id in learner text, identifiers under closed Technical details, and the empty
 * pack named once. Frames are captured at 1049/900/460 in light and dark.
 *
 *   CB009_CDP_PORT=9362 node scripts/h150-capture.mjs docs/h150-shots
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9362'
const OUT = resolve(process.argv[2] || 'docs/h150-shots')

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
const sleep = (ms) => new Promise((res) => setTimeout(res, ms))
const evaluate = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
  return result.result.value
}
const key = async (keyName) => {
  const params = keyName === 'Enter'
    ? { key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 }
    : { key: ' ', code: 'Space', windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 32, text: ' ' }
  await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', ...params })
  await send('Input.dispatchKeyEvent', { type: 'keyDown', ...params })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', ...params })
  await sleep(220)
}

const findButton = async (label) =>
  evaluate(`(() => {
    const b = [...document.querySelectorAll('button')].find((n) => (n.getAttribute('aria-label') || n.textContent || '').replace(/\\s+/g, ' ').trim() === ${JSON.stringify(label)})
    if (b) b.click()
    return Boolean(b)
  })()`)

const setTheme = async (mode) => {
  const label = mode === 'dark' ? 'Dark' : 'Light'
  await findButton('Open settings')
  await sleep(700)
  await findButton('Appearance')
  await sleep(600)
  await findButton('Theme')
  await sleep(600)
  await findButton(label)
  await sleep(700)
  await evaluate(`location.hash = '#/coursebook'`)
  await sleep(1200)
  await navTo('library')
}

await send('Page.enable')
await send('Runtime.enable')

await evaluate(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
await evaluate(`location.hash = '#/'`)
await sleep(300)
await evaluate(`location.hash = '#/coursebook'`)
await sleep(1300)
const mounted = await evaluate(`Boolean(document.querySelector('[data-cb-route]'))`)
if (!mounted) throw new Error('coursebook route did not mount')

const navTo = async (destination) => {
  for (let attempt = 0; attempt < 6; attempt += 1) {
    await evaluate(`(() => { const b = document.querySelector('[data-cb-nav-item="${destination}"]'); if (b) b.click() })()`)
    await sleep(700)
    const mounted = await evaluate(`(() => { const route = document.querySelector('[data-cb-route]'); return route ? route.getAttribute('data-cb-destination') : null })()`)
    if (mounted === destination) return
  }
  throw new Error(`navigation to ${destination} did not take`)
}

const clickFilter = async (label) => {
  await evaluate(`(() => {
    const b = [...document.querySelectorAll('button')].find((n) => (n.textContent || '').trim() === ${JSON.stringify(label)})
    if (b) b.click()
  })()`)
  await sleep(500)
}

const facts = () =>
  evaluate(`(() => {
    const route = document.querySelector('[data-cb-route]')
    const text = (node) => ((node && node.textContent) || '').replace(/\\s+/g, ' ').trim()
    const title = document.querySelector('[data-cb-page-title]')
    const h1s = [...document.querySelectorAll('h1')]
    const rows = [...document.querySelectorAll('[data-cb-pack-row]')]
    const technical = [...document.querySelectorAll('[data-cb-pack-technical]')]
    const routeText = route ? route.innerText : ''
    const lead = routeText.split('\\n').map((s) => s.trim()).find((s) => s.startsWith('Every pack installed on this profile')) || ''
    return {
      innerWidth: window.innerWidth,
      rootFontSize: getComputedStyle(document.documentElement).fontSize,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      mode: route && route.getAttribute('data-cb-scope'),
      destination: route && route.getAttribute('data-cb-destination'),
      h1: { count: h1s.length, text: text(title), fontSize: title ? getComputedStyle(title).fontSize : null },
      libraryLabels: [...document.querySelectorAll('h1,h2,h3')].filter((n) => text(n) === 'Library').length,
      plateLabels: [...document.querySelectorAll('*')].filter((n) => n.children.length === 0 && !n.closest('[data-cb-nav-item]') && text(n) === 'Library').length,
      leadCount: routeText.split(lead).length - 1,
      lead,
      filters: [...document.querySelectorAll('button')].map(text).filter((t) => ['All packs', 'Bundled', 'From someone else', 'All', 'Local'].includes(t)),
      rows: rows.map((row) => ({
        title: text(row.querySelector('h3')),
        source: text(row.querySelector('.badge')),
        empty: row.getAttribute('data-cb-pack-empty'),
        selected: row.getAttribute('data-cb-pack-selected'),
        selectedCue: text(row.querySelector('[data-cb-pack-selected-cue]')),
        buttons: row.querySelectorAll('button').length,
        overlayLabel: (row.querySelector('button[aria-pressed]') || {}).getAttribute ? row.querySelector('button[aria-pressed]').getAttribute('aria-label') : null
      })),
      selectedCount: document.querySelectorAll('[data-cb-pack-selected="true"]').length,
      selectedCueText: [...document.querySelectorAll('[data-cb-pack-selected-cue]')].map(text),
      emptyRows: rows.filter((row) => row.getAttribute('data-cb-pack-empty') === 'true').length,
      noSectionsCount: (routeText.match(/No sections yet/g) || []).length,
      rawRevision: /revision \\d+/i.test(routeText),
      rawPackId: /pack_[0-9a-f]{8,}/i.test(routeText),
      technical: technical.map((node) => ({ open: node.open, label: text(node.querySelector('summary')) })),
      previewPanel: Boolean(document.querySelector('[data-cb-pack-preview]')),
      previewPrimary: [...document.querySelectorAll('[data-cb-pack-preview] [data-variant="default"]')].map(text),
      previewSecondary: [...document.querySelectorAll('[data-cb-pack-preview] [data-variant="secondary"]')].map(text),
      emptyState: routeText.includes('No bundled pack on this profile') ? 'bundled' : routeText.includes('No pack from someone else on this profile') ? 'other' : routeText.includes('No packs on this profile yet') ? 'all' : '',
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      routeText: routeText.slice(0, 1600)
    }
  })()`)

const setWidth = async (target) => {
  let override = target
  for (let i = 0; i < 8; i += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height: 900, deviceScaleFactor: 1, mobile: false })
    await sleep(140)
    const inner = await evaluate('window.innerWidth')
    if (inner === target) return override
    override = Math.round((override * target) / inner)
  }
  throw new Error(`could not calibrate ${target}`)
}

const shoot = async (name) => {
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  mkdirSync(OUT, { recursive: true })
  const path = resolve(OUT, `${name}.png`)
  writeFileSync(path, Buffer.from(shot.data, 'base64'))
  return path
}

const results = { port: PORT, target: page.url, frames: [], facts: {}, actions: {} }

await navTo('library')
for (const mode of ['light', 'dark']) {
  await setTheme(mode)
  for (const width of [1049, 900, 460]) {
    await setWidth(width)
    await sleep(260)
    const snapshot = await facts()
    if (snapshot.destination !== 'library') throw new Error(`capture left Library: destination=${snapshot.destination} at ${mode}-${width}`)
    results.facts[`${mode}-${width}`] = snapshot
    results.frames.push({ mode, width, file: await shoot(`${mode}-${width}`) })
  }
}

// Interaction, at a comfortable width in the light theme.
await setTheme('light')
await setWidth(1049)
await sleep(300)

// A click on the row's own target opens the preview; the Selected cue is a word, not colour.
await evaluate(`(() => {
  const row = document.querySelector('[data-cb-pack-row]')
  row.querySelector('button[aria-pressed]').click()
})()`)
await sleep(500)
results.actions.afterClick = await facts()

// Clear the preview with its own back action, then drive the next row from the keyboard.
await findButton('All packs')
await sleep(400)
results.actions.cleared = await facts()
await evaluate(`(() => {
  const row = document.querySelectorAll('[data-cb-pack-row]')[1]
  row.querySelector('button[aria-pressed]').focus()
})()`)
await key('Enter')
results.actions.afterKeyboardEnter = await facts()
await evaluate(`(() => {
  const row = document.querySelectorAll('[data-cb-pack-row]')[0]
  row.querySelector('button[aria-pressed]').focus()
})()`)
await key(' ')
results.actions.afterKeyboardSpace = await facts()

// Filters must return the rows their labels name.
await clickFilter('Bundled')
results.actions.bundled = await facts()
await clickFilter('From someone else')
results.actions.fromSomeoneElse = await facts()
await clickFilter('All packs')
results.actions.allPacks = await facts()

// Select a pack-backed row, then open the closed technical disclosure.
await evaluate(`(() => {
  const row = [...document.querySelectorAll('[data-cb-pack-row]')].find((n) => !/Authored here/.test(n.innerText)) || document.querySelector('[data-cb-pack-row]')
  row.querySelector('button[aria-pressed]').click()
})()`)
await sleep(400)
results.actions.technicalClosed = await facts()
await evaluate(`(() => { const d = document.querySelector('[data-cb-pack-technical]'); if (d) d.open = true })()`)
await sleep(250)
results.actions.technicalOpen = await evaluate(`(() => {
  const d = document.querySelector('[data-cb-pack-technical]')
  const text = (n) => ((n && n.textContent) || '').replace(/\\s+/g, ' ').trim()
  return { open: Boolean(d && d.open), text: text(d) }
})()`)

// Reduced motion and 200% text, both at 460.
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
await evaluate(`document.documentElement.style.setProperty('font-size', '32px', 'important')`)
await setWidth(460)
await sleep(300)
results.facts['text200-light-460'] = await facts()
results.frames.push({ mode: 'light', width: 460, text: '200%', file: await shoot('text200-light-460') })
await evaluate(`document.documentElement.style.removeProperty('font-size')`)
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })

// Keyboard focus ring on the row target.
await evaluate(`document.querySelector('[data-cb-pack-row] button[aria-pressed]').focus()`)
await sleep(250)
const focus = await evaluate(`(() => {
  const overlay = document.querySelector('[data-cb-pack-row] button[aria-pressed]')
  const style = getComputedStyle(overlay)
  return { tag: overlay.tagName.toLowerCase(), label: overlay.getAttribute('aria-label'), outline: style.outlineStyle + ' ' + style.outlineWidth + ' ' + style.outlineColor }
})()`)
results.actions.focus = focus

await evaluate(`location.hash = '#/coursebook'`)
await setWidth(1049)
await sleep(200)

mkdirSync(OUT, { recursive: true })
writeFileSync(resolve(OUT, 'h150-facts.json'), JSON.stringify(results, null, 2))
console.log(JSON.stringify({ mode: results.facts['light-1049'].mode, frames: results.frames.length, actions: Object.keys(results.actions), focus }, null, 2))
socket.close()
