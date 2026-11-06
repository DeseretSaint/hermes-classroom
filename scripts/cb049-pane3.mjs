/** Close the palette, switch appearance with the shell key (focus off the composer), capture the pane. */
import { connect } from './cb015-lib.mjs'

const cdp = await connect()
await cdp.key('Escape')
await cdp.wait(400)
await cdp.eval(`(() => { const b = document.querySelector('aside button, nav button'); if (b) b.focus(); return document.activeElement && document.activeElement.tagName })()`)
await cdp.wait(200)
await cdp.key('X', { modifiers: 8 })
await cdp.wait(1500)
const mode = await cdp.eval(`document.documentElement.dataset.hermesMode`)
const snippets = await cdp.eval(`(() => {
  const out = []
  for (const el of document.querySelectorAll('*')) {
    if (el.children.length) continue
    const t = (el.innerText || '').trim()
    if (t && /objective|binding|lesson|Coursebook/i.test(t) && t.length < 120) out.push(t)
  }
  return [...new Set(out)].slice(0, 25)
})()`)
console.log('mode', mode)
console.log(JSON.stringify(snippets, null, 2))
console.log(await cdp.shot('docs/cb049-shots/071-chat-pane-dark.png'))
cdp.close()
