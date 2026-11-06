#!/usr/bin/env node
/**
 * CB-015 layout/a11y probe: horizontal overflow + clipping at desktop, narrow (460px) and 200% text,
 * plus the text-only control audit. Values are read from the live renderer.
 */
import { connect, setMode, writeJson } from './cb015-lib.mjs'

const cdp = await connect()
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 25000, label: 'route' })
await cdp.wait(1200)
await setMode(cdp, 'dark')

const measure = () =>
  cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const header = root && root.querySelector('header')
    const body = root && root.children[1]
    const controls = [...root.querySelectorAll('button, a[href], input, select, textarea, [role="tab"], [role="button"]')]
      .filter((el) => el.offsetParent !== null)
    const unnamed = controls.filter((el) => {
      const text = (el.innerText || '').trim()
      const name = el.getAttribute('aria-label') || el.getAttribute('title') || (el.labels && el.labels[0] && el.labels[0].innerText) || ''
      return !text && !name
    })
    const clipped = [...root.querySelectorAll('*')].filter((el) => {
      const s = getComputedStyle(el)
      return s.overflowX === 'visible' && el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0
    }).length
    return {
      rootFontPx: parseFloat(getComputedStyle(document.documentElement).fontSize),
      viewport: [innerWidth, innerHeight],
      overflowX: document.documentElement.scrollWidth - innerWidth,
      routeWidth: root ? Math.round(root.getBoundingClientRect().width) : null,
      gutterPx: root ? getComputedStyle(root).paddingLeft : null,
      headerX: header ? Math.round(header.getBoundingClientRect().x) : null,
      bodyX: body ? Math.round(body.getBoundingClientRect().x) : null,
      controls: controls.length,
      unnamedControls: unnamed.map((el) => el.tagName + '.' + (el.className || '').slice(0, 40)),
      clippedNodes: clipped
    }
  })()`)

const rows = []
for (const scenario of [
  { id: 'desktop-dark', width: 1280, height: 800, text: '100%', mode: 'dark' },
  { id: 'desktop-light', width: 1280, height: 800, text: '100%', mode: 'light' },
  { id: 'narrow-dark', width: 460, height: 900, text: '100%', mode: 'dark' },
  { id: 'text200-dark', width: 1280, height: 800, text: '200%', mode: 'dark' }
]) {
  await setMode(cdp, scenario.mode)
  await cdp.setViewport(scenario.width, scenario.height)
  await cdp.eval(`document.documentElement.style.fontSize = '${scenario.text === '200%' ? '32px' : '16px'}'`)
  await cdp.wait(900)
  const measured = await measure()
  const shot = await cdp.shot(`docs/cb015-shots/layout-${scenario.id}.png`)
  rows.push({ ...scenario, ...measured, shot })
  console.log(scenario.id, JSON.stringify({ ...measured, shot }))
}

await cdp.clearViewport()
await cdp.eval(`document.documentElement.style.fontSize = ''`)
await setMode(cdp, 'dark')
await writeJson('docs/REVIEW_CB015-layout.json', { measuredAt: new Date().toISOString(), cdpPort: process.env.CB015_CDP_PORT || '9338', rows })
cdp.close()
