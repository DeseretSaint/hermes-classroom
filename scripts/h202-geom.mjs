#!/usr/bin/env node
/** H-202 probe: geometry of the player inside its scroll container at a given width. */
import { connect } from './h149-cdp.mjs'
const port = process.env.CB009_CDP_PORT || '9385'
const width = Number(process.argv[2] || 1049)
const height = Number(process.argv[3] || 1400)
const { evaluate, wait, send } = await connect(port)
let override = width
for (let i = 0; i < 8; i += 1) {
  await send('Emulation.setDeviceMetricsOverride', { width: override, height, deviceScaleFactor: 1, mobile: false })
  await wait(160)
  const inner = await evaluate('window.innerWidth')
  if (inner === width) break
  override = Math.round((override * width) / inner)
}
const geo = await evaluate(`(() => {
  const rect = (sel) => { const n = document.querySelector(sel); if (!n) return null; const r = n.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) } }
  const player = document.querySelector('[data-cb-player]')
  const scrollers = []
  for (let n = player; n; n = n.parentElement) {
    const s = getComputedStyle(n)
    if (/(auto|scroll)/.test(s.overflowY)) scrollers.push({ tag: n.tagName, cls: (n.className || '').toString().slice(0, 40), scrollTop: n.scrollTop, scrollHeight: n.scrollHeight, clientHeight: n.clientHeight })
  }
  return {
    win: { w: innerWidth, h: innerHeight },
    scrollY: window.scrollY,
    docScrollHeight: document.documentElement.scrollHeight,
    player: rect('[data-cb-player]'),
    bar: rect('[data-cb-player-bar]'),
    answer: rect('#cb-attempt-answer'),
    chip: rect('[data-cb-evidence-chip]'),
    footer: rect('[data-cb-player-footer]'),
    scrollers
  }
})()`)
console.log(JSON.stringify(geo, null, 1))
