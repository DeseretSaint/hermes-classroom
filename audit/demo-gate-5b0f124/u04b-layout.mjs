// U04 (5b0f124 re-record) — 200% text, narrow, reduced motion, no-media.
import { connectWithConsole, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()

async function ensureRoute() {
  await cdp.eval(`(location.hash = '#/coursebook', true)`)
  try {
    await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 20000, label: 'route' })
  } catch (e) {
    return { mounted: false, error: e.message }
  }
  await cdp.wait(900)
  return { mounted: true }
}

const mount = await ensureRoute()

const measure = () => cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const controls = root ? [...root.querySelectorAll('button, a[href], input, select, textarea, [role=tab], [role=button]')].filter(el => el.offsetParent !== null) : []
  const unnamed = controls.filter(el => !(el.innerText||'').trim() && !(el.getAttribute('aria-label')||el.getAttribute('title')||'').trim())
  const clipped = root ? [...root.querySelectorAll('*')].filter((el) => {
    const s = getComputedStyle(el)
    return s.overflowX === 'visible' && el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0
  }).length : null
  const all = root ? [...root.querySelectorAll('*')] : []
  const durations = all.map(el => { const s = getComputedStyle(el); return { t: parseFloat(s.transitionDuration||'0'), a: parseFloat(s.animationDuration||'0'), n: s.animationName } })
  const maxT = durations.reduce((m, d) => Math.max(m, isNaN(d.t) ? 0 : d.t), 0)
  const maxA = durations.reduce((m, d) => Math.max(m, isNaN(d.a) ? 0 : d.a), 0)
  return {
    rootFontPx: parseFloat(getComputedStyle(document.documentElement).fontSize),
    viewport: [innerWidth, innerHeight],
    overflowX: document.documentElement.scrollWidth - innerWidth,
    routeWidth: root ? Math.round(root.getBoundingClientRect().width) : null,
    routeText: (root?.innerText||'').replace(/\\n{2,}/g,'\\n').slice(0, 240),
    controls: controls.length,
    unnamedControls: unnamed.length,
    clippedNodes: clipped,
    maxTransitionS: maxT,
    maxAnimationS: maxA,
    animationNames: [...new Set(durations.map(d => d.n))].slice(0, 8)
  }
})()`)

const rows = []
for (const scenario of [
  { id: 'desktop-100', width: 1440, height: 900, font: '16px' },
  { id: 'text-200', width: 1440, height: 900, font: '32px' },
  { id: 'narrow-460', width: 460, height: 900, font: '16px' },
  { id: 'narrow-text-200', width: 460, height: 900, font: '32px' }
]) {
  await cdp.setViewport(scenario.width, scenario.height)
  await cdp.eval(`document.documentElement.style.fontSize = '${scenario.font}'`)
  await cdp.wait(900)
  const measured = await measure()
  const shot = await cdp.shot(`audit/demo-gate-5b0f124/shots/u04-${scenario.id}.png`)
  rows.push({ ...scenario, ...measured, shot })
}

// Reduced motion
await cdp.setViewport(1440, 900)
await cdp.eval(`document.documentElement.style.fontSize = '16px'`)
await cdp.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] }).catch(() => {})
await cdp.wait(700)
const motion = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const all = root ? [...root.querySelectorAll('*')] : []
  const map = all.map(el => { const s = getComputedStyle(el); return { t: parseFloat(s.transitionDuration||'0'), a: parseFloat(s.animationDuration||'0'), n: s.animationName } })
  return {
    mediaMatchesReduce: matchMedia('(prefers-reduced-motion: reduce)').matches,
    maxTransitionS: map.reduce((m,d)=>Math.max(m, isNaN(d.t)?0:d.t),0),
    maxAnimationS: map.reduce((m,d)=>Math.max(m, isNaN(d.a)?0:d.a),0),
    nodesWithTransition: map.filter(d=>d.t>0).length,
    nodesWithAnimation: map.filter(d=>d.a>0).length,
    animationNames: [...new Set(map.filter(d=>d.n && d.n!=='none').map(d=>d.n))].slice(0,8)
  }
})()`)
await cdp.send('Emulation.setEmulatedMedia', { features: [] }).catch(() => {})

// No-media: block media URLs, re-enter the route, and require it to mount.
await cdp.send('Network.enable')
await cdp.send('Network.setBlockedURLs', { urls: ['*.png', '*.jpg', '*.jpeg', '*.webp', '*.mp3', '*.wav', '*.ogg', '*.m4a', '*.svg'] }).catch(() => {})
const remount = await ensureRoute()
const noMedia = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  return { hash: location.hash, route: root ? root.getAttribute('data-cb-route') : null,
    text: (root?.innerText||'').replace(/\\n{2,}/g,'\\n').slice(0, 500),
    images: root ? [...root.querySelectorAll('img')].map(i => ({ src: (i.getAttribute('src')||'').slice(0,60), alt: i.getAttribute('alt'), complete: i.complete, w: i.naturalWidth })) : [] }
})()`)
const noMediaShot = await cdp.shot('audit/demo-gate-5b0f124/shots/u04-no-media.png')
await cdp.send('Network.setBlockedURLs', { urls: [] }).catch(() => {})

const result = { scenario: 'U04', name: '200% text / narrow layout / reduced motion / no-media', mount, remount, rows, motion, noMedia, noMediaShot, consoleErrors: console_ }
save('u04-layout.json', result)
console.log(JSON.stringify(result, null, 2))
cdp.close()
