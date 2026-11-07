// Notebook (25-34s) and quiz/check (34-40s) capture on 5b0f124, route-only surfaces.
import { connectWithConsole, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()

async function clickVisible(label) {
  const box = await cdp.json(`(() => {
    const hits = [...document.querySelectorAll('button, a, [role=tab]')].filter(e => ((e.innerText || '').trim() === ${JSON.stringify(label)}))
    const vis = hits.map(e => ({ e, r: e.getBoundingClientRect() })).filter(x => x.r.width > 0 && x.r.height > 0)
    if (!vis.length) return { error: 'no visible control', count: hits.length }
    const { r } = vis[0]
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
  })()`)
  if (box.error) throw new Error(JSON.stringify(box))
  await cdp.click(box.x, box.y)
  return box
}

const steps = []
const snap = (tag) => cdp.json(`(() => { const r = document.querySelector('[data-cb-route]'); const t = r ? r.innerText : ''; return {
  tag: ${JSON.stringify(tag)}, hash: location.hash,
  route: !!r,
  text: t.replace(/\\n{2,}/g,'\\n').slice(0, 1400),
  textareas: r ? [...r.querySelectorAll('textarea, input')].map(i => ({ tag: i.tagName, type: i.type||null, ph: i.placeholder||null, aria: i.getAttribute('aria-label') })).slice(0,10) : [],
  dialogs: [...document.querySelectorAll('[role=dialog]')].map(d => (d.innerText||'').slice(0,500)).slice(0,2),
  submit: (() => { const b = [...document.querySelectorAll('button')].find(x => /^Submit/.test((x.innerText||'').trim())); return b ? { label: (b.innerText||'').trim(), disabled: b.disabled } : null })(),
  pane: (() => { try { return window.__HERMES_PLUGIN_SDK__.host.paneVisibility('coursebook:pane').get() } catch(e) { return 'ERR' } })()
} })()`)

await cdp.eval(`(location.hash = '#/coursebook', true)`)
await cdp.wait(1500)
try { await clickVisible('Open'); await cdp.wait(1800) } catch (e) { steps.push({ open: e.message }) }
try { await clickVisible('Open this section'); await cdp.wait(2200) } catch (e) { steps.push({ section: e.message }) }
const section = await snap('section')
let notebook = null
try {
  await clickVisible('Save to notebook'); await cdp.wait(1500)
  const dialog = await snap('notebook-dialog')
  // type a note into the visible textarea inside the dialog
  const typed = await cdp.eval(`(() => {
    const d = document.querySelector('[role=dialog]'); if (!d) return 'no-dialog'
    const ta = d.querySelector('textarea, input[type=text]'); if (!ta) return 'no-field'
    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set || Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set
    setter.call(ta, 'Sentinel rig note 5b0f124: register carries the relationship.')
    ta.dispatchEvent(new Event('input', { bubbles: true }))
    return 'typed'
  })()`)
  await cdp.wait(600)
  let saved = false
  try { await clickVisible('Save'); saved = true } catch (e) { steps.push({ save: e.message }) }
  await cdp.wait(2200)
  const after = await snap('notebook-after-save')
  const shot = await cdp.shot('audit/demo-gate-5b0f124/shots/u09-notebook.png')
  notebook = { typed, saved, dialog, after, shot }
} catch (e) { notebook = { error: e.message } }

let quiz = null
try {
  await clickVisible('Quizzes'); await cdp.wait(2200)
  const quizzes = await snap('quizzes')
  let opened = false
  try { await clickVisible('Open check'); opened = true; await cdp.wait(2500) } catch (e) { steps.push({ opencheck: e.message }) }
  const check = await snap('check')
  const shot = await cdp.shot('audit/demo-gate-5b0f124/shots/u10-quiz.png')
  quiz = { opened, quizzes, check, shot }
} catch (e) { quiz = { error: e.message } }

save('u09-u10-notebook-quiz.json', { steps, section, notebook, quiz, consoleErrors: console_ })
console.log(JSON.stringify({ steps, section, notebook, quiz, consoleErrors: console_ }, null, 2).slice(0, 7000))
cdp.close()
