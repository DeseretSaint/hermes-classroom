#!/usr/bin/env node
/** H-178 scratch probe: what is on screen and what can be clicked. */
import { connect } from './h149-cdp.mjs'

const port = process.env.CB009_CDP_PORT || '9385'
const { evaluate, wait } = await connect(port)
const decisions = await evaluate("localStorage.getItem('hermes.desktop.pluginDecisions.v2')")
console.log('decisions', decisions)
if (!decisions || !JSON.parse(decisions).coursebook) {
  await evaluate("localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true })); 'ok'")
  console.log('decision set; reload needed')
}
await evaluate("location.hash='#/'; 'ok'")
await wait(400)
await evaluate("location.hash='#/coursebook'; 'ok'")
await wait(2500)
const state = await evaluate(`(() => {
  const text = (n) => (n ? (n.innerText || '').replace(/\\s+/g, ' ').trim() : null)
  return {
    route: !!document.querySelector('[data-cb-route]'),
    shelf: !!document.querySelector('[data-cb-course-shelf]'),
    hash: location.hash,
    headings: [...document.querySelectorAll('[data-cb-route] h1, [data-cb-route] h2')].map(text).slice(0, 8),
    rows: [...document.querySelectorAll('button')].filter((b) => b.offsetParent !== null).map((b) => text(b)).filter(Boolean).slice(0, 40),
    body: text(document.querySelector('[data-cb-route]')).slice(0, 600)
  }
})()`)
console.log(JSON.stringify(state, null, 1))
