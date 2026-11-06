#!/usr/bin/env node
/**
 * Row 8 — restart the isolated backend at an attempt state, then read the same visible state.
 *
 * For each state: navigate the live window, capture what the section/chat shows, cycle the isolated
 * gateway (same data.db) with `scripts/cb013-live-backend.sh`, reload the window, navigate back and
 * capture again. The comparison is the evidence; nothing is inferred.
 *
 *   node row8-restart.mjs <outJson> <shotDir>
 */
import { execFileSync } from 'node:child_process'
import { connect, hardReload, writeJson } from '/home/deseretsaint/Projects/hermes-classroom/scripts/cb015-lib.mjs'

const outPath = process.argv[2]
const shots = process.argv[3] || 'docs/cb015-shots'
const ROOT = '/home/deseretsaint/Projects/hermes-classroom'
let cdp = await connect()
const cycles = []

const clickText = async (text, { exact = true, scope = 'document' } = {}) => {
  const box = await cdp.json(`(() => {
    const all = [...${scope}.querySelectorAll('button, [role=tab], [role=option], a')]
    const el = all.find((e) => ${exact ? `(e.innerText||'').trim() === ${JSON.stringify(text)}` : `(e.innerText||'').includes(${JSON.stringify(text)})`})
    if (!el) return null
    el.scrollIntoView({ block: 'center' })
    const r = el.getBoundingClientRect(); return { x: r.x + r.width/2, y: r.y + r.height/2 }
  })()`)
  if (!box) return 'missing'
  await cdp.click(box.x, box.y); return 'clicked'
}

const routeText = () => cdp.eval(`(document.querySelector('[data-cb-route]') ? document.querySelector('[data-cb-route]').innerText : '')`)

const capture = () =>
  cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const t = root ? root.innerText || '' : ''
    return {
      hash: location.hash,
      destination: root ? root.getAttribute('data-cb-destination') : null,
      objectiveTitle: (t.match(/Tell everyday affection[^\\n]*|Choose the polite expression[^\\n]*|Recall the intimate[^\\n]*|Explain why register[^\\n]*/) || [null])[0],
      currentCheck: /CURRENT CHECK/.test(t),
      checkVersion: (t.match(/Check v(\\d+)/) || [null, null])[1],
      needsRetry: /I couldn.t grade this attempt/.test(t),
      overrideCopy: /Access granted — not independent evidence|Override — not independent evidence/.test(t),
      verdict: (t.match(/\\b(Passed|Partly there|Not yet)\\b/) || [null])[0],
      attempts: (t.match(/ATTEMPTS ON THIS SECTION\\n([\\s\\S]{0,600})/) || [null, null])[1],
      detachedBanner: /binding detached|chat binding is detached/.test(t),
      body: t.replace(/\\n{2,}/g, '\\n').slice(0, 1200)
    }
  })()`)

const selectCombo = async (selector, name) => {
  const box = await cdp.json(`(() => {
    const el = document.querySelector(${JSON.stringify(selector)})
    if (!el) return null
    el.scrollIntoView({ block: 'center' })
    const r = el.getBoundingClientRect(); return { x: r.x + r.width/2, y: r.y + r.height/2 }
  })()`)
  if (!box) return 'no-trigger'
  await cdp.click(box.x, box.y)
  await cdp.wait(700)
  const opt = await cdp.json(`(() => {
    const el = [...document.querySelectorAll('[role=option]')].find(o => (o.innerText||'').trim() === ${JSON.stringify(name)})
    if (!el) return null
    const r = el.getBoundingClientRect(); return { x: r.x + r.width/2, y: r.y + r.height/2 }
  })()`)
  if (!opt) return 'no-option'
  await cdp.click(opt.x, opt.y)
  await cdp.wait(2000)
  const now = await cdp.eval(`(document.querySelector(${JSON.stringify(selector)})||{}).innerText || ''`)
  return String(now).trim() === name ? 'selected' : 'stuck'
}

/** Open the JP course and a section by index; returns the clicked label. */
const openSection = async (index) => {
  await clickText('Coursebook')
  await cdp.wait(1500)
  const nav = await clickText('Courses')
  if (nav === 'missing') throw new Error('no Courses nav')
  await cdp.wait(2000)
  const opened = await cdp.eval(`(() => {
    const wanted = [...document.querySelectorAll('[data-cb-route] *')]
      .filter(n => /^Japanese affection/.test((n.textContent || '').trim()))
      .sort((a, b) => (a.textContent || '').length - (b.textContent || '').length)[0]
    if (!wanted) return 'no-title'
    let node = wanted
    for (let i = 0; i < 10 && node; i += 1) {
      const open = [...node.querySelectorAll('button')].find(b => (b.innerText || '').trim() === 'Open')
      if (open) { open.click(); return 'clicked' }
      node = node.parentElement
    }
    return 'no-open'
  })()`)
  if (opened !== 'clicked') throw new Error('open JP course: ' + opened)
  await cdp.wait(2000)
  const tb = await selectCombo('#cb-view-picker', 'Textbook')
  if (tb !== 'selected') throw new Error('Textbook view: ' + tb)
  await cdp.wait(1800)
  const sec = await cdp.eval(`(() => {
    const bs = [...document.querySelectorAll('[data-cb-route] button')].filter(b => (b.innerText || '').trim() === 'Open section')
    const b = bs[${index}]
    if (!b) return 'missing(' + bs.length + ')'
    b.click(); return 'clicked'
  })()`)
  if (!String(sec).startsWith('clicked')) throw new Error('open section: ' + sec)
  await cdp.wait(2500)
  return sec
}

const waitBackend = async () => {
  for (let i = 0; i < 60; i += 1) {
    try {
      const r = await fetch('http://127.0.0.1:44219/api/plugins/coursebook/runtime?profile=', {
        headers: { Authorization: 'Bearer cb013-test-token' }
      })
      if (r.ok) return true
    } catch {}
    await new Promise((r) => setTimeout(r, 500))
  }
  return false
}

const restart = async () => {
  execFileSync('bash', [`${ROOT}/scripts/cb013-live-backend.sh`], { stdio: 'pipe' })
  return waitBackend()
}

const cycle = async (name, { index, beforeLabel }) => {
  console.log('—', name)
  const before = { ...(await openSection(index)), state: await capture() }
  await cdp.shot(`${shots}/row8-${name}-before.png`)
  const restarted = await restart()
  cdp = await hardReload(cdp, { settleMs: 5000 })
  await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 40000, label: 'route after restart' })
  const afterOpen = await openSection(index)
  const after = await capture()
  await cdp.shot(`${shots}/row8-${name}-after.png`)
  const compare = {
    name,
    restarted,
    objectiveTitleSame: before.state.objectiveTitle === after.objectiveTitle,
    checkVersion: [before.state.checkVersion, after.checkVersion],
    verdict: [before.state.verdict, after.verdict],
    currentCheck: [before.state.currentCheck, after.currentCheck],
    needsRetry: [before.state.needsRetry, after.needsRetry],
    overrideCopy: [before.state.overrideCopy, after.overrideCopy],
    attemptsBefore: before.state.attempts,
    attemptsAfter: after.attempts,
    sameAttemptsBlock: before.state.attempts === after.attempts
  }
  cycles.push({ name, before: before.state, after, compare })
  console.log(JSON.stringify(compare))
  return compare
}

// 1) awaiting input — ordinal 2 has an open check with no attempt on it
await cycle('awaiting-input', { index: 1 })
// 2) graded — ordinal 1 carries the attempt this packet committed in row 7
await cycle('graded', { index: 0 })
// 3) overridden — ordinal 4 carries the recorded override
await cycle('overridden', { index: 3 })

await writeJson(outPath, { at: new Date().toISOString(), cycles })
console.log('wrote', outPath)
cdp.close()
