#!/usr/bin/env node
/**
 * CB-015 fault state 1 — offline (UX_SPEC §13 "offline", proof 11).
 *
 * The Desktop's transport is the Electron IPC bridge, not the renderer's fetch, so the honest
 * emulation is Chromium's own network-condition switch: `Network.emulateNetworkConditions`
 * sets `navigator.onLine = false` and fires the real `offline` event, which is exactly the
 * signal the page listens to. Nothing here fakes a React state.
 *
 * What must be true while offline:
 *   - the page says so in text (a badge and a sentence, not a colour);
 *   - content already read from this profile's local backend still renders;
 *   - the actions that need new model work are absent, not dead;
 *   - going back online removes the notice.
 *
 *   CB015_CDP_PORT=9338 node scripts/cb015-fault-offline.mjs
 */
import { connect, hardReload, writeJson } from './cb015-lib.mjs'

let cdp = await connect()
const SHOTS = 'docs/cb015-shots'
const out = { at: new Date().toISOString(), steps: [] }
const log = (m) => console.error(m)

const state = () =>
  cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const text = root ? (root.innerText || '') : ''
    const buttons = [...document.querySelectorAll('[data-cb-route] button')]
    return {
      hash: location.hash,
      destination: root ? root.getAttribute('data-cb-destination') : null,
      online: navigator.onLine,
      badge: [...document.querySelectorAll('[data-cb-route] *')].some((n) => (n.innerText || '').trim() === 'Offline'),
      offlineSentence: /Offline\\. Lessons, notes and review keep working/.test(text),
      hasNewCourse: buttons.some((b) => (b.innerText || '').trim() === 'New course'),
      hasNewBrief: buttons.some((b) => (b.innerText || '').trim() === 'New lesson brief'),
      rows: buttons.filter((b) => (b.innerText || '').trim() === 'Open').length,
      excerpt: text.replace(/\\n{2,}/g, '\\n').slice(0, 900)
    }
  })()`)

const record = async (step, extra = {}) => {
  const value = { step, at: new Date().toISOString(), ...(await state()), ...extra }
  out.steps.push(value)
  console.log(JSON.stringify({ step, online: value.online, badge: value.badge, newCourse: value.hasNewCourse, rows: value.rows }))
  return value
}

cdp = await hardReload(cdp)
await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 40000, label: 'route' })
await cdp.waitFor(`navigator.onLine === true`, { timeout: 10000, label: 'online' })

// ── online baseline ────────────────────────────────────────────────────────────────────────
await record('online-baseline')

// ── go offline ─────────────────────────────────────────────────────────────────────────────
await cdp.send('Network.enable', {})
await cdp.send('Network.emulateNetworkConditions', {
  offline: true,
  latency: 0,
  downloadThroughput: -1,
  uploadThroughput: -1
})
await cdp.waitFor(`navigator.onLine === false`, { timeout: 10000, label: 'navigator offline' })
await cdp.waitFor(`document.querySelector('[data-cb-route]').innerText.includes('Offline. Lessons')`, {
  timeout: 10000,
  label: 'offline notice'
})
const offlineCourses = await record('offline-courses')
await cdp.shot(`${SHOTS}/64-offline-courses-dark.png`)

// ── cached content still opens while offline ───────────────────────────────────────────────
const opened = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => (x.innerText || '').trim() === 'Open')
  if (!b) return 'missing'
  b.click()
  return 'clicked'
})()`)
if (opened !== 'clicked') throw new Error('no course to open offline')
await cdp.wait(2200)
const offlineCourse = await record('offline-course-detail')
await cdp.shot(`${SHOTS}/65-offline-course-dark.png`)

// ── back online ────────────────────────────────────────────────────────────────────────────
await cdp.send('Network.emulateNetworkConditions', {
  offline: false,
  latency: 0,
  downloadThroughput: -1,
  uploadThroughput: -1
})
await cdp.waitFor(`navigator.onLine === true`, { timeout: 10000, label: 'navigator online' })
await cdp.waitFor(`!document.querySelector('[data-cb-route]').innerText.includes('Offline. Lessons')`, {
  timeout: 10000,
  label: 'offline notice cleared'
})
const backOnline = await record('back-online')
await cdp.shot(`${SHOTS}/66-online-again-dark.png`)

out.verdict = {
  offlineSpaceNamed: offlineCourses.badge && offlineCourses.offlineSentence,
  createActionsAbsentOffline: !offlineCourses.hasNewCourse,
  cachedContentRendered: offlineCourse.rows > 0 || /ATTEMPTS|SECTION|Objective/i.test(offlineCourse.excerpt),
  noticeClearedOnline: !backOnline.badge
}
const path = await writeJson('docs/REVIEW_CB015-fault-offline.json', out)
console.log(JSON.stringify(out.verdict, null, 2))
console.log(`wrote ${path}`)
cdp.close()
process.exit(0)
