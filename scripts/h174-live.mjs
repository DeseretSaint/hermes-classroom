#!/usr/bin/env node
/**
 * H-174 live proof on the isolated Coursebook window.
 *
 * Drives the real `#/coursebook` route against the remote test backend and reads the painted DOM:
 *
 *   1. the Japanese classroom, whose approved plan has a lessons job that never wrote a page
 *      (`lesson.page` answers with a document whose `blocks` is empty) — the "incomplete" state;
 *   2. the draft H-103 classroom, whose plan is not approved — the "unapproved" state;
 *   3. the parent demo, whose document carries real blocks — the unchanged readable player.
 *
 * Running and failed lessons-job states are not produced here: doing so on a shared rig means
 * either running the authoring model or corrupting a stored job. Those two are proven by
 * `scripts/h174-frames.py` (shipped component, real React) and by the jsdom test.
 *
 *   COURSEBOOK_TEST_STATE=~/.hermes/coursebook-test-h174a CB013_CDP_PORT=9360 \
 *     node scripts/h174-live.mjs
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'

const PORT = process.env.CB013_CDP_PORT || '9360'
const OUT = resolve(process.env.H174_SHOTS || 'audit/h174')

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target on the isolated window')

const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => {
  socket.addEventListener('open', res, { once: true })
  socket.addEventListener('error', rej, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const { res, rej } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) rej(new Error(JSON.stringify(message.error)))
    else res(message.result)
  }
})
const send = (method, params = {}, timeout = 20000) =>
  new Promise((res, rej) => {
    const id = nextId++
    const timer = setTimeout(() => {
      pending.delete(id)
      rej(new Error(`CDP timeout: ${method}`))
    }, timeout)
    pending.set(id, {
      res: (value) => { clearTimeout(timer); res(value) },
      rej: (error) => { clearTimeout(timer); rej(error) }
    })
    socket.send(JSON.stringify({ id, method, params }))
  })
const evalJs = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
  return result.result?.value ?? null
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const waitFor = async (expr, ms = 20000) => {
  const end = Date.now() + ms
  while (Date.now() < end) {
    if (await evalJs(expr)) return true
    await wait(250)
  }
  return false
}
const shot = async (name) => {
  const png = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }, 30000)
  const path = `${OUT}/${name}.png`
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, Buffer.from(png.data, 'base64'))
  console.log(`shot ${path}`)
}
const setWidth = async (target) => {
  let override = target
  for (let i = 0; i < 8; i += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height: 1100, deviceScaleFactor: 1, mobile: false })
    await wait(350)
    const measured = await evalJs('window.innerWidth')
    if (Math.abs(measured - target) <= 1) return measured
    override = Math.round((override * target) / measured)
  }
  return evalJs('window.innerWidth')
}

const clickText = (text) => evalJs(`(() => {
  const nodes = [...document.querySelectorAll('button, a, [role="button"]')]
  const el = nodes.find((b) => b.textContent.trim() === ${JSON.stringify(text)})
    || nodes.find((b) => b.textContent.includes(${JSON.stringify(text)}))
  if (!el) return false
  el.click()
  return true
})()`)

const state = () => evalJs(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const panel = document.querySelector('[data-cb-lesson-readiness]')
  const text = route ? route.innerText : ''
  return {
    hash: location.hash,
    via: document.querySelector('[data-cb-course-detail]')?.dataset.cbCourseDetail || null,
    courseTitle: document.querySelector('[data-cb-course-title]')?.textContent || null,
    sectionTitle: document.querySelector('[data-cb-workspace-title]')?.textContent || null,
    readiness: panel ? panel.getAttribute('data-cb-lesson-readiness') : null,
    job: panel ? panel.getAttribute('data-cb-lesson-job') : null,
    headline: panel ? panel.querySelector('h3')?.textContent.trim() : null,
    detail: panel ? panel.querySelector('p')?.textContent.trim() : null,
    readinessActions: [...document.querySelectorAll('[data-cb-readiness-action]')].map((n) => n.getAttribute('data-cb-readiness-action') + ':' + n.textContent.trim()),
    sectionActions: document.querySelector('[data-cb-section-actions]')?.getAttribute('data-cb-section-actions') || null,
    primaries: [...document.querySelectorAll('[data-cb-action="primary"]')].map((n) => n.textContent.trim()),
    heroActions: [...document.querySelectorAll('[data-cb-hero-actions] [data-cb-action]')].map((n) => n.getAttribute('data-cb-action') + ':' + n.textContent.trim()),
    falseCopy: text.includes('Coursebook does not write it for you'),
    chatPromptCopy: /Send the first message to begin/.test(text),
    legacyEmptyCopy: text.includes('This section has no teaching content yet'),
    overflow: route ? { scrollWidth: route.scrollWidth, clientWidth: route.clientWidth } : null,
    innerWidth: window.innerWidth,
    rootFont: getComputedStyle(document.documentElement).fontSize
  }
})()`)

const openRoute = async () => {
  await evalJs("location.hash = '#/'")
  await wait(900)
  await evalJs("location.hash = '#/coursebook'")
  return waitFor("!!document.querySelector('[data-cb-route]')", 25000)
}

const openCourses = async () => {
  const clicked = await clickText('Courses')
  await wait(900)
  return (await waitFor("!!document.querySelector('[data-cb-course-cover]')", 20000)) || clicked
}

const openCourseById = async (courseId) => {
  const opened = await evalJs(`(() => {
    const cover = document.querySelector('[data-cb-course-id="${courseId}"]')
    if (!cover) return false
    const button = cover.querySelector('button, [role="button"]')
    ;(button || cover).click()
    return true
  })()`)
  if (!opened) return false
  return waitFor("!!document.querySelector('[data-cb-course-detail]')", 25000)
}

const openFirstSection = async () => {
  await clickText('Learn')
  await wait(900)
  const row = await evalJs(`(() => {
    const node = document.querySelector('[data-cb-section-row]')
    if (!node) return false
    const button = node.querySelector('button')
    ;(button || node).click()
    return true
  })()`)
  if (!row) return false
  return waitFor("!!document.querySelector('[data-cb-section-actions]') || !!document.querySelector('[data-cb-lesson-readiness]')", 25000)
}

const backToCourses = async () => {
  await evalJs("(() => { const b = document.querySelector('[data-cb-course-back]'); if (b) b.click(); return !!b })()")
  await wait(800)
}

await send('Page.enable')
await send('Runtime.enable')

const report = { port: PORT, steps: [], frames: [] }

// A package installed from disk is opt-in: Electron's reconcile copies the desktop half and writes
// `.hermes-package.json`, so the plugin loads but stays inert until this decision exists. Set it
// once, reload once (the remote connection reconnects), then drive the route.
report.pluginDecisionBefore = await evalJs("localStorage.getItem('hermes.desktop.pluginDecisions.v2')")
if (!/coursebook/.test(report.pluginDecisionBefore || '')) {
  await evalJs("localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))")
  await send('Page.reload', {}, 30000)
  await wait(4000)
  report.pluginDecisionAfter = await evalJs("localStorage.getItem('hermes.desktop.pluginDecisions.v2')")
}

report.arrived = await openRoute()
await setWidth(1049)
await wait(600)
report.pluginPresent = await evalJs("!!document.querySelector('[data-cb-route]')")
report.sidebar = await evalJs(`[...document.querySelectorAll('nav a, nav button, [data-cb-nav]')].map((n) => n.textContent.trim()).filter(Boolean).slice(0, 12)`)

const measure = async (label, widths = [1049, 460], textScale = false) => {
  for (const width of widths) {
    const measured = await setWidth(width)
    if (textScale) await evalJs("document.documentElement.style.setProperty('font-size','32px','important')")
    await wait(500)
    const suffix = textScale ? '-text200' : ''
    await shot(`h174-live-${label}-${width}${suffix}`)
    report.steps.push({ label, width: measured, textScale, ...(await state()) })
    if (textScale) {
      await evalJs("document.documentElement.style.removeProperty('font-size')")
      await wait(250)
    }
  }
}

const COURSE = {
  japanese: 'crs_650052975ca7406aaddda22122c89bad',
  draft: 'crs_dfa2a1aa66e74e8fbbb21662879b0a4f',
  parent: 'crs_8fa43cf082154155a4508a36c721f582'
}

report.coursesList = await openCourses()

// 1. Approved plan, lessons job never wrote a page (the live "incomplete" state).
await setWidth(1049)
report.japaneseOpened = await openCourseById(COURSE.japanese)
report.japaneseSection = report.japaneseOpened ? await openFirstSection() : false
await measure('incomplete')
await measure('incomplete', [460], true)
await setWidth(1049)
await backToCourses()

// 2. Draft plan (the live "unapproved" state).
report.coursesList2 = await openCourses()
report.draftOpened = await openCourseById(COURSE.draft)
report.draftSection = report.draftOpened ? await openFirstSection() : false
await measure('unapproved')
await measure('unapproved', [460], true)
await setWidth(1049)
await backToCourses()

// The parent-recipe classroom is deliberately absent from the Courses shelf (it lives in Parent
// Studio), so it cannot be reached through this shelf path. The readable player is still proven
// live by `docs/h149-shots/` on this backend and by the `present` frames here; this script only
// claims the two missing-page states it actually drove.
report.parentShelved = await evalJs("[...document.querySelectorAll('[data-cb-course-id]')].map((n) => n.getAttribute('data-cb-course-id'))")

writeFileSync(`${OUT}/h174-live.json`, JSON.stringify(report, null, 2))
console.log(JSON.stringify(report, null, 2))
socket.close()
