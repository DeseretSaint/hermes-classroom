#!/usr/bin/env node
/**
 * GM-006 — drive the isolated Desktop window and capture the Parent Studio take-home proof.
 *
 * Real window, real backend (cb.rpc v24), real Page.captureScreenshot. The pack is composed,
 * drafted, approved and exported through the shipped UI; the printed PDF is the artifact the
 * backend minted for that approval, saved beside the frames.
 *
 *   CB015_CDP_PORT=9341 COURSEBOOK_TEST_STATE=~/.hermes/coursebook-test-gm006 \
 *     node scripts/gm006-live-capture.mjs
 */
import { mkdirSync, writeFileSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createHash } from 'node:crypto'
import { connect } from './cb015-lib.mjs'

const OUT = resolve('docs/visual-review/gm-006')
mkdirSync(OUT, { recursive: true })
const wait = (ms) => new Promise((done) => setTimeout(done, ms))
const withTimeout = (promise, ms, label) =>
  Promise.race([promise, new Promise((_, fail) => setTimeout(() => fail(new Error(`timeout: ${label}`)), ms))])

let cdp = null
const open = async () => {
  cdp = await connect()
  await withTimeout(cdp.send('Page.enable', {}), 20000, 'Page.enable')
  await withTimeout(cdp.send('Runtime.enable', {}), 20000, 'Runtime.enable')
}
const send = async (method, params = {}) => withTimeout(cdp.send(method, params), 60000, method)
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text)
  return r.result.value
}
const waitFor = async (expression, label, timeout = 30000) => {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    try { if (await evaluate(`Boolean(${expression})`)) return true } catch { /* retry */ }
    await wait(150)
  }
  throw new Error(`timed out: ${label}`)
}
const clickText = async (text, scope = 'document') => {
  const clicked = await evaluate(`(() => {
    const root = ${scope}
    const button = [...root.querySelectorAll('button, a')].find(
      (node) => node.innerText.trim().toLowerCase() === ${JSON.stringify(text.toLowerCase())}
    )
    if (!button) return false
    button.click()
    return true
  })()`)
  if (!clicked) throw new Error(`no control with text ${text}`)
  return clicked
}
const frames = []
const state = async () => ({
  hash: await evaluate('location.hash'),
  innerWidth: await evaluate('window.innerWidth'),
  rootFont: await evaluate("getComputedStyle(document.documentElement).fontSize"),
  overflow: await evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth'),
  destination: await evaluate("document.querySelector('[data-cb-destination]')?.getAttribute('data-cb-destination') || null"),
  tabs: await evaluate("document.querySelector('[data-cb-parent-studio-tabs]')?.innerText.replace(/\\s+/g, ' ').trim() || null"),
  shelf: await evaluate("document.querySelectorAll('[data-cb-source-course]').length"),
  sourceMode: await evaluate("document.querySelector('[data-cb-source-mode]')?.getAttribute('data-cb-source-mode') || null"),
  objectives: await evaluate("document.querySelectorAll('[data-cb-source-objective]').length"),
  packState: await evaluate("document.querySelector('[data-cb-takehome-pack]')?.getAttribute('data-cb-takehome-pack-state') || null"),
  proofPages: await evaluate("document.querySelectorAll('[data-cb-proof-page]').length"),
  proofRoles: await evaluate("[...document.querySelectorAll('[data-cb-proof-page]')].map((n) => n.getAttribute('data-cb-proof-page')).join(',')"),
  learnerOnProof: await evaluate("!!document.querySelector('[data-cb-proof-page=\\\"learner_page\\\"]')"),
  answerOnProof: await evaluate("!!document.querySelector('[data-cb-proof-page=\\\"answer_guide\\\"]')"),
  exported: await evaluate("document.querySelector('[data-cb-takehome-exported]')?.getAttribute('data-cb-takehome-exported') || null"),
  text: await evaluate("(document.querySelector('[data-cb-parent-studio]')?.innerText || '').replace(/\\s+/g, ' ').slice(0, 220)")
})
const shot = async (id, { full = false } = {}) => {
  let params = { format: 'png', captureBeyondViewport: full }
  if (full) {
    const metrics = await evaluate('({ width: window.innerWidth, height: Math.max(document.documentElement.scrollHeight, document.body.scrollHeight) })')
    params = { ...params, clip: { x: 0, y: 0, width: metrics.width, height: metrics.height, scale: 1 } }
  }
  const png = await send('Page.captureScreenshot', params)
  const buffer = Buffer.from(png.data, 'base64')
  writeFileSync(resolve(OUT, `${id}.png`), buffer)
  const record = { id, file: `${id}.png`, md5: createHash('md5').update(buffer).digest('hex'), bytes: buffer.length, ...(await state()) }
  frames.push(record)
  console.log(id, JSON.stringify({ width: record.innerWidth, pages: record.proofPages, state: record.packState, overflow: record.overflow }))
}
let override = 1049
const setWidth = async (target, height = 1000) => {
  override = target
  for (let i = 0; i < 12; i += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height, deviceScaleFactor: 1, mobile: false })
    await wait(280)
    const measured = await evaluate('window.innerWidth')
    if (measured === target) return measured
    override = Math.max(200, override + (target - measured))
  }
  throw new Error(`width ${target} did not settle (last ${await evaluate('window.innerWidth')})`)
}
const setText = async (scale) => {
  await evaluate(scale === 200
    ? "document.documentElement.style.setProperty('font-size','32px','important')"
    : "document.documentElement.style.removeProperty('font-size')")
  await wait(300)
}

await open()
await waitFor("!!document.querySelector('[data-cb-route]')", 'coursebook route', 30000)
await evaluate("document.querySelector('[data-cb-nav-item=\\\"home\\\"]')?.click()")
await waitFor("document.querySelector('[data-cb-destination]')?.getAttribute('data-cb-destination') === 'home'", 'home', 30000)
await setWidth(1049)

// Parent Studio, both entrances.
await evaluate("document.querySelector('[data-cb-nav-item=\\\"studio\\\"]')?.click()")
await waitFor("!!document.querySelector('[data-cb-parent-studio-tabs]')", 'parent studio tabs', 30000)
// The tab is route state and survives a destination change, so state it explicitly: the first
// frame must be the authored-plans entrance, not whatever tab the previous run left open.
await clickText('My lesson plans')
await waitFor("document.querySelector('[data-cb-parent-studio]')?.getAttribute('data-cb-parent-studio') === 'plans'", 'lesson plans tab', 30000)
await shot('studio-plans--1049--dark')

await clickText('Take-home from a lesson')
// The route remembers its step across a destination change only until the component unmounts;
// if a restored pack is still open, walk back to the shelf rather than assuming a fresh mount.
for (let attempt = 0; attempt < 4; attempt += 1) {
  await wait(400)
  if (await evaluate("!!document.querySelector('[data-cb-takehome-shelf]')")) break
  const back = await evaluate(`(() => {
    const node = [...document.querySelectorAll('button')].find(
      (candidate) => ['Back to the lesson list', 'Back to courses'].includes(candidate.innerText.trim())
    )
    if (!node) return false
    node.click()
    return true
  })()`)
  if (!back) break
}
await waitFor("!!document.querySelector('[data-cb-takehome-shelf]')", 'take-home shelf', 30000)
await shot('takehome-shelf--1049--dark')

// Game source.
await evaluate(`(() => {
  const row = [...document.querySelectorAll('[data-cb-source-course]')].find((node) => node.innerText.includes('Replace a head gasket'))
  row?.querySelector('button')?.click()
})()`)
await waitFor("document.querySelector('[data-cb-source-mode]')?.getAttribute('data-cb-source-mode') === 'game'", 'game source', 30000)
await shot('takehome-source-game--1049--dark')

// Textbook source.
await clickText('Back to courses')
await waitFor("!!document.querySelector('[data-cb-takehome-shelf]')", 'shelf again', 30000)
await evaluate(`(() => {
  const row = [...document.querySelectorAll('[data-cb-source-course]')].find((node) => node.innerText.includes('Braising at home'))
  row?.querySelector('button')?.click()
})()`)
await waitFor("document.querySelector('[data-cb-source-mode]')?.getAttribute('data-cb-source-mode') === 'textbook'", 'textbook source', 30000)
await shot('takehome-source-textbook--1049--dark')

// Pack workspace and the real composed pages.
await evaluate("document.querySelector('[data-cb-source-objective] button')?.click()")
await waitFor("!!document.querySelector('[data-cb-takehome-pack]')", 'pack workspace', 30000)
await shot('takehome-pack--1049--dark')
await clickText('Preview the pages')
await waitFor("document.querySelectorAll('[data-cb-proof-page]').length >= 4", 'print proof', 40000)
await shot('takehome-proof--1049--dark')
await shot('takehome-print-proof--1049--dark', { full: true })

// The proof is longer than the viewport: capture the learner sheet and the parent-only answer
// guide as separate, readable proofs of what each audience actually receives.
for (const role of ['learner_page', 'answer_guide']) {
  await evaluate(`document.querySelector('[data-cb-proof-page="${role}"]')?.scrollIntoView({ block: 'start' })`)
  await wait(350)
  await shot(`takehome-proof-${role}--1049--dark`)
}
await evaluate("document.querySelector('[data-cb-takehome-proof]')?.scrollIntoView({ block: 'start' })")
await wait(300)

await setWidth(900)
await evaluate("document.querySelector('[data-cb-takehome-proof]')?.scrollIntoView({ block: 'start' })")
await wait(300)
await shot('takehome-proof--900--dark')
await setWidth(460)
await evaluate("document.querySelector('[data-cb-takehome-proof]')?.scrollIntoView({ block: 'start' })")
await wait(300)
await shot('takehome-proof--460--dark')
await setText(200)
await evaluate("document.querySelector('[data-cb-takehome-proof]')?.scrollIntoView({ block: 'start' })")
await wait(400)
await shot('takehome-proof--460--dark--200')
await setText(100)
await setWidth(1049)

// Draft → approve the exact pages → export the real PDF.
await clickText('Save this draft')
await waitFor("document.querySelector('[data-cb-takehome-pack-state]')?.getAttribute('data-cb-takehome-pack-state') === 'draft'", 'draft saved', 30000)
await clickText('Approve these pages')
await waitFor("document.querySelector('[data-cb-takehome-pack-state]')?.getAttribute('data-cb-takehome-pack-state') === 'approved'", 'pages approved', 30000)
await shot('takehome-approved--1049--dark')
await clickText('Export the print-ready PDF')
await waitFor("!!document.querySelector('[data-cb-takehome-exported]')", 'exported', 60000)
await evaluate("document.querySelector('[data-cb-takehome-exported]')?.scrollIntoView({ block: 'center' })")
await wait(250)
await shot('takehome-exported--1049--dark')

// The link the panel renders is the backend's session-bound route; in the isolated rig the
// renderer is the Vite origin, so resolve it against the connection's base URL and carry the
// same token the window uses. Both values are read from the live window, never invented.
const href = await evaluate("document.querySelector('[data-cb-takehome-exported] a')?.getAttribute('href') || null")
if (!href) throw new Error('the exported panel rendered no download link')
const connection = await evaluate('(async () => { const c = await window.hermesDesktop.getConnection(); return { baseUrl: c.baseUrl, token: c.token } })()')
const downloadUrl = new URL(href, connection.baseUrl).toString()
const response = await fetch(downloadUrl, { headers: { Authorization: `Bearer ${connection.token}` } })
if (!response.ok) throw new Error(`artifact fetch ${response.status} for ${downloadUrl}`)
const pdf = Buffer.from(await response.arrayBuffer())
if (pdf.subarray(0, 5).toString('latin1') !== '%PDF-') throw new Error('the artifact is not a PDF')
writeFileSync(resolve(OUT, 'takehome-print-proof.pdf'), pdf)

const pluginSha = createHash('sha256').update(readFileSync('desktop/plugin.js')).digest('hex')
const evidence = {
  captured_at: new Date().toISOString(),
  plugin_sha256: pluginSha,
  cdp_port: process.env.CB015_CDP_PORT || '9341',
  backend: `${connection.baseUrl}`,
  download: { href, resolved: downloadUrl, status: response.status, content_type: response.headers.get('content-type') },
  pdf: pdf ? { file: 'takehome-print-proof.pdf', bytes: pdf.length, sha256: createHash('sha256').update(pdf).digest('hex') } : null,
  frames
}
writeFileSync(resolve(OUT, 'live-evidence.json'), JSON.stringify(evidence, null, 2))
console.log('wrote', frames.length, 'frames;', evidence.pdf ? `pdf ${pdf.length} bytes` : 'no pdf')
cdp.close()
