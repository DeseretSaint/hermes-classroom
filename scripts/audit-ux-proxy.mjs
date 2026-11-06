/**
 * Sentinel UX-audit transport proxy.
 *
 * The Desktop plugin reaches the backend through `ctx.rest` (Electron main -> HTTP), so CDP
 * cannot intercept it. This proxy sits between the window and the isolated backend:
 *
 *   window -> 127.0.0.1:44232 (this proxy) -> 127.0.0.1:44231 (isolated Coursebook backend)
 *
 * It records every Coursebook call (provenance for the report) and can inject faults from
 * audit/ux/fault.json WITHOUT touching product code:
 *
 *   { "down": true }                                  -> 503 for every request (backend off)
 *   { "runtime": { ...runtime json... } }             -> replace /runtime body
 *   { "rpc": { "attempt.submit": { "__error": {...} } } } -> replace that method's envelope
 *   { "rpc": { "library.list": { ...full body... } } }    -> replace that method's body
 *
 * Only listens on loopback and only for this audit's isolated ports.
 */
import http from 'node:http'
import { readFileSync, appendFileSync, existsSync, mkdirSync } from 'node:fs'

const PORT = Number(process.env.AUDIT_PROXY_PORT || 44232)
const TARGET = process.env.AUDIT_TARGET || 'http://127.0.0.1:44231'
const ROOT = new URL('..', import.meta.url).pathname
const FAULT = `${ROOT}audit/ux/fault.json`
const LOG = `${ROOT}audit/ux/rpc-log.jsonl`
mkdirSync(`${ROOT}audit/ux`, { recursive: true })

const fault = () => {
  try {
    return JSON.parse(readFileSync(FAULT, 'utf8'))
  } catch {
    return {}
  }
}
const record = (entry) => {
  try {
    appendFileSync(LOG, `${JSON.stringify(entry)}\n`)
  } catch {}
}

const server = http.createServer(async (req, res) => {
  const chunks = []
  for await (const chunk of req) chunks.push(chunk)
  const raw = Buffer.concat(chunks)
  const f = fault()
  const url = new URL(req.url, 'http://proxy.invalid')
  const isRpc = url.pathname.includes('/api/plugins/coursebook/rpc')
  const isRuntime = url.pathname.includes('/api/plugins/coursebook/runtime')
  const isHealth = url.pathname.includes('/api/plugins/coursebook/health')

  let bodyJson = null
  if (isRpc && raw.length) {
    try {
      bodyJson = JSON.parse(raw.toString('utf8'))
    } catch {}
  }

  const send = (status, obj) => {
    const text = JSON.stringify(obj)
    res.writeHead(status, { 'content-type': 'application/json', 'content-length': Buffer.byteLength(text) })
    res.end(text)
  }

  if (f.down) {
    record({ at: Date.now(), method: bodyJson?.method || url.pathname, injected: 'down' })
    return send(503, { detail: 'audit-injected backend down' })
  }
  if (isRuntime && f.runtime) {
    record({ at: Date.now(), method: 'runtime', injected: 'runtime' })
    return send(200, f.runtime)
  }
  if (isHealth && f.health) {
    record({ at: Date.now(), method: 'health', injected: 'health' })
    return send(200, f.health)
  }
  if (f.rest) {
    for (const [suffix, body] of Object.entries(f.rest)) {
      if (url.pathname.endsWith(suffix)) {
        record({ at: Date.now(), method: `rest:${suffix}`, injected: 'rest' })
        return send(typeof body === 'object' && body && body.__status ? body.__status : 200, body)
      }
    }
  }
  if (isRpc && bodyJson && f.rpc && Object.prototype.hasOwnProperty.call(f.rpc, bodyJson.method)) {
    const injected = f.rpc[bodyJson.method]
    record({ at: Date.now(), method: bodyJson.method, injected: true, payload: bodyJson.payload })
    if (injected && injected.__error) {
      return send(200, {
        ok: false,
        contract_version: bodyJson.contract_version,
        operation_id: bodyJson.operation_id,
        error: injected.__error
      })
    }
    return send(200, injected)
  }

  // Forward untouched.
  const headers = { ...req.headers, host: new URL(TARGET).host }
  const upstream = http.request(
    `${TARGET}${req.url}`,
    { method: req.method, headers },
    (up) => {
      const bufs = []
      up.on('data', (d) => bufs.push(d))
      up.on('end', () => {
        const payload = Buffer.concat(bufs)
        if (isRpc || isRuntime) {
          let parsed = null
          try {
            parsed = JSON.parse(payload.toString('utf8'))
          } catch {}
          record({
            at: Date.now(),
            method: isRuntime ? 'runtime' : bodyJson?.method,
            status: up.statusCode,
            payload: bodyJson?.payload ?? null,
            ok: parsed?.ok ?? null,
            error: parsed?.error ?? null
          })
        }
        res.writeHead(up.statusCode || 502, up.headers)
        res.end(payload)
      })
    }
  )
  upstream.on('error', (error) => send(502, { detail: `audit proxy upstream error: ${error.message}` }))
  upstream.end(raw)
})

server.listen(PORT, '127.0.0.1', () => {
  console.log(`audit proxy on http://127.0.0.1:${PORT} -> ${TARGET}`)
  if (!existsSync(FAULT)) console.log('no fault file yet:', FAULT)
})
