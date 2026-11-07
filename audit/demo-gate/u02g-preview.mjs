// U02 — pick the Japanese pack row, Review (grant+preview), then import and confirm the course.
import { connectWithConsole, save } from './lib.mjs'

const { cdp, console_ } = await connectWithConsole()
const PACK = 'japanese-affection-context-l0.zip'
const steps = []

const clickRowButton = async (fileName, label) => {
  const box = await cdp.json(`(() => {
    const rows = [...document.querySelectorAll('div,li')].filter(e => (e.innerText||'').includes(${JSON.stringify(fileName)}))
    const row = rows[rows.length - 1]
    if (!row) return null
    const btn = [...row.querySelectorAll('button')].find(b => (b.innerText||'').trim() === ${JSON.stringify(label)})
    if (!btn) return null
    btn.scrollIntoView({ block: 'center' })
    const r = btn.getBoundingClientRect()
    return { x: r.x + r.width/2, y: r.y + r.height/2, disabled: btn.disabled }
  })()`)
  if (!box) throw new Error(`no ${label} for ${fileName}`)
  if (box.disabled) throw new Error(`${label} disabled for ${fileName}`)
  await cdp.click(box.x, box.y)
  return box
}

steps.push({ step: 'click-review', ...(await clickRowButton(PACK, 'Review')) })

// Wait for the preview step: the pack manifest should render.
let previewOk = false
try {
  await cdp.waitFor("/Import this pack|Import into this profile|Pack preview|pack_id/i.test(document.querySelector('[data-cb-route]')?.innerText||'')", { timeout: 30000, label: 'preview' })
  previewOk = true
} catch (e) { steps.push({ step: 'preview-wait', error: e.message }) }
await cdp.wait(1000)

const preview = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const text = root ? root.innerText : ''
  return {
    text: text.replace(/\\n{2,}/g,'\\n').slice(0, 3000),
    buttons: root ? [...root.querySelectorAll('button')].map(b => ({ label: (b.innerText||'').trim(), disabled: b.disabled })).filter(b=>b.label) : []
  }
})()`)

save('u02-import-preview.json', { steps, previewOk, preview, consoleErrors: console_ })
console.log(JSON.stringify({ steps, previewOk, preview, consoleErrors: console_ }, null, 2))
cdp.close()
