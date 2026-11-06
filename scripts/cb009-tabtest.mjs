const PORT = process.env.CB009_CDP_PORT || '9222'
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((t) => t.type === 'page' && /Hermes/.test(t.title || '')) || targets.find((t) => t.type === 'page')
const s = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((r) => s.addEventListener('open', r, { once: true }))
let id = 1
const p = new Map()
s.addEventListener('message', (e) => {
  const m = JSON.parse(e.data)
  if (m.id && p.has(m.id)) {
    const { res, rej } = p.get(m.id)
    p.delete(m.id)
    m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result)
  }
})
const send = (method, params = {}) =>
  new Promise((res, rej) => {
    const i = id++
    p.set(i, { res, rej })
    s.send(JSON.stringify({ id: i, method, params }))
  })
const ev = async (x) => {
  const r = await send('Runtime.evaluate', { expression: x, awaitPromise: true, returnByValue: true, userGesture: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description)
  return r.result?.value
}
await send('Page.enable')
await send('Runtime.enable')
console.log('hash', await ev('location.hash'))
console.log('before', await ev('document.activeElement && document.activeElement.tagName + ":" + ((document.activeElement.getAttribute("aria-label")||document.activeElement.innerText||"").trim().slice(0,40))'))
for (let i = 0; i < 12; i++) {
  for (const type of ['rawKeyDown', 'keyUp'])
    await send('Input.dispatchKeyEvent', { type, key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 })
  await new Promise((r) => setTimeout(r, 200))
  console.log(i, await ev('(()=>{const a=document.activeElement;return {tag:a.tagName,name:(a.getAttribute("aria-label")||a.innerText||"").trim().slice(0,60),role:a.getAttribute("role"),id:a.id}})()'))
}
s.close()
