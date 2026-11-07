// Probe: click a lesson-start action and record hash / chat / paneVisibility / pane text.
import { connect, rel, writeJson } from '../../scripts/cb015-lib.mjs'
import { clickLabel } from './lib.mjs'

const label = process.argv[2] || 'Resume lesson'
const tag = process.argv[3] || 'resume'
const cdp = await connect()
const host = `window.__HERMES_PLUGIN_SDK__.host`
const pane = () => cdp.eval(`(() => { try { return ${host}.paneVisibility('coursebook:pane').get() } catch (e) { return 'ERR:' + e.message } })()`)
const snap = () => cdp.json(`(() => ({
  hash: location.hash,
  routeMounted: !!document.querySelector('[data-cb-route]'),
  paneText: (() => { const p = document.querySelector('[data-cb-pane], [data-cb-coursebook-pane]'); return p ? p.innerText.slice(0, 600) : null })(),
  bodyHasComposer: !!document.querySelector('textarea, [contenteditable=true], [data-composer]'),
  bodyText: document.body.innerText.slice(0, 500)
}))()`)

const before = { pane: await pane(), state: await snap() }
let clicked = null
try { clicked = await clickLabel(cdp, label, { selector: 'button, a' }) } catch (e) { clicked = { error: e.message } }
const samples = []
for (let i = 0; i < 12; i += 1) {
  await cdp.wait(700)
  samples.push({ t: (i + 1) * 700, pane: await pane(), hash: await cdp.eval('location.hash'), route: await cdp.eval("!!document.querySelector('[data-cb-route]')") })
}
const after = { pane: await pane(), state: await snap() }
const result = { label, tag, clicked, before, after, samples }
writeJson(rel(`audit/demo-gate-5b0f124/u05-${tag}.json`), result)
console.log(JSON.stringify(result, null, 2).slice(0, 4000))
cdp.close()
