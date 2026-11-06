#!/usr/bin/env node
/**
 * CB-015 fault state 2 — backend off, then enabled again (UX_SPEC §13 "backend off", proof 2).
 *
 * The Desktop's plugin transport is the host IPC bridge (`window.hermesDesktop.api` → Electron
 * main), so a renderer-level Fetch interception never sees these calls. The honest fault is the
 * real one: stop the isolated Coursebook gateway on 44220, load the page, look at what it says,
 * start the gateway again, and take its own "Check again" action.
 *
 * The gateway is the disposable one from `scripts/cb013-live-backend.sh` pointed at
 * `~/.hermes/cb015-test/home`. The operator's gateway is never touched.
 *
 *   CB015_CDP_PORT=9338 node scripts/cb015-fault-backend-off.mjs
 */
import { connect, hardReload, writeJson } from './cb015-lib.mjs'
import { execFileSync } from 'node:child_process'

const BASE = process.env.CB015_BASE || 'http://127.0.0.1:44220'
const TOKEN = process.env.CB013_TOKEN || 'cb013-test-token'
const rig = (arg) =>
  execFileSync('bash', ['scripts/cb013-live-backend.sh', arg], {
    env: {
      ...process.env,
      COURSEBOOK_TEST_HOME: `${process.env.HOME}/.hermes/cb015-test/home`,
      CB013_PORT: '44220'
    },
    encoding: 'utf8'
  })

let cdp = await connect()
const SHOTS = 'docs/cb015-shots'
const out = { at: new Date().toISOString(), base: BASE, steps: [] }

const state = () =>
  cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const text = root ? (root.innerText || '') : (document.body.innerText || '')
    const buttons = [...document.querySelectorAll('[data-cb-route] button')]
    return {
      hash: location.hash,
      destination: root ? root.getAttribute('data-cb-destination') : null,
      hasRoute: !!root,
      backendOffBadge: [...document.querySelectorAll('[data-cb-route] *')].some((n) => (n.innerText || '').trim() === 'Backend off'),
      unavailableTitle: /Coursebook needs its agent plugin/.test(text),
      enableInstructions: /Enable Coursebook under Capabilities/.test(text),
      hasOpenCapabilities: buttons.some((b) => (b.innerText || '').trim() === 'Open Capabilities'),
      hasCheckAgain: buttons.some((b) => (b.innerText || '').trim() === 'Check again'),
      hasNewCourse: buttons.some((b) => (b.innerText || '').trim() === 'New course'),
      rows: buttons.filter((b) => (b.innerText || '').trim() === 'Open').length,
      title: (text.split('\\n')[0] || '').trim(),
      excerpt: text.replace(/\\n{2,}/g, '\\n').slice(0, 700)
    }
  })()`)

const record = async (step, extra = {}) => {
  const value = { step, at: new Date().toISOString(), ...(await state()), ...extra }
  out.steps.push(value)
  console.log(
    JSON.stringify({
      step,
      badge: value.backendOffBadge,
      unavailable: value.unavailableTitle,
      checkAgain: value.hasCheckAgain,
      rows: value.rows
    })
  )
  return value
}

const waitForRuntime = async (deadlineMs = 120000) => {
  const started = Date.now()
  while (Date.now() - started < deadlineMs) {
    try {
      const response = await fetch(`${BASE}/api/plugins/coursebook/runtime?profile=`, {
        headers: { Authorization: `Bearer ${TOKEN}` }
      })
      if (response.ok) return (Date.now() - started) / 1000
    } catch {
      /* not up yet */
    }
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
  throw new Error('backend did not come back within the deadline')
}

// ── 1. baseline (data this run must find again afterwards) ─────────────────────────────────
cdp = await hardReload(cdp)
await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 40000, label: 'route' })
await cdp.waitFor(`navigator.onLine === true`, { timeout: 10000, label: 'online' })
await cdp.waitFor(
  `[...document.querySelectorAll('[data-cb-route] button')].some(b => (b.innerText || '').trim() === 'Open')`,
  { timeout: 30000, label: 'course rows' }
)
const baseline = await record('backend-ready-baseline')
await cdp.shot(`${SHOTS}/67-backend-ready-dark.png`)

// ── 2. stop the isolated gateway ───────────────────────────────────────────────────────────
console.log(rig('--stop').trim())
await new Promise((resolve) => setTimeout(resolve, 1500))

// ── 3. the page must say the backend is off, with the enable path in text ──────────────────
cdp = await hardReload(cdp)
await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 40000, label: 'route while down' })
await cdp.waitFor(`/Coursebook needs its agent plugin/.test(document.querySelector('[data-cb-route]').innerText || '')`, {
  timeout: 60000,
  label: 'backend-off copy'
})
const down = await record('backend-off')
await cdp.shot(`${SHOTS}/68-backend-off-dark.png`)

// ── 4. start it again and take the page's own recovery action ──────────────────────────────
console.log(rig('').trim())
const upSeconds = await waitForRuntime()
const clicked = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => (x.innerText || '').trim() === 'Check again')
  if (!b) return 'missing'
  b.click()
  return 'clicked'
})()`)
if (clicked !== 'clicked') throw new Error('no Check again control on the backend-off page')
await cdp.waitFor(
  `[...document.querySelectorAll('[data-cb-route] button')].some(b => (b.innerText || '').trim() === 'Open')`,
  { timeout: 60000, label: 'rows after reconnect' }
)
const recovered = await record('backend-enabled-again', { backendUpAfterSeconds: upSeconds })
await cdp.shot(`${SHOTS}/69-backend-recovered-dark.png`)

out.verdict = {
  offStateNamed: down.backendOffBadge && down.unavailableTitle,
  enableInstructionsInText: down.enableInstructions && down.hasOpenCapabilities,
  recoveryActionPresent: down.hasCheckAgain,
  noFakeContentWhileDown: down.rows === 0 && !down.hasNewCourse,
  dataKeptAcrossCycle: recovered.rows === baseline.rows && recovered.rows > 0,
  recoveredByItsOwnAction: clicked === 'clicked'
}
const path = await writeJson('docs/REVIEW_CB015-fault-backend-off.json', out)
console.log(JSON.stringify(out.verdict, null, 2))
console.log(`wrote ${path}`)
cdp.close()
process.exit(0)
