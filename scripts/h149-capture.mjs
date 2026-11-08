#!/usr/bin/env node
/**
 * H-149 live capture: the lesson player at 1049 / 900 / 460 in light and dark.
 *
 * Drives the real isolated Desktop window against the live cb.rpc backend: open the course, open
 * checkpoint 2 (the one section whose served document has blocks and a check), read the player
 * header/step/footer, type an answer, press Enter, read the verdict, continue to the close plate.
 * Refuses to write a screenshot if the player is not the mounted surface.
 *
 *   CB009_CDP_PORT=9359 node scripts/h149-capture.mjs docs/h149-shots
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { connect } from './h149-cdp.mjs'

const OUT = resolve(process.argv[2] || 'docs/h149-shots')
mkdirSync(OUT, { recursive: true })
const { send, evaluate, wait, screenshot, setWidth, clickSelector } = await connect()
await send('Page.bringToFront')
await send('Emulation.setFocusEmulationEnabled', { enabled: true }).catch(() => {})

const clickText = async (tag, label, exact = true) => {
  const ok = await evaluate(`(() => {
    const wanted = ${JSON.stringify(label)}
    const nodes = [...document.querySelectorAll(${JSON.stringify(tag)})]
    const node = nodes.find((n) => {
      const text = (n.innerText || '').trim()
      return ${exact ? 'text === wanted' : 'text.includes(wanted)'}
    })
    if (!node) return false
    node.click()
    return true
  })()`)
  return ok
}

// --- route ---------------------------------------------------------------------------------
await evaluate("location.hash='#/'; 'ok'")
await wait(500)
await evaluate("location.hash='#/coursebook'; 'ok'")
await wait(2000)
if (!(await evaluate("!!document.querySelector('[data-cb-route]')"))) {
  throw new Error('the Coursebook route did not mount; refusing to capture')
}
for (const label of ['Hide right sidebar', 'Hide sidebar']) {
  await evaluate(`(() => {
    const b = [...document.querySelectorAll('button[aria-label]')].find((n) => n.getAttribute('aria-label') === ${JSON.stringify(label)})
    if (b) b.click()
    return 'ok'
  })()`)
}
await wait(600)

// Open the demonstration course from the shelf, then checkpoint 2 on its path.
if (await evaluate("!!document.querySelector('[data-cb-course-shelf]')")) {
  const opened = await evaluate(`(() => {
    const row = [...document.querySelectorAll('button')].find((n) => (n.innerText || '').trim() === 'Open')
    if (row) { row.click(); return true }
    return false
  })()`)
  if (!opened) throw new Error('no Open control on the course shelf')
  await wait(2200)
}
const openedCheckpoint = await evaluate(`(() => {
  const nodes = [...document.querySelectorAll('button')]
  const node = nodes.find((n) => /^02\\b/.test((n.innerText || '').trim()))
  if (!node) return null
  node.click()
  return (node.innerText || '').trim().slice(0, 60)
})()`)
if (!openedCheckpoint) throw new Error('checkpoint 2 was not on the path')
await wait(2600)

const state = () =>
  evaluate(`(() => {
  const player = document.querySelector('[data-cb-player]')
  const step = document.querySelector('[data-cb-player-step]')
  const footer = document.querySelector('[data-cb-player-footer]')
  const primary = footer ? footer.querySelector('button') : null
  const bar = document.querySelector('[data-cb-player-bar]')
  const textarea = document.querySelector('#cb-attempt-answer')
  const route = document.querySelector('[data-cb-route]')
  const feedback = document.querySelector('[data-cb-player-feedback]')
  const close = document.querySelector('[data-cb-player-close]')
  const all = [...document.querySelectorAll('button')].filter((n) => n.offsetParent !== null)
  const primaryCount = all.filter((n) => n.getAttribute('data-variant') === 'default').length
  return {
    mounted: !!player,
    view: document.querySelector('[data-cb-lesson-view]')?.getAttribute('data-cb-lesson-view') || null,
    document: player?.getAttribute('data-cb-document') || null,
    bar: bar ? bar.innerText.replace(/\\n/g, ' | ') : null,
    step: step ? step.innerText : null,
    stepBlock: document.querySelector('[data-cb-player-step-block]')?.getAttribute('data-cb-player-step-block') || null,
    conceptChars: (document.querySelector('[data-cb-play-concept]')?.innerText || '').length,
    concept: (document.querySelector('[data-cb-play-concept]')?.innerText || '').slice(0, 240),
    checkMounted: !!document.querySelector('[data-cb-block-check]'),
    checkText: (document.querySelector('[data-cb-block-check]')?.innerText || '').slice(0, 300),
    footerText: footer ? footer.innerText.replace(/\\n/g, ' | ') : null,
    primaryLabel: primary ? (primary.innerText || '').trim() : null,
    primaryDisabled: primary ? primary.disabled : null,
    primaryCount,
    feedback: feedback ? feedback.getAttribute('data-cb-player-feedback') : null,
    feedbackText: feedback ? feedback.innerText.replace(/\\n/g, ' | ').slice(0, 500) : null,
    closeText: close ? close.innerText.replace(/\\n/g, ' | ') : null,
    overflowPage: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
    overflowRoute: route ? Math.max(0, route.scrollWidth - route.clientWidth) : null,
    routeWidth: route ? route.clientWidth : null,
    innerWidth: window.innerWidth,
    hasTextarea: !!textarea,
    textareaValue: textarea ? textarea.value : null,
    active: document.activeElement ? document.activeElement.tagName + '#' + (document.activeElement.id || '') : null
  }
})()`)

const measurements = {}
measurements.open = await state()
if (!measurements.open.mounted) {
  throw new Error(`the player did not mount: ${JSON.stringify(measurements.open)}`)
}

// --- truth: same document/check/evidence as the reference views ---------------------------------
measurements.reference = {}
for (const choice of ['Textbook', 'Guided', 'Game']) {
  const clicked = await evaluate(`(() => {
    const b = [...document.querySelectorAll('[data-cb-view-choice]')].find((n) => n.getAttribute('data-cb-view-choice') === ${JSON.stringify(choice === 'Game' ? 'player' : choice.toLowerCase())})
    if (!b || b.disabled) return false
    b.click()
    return true
  })()`)
  await wait(700)
  measurements.reference[choice] = {
    clicked,
    view: await evaluate("document.querySelector('[data-cb-lesson-view]')?.getAttribute('data-cb-lesson-view') || null"),
    document: await evaluate("document.querySelector('[data-cb-lesson-view]')?.getAttribute('data-cb-document') || null"),
    check: await evaluate("!!document.querySelector('[data-cb-block-check]') || !!document.querySelector('#cb-check-node')"),
    disabled: await evaluate(`(() => {
      const b = [...document.querySelectorAll('[data-cb-view-choice]')].find((n) => n.getAttribute('data-cb-view-choice') === '${choice === 'Game' ? 'player' : choice.toLowerCase()}')
      return b ? b.disabled : null
    })()`)
  }
}

// Back to the player for the interaction.
await evaluate(`(() => {
  const b = [...document.querySelectorAll('[data-cb-view-choice]')].find((n) => n.getAttribute('data-cb-view-choice') === 'player')
  if (b) b.click()
  return 'ok'
})()`)
await wait(800)

// --- type and press Enter ------------------------------------------------------------------------
// The check lives on the block that carries it, which may not be the first step. Walk the footer
// (`Continue`) until the response is on screen; the player never skips the check.
measurements.walk = []
for (let i = 0; i < 4; i += 1) {
  const hasField = await evaluate("!!document.querySelector('#cb-attempt-answer')")
  if (hasField) break
  const label = await evaluate(`(() => {
    const b = document.querySelector('[data-cb-player-footer] button')
    if (!b || b.disabled) return null
    const text = (b.innerText || '').trim()
    b.click()
    return text
  })()`)
  measurements.walk.push({ label, step: await evaluate("document.querySelector('[data-cb-player-step]')?.innerText || null") })
  await wait(1200)
}
const typed = await clickSelector('#cb-attempt-answer')
if (!typed) throw new Error('the answer field was not on the check step')
await send('Input.insertText', { text: 'A calm, everyday line to someone close, not a direct confession.' })
await wait(700)
measurements.typed = await state()

// Keyboard only: Tab from the answer field to the footer primary, then Enter.
await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab' })
await wait(400)
measurements.afterTab = await evaluate(`(() => {
  const active = document.activeElement
  return {
    tag: active ? active.tagName : null,
    text: active ? (active.innerText || '').trim().slice(0, 40) : null,
    inPlayer: !!(active && active.closest('[data-cb-player]'))
  }
})()`)
await send('Input.dispatchKeyEvent', {
  type: 'keyDown',
  key: 'Enter',
  code: 'Enter',
  windowsVirtualKeyCode: 13,
  nativeVirtualKeyCode: 13
})
await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter' })
await wait(4000)
measurements.afterEnter = await state()

// --- screenshots ---------------------------------------------------------------------------------
const shot = async (name) => {
  await screenshot(resolve(OUT, `${name}.png`))
}
for (const [mode, force] of [
  ['dark', 'dark'],
  ['light', 'light']
]) {
  await evaluate(`(() => {
    document.documentElement.setAttribute('data-force-theme', ${JSON.stringify(force)})
    return 'ok'
  })()`)
  await wait(400)
  for (const width of [1049, 900, 460]) {
    const inner = await setWidth(width)
    await wait(450)
    const snapshot = await state()
    measurements[`${mode}-${width}`] = snapshot
    if (Math.abs(snapshot.innerWidth - width) > 1) throw new Error(`width ${width} measured ${snapshot.innerWidth}`)
    await shot(`player-${mode}-${width}`)
    // The Electron zoom lands 460 at 459 CSS px; the tolerance is stated in the measurements.
  }
}

// --- 200% text and reduced motion ----------------------------------------------------------------
await setWidth(460)
await evaluate("document.documentElement.style.setProperty('font-size','32px','important'); 'ok'")
await wait(500)
measurements.text200 = await state()
await shot('player-text200-460')
await evaluate("document.documentElement.style.removeProperty('font-size'); 'ok'")

await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
await wait(400)
await evaluate(`(() => {
  const player = document.querySelector('[data-cb-player]')
  const styles = player ? [...player.querySelectorAll('*')].map((n) => {
    const s = getComputedStyle(n)
    return { transition: s.transitionDuration, animation: s.animationName + ' ' + s.animationDuration }
  }) : []
  return 'ok'
})()`)
measurements.reducedMotion = await evaluate(`(() => {
  const moving = [...document.querySelectorAll('[data-cb-player] *')].filter((n) => {
    const s = getComputedStyle(n)
    return (parseFloat(s.transitionDuration) || 0) > 0 || (s.animationName && s.animationName !== 'none')
  })
  return { moving: moving.length, names: moving.slice(0, 4).map((n) => n.tagName + '.' + n.className) }
})()`)
await shot('player-reduced-motion-460')
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })
await setWidth(1049)

// --- continue to the close ------------------------------------------------------------------------
const advance = async () => {
  const clicked = await evaluate(`(() => {
    const b = document.querySelector('[data-cb-player-footer] button')
    if (!b || b.disabled) return null
    const label = (b.innerText || '').trim()
    b.click()
    return label
  })()`)
  await wait(1600)
  return clicked
}
measurements.advance = []
for (let i = 0; i < 4; i += 1) {
  const label = await advance()
  const snapshot = await state()
  measurements.advance.push({ label, step: snapshot.step, close: Boolean(snapshot.closeText), primary: snapshot.primaryLabel })
  if (snapshot.closeText) break
}
measurements.close = await state()
await shot('player-close-1049')
await setWidth(460)
await wait(400)
await shot('player-close-460')
await setWidth(1049)

writeFileSync(resolve(OUT, 'measurements.json'), JSON.stringify(measurements, null, 1))
console.log(JSON.stringify({
  open: measurements.open,
  reference: measurements.reference,
  typedPrimary: measurements.typed.primaryLabel,
  afterEnter: measurements.afterEnter,
  widths: ['dark-1049', 'dark-900', 'dark-460', 'light-1049', 'light-900', 'light-460'].map((k) => ({
    k,
    inner: measurements[k].innerWidth,
    route: measurements[k].routeWidth,
    overflowPage: measurements[k].overflowPage,
    overflowRoute: measurements[k].overflowRoute,
    primary: measurements[k].primaryLabel
  })),
  text200: { inner: measurements.text200.innerWidth, overflowRoute: measurements.text200.overflowRoute },
  reducedMotion: measurements.reducedMotion,
  advance: measurements.advance,
  close: measurements.close.closeText
}, null, 1))
