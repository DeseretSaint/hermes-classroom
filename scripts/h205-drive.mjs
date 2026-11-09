#!/usr/bin/env node
/**
 * H-205: drive the Field Stop sequence on the after rig (default CDP 9385).
 *
 *   node scripts/h205-drive.mjs nav          # route → course → Learn → stop 02 → Game → answer step
 *   node scripts/h205-drive.mjs sequence     # wrong → hint → hinted retry → completion → return
 *
 * Every frame is written to audit/visual/h205-field-sequence/ with viewport, root font size, theme,
 * sha256 and the step label. Uses its own CDP client with a hard per-method timeout so a dead
 * context fails loudly instead of hanging.
 */
import { writeFileSync, mkdirSync, readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { createHash } from 'node:crypto'

const port = process.env.CB009_CDP_PORT || '9385'
const OUT = resolve(process.env.H205_OUT || 'audit/visual/h205-field-sequence')

async function connect() {
  const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
  const page = targets.find((t) => t.type === 'page')
  if (!page) throw new Error(`no page target on CDP ${port}`)
  const socket = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((ok, bad) => {
    const timer = setTimeout(() => bad(new Error(`CDP ${port}: websocket open timeout`)), 10000)
    socket.addEventListener('open', () => { clearTimeout(timer); ok() }, { once: true })
    socket.addEventListener('error', (event) => { clearTimeout(timer); bad(new Error(`CDP ${port}: websocket error ${event.message || ''}`)) }, { once: true })
  })
  let nextId = 1
  const pending = new Map()
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    if (message.id && pending.has(message.id)) {
      const { resolve: res, reject, timer } = pending.get(message.id)
      clearTimeout(timer)
      pending.delete(message.id)
      if (message.error) reject(new Error(`CDP ${port}: ${JSON.stringify(message.error)}`))
      else res(message.result)
    }
  })
  const send = (method, params = {}, timeout = 20000) =>
    new Promise((res, reject) => {
      const id = nextId++
      const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP ${port}: ${method} timed out after ${timeout}ms`)) }, timeout)
      pending.set(id, { resolve: res, reject, timer })
      socket.send(JSON.stringify({ id, method, params }))
    })
  await send('Runtime.enable')
  await send('Page.enable')
  const evaluate = async (expression) => {
    const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
    if (result.exceptionDetails) throw new Error(`evaluate failed: ${JSON.stringify(result.exceptionDetails).slice(0, 500)}`)
    return result.result.value
  }
  const wait = (ms) => new Promise((r) => setTimeout(r, ms))
  return { send, evaluate, wait, close: () => socket.close() }
}

const { send, evaluate, wait, close } = await connect()

const measure = () => evaluate(`(() => {
  const t = (n) => (n ? (n.innerText || '').replace(/\\s+/g, ' ').trim() : null)
  const chip = document.querySelector('[data-cb-evidence-chip]')
  return {
    innerWidth: window.innerWidth, innerHeight: window.innerHeight,
    devicePixelRatio: window.devicePixelRatio,
    rootFontSize: getComputedStyle(document.documentElement).fontSize,
    darkClass: document.documentElement.classList.contains('dark'),
    hash: location.hash,
    view: document.querySelector('[data-cb-lesson-view]')?.getAttribute('data-cb-lesson-view') || null,
    player: !!document.querySelector('[data-cb-player]'),
    bar: t(document.querySelector('[data-cb-player-bar]')),
    step: t(document.querySelector('[data-cb-player-step]')),
    chip: chip?.getAttribute('data-cb-evidence-chip') || null,
    chipPending: chip?.getAttribute('data-cb-evidence-pending') || null,
    chipText: t(chip),
    answerField: !!document.querySelector('#cb-attempt-answer'),
    assist: [...document.querySelectorAll('[data-cb-assist] button')].map((b) => b.innerText.trim()),
    primary: t(document.querySelector('[data-cb-player-footer] button')),
    primaryDisabled: (document.querySelector('[data-cb-player-footer] button') || {}).disabled ?? null,
    feedback: t(document.querySelector('[data-cb-player-feedback]')),
    body: t(document.querySelector('[data-cb-route]')).slice(0, 900)
  }
})()`)

const shoot = async (label) => {
  mkdirSync(OUT, { recursive: true })
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }, 30000)
  const buf = Buffer.from(shot.data, 'base64')
  const path = resolve(OUT, `${label}.png`)
  writeFileSync(path, buf)
  return { label, path, sha256: createHash('sha256').update(buf).digest('hex'), bytes: buf.length }
}

const clickText = (label, root = 'body') => evaluate(`(() => {
  const wanted = ${JSON.stringify(label)}
  const node = [...document.querySelectorAll(${JSON.stringify(root)} + ' button')]
    .find((n) => (n.innerText || '').replace(/\\s+/g, ' ').trim() === wanted && n.offsetParent !== null)
  if (!node) return false
  node.click(); return true
})()`)

const setWidth = async (target) => {
  let override = target
  for (let i = 0; i < 8; i += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height: 1200, deviceScaleFactor: 1, mobile: false })
    await wait(200)
    const inner = await evaluate('window.innerWidth')
    if (inner === target) return override
    override = Math.round((override * target) / inner)
  }
  throw new Error(`CDP ${port}: could not calibrate width ${target}`)
}

async function goToPlayer() {
  // Reuse the open course when the window is already on it (a reload or a failed search leaves us
  // on the section detail, and re-running the shelf walk would bounce off the remembered route).
  const onCourse = await evaluate("!!document.querySelector('[data-cb-tab=\"learn\"]')")
  if (!onCourse) {
    await evaluate("location.hash='#/'; 'ok'")
    await wait(600)
    await evaluate("location.hash='#/coursebook'; 'ok'")
    await wait(2200)
    await evaluate(`(() => { document.querySelector('[data-cb-nav-item="courses"]')?.click(); return true })()`)
    await wait(1600)
    const searched = await evaluate(`(() => {
      const el = document.querySelector('input[aria-label="Search courses"]')
      if (!el) return false
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
      setter.call(el, 'demonstration')
      el.dispatchEvent(new Event('input', { bubbles: true }))
      return true
    })()`)
    if (!searched) throw new Error('CDP ' + port + ': no "Search courses" input on the Courses shelf (step: nav)')
    await wait(1500)
    const opened = await evaluate(`(() => {
      const btns = [...document.querySelectorAll('[data-cb-route] button')]
        .filter((b) => b.offsetParent !== null && /^(Open|Continue)$/.test((b.innerText || '').trim()))
      if (btns.length !== 1) return false
      btns[0].click(); return true
    })()`)
    if (!opened) throw new Error('CDP ' + port + ': shelf did not narrow to one Open/Continue button (step: nav/course)')
    await wait(2800)
  }
  const learn = await evaluate(`(() => {
    const b = document.querySelector('[data-cb-tab="learn"]') || [...document.querySelectorAll('button,[role="tab"]')].find((n) => (n.innerText || '').trim() === 'Learn')
    if (!b) return false
    b.click(); return true
  })()`)
  if (!learn) throw new Error('CDP ' + port + ': no Learn tab (step: nav/learn)')
  await wait(1800)
  const stopClicked = await evaluate(`(() => {
    const node = [...document.querySelectorAll('[data-cb-route] button')].find((n) => /^02\\b/.test((n.innerText || '').trim()))
    if (!node) return false
    node.click(); return true
  })()`)
  if (!stopClicked) throw new Error('CDP ' + port + ': stop 02 not on the trail (step: nav/stop02)')
  await wait(3200)
  let view = await evaluate("document.querySelector('[data-cb-lesson-view]')?.getAttribute('data-cb-lesson-view') || null")
  if (view !== 'player') {
    const clicked = await evaluate(`(() => { const b = document.querySelector('[data-cb-view-choice="player"]'); if (!b) return false; b.click(); return true })()`)
    if (!clicked) throw new Error('CDP ' + port + ': no Game view control (step: nav/game-view)')
    await wait(2400)
  }
  for (let i = 0; i < 5; i += 1) {
    if (await evaluate("!!document.querySelector('#cb-attempt-answer')")) break
    const label = await evaluate(`(() => {
      const b = document.querySelector('[data-cb-player-footer] button')
      if (!b || b.disabled) return null
      b.click(); return (b.innerText || '').trim()
    })()`)
    if (!label) break
    await wait(1500)
  }
  const state = await measure()
  if (!state.answerField) throw new Error('CDP ' + port + ': answer surface never appeared (step: nav/reach-check). state=' + JSON.stringify(state).slice(0, 400))
  return state
}

const typeAnswer = async (text) => {
  const typed = await evaluate(`(() => {
    const el = document.querySelector('#cb-attempt-answer')
    if (!el) return false
    const proto = el instanceof window.HTMLTextAreaElement ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set
    setter.call(el, ${JSON.stringify(text)})
    el.dispatchEvent(new Event('input', { bubbles: true }))
    el.focus()
    return true
  })()`)
  if (!typed) throw new Error('CDP ' + port + ': answer field missing (step: type)')
  await wait(300)
}

const clickCheck = async () => {
  const clicked = await evaluate(`(() => {
    const b = document.querySelector('[data-cb-player-footer] button')
    if (!b || b.disabled) return false
    b.click(); return true
  })()`)
  if (!clicked) throw new Error('CDP ' + port + ': Check disabled or missing (step: submit). state=' + JSON.stringify(await measure()).slice(0, 400))
  await wait(2600)
}

const mode = process.argv[2] || 'nav'
let sequence = []
if (mode === 'finish') {
  try { sequence = JSON.parse(readFileSync(resolve(OUT, 'sequence.json'), 'utf8')).frames || [] } catch { sequence = [] }
}

if (mode === 'nav') {
  const state = await goToPlayer()
  console.log(JSON.stringify({ step: 'nav', state }, null, 1))
} else if (mode === 'sequence') {
  const record = async (stepLabel, extra = {}) => {
    const snapshot = await measure()
    const file = await shoot(stepLabel)
    const row = {
      step: stepLabel,
      viewport: { innerWidth: snapshot.innerWidth, innerHeight: snapshot.innerHeight },
      devicePixelRatio: snapshot.devicePixelRatio,
      rootFontSize: snapshot.rootFontSize,
      theme: snapshot.darkClass ? 'dark' : 'light',
      sha256: file.sha256,
      bytes: file.bytes,
      state: snapshot,
      ...extra
    }
    sequence.push(row)
    writeFileSync(resolve(OUT, 'sequence.json'), JSON.stringify({ port, plugin: process.env.H205_PLUGIN_SHA || null, frames: sequence }, null, 2))
    console.log(`FRAME ${stepLabel}: chip=${snapshot.chip}/${snapshot.chipPending} view=${snapshot.view} w=${snapshot.innerWidth} sha=${file.sha256.slice(0, 12)}`)
    return row
  }

  // Land on the answer surface, wide enough for the full player.
  const landed = await goToPlayer()
  if (!landed.answerField) throw new Error('answer surface missing before sequence (step: preflight)')
  await setWidth(1049)
  await evaluate(`(() => { const p = document.querySelector('[data-cb-player]'); if (p) p.scrollIntoView({ block: 'start' }); return true })()`)
  await wait(400)
  await record('01-answer-cold')

  // 1. Wrong answer, submitted cold.
  await typeAnswer(process.env.H205_WRONG || 'I do not know which line fits.')
  await record('02-answer-typed')
  await clickCheck()
  await record('03-wrong-verdict')

  // 2. Hint recorded from the pane.
  if (!(await clickText('I used a hint', '[data-cb-assist]'))) throw new Error('CDP ' + port + ': "I used a hint" control missing (step: hint)')
  await wait(2200)
  await record('04-hint-recorded')

  // 3. Hinted retry with the accepted answer.
  await typeAnswer(process.env.H205_RIGHT || '好きです')
  await clickCheck()
  const retry = await record('05-hinted-pass')

  // 4. Walk to completion.
  for (let i = 0; i < 4; i += 1) {
    const s = await measure()
    if (/finished/i.test(s.body || '') || s.answerField === false) break
    const label = await evaluate(`(() => {
      const b = document.querySelector('[data-cb-player-footer] button')
      if (!b || b.disabled) return null
      b.click(); return (b.innerText || '').trim()
    })()`)
    if (!label) break
    await wait(1800)
  }
  await wait(800)
  await record('06-completion')

  // 5. Return to the trail.
  const returned = await evaluate(`(() => {
    const b = [...document.querySelectorAll('button')].find((n) => /Return to the trail/i.test((n.innerText || '').trim()) && n.offsetParent !== null)
    if (!b) return false
    b.click(); return true
  })()`)
  if (!returned) throw new Error('CDP ' + port + ': "Return to the trail" control missing (step: return). state=' + JSON.stringify(await measure()).slice(0, 500))
  await wait(2200)
  await record('07-returned-trail')

  console.log('SEQUENCE COMPLETE', sequence.length, 'frames ->', OUT)
} else if (mode === 'finish') {
  const record = async (stepLabel, extra = {}) => {
    const snapshot = await measure()
    const file = await shoot(stepLabel)
    const row = {
      step: stepLabel,
      viewport: { innerWidth: snapshot.innerWidth, innerHeight: snapshot.innerHeight },
      devicePixelRatio: snapshot.devicePixelRatio,
      rootFontSize: snapshot.rootFontSize,
      theme: snapshot.darkClass ? 'dark' : 'light',
      sha256: file.sha256,
      bytes: file.bytes,
      state: snapshot,
      ...extra
    }
    sequence.push(row)
    writeFileSync(resolve(OUT, 'sequence.json'), JSON.stringify({ port, plugin: process.env.H205_PLUGIN_SHA || null, frames: sequence }, null, 2))
    console.log(`FRAME ${stepLabel}: chip=${snapshot.chip}/${snapshot.chipPending} view=${snapshot.view} w=${snapshot.innerWidth} sha=${file.sha256.slice(0, 12)}`)
    return row
  }

  await setWidth(1049)
  await evaluate(`(() => { const p = document.querySelector('[data-cb-player]'); if (p) p.scrollIntoView({ block: 'start' }); return true })()`)
  await wait(300)

  // Return to the answer surface from the wrong verdict.
  const again = await evaluate(`(() => {
    const b = [...document.querySelectorAll('[data-cb-player] button')].find((n) => (n.innerText || '').trim() === 'Try again')
    if (!b || b.disabled) return false
    b.click(); return true
  })()`)
  if (!again) throw new Error('CDP ' + port + ': "Try again" control missing on the wrong verdict (step: retry-surface). state=' + JSON.stringify(await measure()).slice(0, 400))
  await wait(2000)
  await record('04-retry-surface')

  if (!(await clickText('I used a hint', '[data-cb-assist]'))) throw new Error('CDP ' + port + ': "I used a hint" control missing after Try again (step: hint)')
  await wait(2400)
  await record('05-hint-recorded')

  await typeAnswer(process.env.H205_RIGHT || '好きです')
  await clickCheck()
  const pass = await record('06-hinted-pass')
  if (!/quite|pass|correct/i.test(pass.state.feedback || '') && !/quite|correct/i.test(pass.state.body || '')) {
    console.log('WARN: no pass/not-quite marker found in feedback; body head:', (pass.state.body || '').slice(0, 300))
  }

  // Walk the player to the completion surface.
  for (let i = 0; i < 5; i += 1) {
    const s = await measure()
    if (/You finished/i.test(s.body || '')) break
    const label = await evaluate(`(() => {
      const b = document.querySelector('[data-cb-player-footer] button')
      if (!b || b.disabled) return null
      b.click(); return (b.innerText || '').trim()
    })()`)
    if (!label) break
    await wait(2000)
  }
  await wait(600)
  const completion = await record('07-completion')
  if (!/You finished/i.test(completion.state.body || '')) {
    throw new Error('CDP ' + port + ': completion surface never showed "You finished" (step: completion). state=' + JSON.stringify(completion.state).slice(0, 600))
  }

  const returned = await evaluate(`(() => {
    const b = [...document.querySelectorAll('button')].find((n) => /Return to the trail/i.test((n.innerText || '').trim()) && n.offsetParent !== null)
    if (!b) return false
    b.click(); return true
  })()`)
  if (!returned) throw new Error('CDP ' + port + ': "Return to the trail" control missing (step: return). state=' + JSON.stringify(await measure()).slice(0, 500))
  await wait(2400)
  await record('08-returned-trail')

  console.log('SEQUENCE COMPLETE', sequence.length, 'frames ->', OUT)
}
close()
