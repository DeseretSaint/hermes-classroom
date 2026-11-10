#!/usr/bin/env node
/**
 * GM-002 documented failure switch: a pass-through transport proxy in front of the isolated
 * Coursebook backend.
 *
 * The Desktop's plugin transport is the Electron main-process HTTP client, so renderer Fetch
 * interception cannot reach it. Pointing the window's remote connection at this proxy is the real
 * seam: it forwards every request byte-for-byte except the named method.
 *
 *   GM002_PROXY_MODE=slow           delay library.list / course.outline 3000 ms
 *   GM002_PROXY_MODE=library-error  answer library.list with HTTP 500
 *   GM002_PROXY_MODE=outline-error  answer course.outline / world.read with HTTP 500
 *
 * Nothing is faked: a successful request is the backend's own response.
 */
import http from 'node:http'
import net from 'node:net'

const MODE = process.env.GM002_PROXY_MODE || 'slow'
const PORT = Number(process.env.GM002_PROXY_PORT || 44281)
const UPSTREAM = Number(process.env.GM002_UPSTREAM_PORT || 44279)
const DELAY_MS = Number(process.env.GM002_PROXY_DELAY_MS || 3000)

const methodOf = (body) => {
  try { return JSON.parse(body.toString('utf8')).method || null } catch { return null }
}

const server = http.createServer((request, response) => {
  const chunks = []
  request.on('data', (chunk) => chunks.push(chunk))
  request.on('end', () => {
    const body = Buffer.concat(chunks)
    if (request.url === '/health') {
      response.writeHead(200, { 'Content-Type': 'application/json' })
      response.end(JSON.stringify({ ok: true, proxy: MODE }))
      return
    }
    const method = methodOf(body)
    const slow = MODE === 'slow' && (method === 'library.list' || method === 'course.outline')
    const fail = (MODE === 'library-error' && method === 'library.list')
      || (MODE === 'outline-error' && (method === 'course.outline' || method === 'world.read'))
    const forward = () => {
      if (fail) {
        // An RPC-level failure, not a transport failure: HTTP 200 with the contract's error
        // envelope. The Desktop connection stays alive and the plugin paints its own error state;
        // an HTTP 500 makes the shell fall back to its CONNECT screen, which proves nothing.
        response.writeHead(200, { 'Content-Type': 'application/json' })
        response.end(JSON.stringify({
          ok: false,
          contract_version: 20,
          operation_id: `gm002-failure-${Date.now()}`,
          error: { code: 'HOST_UNAVAILABLE', message: `GM-002 failure switch: ${method} could not be read` }
        }))
        return
      }
      const headers = { ...request.headers, host: `127.0.0.1:${UPSTREAM}` }
      delete headers['content-length']
      const upstream = http.request({ host: '127.0.0.1', port: UPSTREAM, path: request.url, method: request.method, headers }, (answer) => {
        response.writeHead(answer.statusCode, answer.headers)
        answer.pipe(response)
      })
      upstream.on('error', () => {
        if (!response.headersSent) response.writeHead(502, { 'Content-Type': 'text/plain' })
        response.end('upstream unavailable')
      })
      upstream.end(body)
    }
    if (slow) setTimeout(forward, DELAY_MS)
    else forward()
  })
})
server.listen(PORT, '127.0.0.1', () => console.log(`gm002 proxy ${MODE} on ${PORT} -> ${UPSTREAM}`))

// The Desktop keeps its live event stream over an upgrade. A proxy that only handles plain HTTP
// drops that socket and the shell falls back to its CONNECT screen, which would invalidate the
// plugin-state capture; pass upgrades through untouched.
server.on('upgrade', (request, socket, head) => {
  const upstream = net.connect(UPSTREAM, '127.0.0.1', () => {
    const lines = [`${request.method} ${request.url} HTTP/1.1`]
    for (const [name, value] of Object.entries(request.headers)) lines.push(`${name}: ${value}`)
    upstream.write(`${lines.join('\r\n')}\r\n\r\n`)
    if (head && head.length) upstream.write(head)
    socket.pipe(upstream).pipe(socket)
  })
  upstream.on('error', () => socket.destroy())
  socket.on('error', () => upstream.destroy())
})
