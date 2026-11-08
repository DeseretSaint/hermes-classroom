const PORT = process.env.CB013_CDP_PORT || '9391'
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((t) => t.type === 'page')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((r) => socket.addEventListener('open', r, { once: true }))
let id = 1
const pending = new Map()
socket.addEventListener('message', (e) => {
  const m = JSON.parse(e.data)
  if (m.id && pending.has(m.id)) {
    const p = pending.get(m.id)
    pending.delete(m.id)
    m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result)
  }
})
const send = (method, params = {}) => new Promise((res, rej) => { const i = id++; pending.set(i, { res, rej }); socket.send(JSON.stringify({ id: i, method, params })) })
const ev = async (expr) => {
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text)
  return r.result?.value ?? null
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const setWidth = async (target, height = 1600) => {
  let override = target
  for (let i = 0; i < 8; i += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height, deviceScaleFactor: 1, mobile: false })
    await wait(320)
    const measured = await ev('window.innerWidth')
    if (Math.abs(measured - target) <= 1) return measured
    override = Math.round((override * target) / measured)
  }
  return ev('window.innerWidth')
}

// Reach the shape step from wherever the window is.
const hasShape = () => ev("!!document.querySelector('[data-cb-scope-option]')")
const hasGoal = () => ev("!!document.querySelector('#cb-goal')")
if (!(await hasGoal()) && !(await hasShape())) {
  await ev("location.hash = '#/'")
  await wait(600)
  await ev("location.hash = '#/coursebook'")
  await wait(1200)
  for (const label of ['Start with a goal', 'Create a course', 'New course']) {
    if (await ev(`(() => { const b=[...document.querySelectorAll('button')].find(x=>x.innerText.trim()===${JSON.stringify(label)}); if(!b) return false; b.click(); return true })()`)) break
  }
  await wait(800)
}
if (!(await hasShape())) {
  await ev(`(() => { const el=document.querySelector('#cb-goal'); if(!el) return false; Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set.call(el,'Order coffee and ask for the bill in Kyoto, politely'); el.dispatchEvent(new Event('input',{bubbles:true})); return true })()`)
  await wait(400)
  await ev(`(() => { const b=[...document.querySelectorAll('button')].find(x=>x.innerText.trim()==='Continue'); if(!b) return false; b.click(); return true })()`)
  await wait(800)
}
if (!(await hasShape())) throw new Error('could not reach the shape step')

for (const width of [1049, 900, 460]) {
  const measured = await setWidth(width)
  await wait(500)
  const report = await ev(`(() => {
    const route = document.querySelector('[data-cb-route]')
    const flow = document.querySelector('[data-cb-scope-cards]')
    const cards = [...document.querySelectorAll('[data-cb-scope-option]')]
    const track = document.querySelector('[data-cb-use-choice]')
    const seg = track ? track.querySelector('[class*="inline-grid"]') || track.children[1] : null
    const box = (n) => { const r = n.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), left: Math.round(r.left) } }
    return {
      innerWidth: window.innerWidth,
      route: box(route),
      flow: flow ? { ...box(flow), grid: getComputedStyle(flow).gridTemplateColumns, scrollW: flow.scrollWidth } : null,
      cards: cards.map((c) => ({ id: c.dataset.cbScopeOption, ...box(c), scrollW: c.scrollWidth, clientW: c.clientWidth, scrollH: c.scrollHeight, clientH: c.clientHeight, ws: getComputedStyle(c.children[2] || c).whiteSpace })),
      track: track ? { ...box(track), scrollW: track.scrollWidth, clientW: track.clientWidth, text: track.innerText.replace(/\\s+/g,' ').trim().slice(0,140) } : null,
      seg: seg ? { ...box(seg), scrollW: seg.scrollWidth, clientW: seg.clientWidth, options: [...seg.querySelectorAll('button')].map((b) => b.innerText.trim()) } : null,
      docOverflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      bodyOverflowX: document.body.scrollWidth - document.body.clientWidth
    }
  })()`)
  console.log(measured, JSON.stringify(report, null, 1))
}
socket.close()
