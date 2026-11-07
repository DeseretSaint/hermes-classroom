// U04 — 200% text, narrow layout, reduced motion, no-media fallback.
import { connectWithConsole, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 20000, label: 'route' })
await cdp.wait(1200)

const measure = () => cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const controls = root ? [...root.querySelectorAll('button, a[href], input, select, textarea, [role=tab], [role=button]')].filter(el => el.offsetParent !== null) : []
  const unnamed = controls.filter(el => !(el.innerText||'').trim() && !(el.getAttribute('aria-label')||el.getAttribute('title')||'').trim())
  const clipped = root ? [...root.querySelectorAll('*')].filter((el) => {
    const s = getComputedStyle(el)
    return s.overflowX === 'visible' && el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0
  }).length : null
  return {
    rootFontPx: parseFloat(getComputedStyle(document.documentElement).fontSize),
    viewport: [innerWidth, innerHeight],
    overflowX: document.documentElement.scrollWidth - innerWidth,
    routeWidth: root ? Math.round(root.getBoundingClientRect().width) : null,
    routeText: (root?.innerText||'').replace(/\\n{2,}/g,'\\n').slice(0, 260),
    controls: controls.length,
    unnamedControls: unnamed.length,
    clippedNodes: clipped
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
  await cdp.wait(800)
  const measured = await measure()
  const shot = await cdp.shot(`audit/demo-gate-5b0f124/shots/u04-${scenario.id}.png`)
  rows.push({ ...scenario, ...measured, shot })
}

// Reduced motion
await cdp.setViewport(1440, 900)
await cdp.eval(`document.documentElement.style.fontSize = '16px'`)
await cdp.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] }).catch(() => {})
await cdp.wait(600)
const motion = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const nodes = root ? [...root.querySelectorAll('*')] : []
  const animated = nodes.filter(el => { const s = getComputedStyle(el); return parseFloat(s.animationDuration||'0') > 0 || s.animationName !== 'none' })
  const transitions = nodes.filter(el => { const s = getComputedStyle(el); return parseFloat(s.transitionDuration||'0') > 0 })
  return { mediaMatchesReduce: matchMedia('(prefers-reduced-motion: reduce)').matches, animatedNodes: animated.length, transitionNodes: transitions.length,
    animationNames: [...new Set(animated.map(el => getComputedStyle(el).animationName))].slice(0, 10) }
})()`)
await cdp.send('Emulation.setEmulatedMedia', { features: [] }).catch(() => {})

// No-media: block network images/audio and reload the route; text must still carry the content.
await cdp.send('Network.enable')
await cdp.send('Network.setBlockedURLs', { urls: ['*.png', '*.jpg', '*.jpeg', '*.webp', '*.mp3', '*.wav', '*.ogg', '*.m4a'] }).catch(() => {})
await cdp.reload()
await cdp.wait(2500)
const noMedia = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  return { hash: location.hash, route: root ? root.getAttribute('data-cb-route') : null, text: (root?.innerText||'').replace(/\\n{2,}/g,'\\n').slice(0, 400),
    images: root ? [...root.querySelectorAll('img')].map(i => ({ src: i.getAttribute('src')?.slice(0,60), alt: i.getAttribute('alt'), complete: i.complete, w: i.naturalWidth })) : [] }
})()`)
await cdp.send('Network.setBlockedURLs', { urls: [] }).catch(() => {})

const result = { scenario: 'U04', name: '200% text / narrow layout / reduced motion / no-media', rows, motion, noMedia, consoleErrors: console_ }
save('u04-layout.json', result)
console.log(JSON.stringify({ rows, motion, noMedia, consoleErrors: console_ }, null, 2))
cdp.close()
