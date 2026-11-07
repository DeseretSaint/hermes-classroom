#!/usr/bin/env node
/**
 * H-61 capture transport: a loopback proxy in front of the isolated Coursebook backend.
 *
 *   window -> 127.0.0.1:44281 (this proxy) -> 44291 (course data) | 44292 (empty profile)
 *
 * Mode is read per request from CB_PROXY_STATE (JSON file):
 *   {"down": true}                     -> 503 for every request (backend-off frame)
 *   {"delay_method": "library.list",   -> hold only that RPC envelope, then forward (loading frame)
 *    "delay_ms": 6000}
 *   {"target": "http://127.0.0.1:44292"} -> which isolated backend to forward to
 *
 * It never rewrites a Coursebook response body, so every pixel and every row in the capture comes
 * from the real backend. Only the read the desk waits on is slowed, so the host's runtime probe
 * still answers and the route stays mounted; WebSocket upgrades are tunnelled unchanged.
 */
import http from 'node:http'
import net from 'node:net'
import { readFileSync } from 'node:fs'

const PORT = Number(process.env.CB_PROXY_PORT || 44301)
const BASE = process.env.CB_PROXY_TARGET || 'http://127.0.0.1:44302'
const STATE = process.env.CB_PROXY_STATE || '/tmp/h61-proxy-state.json'

const mode = () => {
  try { return JSON.parse(readFileSync(STATE, 'utf8')) } catch { return {} }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const targetFor = (m) => new URL(m.target || BASE)

const server = http.createServer(async (req, res) => {
  const m = mode()
  const TARGET = targetFor(m)
  if (m.down) {
    // Refuse at the transport, keeping the host's gateway link up so the route's own backend-off
    // screen is what paints. Body is a plain connection error, the same text a stopped backend
    // produces at this seam — no Coursebook payload is involved.
    res.writeHead(503, { 'content-type': 'application/json' })
    res.end(JSON.stringify({ detail: `connect ECONNREFUSED ${TARGET.host}` }))
    return
  }
  const url = new URL(req.url, TARGET)
  const chunks = []
  try {
    for await (const c of req) chunks.push(c)
  } catch {
    res.destroy()
    return
  }
  const body = Buffer.concat(chunks)
  if (req.url.includes('/api/')) console.log(`${req.method} ${url.pathname} ${body.length}B :: ${body.toString('utf8').slice(0, 160)}`)
  if (Number(m.delay_ms) > 0) {
    const method = m.delay_method || 'library.list'
    const text = body.toString('utf8')
    if (text.includes(`"${method}"`)) {
      console.log(`delaying ${m.delay_ms}ms for ${method} on ${url.pathname}`)
      await sleep(Number(m.delay_ms))
    }
  }
  const headers = { ...req.headers, host: url.host }
  const upstream = http.request(
    { hostname: url.hostname, port: url.port, path: url.pathname + url.search, method: req.method, headers },
    (up) => {
      res.writeHead(up.statusCode || 502, up.headers)
      up.pipe(res)
    }
  )
  upstream.on('error', (err) => {
    console.error('upstream error', err.message)
    res.writeHead(502, { 'content-type': 'application/json' })
    res.end(JSON.stringify({ detail: 'h61 proxy: upstream unreachable' }))
  })
  upstream.end(body)
})

server.on('upgrade', (req, socket, head) => {
  const m = mode()
  const TARGET = targetFor(m)
  const url = new URL(req.url, TARGET)
  const upstream = net.connect(Number(url.port || 80), url.hostname, () => {
    const lines = [`${req.method} ${req.url} HTTP/1.1`]
    for (const [k, v] of Object.entries(req.headers)) lines.push(`${k}: ${v}`)
    upstream.write(lines.join('\r\n') + '\r\n\r\n')
    if (head && head.length) upstream.write(head)
    socket.pipe(upstream).pipe(socket)
  })
  upstream.on('error', () => socket.destroy())
  socket.on('error', () => upstream.destroy())
})

server.listen(PORT, '127.0.0.1', () => console.log(`h61 proxy ${PORT} -> ${BASE} (state ${STATE})`))
