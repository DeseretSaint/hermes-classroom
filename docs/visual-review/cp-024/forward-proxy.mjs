#!/usr/bin/env node
/**
 * CP-024 — a forwarding proxy that can hold one RPC method open.
 *
 * Why this exists: the course home's `loading` state is a read that has not answered yet. No
 * fixture in the rig's database can produce it, and the app's REST door is an IPC bridge, not a
 * renderer `fetch`, so page-level interception cannot reach it either. This proxy sits on the
 * port the window is already connected to, forwards every request to the real backend unchanged,
 * and — only for the method named in `CP024_STALL_METHODS` — holds the request open without
 * answering. The app therefore takes its real in-flight path against a real backend; nothing in
 * the page is patched and no script is injected.
 *
 * It is evidence tooling for the loading cell only. Every other cell talks to the backend
 * directly.
 *
 *   CP024_PROXY_PORT=44427 CP024_PROXY_TARGET=http://127.0.0.1:44428 \
 *   CP024_STALL_METHODS=course.outline node docs/visual-review/cp-024/forward-proxy.mjs
 */
import http from 'node:http'
import net from 'node:net'

const listen = Number(process.env.CP024_PROXY_PORT || 44427)
const target = new URL(process.env.CP024_PROXY_TARGET || 'http://127.0.0.1:44428')
const stallMethods = new Set(
  String(process.env.CP024_STALL_METHODS || 'course.outline')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean)
)

const log = (line) => console.log(`[forward-proxy] ${line}`)

const server = http.createServer((request, response) => {
  const chunks = []
  request.on('data', (chunk) => chunks.push(chunk))
  request.on('end', () => {
    const body = Buffer.concat(chunks)
    let method = null
    if (String(request.url || '').includes('/rpc') && body.length) {
      try {
        method = JSON.parse(body.toString('utf8')).method || null
      } catch {
        method = null
      }
    }
    if (method && stallMethods.has(method)) {
      log(`hold ${method} ${request.url} (no response, by request)`)
      return // deliberately never answered: the learner sees a read in flight
    }
    const headers = { ...request.headers, host: target.host }
    const upstream = http.request(
      {
        protocol: target.protocol,
        hostname: target.hostname,
        port: target.port,
        method: request.method,
        path: request.url,
        headers
      },
      (upstreamResponse) => {
        response.writeHead(upstreamResponse.statusCode || 502, upstreamResponse.headers)
        upstreamResponse.pipe(response)
      }
    )
    upstream.on('error', (error) => {
      log(`upstream error ${String(error && error.message ? error.message : error)}`)
      if (!response.headersSent) response.writeHead(502)
      response.end()
    })
    if (body.length) upstream.write(body)
    upstream.end()
    log(`forward ${method || request.method} ${request.url}`)
  })
})

server.on('upgrade', (request, socket, head) => {
  // The host's boot dials `/api/ws` before it will mount any plugin route, so the upgrade is
  // tunnelled to the same backend rather than refused; only plain HTTP reads are held.
  log(`tunnel websocket ${request.url}`)
  const upstream = net.connect(Number(target.port), target.hostname, () => {
    const headers = Object.entries(request.headers).map(([name, value]) =>
      `${name}: ${name.toLowerCase() === 'host' ? target.host : Array.isArray(value) ? value.join(', ') : value}`
    )
    upstream.write(`${request.method} ${request.url} HTTP/1.1\r\n${headers.join('\r\n')}\r\n\r\n`)
    if (head && head.length) upstream.write(head)
    socket.pipe(upstream)
    upstream.pipe(socket)
  })
  upstream.on('error', () => socket.destroy())
  socket.on('error', () => upstream.destroy())
})

server.listen(listen, '127.0.0.1', () => log(`listening on http://127.0.0.1:${listen} -> ${target.href}`))

const shutdown = () => {
  server.close(() => process.exit(0))
  setTimeout(() => process.exit(0), 1500).unref()
}
process.on('SIGTERM', shutdown)
process.on('SIGINT', shutdown)
