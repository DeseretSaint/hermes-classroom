#!/usr/bin/env node
/**
 * CB-015 fault state 2b — the Coursebook Python half is disabled while Hermes stays up.
 *
 * Stopping the whole gateway (see cb015-fault-backend-off.mjs) also removes the HOST's own
 * connection, so the window paints its own CONNECTING view over the workspace. This script
 * isolates the plugin half: only `plugins.enabled` is emptied in the disposable rig, the gateway
 * restarts, and whatever the plugin route renders is recorded as-is — no expected copy is
 * asserted, so the result is an observation, not a confirmation.
 *
 * The operator's home is never touched; config is restored in a finally block.
 *
 *   CB015_CDP_PORT=9338 node scripts/cb015-fault-plugin-off.mjs
 */
import { connect, hardReload, writeJson } from './cb015-lib.mjs'
import { execFileSync } from 'node:child_process'
import { copyFileSync, writeFileSync, unlinkSync } from 'node:fs'

const HOME = `${process.env.HOME}/.hermes/cb015-test/home`
const CONFIG = `${HOME}/config.yaml`
const BACKUP = `${CONFIG}.cb015-backup`
const rig = (arg) =>
  execFileSync('bash', ['scripts/cb013-live-backend.sh', arg], {
    env: { ...process.env, COURSEBOOK_TEST_HOME: HOME, CB013_PORT: '44220' },
    encoding: 'utf8'
  })

let cdp = await connect()
const SHOTS = 'docs/cb015-shots'
const out = { at: new Date().toISOString(), config: CONFIG, steps: [] }

const state = () =>
  cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const text = root ? (root.innerText || '') : ''
    const buttons = [...document.querySelectorAll('[data-cb-route] button')]
    return {
      hash: location.hash,
      hasRoute: !!root,
      routeVisible: root ? root.getClientRects().length > 0 : false,
      hostConnecting: document.body.innerText.trim() === 'CONNECTING' || /^CONNECTING/m.test(document.body.innerText.trim()),
      backendOffCopy: /Coursebook needs its agent plugin/.test(text),
      scopedError: /could not be read|VALIDATION_FAILED/.test(text),
      errorLine: (text.match(/[A-Z_]+: [^\\n]{0,160}/) || [null])[0],
      hasTryAgain: buttons.some((b) => (b.innerText || '').trim() === 'Try again'),
      hasCheckAgain: buttons.some((b) => (b.innerText || '').trim() === 'Check again'),
      hasNewCourse: buttons.some((b) => (b.innerText || '').trim() === 'New course'),
      rows: buttons.filter((b) => (b.innerText || '').trim() === 'Open').length,
      excerpt: text.replace(/\\n{2,}/g, '\\n').slice(0, 500)
    }
  })()`)

const record = async (step, extra = {}) => {
  const value = { step, at: new Date().toISOString(), ...(await state()), ...extra }
  out.steps.push(value)
  console.log(
    JSON.stringify({
      step,
      visible: value.routeVisible,
      offCopy: value.backendOffCopy,
      scopedError: value.scopedError,
      rows: value.rows,
      error: value.errorLine
    })
  )
  return value
}

copyFileSync(CONFIG, BACKUP)
let exitCode = 0
try {
  cdp = await hardReload(cdp)
  await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 40000, label: 'route' })
  await cdp.waitFor(
    `[...document.querySelectorAll('[data-cb-route] button')].some(b => (b.innerText || '').trim() === 'Open')`,
    { timeout: 30000, label: 'course rows' }
  )
  const baseline = await record('plugin-enabled-baseline')

  writeFileSync(CONFIG, 'plugins:\n  enabled: []\n  disabled:\n    - coursebook\n')
  rig('')
  await new Promise((resolve) => setTimeout(resolve, 3000))

  cdp = await hardReload(cdp, { settleMs: 6000 })
  await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 60000, label: 'route while plugin off' })
  await cdp.waitFor(
    `(() => { const r = document.querySelector('[data-cb-route]'); return r && (r.innerText || '').trim().length > 20 })()`,
    { timeout: 60000, label: 'plugin surface content' }
  )
  const off = await record('plugin-half-disabled')
  await cdp.shot(`${SHOTS}/70-plugin-half-disabled-dark.png`)

  copyFileSync(BACKUP, CONFIG)
  rig('')
  await new Promise((resolve) => setTimeout(resolve, 3000))
  cdp = await hardReload(cdp, { settleMs: 6000 })
  await cdp.waitFor(
    `[...document.querySelectorAll('[data-cb-route] button')].some(b => (b.innerText || '').trim() === 'Open')`,
    { timeout: 60000, label: 'rows after re-enable' }
  )
  const recovered = await record('plugin-enabled-again')
  await cdp.shot(`${SHOTS}/71-plugin-backend-recovered-dark.png`)

  out.verdict = {
    surfaceStillMounted: off.hasRoute && off.routeVisible,
    noFakeRowsWhileDown: off.rows === 0 && !off.hasNewCourse,
    namedFailure: off.backendOffCopy || Boolean(off.errorLine),
    recoveryAffordance: off.hasTryAgain || off.hasCheckAgain,
    dataKeptAcrossCycle: recovered.rows === baseline.rows && recovered.rows > 0
  }
  const path = await writeJson('docs/REVIEW_CB015-fault-plugin-off.json', out)
  console.log(JSON.stringify(out.verdict, null, 2))
  console.log(`wrote ${path}`)
} catch (error) {
  exitCode = 1
  console.error('FAILED:', (error && error.message) || error)
  out.error = String((error && error.message) || error)
  await writeJson('docs/REVIEW_CB015-fault-plugin-off.json', out)
} finally {
  copyFileSync(BACKUP, CONFIG)
  unlinkSync(BACKUP)
  try {
    rig('')
  } catch (error) {
    console.error('restart after cleanup failed:', (error && error.message) || error)
  }
  cdp.close()
  process.exit(exitCode)
}
