#!/usr/bin/env node
/**
 * CP-033 — the re-recordable demo driver.
 *
 * Replays a step list against the live Hermes Desktop window over the same CDP connection
 * `scripts/cp-capture.mjs` already uses (default port 9411), and writes a timestamped marker log the
 * editor cuts to. The point is cost: when the accepted commit changes, re-recording is
 * `node scripts/cp-demo.mjs` and nothing else.
 *
 * It does not capture frames and it does not claim evidence. Frames still come only from
 * `scripts/cp-capture.mjs`, which is the door that refuses a stale module. This driver just moves
 * the window so the capture door has the right state on screen.
 *
 * Step kinds (`docs/launch/cp-demo.steps.json`):
 *   navigate  { hash | url, wait_for?, timeout_ms? }   set the route, then wait for a selector
 *   click     { selector? , text_any? , wait_for? }    click the first match of selector, else the
 *                                                      first button/link whose trimmed text is one of
 *                                                      text_any (copy changes between v2 and v3)
 *   type      { selector, text, human_ms? }            focus the field, then type (per-character delay
 *                                                      when human_ms is set)
 *   wait      { ms | for, timeout_ms? }                sleep, or wait until a selector exists
 *   hover-sweep { selector, ms }                        slow pointer travel across matched elements
 *   marker    { id, note? }                            write a marker line with elapsed ms + beat
 *   assert    { selector, note? }                      fail the take if the selector is missing
 *   assert    { selector, snapshot, changed|equals }   compare the element's value against a
 *                                                      snapshot taken earlier; stop the take when
 *                                                      the value did not move (or did move, for
 *                                                      `equals`). Presence is not a comparison.
 *   snapshot  { id, selector, attribute? }             read an element's `textContent` (or an
 *                                                      attribute) and keep it under `id` for a
 *                                                      later assert
 *   reconnect { timeout_ms? }                          window transition: close this take's socket,
 *                                                      wait for a page target with a DIFFERENT id
 *
 * Snapshots are the only way a note may say a value changed or stayed the same. They are written to
 * `docs/launch/animatic/takes/<take>.snapshots.json` beside the act logs, so an `--act 2` run can
 * compare against what `--act 1` read. Act 1 (and a full run) starts a new store; nothing carries
 * over from a previous take.
 *
 * Every step carries an `act` (1, 2, …). The close beat ends act 1; act 2 begins with `reconnect`,
 * so the take never pretends a window that was closed is still attached. Either run the whole list
 * in one command (the driver announces when to close the window and waits for the reopened one) or
 * run one act at a time with `--act N`, closing and reopening the window in between.
 *
 * Usage:
 *   node scripts/cp-demo.mjs                       # run docs/launch/cp-demo.steps.json on 9411
 *   node scripts/cp-demo.mjs --dry-run             # validate the step list, print the timeline
 *   node scripts/cp-demo.mjs --act 1               # drive act one only, write its own log
 *   node scripts/cp-demo.mjs --act 2               # attach to the reopened window and drive act two
 *   node scripts/cp-demo.mjs --port 9412 --log /tmp/take.jsonl
 *   node scripts/cp-demo.mjs --selftest            # drive a local fixture with headless chromium
 */
import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repo = resolve(here, '..')
const args = process.argv.slice(2)
const flag = (name, fallback = null) => {
  const index = args.indexOf(`--${name}`)
  if (index < 0) return fallback
  const value = args[index + 1]
  return value && !value.startsWith('--') ? value : true
}

const stepsPath = resolve(repo, String(flag('steps', 'docs/launch/cp-demo.steps.json')))
const dryRun = Boolean(flag('dry-run', false))
const selftest = Boolean(flag('selftest', false))
const beatMs = 500 // 120 BPM, the animatic's grid

const spec = JSON.parse(readFileSync(stepsPath, 'utf8'))
const port = Number(flag('port', spec.cdp_port || 9411))
const actArg = flag('act', null)
const actNumber = actArg === null ? null : Number(actArg)
if (actNumber !== null && (!Number.isInteger(actNumber) || actNumber < 1)) {
  console.error(`--act needs a positive integer, got ${JSON.stringify(actArg)}`)
  process.exit(2)
}
const logDefault = actNumber === null
  ? `docs/launch/animatic/takes/${spec.id}.jsonl`
  : `docs/launch/animatic/takes/${spec.id}-act${actNumber}.jsonl`
const logPath = resolve(repo, String(flag('log', logDefault)))

const KINDS = new Set(['navigate', 'click', 'type', 'wait', 'hover-sweep', 'marker', 'assert', 'snapshot', 'reconnect'])

function validate(list, where) {
  const problems = []
  list.forEach((step, index) => {
    const at = `${where}[${index}]`
    if (!step || typeof step !== 'object') { problems.push(`${at}: not an object`); return }
    if (!KINDS.has(step.kind)) problems.push(`${at}: unknown kind ${JSON.stringify(step.kind)}`)
    if (step.kind === 'navigate' && !step.hash && !step.url) problems.push(`${at}: navigate needs hash or url`)
    if (step.kind === 'click' && !step.selector && !(Array.isArray(step.text_any) && step.text_any.length)) {
      problems.push(`${at}: click needs selector or text_any`)
    }
    if (step.kind === 'type' && (!step.selector || typeof step.text !== 'string')) {
      problems.push(`${at}: type needs selector and text`)
    }
    if (step.kind === 'wait' && !step.ms && !step.for) problems.push(`${at}: wait needs ms or for`)
    if (step.kind === 'hover-sweep' && !step.selector) problems.push(`${at}: hover-sweep needs selector`)
    if (step.kind === 'marker' && !step.id) problems.push(`${at}: marker needs id`)
    if (step.kind === 'snapshot' && (!step.selector || !step.id)) problems.push(`${at}: snapshot needs id and selector`)
    if (step.kind === 'assert') {
      if (!step.selector) problems.push(`${at}: assert needs selector`)
      if (step.snapshot) {
        if (!step.changed && !step.equals) problems.push(`${at}: assert against a snapshot needs changed or equals`)
        if (step.changed && step.equals) problems.push(`${at}: assert cannot both expect change and equality`)
      } else if (step.changed || step.equals) {
        problems.push(`${at}: assert compares nothing without a snapshot id`)
      }
    }
  })
  return problems
}

const problems = validate(spec.steps, 'steps')
if (problems.length) {
  console.error(`step list invalid (${problems.length}):`)
  for (const problem of problems) console.error(`  ${problem}`)
  process.exit(2)
}

// Acts must be positive integers, run in file order, and be contiguous from 1. The close/reopen is
// only real if act 2 begins after act 1 ends, so a step that drifts back into act 1 is an error.
// The selftest builds its own step lists, so it skips the production step list's act rules.
let acts = []
let plan = []
if (!selftest) {
  const actProblems = []
  let previousAct = 0
  for (const [index, step] of spec.steps.entries()) {
    if (!Number.isInteger(step.act) || step.act < 1) {
      actProblems.push(`steps[${index}]: act must be a positive integer (${JSON.stringify(step.act)})`)
      continue
    }
    if (step.act < previousAct) actProblems.push(`steps[${index}]: act ${step.act} follows act ${previousAct}`)
    previousAct = Math.max(previousAct, step.act)
  }
  acts = [...new Set(spec.steps.map((step) => step.act))].sort((a, b) => a - b)
  acts.forEach((value, index) => {
    if (value !== index + 1) actProblems.push(`acts are not contiguous from 1: ${acts.join(', ')}`)
  })
  if (actNumber !== null && !acts.includes(actNumber)) {
    actProblems.push(`--act ${actNumber} does not exist; the step list has acts ${acts.join(', ')}`)
  }
  if (actProblems.length) {
    console.error(`step list acts invalid (${actProblems.length}):`)
    for (const problem of actProblems) console.error(`  ${problem}`)
    process.exit(2)
  }

  plan = actNumber === null ? spec.steps : spec.steps.filter((step) => step.act === actNumber)
  if (!plan.length) {
    console.error(`--act ${actNumber} selects no steps`)
    process.exit(2)
  }
}

if (dryRun) {
  let elapsed = 0
  const actLabel = actNumber === null ? `acts ${acts.join('+')}` : `act ${actNumber}`
  console.log(`step list ${stepsPath.replace(`${repo}/`, '')} · ${plan.length} steps · ${actLabel} · port ${port}`)
  let seenAct = null
  for (const step of plan) {
    if (step.act !== seenAct) {
      seenAct = step.act
      console.log(`  --- act ${step.act} ---`)
    }
    if (step.kind === 'wait' && step.ms) elapsed += step.ms
    if (step.kind === 'hover-sweep') elapsed += step.ms || 0
    if (step.kind === 'marker') {
      console.log(`  beat ${String(Math.round(elapsed / beatMs)).padStart(3)}  ~${(elapsed / 1000).toFixed(2)}s  marker ${step.id}`)
    } else if (step.kind === 'reconnect') {
      console.log(`  ·            ~${(elapsed / 1000).toFixed(2)}s  reconnect  (closes this socket; waits for a DIFFERENT page target)`)
    } else if (step.kind === 'snapshot') {
      console.log(`  ·            ~${(elapsed / 1000).toFixed(2)}s  snapshot ${step.id} of ${step.selector}${step.attribute ? `@${step.attribute}` : ''}`)
    } else if (step.kind === 'assert' && step.snapshot) {
      const verb = step.changed ? 'changed' : 'equals'
      console.log(`  ·            ~${(elapsed / 1000).toFixed(2)}s  assert ${step.selector} ${verb} snapshot ${step.snapshot}`)
    } else {
      console.log(`  ·            ~${(elapsed / 1000).toFixed(2)}s  ${step.kind} ${step.selector || step.hash || step.for || step.id || ''}`)
    }
  }
  console.log('dry run only: nothing was driven, no window was touched')
  process.exit(0)
}

// ---------------------------------------------------------------- CDP client

const sleep = (ms) => new Promise((done) => setTimeout(done, ms))

async function connectTo(page) {
  const socket = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((done, fail) => {
    socket.addEventListener('open', done, { once: true })
    socket.addEventListener('error', fail, { once: true })
  })
  let nextId = 1
  const pending = new Map()
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    if (message.id && pending.has(message.id)) {
      const { done, fail } = pending.get(message.id)
      pending.delete(message.id)
      if (message.error) fail(new Error(JSON.stringify(message.error)))
      else done(message.result)
    }
  })
  const send = (method, params = {}) => new Promise((done, fail) => {
    const id = nextId++
    pending.set(id, { done, fail })
    socket.send(JSON.stringify({ id, method, params }))
  })
  const evaluate = async (expression) => {
    const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
    }
    return result.result?.value
  }
  await send('Runtime.enable')
  await send('Page.enable')
  return { send, evaluate, close: () => socket.close(), title: page.title, url: page.url, targetId: page.id }
}

async function findPage(targetPort, exclude) {
  const list = await (await fetch(`http://127.0.0.1:${targetPort}/json/list`)).json()
  const pages = (Array.isArray(list) ? list : []).filter((entry) => entry.type === 'page' && !exclude.includes(entry.id))
  return pages.find((entry) => /Hermes/.test(entry.title || '')) || pages[0] || null
}

async function connect(targetPort) {
  const page = await findPage(targetPort, [])
  if (!page) throw new Error(`no page target on port ${targetPort}`)
  return connectTo(page)
}

/**
 * The window transition. The take's own socket is closed first; the driver then refuses to attach
 * to the target it just left, so act two can only continue on a page that appeared after the close.
 * A reopened window is a new target id; reusing the old one would mean the window was never closed
 * and proof 3 would be stamped on a frame that proves nothing.
 */
async function waitForNewPage(targetPort, exclude, timeoutMs) {
  const deadline = Date.now() + (timeoutMs || 180000)
  let lastError = null
  while (Date.now() < deadline) {
    try {
      const page = await findPage(targetPort, exclude)
      if (page) return await connectTo(page)
    } catch (error) {
      lastError = error
    }
    await sleep(250)
  }
  throw new Error(
    `no new page target on port ${targetPort} within ${Math.round((timeoutMs || 180000) / 1000)} s` +
    `${lastError ? ` (${lastError.message})` : ''}; act two never attaches to the page act one left`,
  )
}

const q = (selector) => JSON.stringify(selector)

async function exists(client, selector) {
  return Boolean(await client.evaluate(`Boolean(document.querySelector(${q(selector)}))`))
}

async function waitFor(client, selector, timeoutMs) {
  const deadline = Date.now() + (timeoutMs || 20000)
  while (Date.now() < deadline) {
    if (await exists(client, selector)) return true
    await sleep(120)
  }
  return false
}

/**
 * The value a snapshot reads: an element's trimmed `textContent`, or one of its attributes when the
 * step names one. Missing elements return null rather than an empty string, so a snapshot of a frame
 * that is not on screen stops the take instead of recording a value nobody saw.
 */
async function readValue(client, step) {
  const raw = await client.evaluate(`(() => {
    const node = document.querySelector(${q(step.selector)})
    if (!node) return null
    const value = ${step.attribute ? `node.getAttribute(${q(step.attribute)})` : 'node.textContent'}
    return value === null || value === undefined ? null : String(value).replace(/\\s+/g, ' ').trim()
  })()`)
  return raw === null || raw === undefined ? null : String(raw)
}

/**
 * Values read by `snapshot` steps, persisted beside the act logs so an `--act 2` invocation can
 * compare against what `--act 1` read. Act 1 and a full run start a fresh store: a snapshot from a
 * previous take must never stand in for this one.
 */
const snapshotStore = {
  path: null,
  started: 0,
  values: new Map(),
  start(path) {
    this.path = path
    this.started = Date.now()
    this.values = new Map()
    try { rmSync(path, { force: true }) } catch { /* nothing to clear */ }
  },
  resume(path) {
    this.path = path
    this.started = Date.now()
    this.values = new Map()
    if (!existsSync(path)) return 0
    const saved = JSON.parse(readFileSync(path, 'utf8'))
    for (const [id, entry] of Object.entries(saved.snapshots || {})) this.values.set(id, entry)
    return this.values.size
  },
  set(id, entry) {
    this.values.set(id, entry)
    this.save()
  },
  get(id) {
    return this.values.get(id)
  },
  save() {
    if (!this.path) return
    mkdirSync(dirname(this.path), { recursive: true })
    const snapshots = Object.fromEntries([...this.values.entries()])
    writeFileSync(this.path, `${JSON.stringify({ take: spec.id, snapshots }, null, 2)}\n`)
  },
}

// ---------------------------------------------------------------- step runner

async function runStep(client, step) {
  switch (step.kind) {
    case 'navigate': {
      if (step.url) {
        await client.send('Page.navigate', { url: step.url })
      } else {
        await client.evaluate(`(() => { location.hash = ${q(step.hash)}; return location.hash })()`)
      }
      if (step.wait_for) {
        const seen = await waitFor(client, step.wait_for, step.timeout_ms)
        if (!seen) throw new Error(`navigate: ${step.wait_for} never appeared`)
      }
      return 'navigated'
    }
    case 'click': {
      if (step.selector) {
        const hit = await client.evaluate(`(() => {
          const node = document.querySelector(${q(step.selector)})
          if (!node) return false
          node.scrollIntoView({ block: 'center' })
          node.click()
          return true
        })()`)
        if (hit) {
          if (step.wait_for && !(await waitFor(client, step.wait_for, step.timeout_ms))) {
            throw new Error(`click: ${step.wait_for} never appeared`)
          }
          return `clicked ${step.selector}`
        }
      }
      if (Array.isArray(step.text_any) && step.text_any.length) {
        const hit = await client.evaluate(`(() => {
          const wanted = ${JSON.stringify(step.text_any)}
          const nodes = [...document.querySelectorAll('button,a,[role=button],[role=link]')]
          const node = nodes.find((n) => wanted.includes((n.innerText || '').trim()))
          if (!node) return null
          node.scrollIntoView({ block: 'center' })
          node.click()
          return (node.innerText || '').trim()
        })()`)
        if (!hit) throw new Error(`click: none of ${JSON.stringify(step.text_any)} is on screen`)
        if (step.wait_for && !(await waitFor(client, step.wait_for, step.timeout_ms))) {
          throw new Error(`click: ${step.wait_for} never appeared`)
        }
        return `clicked "${hit}"`
      }
      throw new Error('click: target not found')
    }
    case 'type': {
      const focused = await client.evaluate(`(() => {
        const node = document.querySelector(${q(step.selector)})
        if (!node) return false
        node.scrollIntoView({ block: 'center' })
        node.focus()
        const proto = node instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
        const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set
        if (setter) setter.call(node, '')
        node.dispatchEvent(new Event('input', { bubbles: true }))
        return true
      })()`)
      if (!focused) throw new Error(`type: ${step.selector} not found`)
      if (step.human_ms) {
        for (const ch of step.text) {
          await client.send('Input.insertText', { text: ch })
          await sleep(step.human_ms)
        }
      } else {
        await client.send('Input.insertText', { text: step.text })
      }
      return `typed ${step.text.length} chars`
    }
    case 'wait': {
      if (step.ms) { await sleep(step.ms); return `waited ${step.ms} ms` }
      const seen = await waitFor(client, step.for, step.timeout_ms)
      if (!seen) throw new Error(`wait: ${step.for} never appeared`)
      return `saw ${step.for}`
    }
    case 'hover-sweep': {
      const boxes = await client.evaluate(`(() => {
        const nodes = [...document.querySelectorAll(${q(step.selector)})]
        return nodes.map((n) => { const r = n.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 } })
      })()`)
      if (!boxes.length) throw new Error(`hover-sweep: ${step.selector} matched nothing`)
      const per = Math.max(60, Math.round((step.ms || 2000) / boxes.length))
      for (const box of boxes) {
        await client.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: Math.round(box.x), y: Math.round(box.y) })
        await sleep(per)
      }
      return `swept ${boxes.length} targets`
    }
    case 'assert': {
      if (!step.snapshot) {
        if (!(await exists(client, step.selector))) throw new Error(`assert: ${step.selector} is missing`)
        return `asserted ${step.selector} is present`
      }
      const saved = snapshotStore.get(step.snapshot)
      if (!saved) {
        throw new Error(`assert: no snapshot named ${step.snapshot}; the take cannot compare a value it never read`)
      }
      // Read the value exactly the way the snapshot read it — same element, same attribute — so the
      // comparison is of like with like. A different selector is a different measurement.
      if (step.selector && step.selector !== saved.selector) {
        throw new Error(
          `assert: snapshot ${step.snapshot} was taken from ${saved.selector}, not ${step.selector}; ` +
          'comparing two different elements is not a comparison',
        )
      }
      if (step.attribute && step.attribute !== saved.attribute) {
        throw new Error(`assert: snapshot ${step.snapshot} read ${saved.attribute || 'textContent'}, not ${step.attribute}`)
      }
      const current = await readValue(client, { selector: saved.selector, attribute: saved.attribute })
      if (current === null) throw new Error(`assert: ${saved.selector} is missing`)
      if (step.changed) {
        if (current === saved.value) {
          throw new Error(
            `assert: ${step.snapshot} did not change (${saved.selector} is still ${JSON.stringify(current)}); ` +
            'refusing to stamp a value change that did not happen',
          )
        }
        return `asserted ${saved.selector} changed ${JSON.stringify(saved.value)} -> ${JSON.stringify(current)}`
      }
      if (current !== saved.value) {
        throw new Error(
          `assert: ${step.snapshot} did not survive as it was (${JSON.stringify(saved.value)} -> ` +
          `${JSON.stringify(current)}); refusing to stamp a state the take did not observe`,
        )
      }
      return `asserted ${saved.selector} still ${JSON.stringify(current)}`
    }
    case 'snapshot': {
      const value = await readValue(client, step)
      if (value === null) throw new Error(`snapshot: ${step.selector} is not on screen, so there is nothing to read`)
      snapshotStore.set(step.id, {
        selector: step.selector,
        attribute: step.attribute || null,
        value,
        act: step.act,
        at_ms: Date.now(),
      })
      return `snapshot ${step.id} = ${JSON.stringify(value)}`
    }
    case 'marker':
      return 'marker'
    case 'reconnect':
      // Handled by the take loop: a reconnect replaces the client, so it cannot run inside a step.
      throw new Error('reconnect must be executed by the take loop')
    default:
      throw new Error(`unknown step kind ${step.kind}`)
  }
}

async function runTake(client, list, log, label, act = null, targetPort = port) {
  const started = Date.now()
  const lines = []
  const write = (entry) => {
    lines.push(entry)
    log(entry)
  }
  write({
    t_ms: 0, kind: 'start', take: spec.id, act,
    surface: spec.surface, label,
    url: client ? client.url : null,
    title: client ? client.title : null,
    target_id: client ? client.targetId : null,
  })
  for (const step of list) {
    if (step.kind === 'reconnect') {
      const from = client ? client.targetId : null
      const timeoutMs = step.timeout_ms || 180000
      if (client) client.close()
      console.log(`  ${String(Date.now() - started).padStart(6)} ms  reconnect   close the window now; waiting up to ${Math.round(timeoutMs / 1000)} s for a fresh page target on port ${targetPort}`)
      client = await waitForNewPage(targetPort, from ? [from] : [], timeoutMs)
      const outcome = {
        t_ms: Date.now() - started,
        kind: 'reconnect',
        detail: `target ${from || '(none)'} -> ${client.targetId}`,
        from_target: from,
        to_target: client.targetId,
        // A reused target id would mean the window was never closed. Null when act two runs as its
        // own invocation, where act one's id lives in the other act's log.
        fresh_target: from === null ? null : client.targetId !== from,
      }
      if (step.note) outcome.note = step.note
      write(outcome)
      console.log(`  ${String(outcome.t_ms).padStart(6)} ms  ${'reconnect'.padEnd(11)} ${outcome.detail} (fresh target: ${outcome.fresh_target})`)
      continue
    }
    const detail = await runStep(client, step)
    const outcome = { t_ms: Date.now() - started, kind: step.kind, detail }
    if (step.kind === 'snapshot') {
      outcome.snapshot = step.id
      outcome.value = snapshotStore.get(step.id)?.value ?? null
    }
    if (step.kind === 'assert' && step.snapshot) {
      outcome.snapshot = step.snapshot
      outcome.comparison = step.changed ? 'changed' : 'equals'
    }
    if (step.kind === 'marker') {
      outcome.marker = step.id
      outcome.beat = Math.round((Date.now() - started) / beatMs)
      if (step.note) outcome.note = step.note
    }
    if (step.note && step.kind !== 'marker') outcome.note = step.note
    write(outcome)
    console.log(`  ${String(outcome.t_ms).padStart(6)} ms  ${step.kind.padEnd(11)} ${outcome.marker || detail}`)
  }
  const total = Date.now() - started
  write({ t_ms: total, kind: 'end', act, markers: lines.filter((line) => line.marker).length })
  return { lines, total, client }
}

function writeLog(lines) {
  mkdirSync(dirname(logPath), { recursive: true })
  writeFileSync(logPath, `${lines.map((line) => JSON.stringify(line)).join('\n')}\n`)
  console.log(`log ${logPath.replace(`${repo}/`, '')} (${lines.length} lines)`)
}

// ---------------------------------------------------------------- selftest

async function selftestRun() {
  const fixture = resolve(repo, 'tests/fixtures/cp-demo/fixture.html')
  if (!existsSync(fixture)) throw new Error(`fixture missing: ${fixture}`)
  const cdpPort = 9590 + Math.floor(Math.random() * 9)
  const profile = resolve(process.env.TMPDIR || '/tmp', `cp-demo-selftest-${Date.now()}`)
  const snapshotFile = resolve(process.env.TMPDIR || '/tmp', `cp-demo-selftest-${Date.now()}.snapshots.json`)
  snapshotStore.start(snapshotFile)
  const child = spawn(process.env.CHROMIUM || 'chromium', [
    '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
    `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
    '--window-size=1280,800', `file://${fixture}`
  ], { stdio: 'ignore' })
  try {
    let client = null
    for (let attempt = 0; attempt < 60 && !client; attempt += 1) {
      await sleep(250)
      try { client = await connect(cdpPort) } catch { client = null }
    }
    if (!client) throw new Error('selftest: chromium never opened a CDP page')
    const steps = [
      { kind: 'navigate', hash: '#selftest', wait_for: '[data-test-ready]', timeout_ms: 10000 },
      { kind: 'marker', id: 'selftest-start' },
      { kind: 'click', selector: '[data-test-start]' },
      { kind: 'wait', for: '[data-test-shelf="ready"]', timeout_ms: 5000 },
      { kind: 'snapshot', id: 'evidence', selector: '[data-test-evidence]', attribute: 'data-test-evidence' },
      { kind: 'type', selector: '[data-test-field]', text: 'sourdough' },
      { kind: 'click', text_any: ['Submit answer', 'Check answer'], wait_for: '[data-test-verdict]', timeout_ms: 5000 },
      { kind: 'assert', selector: '[data-test-evidence]', snapshot: 'evidence', changed: true },
      { kind: 'snapshot', id: 'evidence-after', selector: '[data-test-evidence]', attribute: 'data-test-evidence' },
      { kind: 'hover-sweep', selector: '[data-test-card]', ms: 200 },
      { kind: 'assert', selector: '[data-test-evidence="1"]' },
      { kind: 'marker', id: 'selftest-end' }
    ]
    const problems = validate(steps, 'selftest')
    if (problems.length) throw new Error(`selftest step list invalid: ${problems.join('; ')}`)
    const take = await runTake(client, steps, (entry) => { if (entry.kind === 'end') console.log(`  total ${entry.t_ms} ms`) }, 'selftest', null, cdpPort)
    const markers = take.lines.filter((line) => line.marker).map((line) => line.marker)
    const expected = ['selftest-start', 'selftest-end']
    if (markers.join(',') !== expected.join(',')) throw new Error(`selftest markers ${markers.join(',')}`)
    const evidence = await client.evaluate(`document.querySelector('[data-test-evidence]')?.getAttribute('data-test-evidence')`)
    if (evidence !== '1') throw new Error(`selftest evidence count ${evidence}`)
    const answer = await client.evaluate(`document.querySelector('[data-test-field]')?.value`)
    if (answer !== 'sourdough') throw new Error(`selftest typed value ${answer}`)
    console.log(`selftest ok: ${steps.length} steps, ${take.total} ms, navigate/click/type/wait/hover/marker/assert/snapshot all executed`)

    // --- value comparison. An unchanged snapshot must stop the take before the next marker: the
    // log is what the editor cuts to, so a value that never moved cannot stamp a "changed" frame.
    const refusedEntries = []
    const refusal = await runTake(client, [
      { kind: 'snapshot', id: 'same-evidence', selector: '[data-test-evidence]', attribute: 'data-test-evidence' },
      { kind: 'assert', selector: '[data-test-evidence]', snapshot: 'same-evidence', changed: true },
      { kind: 'marker', id: 'selftest-stamped-anyway' },
    ], (entry) => refusedEntries.push(entry), 'selftest-refusal', null, cdpPort).then(() => null, (error) => error)
    if (!refusal) throw new Error('selftest: an unchanged snapshot did not stop the take')
    if (!/did not change/.test(refusal.message)) throw new Error(`selftest: refusal said ${refusal.message}`)
    if (refusedEntries.some((entry) => entry.marker)) {
      throw new Error('selftest: the take stamped a marker after the value comparison failed')
    }
    // The store is the only channel act two has to act one's readings; prove it survives a reload.
    snapshotStore.resume(snapshotFile)
    const before = snapshotStore.get('evidence')
    const after = snapshotStore.get('evidence-after')
    if (!before || before.value !== '0' || !after || after.value !== '1') {
      throw new Error(`selftest: the snapshot store did not carry act one's values (${JSON.stringify({ before, after })})`)
    }
    console.log('snapshot ok: evidence changed 0 -> 1; an unchanged value stopped the take before its marker; store reloaded with both readings')

    // --- window transition. Act two must attach to a page target act one never held, and a
    // reconnect must skip the page it was told to leave even while that page is still open.
    const actOneTarget = client.targetId
    const closed = await fetch(`http://127.0.0.1:${cdpPort}/json/close/${actOneTarget}`, { method: 'PUT' })
    if (!closed.ok) throw new Error(`selftest: could not close the act-one window (${closed.status})`)
    client.close()
    await sleep(400)
    const openWindow = async (label) => {
      // /json/new answers with a blank target on some Chromium builds, so navigate it explicitly
      // rather than trusting the url query parameter.
      const response = await fetch(`http://127.0.0.1:${cdpPort}/json/new?about:blank`, { method: 'PUT' })
      if (!response.ok) throw new Error(`selftest: could not open the ${label} window (${response.status})`)
      const page = await response.json()
      let connected = null
      for (let attempt = 0; attempt < 40 && !connected; attempt += 1) {
        await sleep(150)
        try {
          const candidate = await connectTo(page)
          await candidate.send('Page.navigate', { url: `file://${fixture}#${label}` })
          for (let load = 0; load < 20; load += 1) {
            await sleep(150)
            if (await candidate.evaluate('Boolean(document.querySelector("[data-test-ready]"))')) break
          }
          if (await candidate.evaluate('Boolean(document.querySelector("[data-test-ready]"))')) connected = candidate
          else candidate.close()
        } catch { connected = null }
      }
      if (!connected) throw new Error(`selftest: the ${label} window never loaded the fixture`)
      connected.close()
      return page.id
    }
    const actTwoTarget = await openWindow('act2')
    const actTwo = await runTake(null, [
      { kind: 'reconnect', timeout_ms: 10000, note: 'selftest: act two attaches to the reopened window' },
      { kind: 'wait', for: '[data-test-ready]', timeout_ms: 5000 },
      { kind: 'marker', id: 'selftest-act2-end' },
    ], (entry) => { if (entry.kind === 'end') console.log(`  act two total ${entry.t_ms} ms`) }, 'selftest-act2', 2, cdpPort)
    const reconnected = actTwo.lines.find((line) => line.kind === 'reconnect')
    if (!reconnected) throw new Error('selftest: act two logged no reconnect line')
    if (actTwoTarget === actOneTarget) throw new Error('selftest: the reopened window reused the act-one target')
    if (reconnected.to_target !== actTwoTarget) {
      throw new Error(`selftest: act two attached to ${reconnected.to_target}, not the reopened ${actTwoTarget}`)
    }
    if (actTwo.lines.filter((line) => line.marker).map((line) => line.marker).join(',') !== 'selftest-act2-end') {
      throw new Error('selftest: act two markers are wrong')
    }

    const actThreeTarget = await openWindow('act3')
    const actThree = await runTake(actTwo.client, [
      { kind: 'reconnect', timeout_ms: 10000, note: 'selftest: reconnect skips the page it left' },
      { kind: 'marker', id: 'selftest-act3-end' },
    ], () => {}, 'selftest-act3', 3, cdpPort)
    const skipped = actThree.lines.find((line) => line.kind === 'reconnect')
    if (!skipped || skipped.to_target !== actThreeTarget) {
      throw new Error(`selftest: reconnect reused a stale target (${skipped && skipped.to_target})`)
    }
    if (skipped.fresh_target !== true) throw new Error('selftest: the reconnect did not report a fresh target')
    actThree.client.close()
    console.log(`transition ok: act 1 target ${actOneTarget} -> act 2 target ${actTwoTarget} (different) -> act 3 target ${actThreeTarget}; skipped the still-open act-two page`)
    return true
  } finally {
    child.kill('SIGINT')
    await sleep(400)
    rmSync(profile, { recursive: true, force: true })
    rmSync(snapshotFile, { force: true })
  }
}

// ---------------------------------------------------------------- main

if (selftest) {
  try {
    await selftestRun()
    process.exit(0)
  } catch (error) {
    console.error(`selftest failed: ${error.message}`)
    process.exit(1)
  }
}

let client = null
const snapshotPath = resolve(dirname(logPath), `${spec.id}.snapshots.json`)
if (actNumber === null || actNumber === 1) {
  snapshotStore.start(snapshotPath)
} else {
  const carried = snapshotStore.resume(snapshotPath)
  if (carried === 0) {
    console.log(`act ${actNumber}: no snapshot store at ${snapshotPath.replace(`${repo}/`, '')}; a value comparison against act one will stop the take`)
  } else {
    console.log(`act ${actNumber}: read ${carried} snapshot(s) taken before the close`)
  }
}
const opensWithReconnect = plan[0].kind === 'reconnect'
if (!opensWithReconnect) {
  try {
    client = await connect(port)
  } catch (error) {
    console.error(`cannot attach to the window on port ${port}: ${error.message}`)
    console.error('this driver never invents a take; start the accepted-commit rig first')
    process.exit(1)
  }
} else {
  try {
    await fetch(`http://127.0.0.1:${port}/json/list`)
  } catch (error) {
    console.error(`cannot reach the CDP port ${port}: ${error.message}`)
    console.error('act two attaches to the reopened window; open it before running this act')
    process.exit(1)
  }
  console.log(`act ${actNumber}: re-attaching to the reopened window on port ${port}`)
}
try {
  const take = await runTake(client, plan, () => {}, 'live', actNumber)
  if (actNumber === null) {
    const transitions = take.lines.filter((line) => line.kind === 'reconnect')
    for (const transition of transitions) {
      if (transition.fresh_target !== true) {
        throw new Error(`the reconnect at ${transition.t_ms} ms did not attach to a fresh page target`)
      }
    }
  } else if (client === null) {
    console.log(`act ${actNumber} alone cannot compare target ids; act 1's log records its target_id`)
  }
  writeLog(take.lines)
  console.log(`take complete in ${(take.total / 1000).toFixed(2)} s (${(take.total / beatMs).toFixed(1)} beats at 120 BPM)`)
  take.client.close()
} catch (error) {
  console.error(`take stopped: ${error.message}`)
  try { client.close() } catch { /* already closed */ }
  process.exit(1)
}
