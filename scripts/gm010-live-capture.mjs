#!/usr/bin/env node
/**
 * GM-010 — capture the Game play layer from the isolated live window.
 *
 *   CB015_CDP_PORT=9365 COURSEBOOK_TEST_STATE=~/.hermes/coursebook-test-gm010 \
 *     node scripts/gm010-live-capture.mjs
 *
 * Frames: dark + light at 1049/900/460, 460 at 200% text, and two keyboard frames that show the
 * `Game feedback` switch driven by Tab+Space (the band is absent, the course path is untouched).
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createHash } from 'node:crypto'
import { connect } from './cb015-lib.mjs'

const OUT = resolve('docs/visual-review/gm-010')
mkdirSync(OUT, { recursive: true })
const wait = (ms) => new Promise((done) => setTimeout(done, ms))
const cdp = await connect()
await cdp.send('Page.enable')
await cdp.send('Runtime.enable')
const withTimeout = (p, ms, label) =>
  Promise.race([p, new Promise((_, fail) => setTimeout(() => fail(new Error(`timeout: ${label}`)), ms))])
const send = (method, params = {}) => withTimeout(cdp.send(method, params), 60000, method)
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text)
  return r.result.value
}
const shot = async (name) => {
  const png = await send('Page.captureScreenshot', { format: 'png' })
  const bytes = Buffer.from(png.data, 'base64')
  const path = resolve(OUT, name)
  writeFileSync(path, bytes)
  return { name, md5: createHash('md5').update(bytes).digest('hex') }
}
// Calibrate the viewport override: this Electron build paints ~0.896 zoom, so a raw 460 lands wide.
const setWidth = async (target) => {
  let override = target
  for (let i = 0; i < 6; i += 1) {
    await send('Emulation.setDeviceMetricsOverride', {
      width: override, height: 1400, deviceScaleFactor: 1, mobile: false
    })
    await wait(250)
    const inner = await evaluate('window.innerWidth')
    if (inner === target) return
    override = Math.round((override * target) / inner)
  }
}
const setText = async (font) => {
  await evaluate(font
    ? `document.documentElement.style.setProperty('font-size', ${JSON.stringify(font)}, 'important')`
    : "document.documentElement.style.removeProperty('font-size')")
  await wait(300)
}
const waitFor = async (expression, label) => {
  for (let i = 0; i < 60; i += 1) {
    if (await evaluate(expression)) return
    await wait(250)
  }
  throw new Error(`waitFor: ${label}`)
}

const openCourseHome = async () => {
  await evaluate("location.hash = '#/'")
  await wait(700)
  await evaluate("location.hash = '#/coursebook'")
  await wait(2500)
  const clicked = await evaluate(`(() => {
    const card = [...document.querySelectorAll('[data-cb-home-card]')].find((n) => /Japanese at home/.test(n.innerText))
    if (!card) return false
    ;(card.querySelector('button, a') || card).click()
    return true
  })()`)
  if (!clicked) throw new Error('no Japanese at home card on the shelf')
  await waitFor("!!document.querySelector('[data-cb-course-home], [data-cb-course-detail]')", 'course home')
  await wait(1200)
}

const openSettings = async () => {
  if (await evaluate("Boolean(document.querySelector('[data-cb-settings-control=\"appearance\"]'))")) return
  const opened = await evaluate(`(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.getAttribute('aria-label') === 'Open Coursebook settings')
    if (!b) return false
    b.click(); return true
  })()`)
  if (!opened) throw new Error('no settings button')
  await waitFor("!!document.querySelector('[data-cb-settings-control=\"appearance\"]')", 'settings sheet')
  await wait(350)
}
const closeSettings = async () => {
  await evaluate("document.querySelector('[data-cb-settings-close]')?.click()")
  await wait(450)
}
const setAppearance = async (mode) => {
  await openSettings()
  const clicked = await evaluate(`(() => {
    const root = document.querySelector('[data-cb-settings-control="appearance"]')
    if (!root) return 'no-control'
    const btn = [...root.querySelectorAll('button')].find((b) => b.innerText.trim().toLowerCase() === ${JSON.stringify(mode)})
    if (!btn) return 'no-option:' + root.innerText.replace(/\\s+/g, ' ').slice(0, 60)
    btn.click(); return 'ok'
  })()`)
  await wait(400)
  await closeSettings()
  const painted = await evaluate("document.querySelector('[data-cb-route]')?.getAttribute('data-cb-scope')")
  if (painted !== mode) throw new Error(`appearance ${mode} -> ${painted} (${clicked})`)
  await wait(500)
}

const TAB = async () => {
  for (const type of ['keyDown', 'keyUp']) {
    await send('Input.dispatchKeyEvent', { type, key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 })
  }
  await wait(120)
}
const SPACE = async () => {
  for (const type of ['keyDown', 'keyUp']) {
    await send('Input.dispatchKeyEvent', {
      type, key: ' ', code: 'Space', windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 32, text: type === 'keyDown' ? ' ' : undefined
    })
  }
  await wait(500)
}

const state = async () => ({
  hash: await evaluate('location.hash'),
  innerWidth: await evaluate('window.innerWidth'),
  rootFont: await evaluate('getComputedStyle(document.documentElement).fontSize'),
  scope: await evaluate("document.querySelector('[data-cb-route]')?.getAttribute('data-cb-scope') || null"),
  overflow: await evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth'),
  game: await evaluate("document.querySelector('[data-cb-game]')?.getAttribute('data-cb-game') || null"),
  xp: await evaluate("document.querySelector('[data-cb-game-xp]')?.getAttribute('data-cb-game-xp') || null"),
  journal: await evaluate("document.querySelector('[data-cb-game-journal]')?.getAttribute('data-cb-game-journal') || null"),
  cards: await evaluate("document.querySelectorAll('[data-cb-game-card]').length"),
  continueVisible: await evaluate("Boolean(document.querySelector('[data-cb-trail]'))"),
  objectiveVisible: await evaluate("/Section 1 of 4/.test(document.querySelector('[data-cb-trail]')?.innerText || '')"),
  checkVisible: await evaluate("/finish its check/.test(document.querySelector('[data-cb-trail]')?.innerText || '')"),
  text: await evaluate("(document.querySelector('[data-cb-game]')?.innerText || '').replace(/\\s+/g, ' ').slice(0, 240)"),
  forbidden: await evaluate(`(() => {
    const text = (document.querySelector('[data-cb-route]')?.innerText || '').toLowerCase()
    return ['mastery', 'mastered', 'proficien', 'verified skill', 'star rating', '5 stars', 'rating', 'out of 5']
      .filter((word) => new RegExp('(^|[^a-z0-9])' + word + '($|[^a-z0-9])').test(text))
  })()`)
})

await closeSettings()
await openCourseHome()
const frames = []
const capture = async (name, { width, font = null, theme = 'dark' }) => {
  await setWidth(width)
  await setText(font)
  await wait(700)
  const s = await state()
  frames.push({ frame: name, ...s, md5: (await shot(name)).md5 })
  return s
}

// ---- The play layer, dark and light ----
for (const theme of ['dark', 'light']) {
  await setAppearance(theme)
  for (const [label, width, font] of [
    ['1049', 1049, null],
    ['900', 900, null],
    ['460', 460, null],
    ['460--200', 460, '32px']
  ]) {
    await capture(`game-home--${label}--${theme}.png`, { width, font, theme })
  }
}

// ---- Keyboard: the Game feedback switch, driven by Tab + Space, in light at 1049 ----
await setAppearance('light')
await openSettings()
// Tab until the focus lands on the Game feedback switch itself.
let tabs = 0
let reached = null
for (; tabs < 40; tabs += 1) {
  await TAB()
  reached = await evaluate(`(() => {
    const a = document.activeElement
    if (!a) return null
    return {
      tag: a.tagName,
      role: a.getAttribute('role'),
      checked: a.getAttribute('aria-checked'),
      label: a.getAttribute('aria-label'),
      text: (a.innerText || '').trim().slice(0, 40)
    }
  })()`)
  if (reached && reached.role === 'switch' && /show game feedback/i.test(reached.label || '')) break
  reached = null
}
if (!reached) throw new Error(`Game feedback switch not reachable by Tab (${tabs} tabs)`)
const outline = await evaluate("(() => { const a = document.activeElement; return a ? getComputedStyle(a).outlineStyle : null })()")
const ringState = await evaluate(`(() => {
  const w = document.querySelector('[data-cb-settings-toggle="game-feedback"]')
  if (!w) return null
  const s = getComputedStyle(w)
  return { attr: w.getAttribute('data-cb-settings-focus'), outline: [s.outlineStyle, s.outlineWidth, s.outlineColor].join(' ') }
})()`)
const focusFrame = await shot('game-feedback-focus--1049--light.png')
await SPACE()
const toggledOff = await evaluate(`(() => {
  const a = document.activeElement
  const sw = document.querySelector('[data-cb-settings-toggle="game-feedback"] button[role="switch"]')
  return {
    checked: Boolean(a && a.getAttribute('aria-checked') === 'true'),
    bandPresent: Boolean(document.querySelector('[data-cb-game]')),
    switchAriaChecked: sw ? sw.getAttribute('aria-checked') : null
  }
})()`)
await closeSettings()
await wait(600)
const offState = await capture('game-feedback-off--1049--light.png', { width: 1049 })
const offEvidence = {
  keyboard: {
    tabsToSwitch: tabs + 1,
    focused: reached,
    outlineStyle: outline,
    wrapperRing: ringState,
    focusFrame: focusFrame.name,
    switchAriaCheckedAfterSpace: toggledOff.switchAriaChecked,
    bandPresentWhileOff: toggledOff.bandPresent,
    bandAfterClose: offState.game
  }
}
// Restore the switch with the same keyboard path, then prove the band returns.
await openSettings()
let restoreTabs = 0
let restored = false
for (; restoreTabs < 40; restoreTabs += 1) {
  await TAB()
  const hit = await evaluate(`(() => {
    const a = document.activeElement
    return Boolean(a && a.getAttribute('role') === 'switch' && /show game feedback/i.test(a.getAttribute('aria-label') || ''))
  })()`)
  if (hit) { restored = true; break }
}
if (!restored) throw new Error('could not return to the Game feedback switch')
await SPACE()
const backOn = await evaluate("document.querySelector('[data-cb-settings-toggle=\"game-feedback\"] button[role=\"switch\"]')?.getAttribute('aria-checked')")
await closeSettings()
await wait(600)
await capture('game-feedback-restored--1049--light.png', { width: 1049 })
offEvidence.keyboard.restoreTabsToSwitch = restoreTabs + 1
offEvidence.keyboard.switchAriaCheckedAfterRestore = backOn
offEvidence.keyboard.bandRestored = await evaluate("document.querySelector('[data-cb-game]')?.getAttribute('data-cb-game') || null")

// Leave the rig as we found it: dark, 1049, 100% text, feedback on.
await setAppearance('dark')
await setWidth(1049)
await setText(null)
await wait(400)

const evidence = {
  capturedAt: new Date().toISOString(),
  route: 'course home (#/coursebook, data-cb-course-home)',
  engagementSource: 'engagement.read (cb.rpc v24)',
  keyboard: offEvidence.keyboard,
  frames
}
writeFileSync(resolve(OUT, 'live-evidence.json'), JSON.stringify(evidence, null, 2) + '\n')
console.log(JSON.stringify({ keyboard: offEvidence.keyboard, frames: frames.map((f) => ({ frame: f.frame, scope: f.scope, width: f.innerWidth, game: f.game, cards: f.cards, overflow: f.overflow, md5: f.md5 })) }, null, 2))
cdp.close()
