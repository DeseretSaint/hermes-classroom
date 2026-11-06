#!/usr/bin/env node
/**
 * One-shot JSON-RPC probe for a running Hermes backend.
 *
 *   node scripts/ws-rpc.mjs 'ws://127.0.0.1:44219/api/ws?token=…' plugins.manage '{"action":"list"}'
 *
 * Connects, waits for `gateway.ready`, sends one request, prints the matching
 * response as JSON, exits. Events are ignored. 15s ceiling.
 */
const [url, rawMethod, rawParams] = process.argv.slice(2)
if (!url || !rawMethod) {
  console.error('usage: node scripts/ws-rpc.mjs <ws-url> <method> [params-json]')
  process.exit(2)
}
const params = rawParams ? JSON.parse(rawParams) : {}
const socket = new WebSocket(url)
let settled = false
const finish = (code, text) => {
  if (settled) return
  settled = true
  console.log(text)
  try { socket.close() } catch {}
  process.exit(code)
}
const timer = setTimeout(() => finish(1, 'TIMEOUT'), 15000)
socket.addEventListener('open', () => {
  socket.send(JSON.stringify({ jsonrpc: '2.0', id: 1, method: rawMethod, params }))
})
socket.addEventListener('message', (event) => {
  let message
  try { message = JSON.parse(String(event.data)) } catch { return }
  if (message.id !== 1) return
  clearTimeout(timer)
  finish(0, JSON.stringify(message))
})
socket.addEventListener('error', () => finish(1, 'WS-ERROR'))
socket.addEventListener('close', (event) => finish(1, 'WS-CLOSE ' + event.code))
