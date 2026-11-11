#!/usr/bin/env node
/**
 * audit-screen.mjs — measure a rendered screen against a UI spec, structurally.
 *
 * Reads a spec from `visual/spec/<screen>.json` (see scripts/gen-ui-spec.py), measures the render
 * at 1344x768, and writes a per-node diff plus 600x600 reference/current crops for each signature
 * element.
 *
 * Usage:
 *   node scripts/audit-screen.mjs visual/spec/home.json --html design/home-scene.html
 *   node scripts/audit-screen.mjs visual/spec/home.json --port 9371
 *   node scripts/audit-screen.mjs visual/spec/home.json --html <file> --out <dir>
 *
 * Hard rule (coursebook-visual-production §2): against a live window this script never reloads,
 * never resizes, never focuses and never navigates. It attaches, verifies that the render is
 * already 1344x768, and refuses (exit 3) instead of changing the window to fit. The `--html` path
 * renders its own offscreen Chromium, so it still obeys the rule for the owner's window.
 *
 * Exit codes: 0 wrote the audit, 2 bad usage/input, 3 refused (wrong viewport or no route).
 */
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { createRequire } from 'node:module'
import { fileURLToPath, pathToFileURL } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const argv = process.argv.slice(2)
const specArg = argv.find((value) => !value.startsWith('--'))
const opt = (name, fallback) => {
  const i = argv.indexOf(name)
  return i === -1 ? fallback : argv[i + 1]
}
const HTML = opt('--html', null)
const PORT = Number(opt('--port', 0))
const EXPLICIT_OUT = opt('--out', null)
const TOLERANCE = 2 // CSS px, the card's +/-2 px gate
const VIEWPORT = { width: 1344, height: 768 }
const CROP = 600

if (!specArg) {
  console.error('usage: audit-screen.mjs <spec.json> --html <file> | --port <cdp>')
  process.exit(2)
}
if (!HTML && !PORT) {
  console.error('one of --html <file> or --port <cdp> is required')
  process.exit(2)
}

const SPEC_PATH = path.resolve(specArg)
if (!fs.existsSync(SPEC_PATH)) {
  console.error(`no spec at ${SPEC_PATH}`)
  process.exit(2)
}
const spec = JSON.parse(fs.readFileSync(SPEC_PATH, 'utf8'))
// visual/spec/<screen>.json -> repository root. Output lands beside the spec, not in the cwd,
// so an audit can be run from any worktree that has the reference HTML checked out.
const ROOT = path.resolve(path.dirname(SPEC_PATH), '..', '..')
const OUT_DIR = path.resolve(EXPLICIT_OUT || path.join(ROOT, 'visual', 'audit'))
const SCREEN = spec.screen || path.basename(SPEC_PATH, '.json')
const AUDIT_JSON = path.join(OUT_DIR, `${SCREEN}.json`)
const CROP_DIR = path.join(OUT_DIR, SCREEN)

const requireVisual = createRequire(path.join(ROOT, 'visual', 'package.json'))
const { chromium } = requireVisual('playwright')
const { PNG } = requireVisual('pngjs')

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const sha256 = (buffer) => crypto.createHash('sha256').update(buffer).digest('hex')
const round = (value, digits = 2) => Math.round(value * 10 ** digits) / 10 ** digits

function flatten(node, depth = 0, out = []) {
  out.push({ node, depth })
  for (const child of node.children || []) flatten(child, depth + 1, out)
  return out
}

function tableOf(element) {
  let colour = null
  if (typeof element === 'string') {
    const raw = String(element).trim()
    if (/^#[0-9a-f]{6}$/i.test(raw)) colour = raw.toLowerCase()
  }
  return colour
}

function firstFamily(css) {
  return String(css || '').split(',')[0].trim().replace(/^["']|["']$/g, '')
}

function rgbToHex(css) {
  const match = /rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/.exec(String(css || ''))
  if (!match) return null
  const toHex = (v) => Math.round(Number(v)).toString(16).padStart(2, '0')
  return `#${toHex(match[1])}${toHex(match[2])}${toHex(match[3])}`
}

async function launchBrowser() {
  const args = ['--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1']
  try {
    return await chromium.launch({ args })
  } catch (error) {
    const candidates = [
      process.env.CHROMIUM_PATH,
      '/usr/bin/chromium',
      '/usr/bin/chromium-browser',
      '/usr/bin/google-chrome',
      '/usr/bin/google-chrome-stable'
    ].filter(Boolean)
    for (const executablePath of candidates) {
      if (fs.existsSync(executablePath)) {
        return chromium.launch({ executablePath, args })
      }
    }
    throw error
  }
}

const MEASURE = (jobs) => {
  const out = []
  for (const job of jobs) {
    let selectorUsed = job.selector
    let matches = document.querySelectorAll(job.selector)
    if (!matches.length && job.fallback) {
      selectorUsed = job.fallback
      matches = document.querySelectorAll(job.fallback)
    }
    const element = matches[job.index || 0]
    if (!element) {
      out.push({ id: job.id, found: false, matches: matches.length, selectorUsed })
      continue
    }
    const rect = element.getBoundingClientRect()
    const style = getComputedStyle(element)
    // The layout box: offsetLeft/offsetTop against the offset parent's border box, plus
    // offsetWidth/offsetHeight. This is transform-free, so the reference's slight card and tag
    // rotations do not inflate a 176 px card into a 180.8 px bounding box.
    const offsetParent = element.offsetParent
    const parentRect = offsetParent ? offsetParent.getBoundingClientRect() : null
    const layout = {
      left: (parentRect ? parentRect.left : 0) + element.offsetLeft,
      top: (parentRect ? parentRect.top : 0) + element.offsetTop,
      width: element.offsetWidth,
      height: element.offsetHeight
    }
    layout.right = layout.left + layout.width
    const record = {
      id: job.id,
      found: true,
      matches: matches.length,
      selectorUsed,
      rect: {
        left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom,
        width: rect.width, height: rect.height
      },
      layout,
      style: {
        fontSize: style.fontSize,
        fontFamily: style.fontFamily,
        fontWeight: style.fontWeight,
        color: style.color,
        backgroundColor: style.backgroundColor,
        display: style.display,
        visibility: style.visibility,
        opacity: style.opacity,
        transitionDuration: style.transitionDuration
      },
      text: (element.innerText || element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120)
    }
    if (element.tagName === 'IMG') {
      record.image = {
        currentSrc: element.currentSrc || element.src || '',
        naturalWidth: element.naturalWidth,
        naturalHeight: element.naturalHeight,
        renderedWidth: layout.width,
        renderedHeight: layout.height,
        complete: element.complete
      }
    }
    out.push(record)
  }
  return out
}

async function bytesOfSrc(currentSrc) {
  if (!currentSrc) return null
  if (currentSrc.startsWith('data:')) {
    const comma = currentSrc.indexOf(',')
    if (comma === -1) return null
    const meta = currentSrc.slice(0, comma)
    const payload = currentSrc.slice(comma + 1)
    if (/;base64/i.test(meta)) return Buffer.from(payload, 'base64')
    return Buffer.from(decodeURIComponent(payload), 'utf8')
  }
  if (currentSrc.startsWith('file://')) {
    return fs.readFileSync(fileURLToPath(currentSrc))
  }
  if (/^https?:/.test(currentSrc)) {
    const response = await fetch(currentSrc)
    return Buffer.from(await response.arrayBuffer())
  }
  return null
}

function cropPng(source, rect) {
  const x = Math.max(0, Math.min(source.width - rect.width, rect.x))
  const y = Math.max(0, Math.min(source.height - rect.height, rect.y))
  const out = new PNG({ width: rect.width, height: rect.height })
  PNG.bitblt(source, out, x, y, rect.width, rect.height, 0, 0)
  return out
}

function meanAbsDiff(a, b) {
  const width = Math.min(a.width, b.width)
  const height = Math.min(a.height, b.height)
  let total = 0
  let count = 0
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const i = (y * a.width + x) * 4
      const j = (y * b.width + x) * 4
      total += Math.abs(a.data[i] - b.data[j])
      total += Math.abs(a.data[i + 1] - b.data[j + 1])
      total += Math.abs(a.data[i + 2] - b.data[j + 2])
      count += 3
    }
  }
  return count ? round(total / count, 3) : null
}

function cropRectFor(box) {
  const left = Number.isFinite(box.left) ? box.left : 0
  const top = Number.isFinite(box.top) ? box.top : 0
  const width = Number.isFinite(box.width) ? box.width : CROP
  const height = Number.isFinite(box.height) ? box.height : CROP
  const centreX = left + width / 2
  const centreY = top + height / 2
  const x = Math.max(0, Math.min(VIEWPORT.width - CROP, Math.round(centreX - CROP / 2)))
  const y = Math.max(0, Math.min(VIEWPORT.height - CROP, Math.round(centreY - CROP / 2)))
  return { x, y, width: CROP, height: CROP }
}

function alignBox(box) {
  const out = {}
  for (const key of ['left', 'top', 'right', 'width', 'height']) {
    const entry = box ? box[key] : undefined
    if (entry && typeof entry === 'object' && 'value' in entry) {
      if (entry.value !== null) out[key] = entry.value
    } else if (typeof entry === 'number') {
      out[key] = entry
    }
  }
  return out
}

// ── main ────────────────────────────────────────────────────────────────────────────────────
const flat = flatten(spec.tree).map(({ node, depth }) => ({ node, depth }))
const typeRoles = new Map(((JSON.parse(fs.readFileSync(path.join(ROOT, 'visual/spec/type-map.json'), 'utf8')).roles) || []).map((row) => [row.role, row]))

const jobs = []
for (const { node } of flat) {
  const selector = node.live_selector || node.reference_selector || null
  if (!selector) continue
  const fallback = node.live_selector && node.reference_selector ? node.reference_selector : null
  jobs.push({ id: node.id, selector, fallback, index: node.index || 0 })
}

let browser
let mode
let plate
let measured
let viewportNote

if (HTML) {
  mode = 'html'
  const htmlPath = path.resolve(HTML)
  if (!fs.existsSync(htmlPath)) {
    console.error(`no html at ${htmlPath}`)
    process.exit(2)
  }
  browser = await launchBrowser()
  const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 1 })
  const page = await context.newPage()
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'load' })
  await page.evaluate(() => document.fonts.ready).catch(() => {})
  await sleep(250)
  const got = await page.evaluate(() => ({ width: window.innerWidth, height: window.innerHeight }))
  if (got.width !== VIEWPORT.width || got.height !== VIEWPORT.height) {
    console.error(`refused: the render is ${got.width}x${got.height}, the spec requires ${VIEWPORT.width}x${VIEWPORT.height}`)
    await browser.close().catch(() => {})
    process.exit(3)
  }
  viewportNote = `${got.width}x${got.height}`
  measured = await page.evaluate(MEASURE, jobs)
  plate = PNG.sync.read(await page.screenshot({ clip: { x: 0, y: 0, ...VIEWPORT } }))
  await browser.close()
} else {
  mode = 'port'
  browser = await chromium.connectOverCDP(`http://127.0.0.1:${PORT}`)
  let page = null
  let frame = null
  for (const context of browser.contexts()) {
    for (const candidate of context.pages()) {
      for (const candidateFrame of candidate.frames()) {
        const hasRoot = await candidateFrame
          .evaluate((selector) => Boolean(document.querySelector(selector)), spec.tree.live_selector || '[data-cb-route]')
          .catch(() => false)
        if (hasRoot) { page = candidate; frame = candidateFrame; break }
      }
      if (page) break
    }
    if (page) break
  }
  if (!page) {
    console.error('refused: no page showing the route root; open the screen first')
    await browser.close().catch(() => {})
    process.exit(3)
  }
  // Read-only: no reload, no setViewportSize, no bringToFront, no focus.
  const got = await page.evaluate(() => ({ width: window.innerWidth, height: window.innerHeight }))
  if (got.width !== VIEWPORT.width || got.height !== VIEWPORT.height) {
    console.error(`refused: the live window is ${got.width}x${got.height}; resizing it is forbidden. ` +
      `Set the window to ${VIEWPORT.width}x${VIEWPORT.height} and re-run.`)
    await browser.close().catch(() => {})
    process.exit(3)
  }
  viewportNote = `${got.width}x${got.height} (attached, unmodified)`
  measured = await frame.evaluate(MEASURE, jobs)
  const rootBox = await frame.evaluate((selector) => {
    const element = document.querySelector(selector)
    if (!element) return null
    const rect = element.getBoundingClientRect()
    return { x: rect.left, y: rect.top, width: rect.width, height: rect.height }
  }, spec.tree.live_selector || '[data-cb-route]')
  const clip = rootBox
    ? { x: Math.max(0, rootBox.x), y: Math.max(0, rootBox.y), width: VIEWPORT.width, height: VIEWPORT.height }
    : { x: 0, y: 0, ...VIEWPORT }
  plate = PNG.sync.read(await page.screenshot({ clip }))
  await browser.close()
}

// ── reference plate ─────────────────────────────────────────────────────────────────────────
const referenceRel = (spec.source && spec.source.reference_image) || null
let reference = null
let referenceNote = null
if (referenceRel) {
  const referencePath = path.join(ROOT, referenceRel)
  if (fs.existsSync(referencePath)) {
    reference = PNG.sync.read(fs.readFileSync(referencePath))
    if (reference.width !== VIEWPORT.width || reference.height !== VIEWPORT.height) {
      referenceNote = `reference is ${reference.width}x${reference.height}, not ${VIEWPORT.width}x${VIEWPORT.height}`
      reference = null
    }
  } else {
    referenceNote = `reference image missing: ${referenceRel}`
  }
} else {
  referenceNote = 'spec names no reference image'
}

// ── diff ────────────────────────────────────────────────────────────────────────────────────
const byId = new Map(measured.map((row) => [row.id, row]))
const nodes = []
const deltas = []

function addDelta(node, field, target, current, unit) {
  const numeric = Number.isFinite(Number(current)) && Number.isFinite(Number(target)) && current !== null && target !== null
  const delta = numeric ? round(Number(current) - Number(target), 2) : null
  deltas.push({
    node: node.id,
    field,
    target,
    current,
    delta,
    abs: numeric ? Math.abs(delta) : null,
    verdict: numeric ? (Math.abs(delta) <= TOLERANCE ? 'within-tolerance' : 'out') : 'differs',
    unit: unit || (numeric ? 'px' : null)
  })
}

for (const { node, depth } of flat) {
  const record = byId.get(node.id) || null
  const entry = { id: node.id, depth, kind: node.kind, type_role: node.type_role || null,
                  selector: node.live_selector || node.reference_selector || null,
                  index: node.index ?? null, status: 'ok', checks: [] }
  if (!node.live_selector && !node.reference_selector) {
    entry.status = 'not-addressable'
    nodes.push(entry)
    continue
  }
  if (!record || !record.found) {
    entry.status = 'absent'
    entry.matches = record ? record.matches : 0
    addDelta(node, 'presence', 'present', 'absent', null)
    nodes.push(entry)
    continue
  }
  entry.rect = record.rect
  entry.selector_used = record.selectorUsed
  entry.style = record.style
  entry.text = record.text
  entry.matches = record.matches

  const targetBox = alignBox(node.box)
  for (const [key, target] of Object.entries(targetBox)) {
    const current = key === 'right' ? VIEWPORT.width - record.layout.right : record.layout[key]
    const pass = Math.abs(current - target) <= TOLERANCE
    entry.checks.push({ field: `box.${key}`, target, current: round(current, 2), pass })
    if (!pass) addDelta(node, `box.${key}`, round(target, 2), round(current, 2), 'px')
  }

  const roleName = node.type_role
  if (roleName && node.painted !== false) {
    const role = typeRoles.get(roleName)
    if (!role) {
      entry.checks.push({ field: 'type_role', target: roleName, current: 'unknown', pass: false })
    } else {
      const size = parseFloat(record.style.fontSize)
      const sizePass = Math.abs(size - role.step_px_at_1344) <= 0.25
      entry.checks.push({ field: 'font-size', target: role.step_px_at_1344, current: round(size, 2), pass: sizePass })
      if (!sizePass) addDelta(node, 'font-size', round(role.step_px_at_1344, 2), round(size, 2), 'px')

      const wantFamily = firstFamily(role.family)
      const gotFamily = firstFamily(record.style.fontFamily)
      const familyPass = wantFamily === gotFamily
      entry.checks.push({ field: 'font-family', target: wantFamily, current: gotFamily, pass: familyPass })
      if (!familyPass) addDelta(node, 'font-family', wantFamily, gotFamily, null)

      const weight = Number(record.style.fontWeight)
      const weightPass = weight === role.weight
      entry.checks.push({ field: 'font-weight', target: role.weight, current: weight, pass: weightPass })
      if (!weightPass) addDelta(node, 'font-weight', role.weight, weight, null)

      const wantedColour = tableOf((spec.palette || {})[node.paint && node.paint.color])
      if (wantedColour) {
        const gotColour = rgbToHex(record.style.color)
        const colourPass = gotColour === wantedColour
        entry.checks.push({ field: 'color', target: wantedColour, current: gotColour, pass: colourPass })
        if (!colourPass) addDelta(node, 'color', wantedColour, gotColour, null)
      }
    }
  }

  if (node.kind === 'image' && record.image) {
    const image = { ...record.image }
    const expectedPath = node.asset ? path.join(ROOT, node.asset) : null
    if (expectedPath && fs.existsSync(expectedPath)) {
      image.assetPath = node.asset
      image.assetSha256 = sha256(fs.readFileSync(expectedPath))
      image.assetNatural = node.natural || null
    }
    const bytes = await bytesOfSrc(image.currentSrc).catch(() => null)
    image.currentSrcSha256 = bytes ? sha256(bytes) : null
    image.currentSrcBytes = bytes ? bytes.length : null
    const min = node.natural_min || {}
    for (const axis of ['Width', 'Height']) {
      const want = min[axis.toLowerCase()]
      if (!want) continue
      const got = axis === 'Width' ? image.naturalWidth : image.naturalHeight
      const pass = got >= want
      entry.checks.push({ field: `image.natural${axis}`, target: want, current: got, pass })
      if (!pass) addDelta(node, `image.natural${axis}`, want, got, 'px')
    }
    const rendered = node.rendered || {}
    for (const axis of ['width', 'height']) {
      const want = rendered[axis]
      if (!want) continue
      const got = axis === 'width' ? image.renderedWidth : image.renderedHeight
      const pass = Math.abs(got - want) <= TOLERANCE
      entry.checks.push({ field: `image.rendered.${axis}`, target: want, current: round(got, 2), pass })
      if (!pass) addDelta(node, `image.rendered.${axis}`, want, round(got, 2), 'px')
    }
    const renderedPass = image.renderedWidth > 0 && image.renderedHeight > 0
    if (!renderedPass) addDelta(node, 'image.rendered.present', 1, 0, 'px')
    entry.image = image
  } else if (node.kind === 'image') {
    entry.checks.push({ field: 'image.present', target: '<img>', current: 'absent', pass: false })
    addDelta(node, 'image.present', '<img>', 'absent', null)
  }
  entry.pass = entry.checks.every((check) => check.pass) && entry.status === 'ok'
  if (!entry.pass) entry.status = entry.status === 'ok' ? 'mismatch' : entry.status
  nodes.push(entry)
}

// ── signature crops ─────────────────────────────────────────────────────────────────────────
fs.mkdirSync(CROP_DIR, { recursive: true })
const signatures = []
const platePath = path.join(CROP_DIR, `${SCREEN}-current-plate.png`)
fs.writeFileSync(platePath, PNG.sync.write(plate))
for (const element of spec.signature_elements || []) {
  const box = element.box || {}
  const rect = cropRectFor(box)
  const record = { id: element.id, nodes: element.nodes || [], targetBox: box, crop: rect, files: {} }
  const currentCrop = cropPng(plate, { x: rect.x, y: rect.y, width: rect.width, height: rect.height })
  const currentFile = path.join(CROP_DIR, `${element.id}-current.png`)
  fs.writeFileSync(currentFile, PNG.sync.write(currentCrop))
  record.files.current = path.relative(ROOT, currentFile)
  record.currentSha256 = sha256(fs.readFileSync(currentFile))
  if (reference) {
    const refCrop = cropPng(reference, { x: rect.x, y: rect.y, width: rect.width, height: rect.height })
    const refFile = path.join(CROP_DIR, `${element.id}-reference.png`)
    fs.writeFileSync(refFile, PNG.sync.write(refCrop))
    record.files.reference = path.relative(ROOT, refFile)
    record.referenceSha256 = sha256(fs.readFileSync(refFile))
    record.meanAbsDiff = meanAbsDiff(refCrop, currentCrop)
  } else {
    record.referenceNote = referenceNote
  }
  signatures.push(record)
}

// ── report ──────────────────────────────────────────────────────────────────────────────────
const numeric = deltas.filter((delta) => delta.abs !== null)
const largest = [...numeric].sort((a, b) => b.abs - a.abs).slice(0, 5)
const outOfTolerance = deltas.filter((delta) => delta.verdict === 'out' || delta.verdict === 'differs')
const report = {
  schema: 'cb.ui.audit.v1',
  screen: SCREEN,
  spec: path.relative(ROOT, SPEC_PATH),
  generated_by: 'scripts/audit-screen.mjs',
  mode,
  source: HTML ? path.relative(ROOT, path.resolve(HTML)) : `cdp:${PORT}`,
  viewport: { ...VIEWPORT, observed: viewportNote },
  safety: mode === 'port'
    ? 'attached read-only: no reload, no resize, no focus, no navigation'
    : 'offscreen Chromium; the owner window was not touched',
  reference: referenceRel ? { path: referenceRel, available: Boolean(reference), note: referenceNote } : null,
  plate: { path: path.relative(ROOT, platePath), sha256: sha256(fs.readFileSync(platePath)) },
  summary: {
    nodes: nodes.length,
    absent: nodes.filter((node) => node.status === 'absent').length,
    mismatched: nodes.filter((node) => node.status === 'mismatch').length,
    checks: nodes.reduce((total, node) => total + node.checks.length, 0),
    deltas: deltas.length,
    out_of_tolerance: outOfTolerance.length,
    largest
  },
  signatures,
  nodes,
  deltas
}
fs.mkdirSync(OUT_DIR, { recursive: true })
fs.writeFileSync(AUDIT_JSON, `${JSON.stringify(report, null, 2)}\n`)

console.log(`mode: ${mode}  viewport: ${viewportNote}  (${report.safety})`)
console.log(`wrote ${path.relative(process.cwd(), AUDIT_JSON) || AUDIT_JSON}`)
console.log(`crops ${path.relative(process.cwd(), CROP_DIR) || CROP_DIR} (${signatures.length} signature elements, 600x600)`)
console.log(`nodes ${report.summary.nodes}  absent ${report.summary.absent}  mismatched ${report.summary.mismatched}  out-of-tolerance ${report.summary.out_of_tolerance}`)
console.log('five largest deltas:')
if (!largest.length) {
  console.log('  none: every measured field is within tolerance')
}
largest.forEach((delta, index) => {
  const sign = delta.delta > 0 ? '+' : ''
  console.log(`  ${index + 1}. ${delta.node} ${delta.field}: target ${delta.target} current ${delta.current} (${sign}${delta.delta} ${delta.unit || ''})`.trimEnd())
})
if (outOfTolerance.some((delta) => delta.verdict === 'differs' && delta.abs === null)) {
  const names = outOfTolerance.filter((delta) => delta.abs === null).map((delta) => `${delta.node}.${delta.field}`)
  console.log(`non-numeric differences: ${names.join(', ')}`)
}
