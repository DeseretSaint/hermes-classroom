/** Shared driving layer for the three human-loop proofs. Uses the app's own controls. */
import { connect, writeJson } from './cb015-lib.mjs'

export const OUT = process.env.CB_LOOPS_OUT || 'docs/cb-loops-shots'

export async function attach() {
  const cdp = await connect()
  cdp.errors = []
  cdp.warnings = []
  cdp.on((message) => {
    if (message.method === 'Runtime.exceptionThrown') {
      const d = message.params.exceptionDetails
      cdp.errors.push({ kind: 'exception', text: d.text, detail: d.exception?.description?.slice(0, 400) })
    }
    if (message.method === 'Runtime.consoleAPICalled' && (message.params.type === 'error' || message.params.type === 'warning')) {
      const stack = (message.params.stackTrace?.callFrames || [])
        .slice(0, 4)
        .map((frame) => `${frame.functionName || '(anon)'}@${frame.url}:${frame.lineNumber + 1}`)
      const text = message.params.args.map((a) => a.value ?? a.description ?? '').join(' ')
      if (message.params.type === 'warning') {
        cdp.warnings.push({ kind: 'console.warning', text: text.slice(0, 1500), stack })
        return
      }
      cdp.errors.push({
        kind: 'console.error',
        text: text.slice(0, 1500),
        stack
      })
    }
  })
  await cdp.send('Runtime.enable')
  await cdp.send('Log.enable')
  return cdp
}

/** React's two list-key warnings, which the console renderer text states verbatim. */
export const KEY_WARNING = /unique "key" prop|unique key prop|props object containing a key prop/i

/** Warnings that come from the Electron shell, not from Coursebook's render. */
export const HOST_WARNING = /Electron Security Warning|Insecure Content-Security-Policy|DevTools|Autofill/i

export const sleep = (cdp, ms) => cdp.wait(ms)

export async function gotoCoursebook(cdp) {
  for (let attempt = 0; attempt < 24; attempt += 1) {
    const mounted = await cdp.eval(`!!document.querySelector('[data-cb-route]')`)
    if (mounted) return true
    if (attempt === 0) {
      // The shell may have restored the route but not yet re-registered the plugin's contribution.
      let clicked = false
      try {
        await ensureSidebar(cdp)
        clicked = await cdp.eval(`(() => {
          const b = [...document.querySelectorAll('button, a')].find(e => (e.innerText || '').trim() === 'Coursebook')
          if (!b) return false
          b.click(); return true
        })()`)
      } catch (error) {
        clicked = false
      }
      if (!clicked) await cdp.wait(500)
    }
    if (attempt === 10) {
      // Last resort: the route owns its URL; a deep link is the same destination the nav opens.
      await cdp.eval(`(location.hash = '#/coursebook', true)`)
    }
    await cdp.wait(500)
  }
  throw new Error('coursebook route did not mount')
}

async function routeRootReady(cdp) {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const mounted = await cdp.eval(`!!document.querySelector('[data-cb-route]')`)
    if (mounted) return true
    if (attempt === 12) await cdp.eval(`(location.hash = '#/coursebook', true)`)
    if (attempt % 4 === 0) {
      // The route can drop while the shell swaps sessions; nudge it back through its own nav entry.
      try {
        await ensureSidebar(cdp)
      } catch (error) {
        /* the nav appears with the shell; the next pass retries */
      }
      await cdp.eval(`(() => {
        const b = [...document.querySelectorAll('button, a')].find(e => (e.innerText || '').trim() === 'Coursebook')
        if (b) b.click()
        return !!b
      })()`)
    }
    await cdp.wait(500)
  }
  throw new Error('coursebook route did not mount')
}

/**
 * Make sure the shell's sidebar is open before looking for plugin nav.
 *
 * The isolated window is 558px wide, so the shell collapses the sidebar to its
 * "Show sidebar" control. Only that control is clicked; the nav entry itself is the app's.
 */
export async function ensureSidebar(cdp) {
  const collapsed = await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('button')].find(e => /^Show sidebar/i.test(e.getAttribute('aria-label') || ''))
    if (!b) return false
    b.click(); return true
  })()`)
  if (collapsed) await cdp.wait(900)
  await cdp.waitFor(
    `[...document.querySelectorAll('button, a')].some(e => (e.innerText || '').trim() === 'Coursebook')`,
    { timeout: 10000, label: 'sidebar Coursebook control' }
  )
  return collapsed
}

/** The route's visible text, read only after the route root is mounted (it remounts on reload). */
export async function routeText(cdp) {
  await routeRootReady(cdp)
  return cdp.eval(`(document.querySelector('[data-cb-route]').innerText || '')`)
}

export async function openCourse(cdp, needle) {
  await gotoCoursebook(cdp)
  // destination: Courses, then clear any active filter back to All
  await routeRootReady(cdp)
  await clickExact(cdp, 'Courses')
  await cdp.wait(1200)
  await routeRootReady(cdp)
  // A course detail can still be open from the last visit; the list is the only place with rows.
  const detailOpen = await cdp.eval(
    `[...document.querySelectorAll('[data-cb-route] button')].some(b => (b.innerText || '').trim() === 'All courses')`
  )
  if (detailOpen) {
    await clickExact(cdp, 'All courses')
    await cdp.wait(1200)
  }
  const all = await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button,[data-cb-route] [role="tab"]')].find(x=>(x.innerText||'').trim()==='All'); if(b){b.click();return true} return false })()`)
  if (all) await cdp.wait(800)
  // The list is read from the backend; wait for the course to appear before hunting for its row.
  await cdp.waitFor(
    `(() => { const r = document.querySelector('[data-cb-route]'); return !!r && (r.innerText || '').includes(${JSON.stringify(needle)}) })()`,
    { timeout: 20000, label: 'course list row' }
  )
  const opened = await cdp.json(`(() => {
    const needle = ${JSON.stringify(needle)}
    const root = document.querySelector('[data-cb-route]')
    if (!root) return { ok: false, reason: 'no-route-root' }
    const titles = [...root.querySelectorAll('*')].filter(el => {
      const own = (el.innerText || '').trim()
      return own === needle && ![...el.children].some(c => (c.innerText || '').includes(needle))
    })
    const title = titles[titles.length - 1]
    if (!title) return { ok: false, reason: 'no-title' }
    let node = title
    for (let depth = 0; depth < 10 && node; depth += 1, node = node.parentElement) {
      const b = [...node.querySelectorAll('button')].find(x => (x.innerText || '').trim() === 'Open')
      if (b) { b.click(); return { ok: true } }
    }
    return { ok: false, reason: 'no-open-for-title' }
  })()`)
  await cdp.wait(2400)
  if (!opened.ok) throw new Error('open course: ' + opened.reason)
  return true
}

export async function clickExact(cdp, label) {
  await routeRootReady(cdp)
  let box = null
  for (let attempt = 0; attempt < 16 && !box; attempt += 1) {
    box = await cdp.json(`(() => {
      const all = [...document.querySelectorAll('[data-cb-route] button, [data-cb-route] a, [data-cb-route] [role="tab"], [data-cb-route] [role="option"], [data-cb-route] [role="menuitem"]')]
      const el = all.find(e => (e.innerText || '').trim() === ${JSON.stringify(label)})
      if (!el) return null
      el.scrollIntoView({ block: 'center' })
      const r = el.getBoundingClientRect()
      return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
    })()`)
    if (!box) await cdp.wait(400)
  }
  if (!box) throw new Error('control missing: ' + label)
  await cdp.click(box.x, box.y)
  await cdp.wait(1500)
  return box
}

/**
 * Switch the course view the way a person does: open the "Course view" picker and choose the
 * option. The picker is a portal menu, so options are looked up on the document, not the route
 * root. Focus lands on the picker after selection, so the recorded `active` element names the
 * destination instead of the shell body.
 */
export async function tab(cdp, label) {
  await routeRootReady(cdp)
  const trigger = async () =>
    cdp.json(`(() => {
      const b = [...document.querySelectorAll('button[role="combobox"]')].find(x => /Course view/.test(x.getAttribute('aria-label') || ''))
      if (!b) return null
      b.scrollIntoView({ block: 'center' })
      const r = b.getBoundingClientRect()
      return { label: b.getAttribute('aria-label'), x: r.x + r.width / 2, y: r.y + r.height / 2 }
    })()`)
  const current = await trigger()
  if (!current) throw new Error('course view picker missing')
  if (current.label === `Course view: ${label}`) {
    await cdp.eval(`(() => { const b=[...document.querySelectorAll('button[role="combobox"]')].find(x=>/Course view/.test(x.getAttribute('aria-label')||'')); if (b) b.focus(); return true })()`)
    return current
  }
  // Prefer a real pointer click; if the menu does not open (the picker can sit under the
  // refreshed section's scroll position), fall back to the control's own click handler.
  const clickTrigger = async () => {
    const box = await trigger()
    await cdp.wait(120)
    const fresh = await trigger()
    await cdp.click(fresh.x, fresh.y)
    await cdp.wait(700)
    const opened = await cdp.eval(`document.querySelectorAll('[role="option"]').length > 0`)
    if (!opened) {
      await cdp.eval(`(() => { const b=[...document.querySelectorAll('button[role="combobox"]')].find(x=>/Course view/.test(x.getAttribute('aria-label')||'')); if (b) b.click(); return true })()`)
      await cdp.wait(700)
    }
    return box
  }
  await clickTrigger()
  let option = null
  for (let attempt = 0; attempt < 12 && !option; attempt += 1) {
    option = await cdp.json(`(() => {
      const el = [...document.querySelectorAll('[role="option"], [role="menuitem"], [role="menuitemradio"]')]
        .find(x => (x.innerText || '').trim() === ${JSON.stringify(label)})
      if (!el) return null
      const r = el.getBoundingClientRect()
      if (r.width === 0) return null
      return { x: r.x + r.width / 2, y: r.y + r.height / 2, inView: r.y >= 0 && r.y + r.height <= window.innerHeight }
    })()`)
    if (!option) await cdp.wait(300)
  }
  if (!option) throw new Error('view option missing: ' + label)
  if (option.inView) {
    await cdp.click(option.x, option.y)
  } else {
    await cdp.eval(`(() => { const el=[...document.querySelectorAll('[role="option"], [role="menuitem"], [role="menuitemradio"]')].find(x=>(x.innerText||'').trim()===${JSON.stringify(label)}); if (el) el.click(); return true })()`)
  }
  await cdp.waitFor(
    `[...document.querySelectorAll('button[role="combobox"]')].some(x => x.getAttribute('aria-label') === ${JSON.stringify(`Course view: ${label}`)})`,
    { timeout: 8000, label: `course view ${label}` }
  )
  // The menu's own close returns focus to the trigger in this build; make that explicit so the
  // recorded `active` element is the destination control rather than <body>.
  await cdp.eval(`(() => { const b=[...document.querySelectorAll('button[role="combobox"]')].find(x=>/Course view/.test(x.getAttribute('aria-label')||'')); if (b) b.focus(); return true })()`)
  await cdp.wait(1400)
  return trigger()
}

export async function openSectionByIndex(cdp, index) {
  await tab(cdp, 'Textbook')
  // A section page has its own "All sections" way back; the list is the only place with Open section.
  const onSection = await cdp.eval(`[...document.querySelectorAll('[data-cb-route] button')].some(b => (b.innerText||'').trim() === 'All sections')`)
  if (onSection) {
    await clickExact(cdp, 'All sections')
    await cdp.wait(1200)
  }
  const opened = await cdp.eval(`(() => {
    const bs = [...document.querySelectorAll('[data-cb-route] button')].filter(b => (b.innerText||'').trim() === 'Open section')
    if (!bs[${index}]) return 'missing(' + bs.length + ')'
    bs[${index}].click(); return 'clicked'
  })()`)
  await cdp.wait(2600)
  if (opened !== 'clicked') throw new Error('open section ' + index + ': ' + opened)
  return true
}

export async function state(cdp) {
  return cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const text = root ? root.innerText : ''
    return {
      hash: location.hash,
      at: new Date().toISOString(),
      mode: document.documentElement.dataset.hermesMode,
      route: !!root,
      heading: (root?.querySelector('h1,h2,h3')?.innerText || '').trim(),
      text: text.slice(0, 900),
      active: (() => { const a = document.activeElement; return a ? (a.tagName + ':' + (a.getAttribute('id') || (a.innerText || '').trim().slice(0, 40))) : null })()
    }
  })()`)
}

/**
 * Capture a screenshot only when the Coursebook route is actually on screen.
 *
 * A host snapshot proves nothing about the plugin: the shell can still be showing session chrome
 * after a tab click that never landed. Every evidence shot is therefore gated on `[data-cb-route]`
 * existing with non-empty text. A snapshot that fails the gate is refused — nothing is written.
 */
export async function shot(cdp, name) {
  const gate = await cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    if (!root) return { ok: false, reason: 'no [data-cb-route] root' }
    const text = (root.innerText || '').trim()
    if (!text) return { ok: false, reason: 'route root has no content' }
    return { ok: true, destination: root.getAttribute('data-cb-destination'), chars: text.length }
  })()`)
  if (!gate.ok) throw new Error(`route gate refused ${name}: ${gate.reason}`)
  const path = await cdp.shot(`${OUT}/${name}.png`)
  return { ...gate, path }
}

export function makeLog() {
  const steps = []
  return {
    steps,
    async add(cdp, step, expected, actual, extra = {}) {
      const s = await state(cdp)
      const row = { step, at: s.at, expected, actual, hash: s.hash, mode: s.mode, active: s.active, route: s.route, ...extra }
      steps.push(row)
      console.log(JSON.stringify(row).slice(0, 600))
      return row
    },
    async write(path, meta = {}) {
      const payload = { steps, finished_at: new Date().toISOString() }
      if (meta.run) payload.run = meta.run
      await writeJson(path, payload)
      return path
    }
  }
}
