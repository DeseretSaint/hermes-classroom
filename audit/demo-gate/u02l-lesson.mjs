// Enter the lesson (check surface) from the course overview.
import { connectWithConsole, clickLabel, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
await clickLabel(cdp, 'Resume lesson', { selector: 'button, a' })
await cdp.wait(3000)
const state = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const text = root ? root.innerText : ''
  return {
    hash: location.hash, text: text.replace(/\\n{2,}/g,'\\n').slice(0,2600),
    objective: root ? (root.querySelector('[data-cb-objective]')?.getAttribute('data-cb-objective') || null) : null,
    buttons: root ? [...root.querySelectorAll('button')].map(b=>({label:(b.innerText||'').trim(),disabled:b.disabled})).filter(b=>b.label) : [],
    inputs: root ? [...root.querySelectorAll('input,textarea,select,[contenteditable=true],[role=textbox]')].map(i=>({tag:i.tagName,type:i.type||null,role:i.getAttribute('role'),label:i.getAttribute('aria-label'),ph:i.placeholder})) : [],
    images: root ? [...root.querySelectorAll('img')].map(i=>({alt:i.getAttribute('alt'),src:(i.getAttribute('src')||'').slice(0,60)})) : []
  }
})()`)
save('u02l-lesson.json', { state, consoleErrors: console_ })
console.log(JSON.stringify({ state, consoleErrors: console_ }, null, 2))
cdp.close()
