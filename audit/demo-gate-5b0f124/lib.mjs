// Shared helpers for the DEMO gate (U01-U04) on the 5b0f124 isolated rig.
// Read-only against the renderer; every value is read live, none is fixture data.
import { connect as baseConnect, writeJson, rel } from '../../scripts/cb015-lib.mjs'

export async function connectWithConsole() {
  const cdp = await baseConnect()
  const console_ = []
  cdp.on((message) => {
    if (message.method === 'Runtime.consoleAPICalled') {
      const args = (message.params.args || []).map((a) => a.value ?? a.description ?? a.type).join(' ')
      if (message.params.type === 'error' || message.params.type === 'assert') {
        console_.push({ kind: 'console', level: message.params.type, text: args.slice(0, 500) })
      }
    }
    if (message.method === 'Runtime.exceptionThrown') {
      const d = message.params.exceptionDetails
      console_.push({ kind: 'exception', level: 'error', text: (d.exception?.description || d.text || '').slice(0, 500) })
    }
    if (message.method === 'Log.entryAdded') {
      const e = message.params.entry
      if (e.level === 'error') console_.push({ kind: 'log', level: 'error', text: `${e.source}: ${e.text}`.slice(0, 500) })
    }
  })
  await cdp.send('Runtime.enable')
  await cdp.send('Log.enable').catch(() => {})
  return { cdp, console_ }
}

export async function clickLabel(cdp, text, { exact = true, selector } = {}) {
  const SEL = selector || 'button, a, [role=tab], [role=option], [role=radio], [role=menuitem], [role=button]'
  const box = await cdp.json(`(() => {
    const all = [...document.querySelectorAll(${JSON.stringify(SEL)})]
    const el = all.find((e) => {
      const label = (e.innerText || e.getAttribute('aria-label') || '').trim()
      return ${exact ? `label === ${JSON.stringify(text)}` : `label.includes(${JSON.stringify(text)})`}
    })
    if (!el) return null
    el.scrollIntoView({ block: 'center' })
    const r = el.getBoundingClientRect()
    return { x: r.x + r.width / 2, y: r.y + r.height / 2, label: (el.innerText || '').trim().slice(0, 90), disabled: el.disabled === true }
  })()`)
  if (!box) throw new Error(`no control labelled ${JSON.stringify(text)}`)
  if (box.disabled) throw new Error(`control labelled ${JSON.stringify(text)} is disabled`)
  await cdp.click(box.x, box.y)
  return box
}

export function save(name, value) {
  return writeJson(rel(`audit/demo-gate-5b0f124/${name}`), value)
}

/** Press a key with the text payload Chromium needs for native activation (Enter = '\r'). */
export async function press(cdp, key) {
  const map = {
    Enter: { code: 'Enter', vk: 13, text: '\r' },
    Space: { code: 'Space', vk: 32, text: ' ' },
    Escape: { code: 'Escape', vk: 27 },
    Tab: { code: 'Tab', vk: 9 }
  }
  const entry = map[key]
  if (key === 'Tab') { await cdp.key('Tab'); await cdp.wait(110); return }
  const base = { key, code: entry.code, windowsVirtualKeyCode: entry.vk, nativeVirtualKeyCode: 0 }
  if (entry.text) base.text = entry.text
  await cdp.send('Input.dispatchKeyEvent', { type: 'keyDown', ...base })
  await cdp.send('Input.dispatchKeyEvent', { type: 'keyUp', ...base })
  await cdp.wait(400)
}

export { rel, writeJson }
