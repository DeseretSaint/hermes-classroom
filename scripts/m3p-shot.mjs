#!/usr/bin/env node
/** One-shot read of the live window: route, DOM facts, console errors, screenshot. */
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { attach } from './cb-loops-lib.mjs'

const OUT = resolve('audit/visual/m3-pronunciation/live')
mkdirSync(OUT, { recursive: true })
const cdp = await attach()
await cdp.wait(1500)
const facts = await cdp.json(`(() => ({
  hash: location.hash,
  route: Boolean(document.querySelector('[data-cb-route="/coursebook"]')),
  destination: document.querySelector('[data-cb-destination]') ? document.querySelector('[data-cb-destination]').getAttribute('data-cb-destination') : null,
  desk: Boolean(document.querySelector('[data-cb-desk]')),
  coursebookNav: [...document.querySelectorAll('a,button')].some((node) => (node.textContent || '').trim() === 'Coursebook'),
  studioSeats: document.querySelectorAll('[data-cb-pronunciation]').length,
  document: document.querySelector('[data-cb-document]') ? document.querySelector('[data-cb-document]').getAttribute('data-cb-document') : null,
  width: innerWidth,
  scrollWidth: document.documentElement.scrollWidth
}))()`)
console.log(JSON.stringify(facts))
await cdp.shot(`${OUT}/live-01-coursebook-route.png`)
await cdp.send('Emulation.setDeviceMetricsOverride', { width: 460, height: 900, deviceScaleFactor: 1, mobile: false })
await cdp.wait(900)
const narrow = await cdp.json(`(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth, overflow: document.documentElement.scrollWidth > innerWidth + 1 }))()`)
await cdp.shot(`${OUT}/live-02-coursebook-460.png`)
await cdp.send('Emulation.clearDeviceMetricsOverride')
const payload = {
  facts,
  narrow,
  consoleErrors: cdp.errors.filter((entry) => !/ResizeObserver|Autofill|DevTools|Electron Security/.test(entry.text || '')),
  notProven: [
    'A live Record -> Stop -> Compare walk: no section in this isolated home carries a narration media child, so no block seats the studio. Both the target phrase and the reference audio come from that authored narration, and generating one is provider TTS spend this card does not authorise.',
    'Live availability: this window talks to the older isolated backend (wire v7) which has no pronunciation route, so the studio status probe is not demonstrated live here. The renderer states are proven by the component-driven frames and by tests/test_desktop_pronunciation.py.'
  ]
}
writeFileSync(`${OUT}/live-evidence.json`, JSON.stringify(payload, null, 2))
console.log(JSON.stringify({ narrow, errors: payload.consoleErrors.length }))
