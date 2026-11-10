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
 *
 * Usage:
 *   node scripts/cp-demo.mjs                       # run docs/launch/cp-demo.steps.json on 9411
 *   node scripts/cp-demo.mjs --dry-run             # validate the step list, print the timeline
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
const logPath = resolve(repo, String(flag('log', `docs/launch/animatic/takes/${spec.id}.jsonl`)))

const KINDS = new Set(['navigate', 'click', 'type', 'wait', 'hover-sweep', 'marker', 'assert'])

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
    if (step.kind === 'assert' && !step.selector) problems.push(`${at}: assert needs selector`)
  })
  return problems
}

const problems = validate(spec.steps, 'steps')
if (problems.length) {
  console.error(`step list invalid (${problems.length}):`)
  for (const problem of problems) console.error(`  ${problem}`)
  process.exit(2)
}

if (dryRun) {
  let elapsed = 0
  console.log(`step list ${stepsPath.replace(`${repo}/`, '')} · ${spec.steps.length} steps · port ${port}`)
  for (const step of spec.steps) {
    if (step.kind === 'wait' && step.ms) elapsed += step.ms
    if (step.kind === 'hover-sweep') elapsed += step.ms || 0
    if (step.kind === 'marker') {
      console.log(`  beat ${String(Math.round(elapsed / beatMs)).padStart(3)}  ~${(elapsed / 1000).toFixed(2)}s  marker ${step.id}`)
    } else {
      console.log(`  ·            ~${(elapsed / 1000).toFixed(2)}s  ${step.kind} ${step.selector || step.hash || step.for || step.id || ''}`)
    }
  }
  console.log('dry run only: nothing was driven, no window was touched')
  process.exit(0)
}

// ---------------------------------------------------------------- CDP client

const sleep = (ms) => new Promise((done) => setTimeout(done, ms))

async function connect(targetPort) {
  const list = await (await fetch(`http://127.0.0.1:${targetPort}/json/list`)).json()
  const page = list.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || ''))
    || list.find((entry) => entry.type === 'page')
  if (!page) throw new Error(`no page target on port ${targetPort}`)
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
  return { send, evaluate, close: () => socket.close(), title: page.title, url: page.url }
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
      if (!(await exists(client, step.selector))) throw new Error(`assert: ${step.selector} is missing`)
      return `asserted ${step.selector}`
    }
    case 'marker':
      return 'marker'
    default:
      throw new Error(`unknown step kind ${step.kind}`)
  }
}

async function runTake(client, list, log, label) {
  const started = Date.now()
  const lines = []
  const write = (entry) => {
    lines.push(entry)
    log(entry)
  }
  write({ t_ms: 0, kind: 'start', take: spec.id, surface: spec.surface, label, url: client.url, title: client.title })
  for (const step of list) {
    const detail = await runStep(client, step)
    const outcome = { t_ms: Date.now() - started, kind: step.kind, detail }
    if (step.kind === 'marker') {
      outcome.marker = step.id
      outcome.beat = Math.round((Date.now() - started) / beatMs)
      outcome.note = step.note || null
    }
    if (step.note) outcome.note = step.note
    write(outcome)
    console.log(`  ${String(outcome.t_ms).padStart(6)} ms  ${step.kind.padEnd(11)} ${outcome.marker || detail}`)
    if (step.kind === 'marker') continue
  }
  const total = Date.now() - started
  write({ t_ms: total, kind: 'end', markers: lines.filter((line) => line.marker).length })
  return { lines, total }
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
      { kind: 'type', selector: '[data-test-field]', text: 'sourdough' },
      { kind: 'click', text_any: ['Submit answer', 'Check answer'], wait_for: '[data-test-verdict]', timeout_ms: 5000 },
      { kind: 'hover-sweep', selector: '[data-test-card]', ms: 200 },
      { kind: 'assert', selector: '[data-test-evidence="1"]' },
      { kind: 'marker', id: 'selftest-end' }
    ]
    const problems = validate(steps, 'selftest')
    if (problems.length) throw new Error(`selftest step list invalid: ${problems.join('; ')}`)
    const { lines, total } = await runTake(client, steps, (entry) => { if (entry.kind === 'end') console.log(`  total ${entry.t_ms} ms`) }, 'selftest')
    const markers = lines.filter((line) => line.marker).map((line) => line.marker)
    const expected = ['selftest-start', 'selftest-end']
    if (markers.join(',') !== expected.join(',')) throw new Error(`selftest markers ${markers.join(',')}`)
    const evidence = await client.evaluate(`document.querySelector('[data-test-evidence]')?.getAttribute('data-test-evidence')`)
    if (evidence !== '1') throw new Error(`selftest evidence count ${evidence}`)
    const answer = await client.evaluate(`document.querySelector('[data-test-field]')?.value`)
    if (answer !== 'sourdough') throw new Error(`selftest typed value ${answer}`)
    client.close()
    console.log(`selftest ok: ${steps.length} steps, ${total} ms, navigate/click/type/wait/hover/marker/assert all executed`)
    return true
  } finally {
    child.kill('SIGINT')
    await sleep(400)
    rmSync(profile, { recursive: true, force: true })
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

let client
try {
  client = await connect(port)
} catch (error) {
  console.error(`cannot attach to the window on port ${port}: ${error.message}`)
  console.error('this driver never invents a take; start the accepted-commit rig first')
  process.exit(1)
}
try {
  const { lines, total } = await runTake(client, spec.steps, () => {}, 'live')
  writeLog(lines)
  console.log(`take complete in ${(total / 1000).toFixed(2)} s (${(total / beatMs).toFixed(1)} beats at 120 BPM)`)
  client.close()
} catch (error) {
  console.error(`take stopped: ${error.message}`)
  try { client.close() } catch { /* already closed */ }
  process.exit(1)
}
