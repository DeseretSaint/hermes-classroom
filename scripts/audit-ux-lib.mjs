/**
 * Sentinel a11y/UX measurement library for the Coursebook Desktop route.
 *
 * Everything is measured from the live renderer: computed styles, real key events, real layout.
 * No fixture DOM, no injected CSS; only CDP emulation (viewport, root text size, media features).
 */
import { connect, setMode, writeJson } from './cb015-lib.mjs'

export const ROUTE = '[data-cb-route]'

export async function attach(port = process.env.CB015_CDP_PORT || '9351') {
  process.env.CB015_CDP_PORT = port
  return connect()
}

export async function setRootText(cdp, px) {
  await cdp.eval(`document.documentElement.style.fontSize = ${JSON.stringify(`${px}px`)}`)
}

/**
 * Set the CSS-pixel viewport. This window runs at a host zoom factor (outerWidth/innerWidth),
 * so the device-metrics width must be scaled by that factor to land on the requested CSS width.
 */
export async function setViewportCss(cdp, width, height) {
  const zoom = await cdp.eval('(outerWidth || innerWidth) / innerWidth')
  let deviceWidth = Math.round(width * zoom)
  let deviceHeight = Math.round(height * zoom)
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: deviceWidth,
    height: deviceHeight,
    deviceScaleFactor: 1,
    mobile: false
  })
  await cdp.wait(350)
  const got = await cdp.eval('innerWidth')
  if (Math.abs(got - width) > 6) {
    const factor = got / width
    deviceWidth = Math.round(deviceWidth * factor)
    deviceHeight = Math.round(deviceHeight * factor)
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: deviceWidth,
      height: deviceHeight,
      deviceScaleFactor: 1,
      mobile: false
    })
    await cdp.wait(350)
  }
  return { requested: { width, height }, got: await cdp.eval('JSON.stringify([innerWidth, innerHeight])') }
}

export async function clearRootText(cdp) {
  await cdp.eval(`document.documentElement.style.removeProperty('font-size')`)
}

export async function setReducedMotion(cdp, on) {
  await cdp.send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-motion', value: on ? 'reduce' : 'no-preference' }]
  })
  await cdp.wait(200)
}

export async function setForcedColors(cdp, on) {
  await cdp.send('Emulation.setEmulatedMedia', {
    features: [{ name: 'forced-colors', value: on ? 'active' : 'none' }]
  })
  await cdp.wait(200)
}

export async function setOffline(cdp, on) {
  await cdp.send('Network.emulateNetworkConditions', {
    offline: on,
    latency: 0,
    downloadThroughput: on ? 0 : -1,
    uploadThroughput: on ? 0 : -1
  })
  await cdp.wait(200)
}

const MEASURE = `(() => {
  const route = document.querySelector('${ROUTE}') || document.body
  const visible = (el) => {
    const cs = getComputedStyle(el)
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false
    const r = el.getBoundingClientRect()
    return r.width > 0 && r.height > 0
  }
  const nameOf = (el) => {
    const label = el.getAttribute('aria-label')
    if (label) return label.trim()
    const by = el.getAttribute('aria-labelledby')
    if (by) {
      const t = by.split(/\\s+/).map(id => document.getElementById(id)?.innerText || '').join(' ').trim()
      if (t) return t
    }
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') {
      const lab = el.labels && el.labels[0] ? el.labels[0].innerText.trim() : ''
      if (lab) return lab
      if (el.getAttribute('placeholder')) return el.getAttribute('placeholder').trim()
      if (el.type === 'checkbox' || el.type === 'radio') return el.value || ''
    }
    const img = el.tagName === 'IMG' ? (el.getAttribute('alt') || '') : ''
    if (img) return img.trim()
    return (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim()
  }
    const parseColor = (() => {
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    const cache = new Map()
    const parseSrgb = (value) => {
      const m = String(value).match(/^color\\(srgb\\s+([^)]+)\\)$/)
      if (!m) return null
      const parts = m[1].split(/[\\s/]+/).filter(Boolean).map(Number)
      if (parts.length < 3 || parts.some((n) => Number.isNaN(n))) return null
      return {
        r: Math.round(parts[0] * 255),
        g: Math.round(parts[1] * 255),
        b: Math.round(parts[2] * 255),
        a: parts.length > 3 ? parts[3] : 1
      }
    }
    return (value) => {
      if (!value) return null
      if (cache.has(value)) return cache.get(value)
      let out = parseSrgb(value)
      if (out) {
        cache.set(value, out)
        return out
      }
      ctx.fillStyle = '#000000'
      ctx.fillStyle = value
      let normalized = ctx.fillStyle
      if (typeof normalized !== 'string') normalized = null
      if (normalized && normalized.startsWith('#')) {
        const hex = normalized.length === 4
          ? normalized.slice(1).split('').map((c) => c + c).join('')
          : normalized.slice(1, 7)
        const num = parseInt(hex, 16)
        out = { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255, a: 1 }
      } else {
        const m = normalized && normalized.match(/rgba?\\(([^)]+)\\)/)
        if (m) {
          const parts = m[1].split(/[ ,/]+/).filter(Boolean).map(Number)
          out = { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 }
        } else out = null
      }
      cache.set(value, out)
      return out
    }
  })()
  const bgOf = (el) => {
    let node = el
    while (node && node !== document.documentElement) {
      const c = parseColor(getComputedStyle(node).backgroundColor)
      if (c && c.a > 0.5) return c
      node = node.parentElement
    }
    return parseColor(getComputedStyle(document.body).backgroundColor) || { r: 0, g: 0, b: 0, a: 1 }
  }
  const lum = (c) => {
    const f = (v) => {
      v /= 255
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)
    }
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b)
  }
  const ratio = (a, b) => {
    const l1 = lum(a), l2 = lum(b)
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
  }

  const docEl = document.scrollingElement || document.documentElement
  const overflowX = Math.max(0, docEl.scrollWidth - docEl.clientWidth)
  const routeRect = route.getBoundingClientRect()

  const clipped = []
  const contrast = []
  const unnamed = []
  const colorOnly = []
  const smallTargets = []
  const seenText = new Set()

  const walker = document.createTreeWalker(route, NodeFilter.SHOW_TEXT)
  const textNodes = []
  while (walker.nextNode()) textNodes.push(walker.currentNode)

  for (const node of textNodes) {
    const text = (node.nodeValue || '').replace(/\\s+/g, ' ').trim()
    if (!text) continue
    const el = node.parentElement
    if (!el || !visible(el)) continue
    if (/^(SCRIPT|STYLE)$/.test(el.tagName)) continue
    const cs = getComputedStyle(el)
    const key = el
    if (seenText.has(key)) continue
    seenText.add(key)
    const r = el.getBoundingClientRect()
    const elCs = cs
    const clips = (elCs.overflow !== 'visible' || elCs.overflowX !== 'visible' || elCs.overflowY !== 'visible')
    if (clips && (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1)) {
      clipped.push({ text: text.slice(0, 80), cls: String(el.className || '').slice(0, 90), sw: el.scrollWidth, cw: el.clientWidth, sh: el.scrollHeight, ch: el.clientHeight })
    }
    if (r.right > window.innerWidth + 1 || r.left < -1) {
      clipped.push({ text: text.slice(0, 80), cls: String(el.className || '').slice(0, 90), offscreenX: Math.round(Math.max(r.right - window.innerWidth, -r.left)) })
    }
    if (text.length >= 2) {
      let fg = parseColor(cs.color)
      const bg = bgOf(el)
      if (fg && bg && fg.a > 0.05) {
        if (fg.a < 1) {
          // composite a translucent foreground over its background before measuring
          fg = {
            r: Math.round(fg.r * fg.a + bg.r * (1 - fg.a)),
            g: Math.round(fg.g * fg.a + bg.g * (1 - fg.a)),
            b: Math.round(fg.b * fg.a + bg.b * (1 - fg.a)),
            a: 1
          }
        }
        const size = parseFloat(cs.fontSize)
        const bold = Number(cs.fontWeight) >= 700
        const large = size >= 24 || (size >= 18.66 && bold)
        const need = large ? 3 : 4.5
        const cr = ratio(fg, bg)
        if (cr + 0.02 < need) {
          contrast.push({ text: text.slice(0, 70), ratio: Math.round(cr * 100) / 100, need, size, fg: cs.color, bg: 'rgb(' + [bg.r, bg.g, bg.b].join(',') + ')' })
        }
      }
    }
  }

  // Clipping by an ancestor scroll box (text inside overflow:hidden that does not fit).
  for (const node of textNodes) {
    const text = (node.nodeValue || '').replace(/\\s+/g, ' ').trim()
    if (text.length < 2) continue
    const el = node.parentElement
    if (!el || !visible(el)) continue
    const r = el.getBoundingClientRect()
    let anc = el.parentElement
    while (anc && anc !== document.body) {
      const acs = getComputedStyle(anc)
      if (acs.overflow !== 'visible' || acs.overflowX !== 'visible' || acs.overflowY !== 'visible') {
        const ar = anc.getBoundingClientRect()
        // A scroll box (auto/scroll) is not clipping: the content stays reachable by scrolling.
        const clipsX = (acs.overflowX === 'hidden' || acs.overflowX === 'clip')
        const clipsY = (acs.overflowY === 'hidden' || acs.overflowY === 'clip')
        if ((clipsX && (r.right > ar.right + 2 || r.left < ar.left - 2)) ||
            (clipsY && (r.bottom > ar.bottom + 2 || r.top < ar.top - 2))) {
          const key = text.slice(0, 60) + '|' + Math.round(r.top)
          if (!clipped.some((c) => c.ancestorClip && c.key === key)) {
            clipped.push({ text: text.slice(0, 70), ancestorClip: true, key, cls: String(el.className || '').slice(0, 70), overflow: acs.overflowX + '/' + acs.overflowY })
          }
        }
        break
      }
      anc = anc.parentElement
    }
  }

  const controls = [...route.querySelectorAll('button, a[href], input, select, textarea, [role="button"], [role="tab"], [role="checkbox"], [role="switch"], [role="menuitem"], [tabindex]:not([tabindex="-1"])')]
    .filter(visible)
  for (const el of controls) {
    const name = nameOf(el)
    if (!name) unnamed.push({ tag: el.tagName, role: el.getAttribute('role'), cls: String(el.className || '').slice(0, 80) })
    const r = el.getBoundingClientRect()
    if (r.width < 20 || r.height < 20) smallTargets.push({ name: name.slice(0, 40), w: Math.round(r.width), h: Math.round(r.height) })
  }

  // Controls whose only visible content is an icon (no text anywhere in subtree).
  for (const el of controls) {
    const own = (el.innerText || '').replace(/\\s+/g, ' ').trim()
    const label = el.getAttribute('aria-label') || el.getAttribute('title') || ''
    const hasSvg = !!el.querySelector('svg, i.codicon, [class*="codicon"]')
    if (!own && hasSvg && !label) colorOnly.push({ kind: 'icon-control-without-name', cls: String(el.className || '').slice(0, 80) })
  }
  // Status chips/badges must carry words, not only a colour.
  const chips = [...route.querySelectorAll('[class*="badge"], [data-cb-badge], [role="status"]')]
    .filter(visible)
  for (const el of chips) {
    const words = (el.innerText || '').replace(/\\s+/g, ' ').trim()
    if (!words) colorOnly.push({ kind: 'status-without-text', cls: String(el.className || '').slice(0, 90) })
  }

  const live = [...route.querySelectorAll('[aria-live], [role="status"], [role="alert"], [role="log"]')].map((el) => ({
    role: el.getAttribute('role'), live: el.getAttribute('aria-live'), text: (el.innerText || '').slice(0, 60)
  }))

  const headings = [...route.querySelectorAll('h1,h2,h3,h4,[role="heading"]')].filter(visible).map((el) => ({
    level: el.tagName === 'H1' ? 1 : el.tagName === 'H2' ? 2 : el.tagName === 'H3' ? 3 : el.tagName === 'H4' ? 4 : Number(el.getAttribute('aria-level') || 0),
    text: (el.innerText || '').trim().slice(0, 70)
  }))

  const animation = [...route.querySelectorAll('*')].filter(visible).map((el) => {
    const cs = getComputedStyle(el)
    const dur = (s) => s.split(',').map((v) => parseFloat(v) || 0)
    return {
      cls: String(el.className || '').slice(0, 60),
      transition: Math.max(0, ...dur(cs.transitionDuration)),
      animation: Math.max(0, ...dur(cs.animationDuration))
    }
  }).filter((x) => x.transition > 0.15 || x.animation > 0.15).slice(0, 15)

  return {
    url: location.hash,
    viewport: { w: innerWidth, h: innerHeight },
    rootFont: getComputedStyle(document.documentElement).fontSize,
    mode: document.documentElement.dataset.hermesMode,
    theme: document.documentElement.dataset.hermesTheme,
    overflowX,
    routeWidth: Math.round(routeRect.width),
    routeText: (route.innerText || '').slice(0, 500),
    textLength: (route.innerText || '').length,
    clipped: clipped.slice(0, 40),
    contrast: contrast.slice(0, 40),
    unnamed: unnamed.slice(0, 30),
    colorOnly: colorOnly.slice(0, 20),
    smallTargets: smallTargets.slice(0, 20),
    live,
    headings,
    animation
  }
})()`

export async function measure(cdp) {
  return cdp.json(MEASURE)
}

const FOCUS_DESC = `(() => {
  const el = document.activeElement
  if (!el || el === document.body) return { tag: 'BODY', name: '', inRoute: false }
  const route = document.querySelector('${ROUTE}')
  const name = (el.getAttribute('aria-label') || el.innerText || el.value || el.getAttribute('placeholder') || el.getAttribute('title') || '').replace(/\\s+/g, ' ').trim().slice(0, 60)
  const r = el.getBoundingClientRect()
  const cs = getComputedStyle(el)
  return {
    tag: el.tagName,
    role: el.getAttribute('role') || '',
    name,
    inRoute: !!(route && route.contains(el)),
    visible: r.width > 0 && r.height > 0,
    outline: cs.outlineStyle === 'none' ? 'none' : cs.outlineWidth + ' ' + cs.outlineStyle,
    ring: cs.boxShadow && cs.boxShadow !== 'none' ? 'shadow' : 'none',
    x: Math.round(r.x + r.width / 2),
    y: Math.round(r.y + r.height / 2)
  }
})()`

export async function focusNow(cdp) {
  return cdp.json(FOCUS_DESC)
}

/** Walk real Tab presses from the current focus; stops on repetition (trap) or after `steps`. */
export async function tabWalk(cdp, steps = 30, { label = 'tab' } = {}) {
  const stops = []
  for (let i = 0; i < steps; i += 1) {
    await cdp.key('Tab')
    await cdp.wait(60)
    const f = await focusNow(cdp)
    stops.push(f)
    const prev = stops[stops.length - 2]
    const prev2 = stops[stops.length - 3]
    if (prev && prev2 && f.tag !== 'BODY' && f.name === prev.name && f.name === prev2.name && f.tag === prev.tag) {
      return { stops, trap: f, label }
    }
  }
  return { stops, trap: null, label }
}

export async function esc(cdp) {
  const before = await focusNow(cdp)
  await cdp.key('Escape')
  await cdp.wait(250)
  return { before, after: await focusNow(cdp) }
}

export { setMode, writeJson }
