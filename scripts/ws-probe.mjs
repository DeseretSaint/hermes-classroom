#!/usr/bin/env node
// Direct WS probe for the CB-013 isolated backend. Usage: node scripts/ws-probe.mjs <url>
const url = process.argv[2]
if (!url) {
  console.error('usage: node scripts/ws-probe.mjs ws://host:port/api/ws?token=...')
  process.exit(2)
}
const socket = new WebSocket(url)
const done = (code, message) => {
  console.log(message)
  try { socket.close() } catch {}
  process.exit(code)
}
const timer = setTimeout(() => done(1, 'TIMEOUT: no open or error within 6s'), 6000)
socket.addEventListener('open', () => {
  clearTimeout(timer)
  console.log('OPEN')
  socket.send(JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'runtime.info', params: {} }))
})
socket.addEventListener('message', (event) => {
  console.log('MESSAGE: ' + String(event.data).slice(0, 600))
  done(0, 'MESSAGE-RECEIVED')
})
socket.addEventListener('error', (event) => {
  console.log('ERROR: ' + JSON.stringify(event?.message || event?.error || 'websocket error'))
})
socket.addEventListener('close', (event) => {
  clearTimeout(timer)
  done(1, 'CLOSE code=' + event.code + ' reason=' + JSON.stringify(event.reason))
})
