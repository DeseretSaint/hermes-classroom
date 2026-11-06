/** Evidence probe: exact computed colour/bg for a failing muted label in light mode. */
import { attach, setMode, setForcedColors, clearRootText, setViewportCss } from './audit-ux-lib.mjs'

const cdp = await attach()
await setForcedColors(cdp, false)
await clearRootText(cdp)
await setViewportCss(cdp, 1280, 900)
await setMode(cdp, 'light')
await cdp.wait(400)
const out = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const nodes = [...root.querySelectorAll('*')].filter((el) => (el.innerText || '').trim().startsWith('A governed learning workspace'))
  const el = nodes[nodes.length - 1]
  if (!el) return { found: false, sample: [...root.querySelectorAll('*')].map((e) => (e.innerText || '').trim()).filter(Boolean).slice(0, 20) }
  const cs = getComputedStyle(el)
  let bgEl = el
  let bg = 'transparent'
  while (bgEl && bgEl !== document.documentElement) {
    const b = getComputedStyle(bgEl).backgroundColor
    if (b && !/rgba\\(0, 0, 0, 0\\)|transparent/.test(b)) { bg = b; break }
    bgEl = bgEl.parentElement
  }
  return {
    found: true,
    text: el.innerText,
    color: cs.color,
    fontSize: cs.fontSize,
    fontWeight: cs.fontWeight,
    backgroundColor: bg,
    bodyBg: getComputedStyle(document.body).backgroundColor,
    rootVars: {
      tertiary: getComputedStyle(document.documentElement).getPropertyValue('--ui-text-tertiary'),
      secondary: getComputedStyle(document.documentElement).getPropertyValue('--ui-text-secondary'),
      primary: getComputedStyle(document.documentElement).getPropertyValue('--ui-text-primary')
    },
    path: el.tagName + '.' + String(el.className).slice(0, 80)
  }
})()`)
console.log(JSON.stringify(out, null, 2))
cdp.close()
