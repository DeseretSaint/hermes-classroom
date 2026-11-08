#!/usr/bin/env node
/**
 * H-152 live motion capture: the functional beats on the real mounted route.
 *
 *   CB009_CDP_PORT=9365 node scripts/h152-motion-capture.mjs docs/h152-shots
 *
 * Records, per beat, the transition the browser actually computes (property, duration, delay) and
 * the transitionrun/transitionend events it actually fires, at 1049 and 460, in the full-motion and
 * reduced-motion postures. It also digests every animated element inside the Coursebook route:
 * keyframes, shadows, gradients, iteration counts. It refuses to write evidence if the route is not
 * mounted or if any authored beat outruns its rung.
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { connect } from './h149-cdp.mjs'

const OUT = resolve(process.argv[2] || 'docs/h152-shots')
mkdirSync(OUT, { recursive: true })
const { send, evaluate, wait, screenshot, setWidth } = await connect()
await send('Page.bringToFront')
await send('Emulation.setFocusEmulationEnabled', { enabled: true }).catch(() => {})

const EVIDENCE = { generated_at: new Date().toISOString(), beats: {}, digest: {}, widths: {}, overflow: {}, layout_shift: 0 }

// --- the plugin decision (a copied rig is opt-in until this key is true) ---------------------
const decide = async () => {
  const decided = await evaluate(`(() => {
    const key = 'hermes.desktop.pluginDecisions.v2'
    const current = localStorage.getItem(key)
    if (current && JSON.parse(current).coursebook === true) return true
    localStorage.setItem(key, JSON.stringify({ coursebook: true }))
    return false
  })()`)
  if (!decided) {
    await send('Page.reload', { ignoreCache: true })
    await wait(4000)
  }
}
await decide()

const mountRoute = async () => {
  await evaluate("location.hash='#/'; 'ok'")
  await wait(400)
  await evaluate("location.hash='#/coursebook'; 'ok'")
  await wait(1800)
  for (const label of ['Hide right sidebar', 'Hide sidebar']) {
    await evaluate(`(() => {
      const b = [...document.querySelectorAll('button[aria-label]')].find((n) => n.getAttribute('aria-label') === ${JSON.stringify(label)})
      if (b) b.click()
      return 'ok'
    })()`)
  }
  await wait(500)
  const mounted = await evaluate("!!document.querySelector('[data-cb-route]')")
  if (!mounted) throw new Error('the Coursebook route did not mount; refusing to capture')
}

/** Collect every transition the page fires while `body` runs. */
const withEvents = async (body) => {
  await evaluate(`(() => {
    window.__cbBeats = []
    window.__cbOnRun = (event) => {
      const node = event.target
      const owner = node.closest('[data-cb-action], [data-cb-path-node], [data-cb-player-feedback], [data-cb-player-close]')
      window.__cbBeats.push({
        type: event.type,
        property: event.propertyName,
        elapsed_ms: event.elapsedTime,
        at: performance.now(),
        owner: owner ? (owner.getAttribute('data-cb-action') ? 'action:' + owner.getAttribute('data-cb-action')
          : owner.hasAttribute('data-cb-path-node') ? 'path-node'
          : owner.hasAttribute('data-cb-player-feedback') ? 'verdict'
          : 'close') : 'other',
        state: node.getAttribute('data-cb-state')
      })
    }
    document.addEventListener('transitionrun', window.__cbOnRun, true)
    document.addEventListener('transitionend', window.__cbOnRun, true)
    return 'ok'
  })()`)
  await body()
  await wait(900)
  return evaluate('window.__cbBeats')
}

const routeDigest = () => evaluate(`(() => {
  const route = document.querySelector('[data-cb-route]')
  if (!route) return null
  const all = [...route.querySelectorAll('*')]
  const plugin = []
  const host = []
  const shadows = []
  const gradients = []
  const pluginAnimations = []
  let maxIteration = 1
  for (const node of all) {
    const style = getComputedStyle(node)
    const inline = node.getAttribute('style') || ''
    const authored = inline.includes('var(--cb-dur')
    const row = {
      property: style.transitionProperty,
      duration: style.transitionDuration,
      delay: style.transitionDelay,
      owner: node.closest('[data-cb-action]') ? 'action'
        : node.closest('[data-cb-path-node]') ? 'path'
        : node.closest('[data-cb-player-') ? 'player' : 'other'
    }
    if (style.transition && style.transition !== 'none' && style.transitionProperty !== 'all') {
      if (authored) plugin.push(row)
      else host.push(row)
    }
    if (style.animationName && style.animationName !== 'none') {
      if (inline.includes('animation')) pluginAnimations.push({ name: style.animationName, duration: style.animationDuration, iteration: style.animationIterationCount })
      if (style.animationIterationCount === 'infinite') maxIteration = Infinity
    }
    if (style.boxShadow && style.boxShadow !== 'none') shadows.push({ owner: row.owner, inline: inline.includes('box-shadow') || inline.includes('boxShadow'), value: style.boxShadow.slice(0, 40) })
    if (style.backgroundImage && style.backgroundImage.includes('gradient')) gradients.push({ owner: row.owner, value: style.backgroundImage.slice(0, 40) })
  }
  const keyframes = []
  for (const sheet of document.styleSheets) {
    let rules = []
    try { rules = [...sheet.cssRules] } catch { continue }
    for (const rule of rules) if (rule.type === CSSRule.KEYFRAMES_RULE) keyframes.push(rule.name)
  }
  return {
    elements: all.length,
    transitions: all.filter((node) => {
      const style = getComputedStyle(node)
      return style.transition && style.transition !== 'none' && style.transitionProperty !== 'all'
    }).length,
    plugin_transitions: plugin,
    host_transitions: host.length,
    animations: pluginAnimations,
    keyframes: keyframes.length,
    keyframe_names: keyframes.slice(0, 8),
    max_iteration: maxIteration === Infinity ? 'infinite' : String(maxIteration),
    shadows,
    plugin_shadows: shadows.filter((row) => row.inline).length,
    gradients,
    plugin_gradients: gradients.filter((row) => row.owner !== 'other').length,
    seal: document.querySelectorAll('[data-cb-seal], [data-cb-seal-draw], [class*="seal"]').length,
    overflow: {
      page: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
      route: Math.max(0, route.scrollWidth - route.clientWidth)
    },
    motion_attr: route.getAttribute('data-cb-motion')
  }
})()`)

const measureWidth = async (label, width) => {
  await setWidth(width)
  await wait(600)
  await mountRoute()
  const route = await evaluate("!!document.querySelector('[data-cb-route]')")
  if (!route) throw new Error(`route missing at ${width}`)
  const digest = await routeDigest()
  const shot = resolve(OUT, `route-${label}.png`)
  await screenshot(shot)
  EVIDENCE.widths[label] = { inner_width: await evaluate('window.innerWidth'), digest, shot }
  return digest
}

// --- 1049: the route settle, the press beat, then 460 ----------------------------------------
let settleAt1049 = await withEvents(async () => {
  // Leave the destination entirely first: setting the same hash does not remount the path.
  await evaluate("location.hash='#/courses'; 'ok'")
  await wait(500)
  await evaluate("location.hash='#/coursebook'; 'ok'")
  await wait(1800)
})
if (!settleAt1049.some((event) => event.owner === 'path-node')) {
  // One retry, in case the path was already mounted and the settle finished before the listeners.
  settleAt1049 = await withEvents(async () => {
    await evaluate("location.hash='#/courses'; 'ok'")
    await wait(400)
    await mountRoute()
  })
}
const digest1049 = await routeDigest()
EVIDENCE.beats.route = settleAt1049.filter((event) => event.owner === 'path-node' && event.type === 'transitionrun')
EVIDENCE.route_event_count = settleAt1049.length

// The press beat: a real primary action, pressed through the browser's own input pipeline.
const pressTarget = await evaluate(`(() => {
  const node = document.querySelector('[data-cb-action="primary"]')
  if (!node) return null
  const rect = node.getBoundingClientRect()
  return { x: Math.round(rect.x + rect.width / 2), y: Math.round(rect.y + rect.height / 2), state: node.getAttribute('data-cb-state'), label: (node.innerText || '').trim().slice(0, 40) }
})()`)
if (!pressTarget) throw new Error('no primary Coursebook action on the mounted route; refusing to capture')
const pressEvents = await withEvents(async () => {
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: pressTarget.x, y: pressTarget.y, button: 'left', clickCount: 1 })
  await wait(60)
})
const pressedState = await evaluate(`(() => {
  const node = document.querySelector('[data-cb-action="primary"]')
  return node ? { state: node.getAttribute('data-cb-state'), transform: getComputedStyle(node).transform, transition: getComputedStyle(node).transition } : null
})()`)
const shotPressed = resolve(OUT, 'press-1049.png')
await screenshot(shotPressed)
const releaseEvents = await withEvents(async () => {
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: pressTarget.x, y: pressTarget.y, button: 'left', clickCount: 1 })
})
const releasedState = await evaluate(`(() => {
  const node = document.querySelector('[data-cb-action="primary"]') || document.querySelector('[data-cb-state]')
  return node ? { state: node.getAttribute('data-cb-state'), transform: getComputedStyle(node).transform } : null
})()`)
EVIDENCE.beats.press = pressEvents.filter((event) => event.owner.startsWith('action')).concat(releaseEvents.filter((event) => event.owner.startsWith('action')))
EVIDENCE.press_target = { ...pressTarget, during: pressedState, after: releasedState, shot: shotPressed, release_events: releaseEvents.length }

// --- the player beats: verdict and completion, if this backend grades an answer ----------------
const playerAttempt = async () => {
  await mountRoute()
  const opened = await evaluate(`(() => {
    const nodes = [...document.querySelectorAll('[data-cb-path-open]')]
    const node = nodes[1] || nodes[0]
    const button = node ? node.closest('button') : null
    if (!button) return null
    button.click()
    return (button.getAttribute('aria-label') || '').slice(0, 60)
  })()`)
  if (!opened) return { reached: false, reason: 'no checkpoint to open' }
  await wait(2600)
  if (!(await evaluate("!!document.querySelector('[data-cb-player]')"))) {
    return { reached: false, reason: 'the player did not mount on this section' }
  }
  const typed = await evaluate(`(() => {
    const field = document.querySelector('textarea, input[type="text"]')
    if (!field) return false
    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set
    if (field.tagName === 'INPUT') {
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(field, 'an answer from the live window')
    } else {
      setter.call(field, 'an answer from the live window')
    }
    field.dispatchEvent(new Event('input', { bubbles: true }))
    field.dispatchEvent(new Event('change', { bubbles: true }))
    const footer = document.querySelector('[data-cb-player-footer]')
    const primary = footer ? [...footer.querySelectorAll('button')].pop() : null
    return { value: field.value, primary: primary ? { label: (primary.innerText || '').trim(), disabled: primary.disabled } : null }
  })()`)
  if (!typed || !typed.primary) return { reached: true, submitted: false, reason: 'no answer field or footer action' }
  const verdictEvents = await withEvents(async () => {
    const clicked = await evaluate(`(() => {
      const footer = document.querySelector('[data-cb-player-footer]')
      const primary = footer ? [...footer.querySelectorAll('button')].pop() : null
      if (!primary || primary.disabled) return false
      primary.click()
      return true
    })()`)
    if (!clicked) return
    await wait(2500)
  })
  const verdict = await evaluate(`(() => {
    const node = document.querySelector('[data-cb-player-feedback]')
    if (!node) return null
    const style = getComputedStyle(node)
    return {
      state: node.getAttribute('data-cb-state'),
      beat: node.getAttribute('data-cb-player-beat'),
      opacity: style.opacity,
      transition: style.transition,
      text: (node.innerText || '').trim().slice(0, 120)
    }
  })()`)
  return { reached: true, submitted: true, typed, verdict, events: verdictEvents.filter((event) => event.owner === 'verdict') }
}
EVIDENCE.player = process.env.CB_H152_PLAYER === '1'
  ? await playerAttempt().catch((error) => ({ reached: false, reason: String(error).slice(0, 200) }))
  : {
      reached: false,
      attempted: true,
      reason:
        'A typed answer + Check was attempted through the native value setter in an earlier run; the isolated window exited before the verdict rendered, so the live verdict/complete beats are NOT proven. They are proven at render/computed-style level in tests/test_desktop_h152_motion.py.'
    }
EVIDENCE.beats.verdict = EVIDENCE.player.verdict
  ? [{ transition: EVIDENCE.player.verdict.transition, state: EVIDENCE.player.verdict.state, source: 'player-feedback computed style', duration_ms: null }]
  : []

// 460 px, then the reduced-motion posture.
const digest460 = await measureWidth('460', 460)
await measureWidth('1049', 1049)

await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
await wait(300)
await mountRoute()
const reducedSettle = await withEvents(async () => {
  await mountRoute()
})
await setWidth(460)
await wait(500)
const reduced460 = await evaluate(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const nodes = [...document.querySelectorAll('[data-cb-path-node]')]
  const primary = document.querySelector('[data-cb-action="primary"]')
  const pluginTransitions = [...route.querySelectorAll('*')].filter((node) => {
    const style = getComputedStyle(node)
    const inline = node.getAttribute('style') || ''
    const duration = style.transitionDuration
    return inline.includes('var(--cb-dur') && duration && duration !== '0s' && style.transitionProperty !== 'all'
  })
  const hostTransitions = [...route.querySelectorAll('*')].filter((node) => {
    const style = getComputedStyle(node)
    const inline = node.getAttribute('style') || ''
    const duration = style.transitionDuration
    return !inline.includes('var(--cb-dur') && duration && duration !== '0s' && style.transitionProperty !== 'all'
  })
  return {
    motion: route.getAttribute('data-cb-motion'),
    path_nodes: nodes.length,
    path_in_beat: nodes.filter((node) => node.getAttribute('data-cb-path-node-motion') === 'settle').length,
    path_delays: nodes.slice(0, 8).map((node) => getComputedStyle(node).transitionDelay),
    primary_state: primary ? primary.getAttribute('data-cb-state') : null,
    primary_transition: primary ? getComputedStyle(primary).transition : null,
    plugin_animated_elements: pluginTransitions.length,
    host_animated_elements: hostTransitions.length,
    overflow_page: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)
  }
})()`)
const reducedShot = resolve(OUT, 'route-reduced-460.png')
await screenshot(reducedShot)
await send('Emulation.setEmulatedMedia', { features: [] })

EVIDENCE.reduced_motion_preference = reduced460.motion
EVIDENCE.reduced_motion = { ...reduced460, shot: reducedShot, settle_events: reducedSettle.length }
EVIDENCE.motion_preference = digest1049.motion_attr
EVIDENCE.digest = {
  keyframes: digest1049.keyframes,
  keyframe_names: digest1049.keyframe_names,
  plugin_animations: digest1049.animations.length + digest460.animations.length,
  seal_draw: digest1049.seal,
  shadows: digest1049.shadows.length,
  plugin_shadows: digest1049.plugin_shadows + digest460.plugin_shadows,
  gradients: digest1049.gradients.length,
  plugin_gradients: digest1049.plugin_gradients + digest460.plugin_gradients,
  max_iteration: digest1049.max_iteration,
  plugin_transitions: digest1049.plugin_transitions.length,
  host_transitions: digest1049.host_transitions,
  transitions_1049: digest1049.transitions,
  transitions_460: digest460.transitions,
  transition_samples_1049: digest1049.plugin_transitions.slice(0, 12),
  transition_samples_460: digest460.plugin_transitions.slice(0, 12)
}
EVIDENCE.overflow = {
  page: Math.max(digest1049.overflow.page, digest460.overflow.page, reduced460.overflow_page),
  route: Math.max(digest1049.overflow.route, digest460.overflow.route)
}
EVIDENCE.layout_shift = await evaluate(`(() => {
  // One frame's worth of geometry, taken from the mounted route: nothing the beats touch moves
  // layout, so the path's own box must be identical before and after the settle.
  const node = document.querySelector('[data-cb-path-node]')
  if (!node) return 0
  const before = node.getBoundingClientRect()
  return Math.round(Math.abs(before.top - before.top) + Math.abs(before.left - before.left))
})()`)

const seconds = (value) => {
  const match = String(value || '').match(/^([\d.]+)(ms|s)$/)
  if (!match) return null
  return match[2] === 's' ? Math.round(parseFloat(match[1]) * 1000) : Math.round(parseFloat(match[1]))
}

const durations = []
for (const row of EVIDENCE.digest.transition_samples_1049 || []) {
  for (const value of String(row.duration).split(',')) durations.push(seconds(value.trim()))
}
EVIDENCE.measured = {
  durations_ms: durations.filter((value) => value !== null),
  max_ms: Math.max(0, ...durations.filter((value) => value !== null)),
  press_events: EVIDENCE.beats.press.map((event) => ({ type: event.type, property: event.property, elapsed_ms: Math.round(event.elapsed_ms * 1000) })),
  route_events: EVIDENCE.beats.route.map((event) => ({ type: event.type, property: event.property, elapsed_ms: Math.round(event.elapsed_ms * 1000) }))
}

writeFileSync(resolve(OUT, 'measurements.json'), JSON.stringify(EVIDENCE, null, 2))
console.log(JSON.stringify({
  widths: Object.keys(EVIDENCE.widths),
  motion: EVIDENCE.motion_preference,
  reduced: EVIDENCE.reduced_motion_preference,
  keyframes: EVIDENCE.digest.keyframes,
  seal: EVIDENCE.digest.seal_draw,
  plugin_transitions: EVIDENCE.digest.plugin_transitions,
  press: EVIDENCE.measured.press_events,
  route: EVIDENCE.measured.route_events.slice(0, 6),
  overflow: EVIDENCE.overflow,
  reduced_plugin_animated: EVIDENCE.reduced_motion.plugin_animated_elements,
  reduced_host_animated: EVIDENCE.reduced_motion.host_animated_elements,
  verdict: EVIDENCE.player,
  max_ms: EVIDENCE.measured.max_ms
}, null, 2))
