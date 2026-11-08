#!/usr/bin/env node
/**
 * H-156 evidence capture: parent and child defaults.
 *
 * Drives the isolated Electron window over CDP (never the operator's window) and records, from
 * the running plugin:
 *
 *   - Home naming the child-safe floor and the parent-set session length before the sheet opens;
 *   - the one Settings sheet with its child-safe section: four rules, each "Never", and the
 *     session-length choice, measured for 44 px targets and horizontal overflow;
 *   - the session length applying at once, writing the profile document, and a Reset restoring 15;
 *   - Parent Studio as a separate authoring space whose copy says "prepare a lesson for a child",
 *     carrying the same child-safe line, and whose plan view reports evidence, not points;
 *   - Escape from the Parent Studio sheet returning focus to the Studio trigger;
 *   - frames at 1049 and 460 px in light and dark: Home, the child-safe section of the sheet, and
 *     Parent Studio.
 *
 *   CB009_CDP_PORT=9382 node scripts/h156-capture.mjs docs/h156-shots
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9382'
const OUT = resolve(process.argv[2] || 'docs/h156-shots')
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
// Start from the defaults so every number below belongs to this run.
await evaluate(
  `Object.keys(localStorage).filter((key) => key.startsWith('hermes.plugin.coursebook.home-preferences.')).forEach((key) => localStorage.removeItem(key))`
)
await evaluate(`location.hash = '#/'`)
await sleep(500)
await evaluate(`location.hash = '#/coursebook'`)
await sleep(2400)

const facts = { port: PORT, startedAt: new Date().toISOString() }

const setWidth = async (target) => {
  let override = target
  for (let attempt = 0; attempt < 5; attempt += 1) {
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

const CONTRAST_JS = `(() => {
  const parse = (value) => {
    const match = String(value).match(/rgba?\\(([^)]+)\\)/)
    if (!match) return null
    const parts = match[1].split(',').map((part) => Number(part.trim()))
    return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 }
  }
  const lum = (colour) => {
    const channel = (value) => {
      const c = value / 255
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
    }
    return 0.2126 * channel(colour.r) + 0.7152 * channel(colour.g) + 0.0722 * channel(colour.b)
  }
  const ratio = (a, b) => {
    const la = lum(a)
    const lb = lum(b)
    const [hi, lo] = la > lb ? [la, lb] : [lb, la]
    return Number(((hi + 0.05) / (lo + 0.05)).toFixed(2))
  }
  const section = document.querySelector('[data-cb-settings-section="child-safe"]')
  const sheet = document.querySelector('[data-cb-settings-sheet]')
  if (!section || !sheet) return null
  const background = parse(getComputedStyle(sheet).backgroundColor)
  const heading = section.querySelector('h3')
  const description = section.querySelector('p')
  return {
    heading: heading ? ratio(parse(getComputedStyle(heading).color), background) : null,
    description: description ? ratio(parse(getComputedStyle(description).color), background) : null,
    sheetBackground: getComputedStyle(sheet).backgroundColor
  }
})()`

const read = () =>
  evaluate(`(() => {
    const route = document.querySelector('[data-cb-route]')
    const line = document.querySelector('[data-cb-home-defaults]')
    const sheet = document.querySelector('[data-cb-settings-sheet]')
    const trigger = document.querySelector('[data-cb-settings-open]')
    const safe = document.querySelector('[data-cb-child-safe]')
    const session = document.querySelector('[data-cb-session-minutes]')
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
    return {
      mounted: Boolean(route),
      destination: route ? route.getAttribute('data-cb-destination') : null,
      pageTitle: (document.querySelector('[data-cb-page-title]') || {}).textContent || null,
      lineText: line ? (line.textContent || '').replace(/\\s+/g, ' ').trim() : null,
      childSafe: safe ? safe.getAttribute('data-cb-child-safe') : null,
      childSafeText: safe ? (safe.textContent || '').replace(/\\s+/g, ' ').trim() : null,
      sessionMinutes: session ? session.getAttribute('data-cb-session-minutes') : null,
      childSafeRules: [...document.querySelectorAll('[data-cb-child-safe-rule]')].map((node) => ({
        id: node.getAttribute('data-cb-child-safe-rule'),
        state: node.getAttribute('data-cb-child-safe-state'),
        text: (node.textContent || '').replace(/\\s+/g, ' ').trim()
      })),
      parentEvidence: (document.querySelector('[data-cb-parent-evidence]') || {}).textContent || null,
      trigger: trigger ? {
        label: trigger.getAttribute('aria-label'),
        haspopup: trigger.getAttribute('aria-haspopup'),
        height: Math.round(trigger.getBoundingClientRect().height)
      } : null,
      sheetOpen: Boolean(sheet),
      sheetRole: sheet ? sheet.getAttribute('role') : null,
      sheetModal: sheet ? sheet.getAttribute('aria-modal') : null,
      sheetWidth: sheet ? Math.round(sheet.getBoundingClientRect().width) : null,
      sections: [...document.querySelectorAll('[data-cb-settings-section]')].map((node) =>
        node.getAttribute('data-cb-settings-section')),
      sessionOptionHeights: [...document.querySelectorAll('[data-cb-settings-control="session-length"] button')].map(
        (node) => ({ label: (node.textContent || '').trim(), height: Math.round(node.getBoundingClientRect().height) })
      ),
      resetButtons: [...document.querySelectorAll('[data-cb-settings-reset]')].map((node) => ({
        section: node.getAttribute('data-cb-settings-reset'),
        disabled: Boolean(node.disabled),
        height: Math.round(node.getBoundingClientRect().height)
      })),
      controls,
      scope: route ? route.getAttribute('data-cb-scope') : null,
      motion: route ? route.getAttribute('data-cb-motion') : null,
      horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      focus: describe(active),
      focusInSheet: Boolean(active && active.closest && active.closest('[data-cb-settings-sheet]')),
      bodyText: ((document.querySelector('[data-cb-main]') || {}).innerText || '').replace(/\\s+/g, ' ').trim(),
      stored: Object.fromEntries(
        Object.keys(localStorage)
          .filter((key) => key.startsWith('hermes.plugin.coursebook.home-preferences.'))
          .map((key) => [key, JSON.parse(localStorage.getItem(key))])
      )
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
  await sleep(520)
}
const clickText = async (selector, text) => {
  const ok = await evaluate(`(() => {
    const node = [...document.querySelectorAll(${JSON.stringify(selector)})].find(
      (candidate) => (candidate.textContent || '').trim() === ${JSON.stringify(text)}
    )
    if (!node) return false
    node.click()
    return true
  })()`)
  if (!ok) throw new Error(`missing control: ${selector} "${text}"`)
  await sleep(520)
}
const clickNav = (label) => clickText('[data-cb-nav-item]', label)
const clickOption = async (section, label) => {
  const ok = await evaluate(`(() => {
    const scope = document.querySelector('[data-cb-settings-control="${section}"]')
    const button = scope ? [...scope.querySelectorAll('button')].find(
      (candidate) => (candidate.textContent || '').trim() === ${JSON.stringify(label)}
    ) : null
    if (button) button.click()
    return Boolean(button)
  })()`)
  if (!ok) throw new Error(`missing option: ${section} "${label}"`)
  await sleep(450)
}
const scrollSectionIntoView = async (id) => {
  const info = await evaluate(`(() => {
    const node = document.querySelector('[data-cb-settings-section="${id}"]')
    if (!node) return null
    node.scrollIntoView({ block: 'start' })
    const rect = node.getBoundingClientRect()
    return { top: Math.round(rect.top), height: Math.round(rect.height) }
  })()`)
  await sleep(300)
  return info
}

await clickNav('Home')
facts.homeInitial = await read()
facts.window = await evaluate(`(() => ({ inner: innerWidth, outer: outerWidth, dpr: devicePixelRatio }))()`)
if (!facts.homeInitial.mounted) {
  facts.error = 'the /coursebook route did not mount'
  writeFileSync(resolve(OUT, 'h156-facts.json'), JSON.stringify(facts, null, 2))
  socket.close()
  throw new Error('route did not mount; see h156-facts.json')
}

// ── the sheet, the child-safe section and the session choice ───────────────────────────────────
await click('[data-cb-settings-open]')
facts.sheetOpen = await read()
facts.childSafeSectionScroll = await scrollSectionIntoView('child-safe')
facts.childSafeContrast = await evaluate(CONTRAST_JS)
await clickOption('session-length', '20 min')
facts.afterSessionTwenty = await read()
await clickOption('session-length', '10 min')
facts.afterSessionTen = await read()
await click('[data-cb-settings-reset="child-safe"]')
facts.afterSessionReset = await read()
facts.resetContrast = await evaluate(CONTRAST_JS)
await click('[data-cb-settings-close]')
facts.homeAfterSheet = await read()

// ── Parent Studio: a separate authoring space with the same floor ──────────────────────────────
await clickNav('Parent Studio')
facts.studio = await read()
await click('[data-cb-settings-open]')
facts.studioSheet = await read()
// Keyboard: Tab from the sheet's first focus stop stays inside the sheet.
await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
await sleep(400)
facts.studioSheetTab = await read()
await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
await sleep(500)
facts.studioAfterEscape = await read()

// ── one real plan: the parent view reports evidence, not points ────────────────────────────────
const openedPlan = await evaluate(`(() => {
  const button = [...document.querySelectorAll('button')].find((node) => (node.textContent || '').trim() === 'Open plan')
  if (!button) return false
  button.click()
  return true
})()`)
if (openedPlan) {
  await sleep(1600)
  facts.studioPlan = await read()
  await shot('h156-studio-plan-light-1049')
} else {
  facts.studioPlan = { skipped: 'this profile has no parent plan to open' }
}

// ── frames: 1049 and 460 px, light and dark ────────────────────────────────────────────────────
facts.frames = []
const modes = ['light', 'dark']
for (const mode of modes) {
  await clickNav('Home')
  await click('[data-cb-settings-open]')
  await clickOption('appearance', mode === 'light' ? 'Light' : 'Dark')
  await click('[data-cb-settings-close]')
  await sleep(300)
  for (const width of [1049, 460]) {
    const calibrated = await setWidth(width)
    await sleep(450)
    const home = await read()
    await shot(`h156-home-${mode}-${width}`)
    await click('[data-cb-settings-open]')
    await scrollSectionIntoView('child-safe')
    const sheet = await read()
    const contrast = await evaluate(CONTRAST_JS)
    await shot(`h156-child-safe-${mode}-${width}`)
    await click('[data-cb-settings-close]')
    await clickNav('Parent Studio')
    await sleep(500)
    const studio = await read()
    await shot(`h156-studio-${mode}-${width}`)
    facts.frames.push({ mode, width, calibrated, home, sheet, studio, contrast })
    await clickNav('Home')
    await clearWidth()
  }
}

// ── 200% text at 460: the child-safe line and the section still fit ───────────────────────────
await setWidth(460)
await evaluate(
  `document.documentElement.style.setProperty('font-size', '32px', 'important')`
)
await sleep(500)
await clickNav('Home')
facts.text200Home = await read()
await shot('h156-text200-home-light-460')
await click('[data-cb-settings-open]')
await scrollSectionIntoView('child-safe')
facts.text200Sheet = await read()
await shot('h156-text200-child-safe-light-460')
await click('[data-cb-settings-close]')
await clearWidth()
await evaluate(`document.documentElement.style.removeProperty('font-size')`)

facts.final = await read()
writeFileSync(resolve(OUT, 'h156-facts.json'), JSON.stringify(facts, null, 2))
console.log(
  JSON.stringify(
    {
      homeLine: facts.homeInitial.lineText,
      childSafe: facts.homeInitial.childSafe,
      session: facts.homeInitial.sessionMinutes,
      sections: facts.sheetOpen.sections,
      rules: facts.sheetOpen.childSafeRules,
      sessionOptions: facts.sheetOpen.sessionOptionHeights,
      sessionStore: facts.afterSessionTwenty.stored,
      afterReset: facts.afterSessionReset.controls['session-length'],
      studioText: (facts.studio.bodyText || '').slice(0, 240),
      studioChildSafe: facts.studio.childSafeText,
      escapeFocus: facts.studioAfterEscape.focus,
      parentEvidence: facts.studioPlan.parentEvidence,
      contrast: facts.childSafeContrast,
      frames: facts.frames.map((frame) => ({
        mode: frame.mode,
        width: frame.width,
        inner: frame.calibrated.inner,
        scope: frame.home.scope,
        sheetWidth: frame.sheet.sheetWidth,
        overflow: frame.home.horizontalOverflow,
        sheetOverflow: frame.sheet.horizontalOverflow,
        destination: frame.studio.destination
      }))
    },
    null,
    2
  )
)
socket.close()
