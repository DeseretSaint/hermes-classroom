/**
 * Coursebook — Desktop half.
 *
 * This is the disk-door plugin module for the `coursebook` unified package: the Electron main
 * process copies it to `$HERMES_HOME/desktop-plugins/coursebook/plugin.js` and the renderer loads
 * it uncompiled. That has two hard consequences, verified against
 * `apps/desktop/src/contrib/runtime-loader.ts`:
 *
 *   1. exactly ONE module — a runtime plugin may only import `@hermes/plugin-sdk`, `react` and
 *      `react/jsx-runtime`, so relative imports and extra files do not resolve;
 *   2. no JSX — UI is built with `jsx()` / `jsxs()`.
 *
 * Phase boundary (CB-005, the Desktop shell):
 *
 *   - destination shell: Courses and Library, page header, scope badges;
 *   - first-run welcome, no-courses, filtered-empty, backend-off, reconnecting and
 *     database-not-migrated states, each with a real action;
 *   - Courses list from `library.list` (the contract's own row shape: next step, evidence
 *     summary, warning, revision) with search, filter, archive and a previewed delete;
 *   - Library reading installed packs from the same real rows, grouped by provenance;
 *   - the staged create-course flow that ends in `course.create` + `enrollment.create`.
 *
 * Everything this file renders is read from the mounted backend or from state the user just
 * entered. There is no sample course, no sample evidence and no second chat surface. A control is
 * present only when the command behind it is in the backend's `/runtime` method registry and a
 * real screen exists for it — a button that does nothing is not a shell, it is a lie.
 *
 * Session ids are never interchangeable here. `host.state.focusedSessionId` is the live runtime
 * id (diagnostics only); `host.state.focusedStoredSessionId` is the durable id a binding stores
 * and the only id `binding.get` / `host.openSession` may receive. A fresh draft legitimately has
 * no stored id — the pane says so instead of falling back to "most recent".
 */
import * as sdk from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useCallback, useEffect, useRef, useState } from 'react'

const PLUGIN_ID = 'coursebook'
const ROUTE_PATH = '/coursebook'
const ROUTE_TITLE = 'Coursebook'

const AREAS = {
  routes: sdk.ROUTES_AREA || 'routes',
  sidebarNav: sdk.SIDEBAR_NAV_AREA || 'sidebar.nav',
  panes: sdk.PANES_AREA || 'panes',
  palette: sdk.PALETTE_AREA || 'palette',
  keybinds: sdk.KEYBINDS_AREA || 'keybinds'
}

/**
 * Mirrors of frozen contract enums. `tests/test_desktop_contracts.py` reads this module and
 * refuses any drift from `contracts/vocabulary.v1.json` and `contracts/rpc.v2.json`, so these
 * are checked copies rather than a second authority.
 */
const RECIPES = ['one_off', 'casual', 'committed', 'companion', 'parent']
const RECIPE_COPY = {
  one_off: {
    title: 'One-off',
    description: 'A single skill or question you want handled, then done.'
  },
  casual: {
    title: 'Casual',
    description: 'Short sessions, low pressure, pick it up when you have ten minutes.'
  },
  committed: {
    title: 'Committed',
    description: 'A sequence that builds on itself with scheduled practice.'
  },
  companion: {
    title: 'Companion',
    description: 'A long-running subject you keep returning to alongside other work.'
  },
  parent: {
    title: 'Parent preparation',
    description: 'You are preparing material for a child. Authored in Parent Studio, not here.'
  }
}
const DIALS = {
  pace: {
    label: 'Pace',
    options: [
      { id: 'light', label: 'Light' },
      { id: 'steady', label: 'Steady' },
      { id: 'intense', label: 'Intense' }
    ]
  },
  depth: {
    label: 'Depth',
    options: [
      { id: 'survey', label: 'Survey' },
      { id: 'working', label: 'Working' },
      { id: 'deep', label: 'Deep' }
    ]
  },
  assessment: {
    label: 'Assessment',
    options: [
      { id: 'none', label: 'None' },
      { id: 'self_check', label: 'Self-check' },
      { id: 'graded', label: 'Graded' }
    ]
  },
  autonomy: {
    label: 'Autonomy',
    options: [
      { id: 'guided', label: 'Guided' },
      { id: 'balanced', label: 'Balanced' },
      { id: 'independent', label: 'Independent' }
    ]
  }
}
const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'in_progress', label: 'In progress' },
  { id: 'review_due', label: 'Review due' },
  { id: 'archived', label: 'Archived' }
]
const DESTINATIONS = [
  { id: 'courses', label: 'Courses' },
  { id: 'library', label: 'Library' },
  { id: 'studio', label: 'Parent Studio' }
]

/**
 * Set true by the pack work package when its import/export screens land in this module. The
 * import action is a two-step trust/rights review that does not exist yet, so the button is
 * absent rather than disabled-forever. Named here so the next package has one place to flip.
 */
const IMPORT_FLOW_WIRED = true
/** The create flow lives in this file, so it needs no separate flag. */

/** Set once in register(); components read the scoped context from here. */
let pluginContext = null

/** Resolved once from `host.profileRoutes()` (async in current builds) — profile → connection. */
let profileRouteCache = []

/** The host door, imported once. Everything below calls `host.*` exactly as documented. */
const host = sdk.host

/**
 * What the mounted backend actually speaks, read from `/runtime`.
 *
 * This is the registry, not a second copy of the contract: `contractVersion` travels on every
 * envelope and `implemented` gates any control that would call an unimplemented command. When
 * the frozen contract is amended (v2 adds library.list / lesson.* / artifact.get / jobs.list /
 * notebook.update), this module needs no edit — it re-reads the version and the method list.
 *
 * `singleHome` is the host's own declaration that this backend process serves exactly ONE home
 * (``HERMES_COURSEBOOK_SINGLE_HOME=1``, set by ``scripts/install-local.sh``). It changes only
 * one thing: :func:`rest` then states the scope explicitly as `?profile=` — "the current
 * profile", the host's documented spelling for "no profile scope" — instead of letting the app
 * append the ambient profile, which on an isolated backend resolves to a DIFFERENT home (and is
 * forwarded to that profile's plugin host). Multi-profile hosting never advertises the flag and
 * keeps today's behaviour.
 */
let backendWire = { contractVersion: 1, implemented: null, error: null, singleHome: false }

/** Route-level intents the palette and keybind can hand to an already-mounted page. */
const intentListeners = new Set()
let pendingIntent = null

/**
 * A fresh run this Desktop opened, waiting for its chat to get a durable id.
 *
 * `lesson.begin` returns the run before the chat exists; a draft has no stored session id until
 * its first turn. The pane therefore arms the exact run it started (never "the newest run") and
 * calls the `POST /sessions/bind` host seam once the focused chat has a stored id. One arming is
 * one attempt: the intent is consumed by the bind call, expires after 15 minutes, and never
 * survives a reload as a guess about which chat the user meant.
 */
const PENDING_BIND_TTL_MS = 15 * 60 * 1000
let pendingBind = null

function armPendingBind({ enrollmentId, objectiveId, lessonRunId, profile }) {
  if (!enrollmentId || !objectiveId || !lessonRunId) {
    pendingBind = null
    return null
  }
  pendingBind = {
    enrollmentId,
    objectiveId,
    lessonRunId,
    profile: profile || null,
    armedAt: Date.now()
  }
  return pendingBind
}

function pendingBindFor(profile) {
  if (!pendingBind) return null
  if (Date.now() - pendingBind.armedAt > PENDING_BIND_TTL_MS) {
    pendingBind = null
    return null
  }
  if (pendingBind.profile && profile && pendingBind.profile !== profile) return null
  return pendingBind
}

/**
 * Bind the focused chat to the armed run. Returns the seam response, or null when nothing is
 * armed. The seam — not this file — decides whether the bind is legal, so a refusal is rendered
 * as the seam's own code and message.
 */
async function bindPendingChat(storedSessionId, profile) {
  const intent = pendingBindFor(profile)
  if (!intent || !storedSessionId || !pluginContext) return null
  pendingBind = null
  try {
    return await rest('/sessions/bind', {
      method: 'POST',
      body: {
        stored_session_id: storedSessionId,
        enrollment_id: intent.enrollmentId,
        objective_id: intent.objectiveId,
        lesson_run_id: intent.lessonRunId,
        profile: intent.profile || profile || currentScope().profile || undefined
      }
    })
  } catch (error) {
    return { ok: false, code: 'HOST_UNAVAILABLE', message: describeError(error) }
  }
}

function requestIntent(intent) {
  pendingIntent = intent
  intentListeners.forEach((listener) => listener(intent))
  host.navigate(ROUTE_PATH)
}

function useRouteIntent(handler) {
  const handlerRef = useRef(handler)
  handlerRef.current = handler
  useEffect(() => {
    const listener = (intent) => handlerRef.current(intent)
    intentListeners.add(listener)
    if (pendingIntent) {
      const intent = pendingIntent
      pendingIntent = null
      listener(intent)
    }
    return () => {
      intentListeners.delete(listener)
    }
  }, [])
}

/** The destination survives leaving the route; it is a view preference, not navigation state. */
let rememberedDestination = 'courses'

function requireContext() {
  if (!pluginContext) throw new Error('Coursebook is not registered')
  return pluginContext
}

function newOperationId(method) {
  const slug = String(method || 'call')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .toLowerCase()
  const random =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID().slice(0, 12)
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
  return `cb-${slug}-${random}`
}

/** Envelope-shaped transport failure. A dead backend is `ok:false`, not a thrown control flow. */
function transportFailure(operationId, method, error) {
  return {
    ok: false,
    contract_version: backendWire.contractVersion,
    operation_id: operationId,
    error: {
      code: 'HOST_UNAVAILABLE',
      category: 'capability',
      message: describeError(error),
      retryable: true,
      details: { method }
    }
  }
}

/**
 * One command over `ctx.rest('/rpc')`.
 *
 * Contract refusals come back as `ok:false` and are returned, never thrown: the caller renders
 * `error.code`. Only a transport failure is converted into an envelope here, so a caller cannot
 * mistake "backend down" for "policy refused". `idempotencyKey` / `expectedRevision` are passed
 * explicitly because a mutation requires them — nothing is generated behind the caller's back.
 */
async function rpc(method, payload = {}, options = {}) {
  // A cold mount (the pane renders before the health probe resolves) used to send
  // contract_version 1 and take a VALIDATION_FAILED refusal from a v5 backend. Resolve the wire
  // facts first; the probe is cached per page and its failure is already a handled envelope.
  if (typeof ensureBackendWire === 'function') await ensureBackendWire()
  const operationId = options.operationId || newOperationId(method)
  const body = {
    contract: 'cb.rpc',
    contract_version: options.contractVersion || backendWire.contractVersion,
    method,
    operation_id: operationId,
    payload
  }
  if (options.idempotencyKey !== undefined && options.idempotencyKey !== null) {
    body.idempotency_key = options.idempotencyKey
  }
  if (options.expectedRevision !== undefined && options.expectedRevision !== null) {
    body.expected_revision = options.expectedRevision
  }
  let response
  try {
    response = await rest('/rpc', {
      method: 'POST',
      body,
      timeoutMs: options.timeoutMs
    })
  } catch (error) {
    return transportFailure(operationId, method, error)
  }
  if (!response || typeof response !== 'object' || typeof response.ok !== 'boolean') {
    return {
      ok: false,
      contract_version: body.contract_version,
      operation_id: operationId,
      error: {
        code: 'INTERNAL_ERROR',
        category: 'internal',
        message: 'The Coursebook backend answered with something that is not a contract envelope.',
        retryable: true,
        details: { method }
      }
    }
  }
  return response
}

/** True when the mounted backend has a handler. Unknown registry (old backend) means "ask". */
function backendSupports(method) {
  if (!backendWire.implemented) return true
  return backendWire.implemented.has(method)
}

async function loadBackendWire() {
  try {
    // Ask for "the current profile" explicitly. On a single-home backend the ambient profile
    // resolves elsewhere, so an unscoped `/runtime` would describe a different process.
    const runtime = await requireContext().rest('/runtime?profile=')
    const version = Number(runtime && runtime.wire_version)
    backendWire = {
      contractVersion: Number.isFinite(version) && version > 0 ? version : 1,
      implemented: Array.isArray(runtime && runtime.implemented_methods)
        ? new Set(runtime.implemented_methods)
        : null,
      error: null,
      singleHome: runtime?.single_home_host === true
    }
  } catch (error) {
    backendWire = {
      contractVersion: backendWire.contractVersion,
      implemented: null,
      error,
      singleHome: false
    }
  }
  return backendWire
}

/** The backend facts, loaded once per page (the registry is static for a mounted process). */
let wireReady = null

function ensureBackendWire() {
  if (!wireReady) {
    wireReady = loadBackendWire().then((wire) => {
      // A dead backend is a fact for this call, not for the life of the page: let the next
      // call probe again instead of pinning `singleHome: false` forever.
      if (wire.error) wireReady = null
      return wire
    })
  }
  return wireReady
}

/** State the profile scope explicitly (`profile=` = the current profile) for a single-home host. */
function scopePath(path) {
  const target = String(path || '')
  if (!backendWire.singleHome || !target) return target
  try {
    const parsed = new URL(target, 'http://coursebook.invalid')
    if (parsed.searchParams.has('profile')) return target
    parsed.searchParams.set('profile', '')
    return `${parsed.pathname}${parsed.search}${parsed.hash}`
  } catch {
    return target
  }
}

/**
 * The one REST door this module uses.
 *
 * Same `ctx.rest` seam as everywhere else, plus the single-home scope decision. It waits for the
 * `/runtime` probe so a call issued before boot finishes cannot fall back to the ambient profile
 * and read another home; `loadBackendWire` itself calls `ctx.rest` directly, so this cannot
 * recurse.
 */
async function rest(path, options) {
  await ensureBackendWire()
  return requireContext().rest(scopePath(path), options)
}

/**
 * Which profile/connection this page is acting for.
 *
 * Explicit and read-only: the focused chat's owning profile first (a tile can show another
 * profile than the launch one), then the window's active profile. `connectionId` comes from the
 * registry route for that profile, or stays null — it is never inferred from a URL.
 */
function currentScope() {
  const focused = host.state.focusedSessionProfile && host.state.focusedSessionProfile.get()
  const profile = String(focused || (host.state.profile && host.state.profile.get()) || '').trim() || null
  let connectionId = null
  const routes = Array.isArray(profileRouteCache) ? profileRouteCache : []
  const match = routes.find((route) => route && route.profile === profile)
  if (match && match.connectionId) connectionId = match.connectionId
  return { profile, connectionId }
}

/**
 * The focused chat's two ids, kept apart on purpose.
 *
 * `runtimeId` is the live gateway id — valid for this turn's tool/RPC calls only.
 * `storedId` is the durable id that survives compression and is what a binding row stores.
 * There is no fallback between them: a fresh draft legitimately has `storedId: null`, and
 * guessing (or picking "most recent") would attach a lesson to the wrong chat.
 */
function currentSessionIds() {
  return {
    runtimeId: (host.state.focusedSessionId && host.state.focusedSessionId.get()) || null,
    storedId: (host.state.focusedStoredSessionId && host.state.focusedStoredSessionId.get()) || null
  }
}

/** `binding.get` for exactly one explicit identifier. */
async function loadBinding({ storedSessionId = null, enrollmentId = null } = {}) {
  if (Boolean(storedSessionId) === Boolean(enrollmentId)) {
    throw new Error('loadBinding needs exactly one of storedSessionId or enrollmentId')
  }
  return rpc('binding.get', storedSessionId ? { session_id: storedSessionId } : { enrollment_id: enrollmentId })
}

/**
 * Open the chat a binding row names. Only `stored_session_id` is accepted, and only for an
 * active binding: a paused/detached/branched/orphaned lesson is a state the UI must explain,
 * not quietly bypass by opening some other chat.
 */
async function resumeBoundSession(binding) {
  if (!binding || !binding.stored_session_id) {
    return { ok: false, reason: 'no-durable-chat', message: 'This lesson has no durable chat to resume yet.' }
  }
  if (binding.status !== 'active') {
    return { ok: false, reason: 'binding-not-active', message: `This lesson's chat binding is ${binding.status}.` }
  }
  if (typeof host.openSession !== 'function') {
    return { ok: false, reason: 'unsupported', message: 'Update Hermes Desktop to resume a bound lesson.' }
  }
  await host.openSession(binding.stored_session_id, {
    profile: binding.profile || currentScope().profile || undefined
  })
  return { ok: true, storedSessionId: binding.stored_session_id }
}

/** Start a fresh chat draft. A draft has no session id until its first turn — callers must not
 * treat the return value as one. */
function startLessonChat(profile) {
  if (typeof host.newChat !== 'function') return false
  host.newChat(profile || null)
  return true
}

function describeError(error) {
  if (!error) return 'The Coursebook backend did not answer.'
  if (typeof error === 'string') return error
  if (error.message) return String(error.message)
  return 'The Coursebook backend did not answer.'
}

async function fetchHealth() {
  if (!pluginContext) throw new Error('Coursebook is not registered')
  return rest('/health')
}

async function fetchSchema() {
  if (!pluginContext) throw new Error('Coursebook is not registered')
  return rest('/schema')
}

/**
 * Backend health, as the UI must see it:
 *   loading | ready | degraded (backend answered, database not migrated) | unavailable (no backend)
 * Never optimistic: nothing here reports a course state it did not read.
 */
function useHealth() {
  const [state, setState] = useState({ status: 'loading', result: null, error: null })
  const [ticket, setTicket] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState((previous) => ({
      status: 'loading',
      result: previous.result,
      error: null
    }))
    ;(async () => {
      try {
        const response = await fetchHealth()
        if (cancelled) return
        if (response && response.ok) {
          setState({
            status: response.result.db && response.result.db.ready ? 'ready' : 'degraded',
            result: response.result,
            error: null
          })
        } else {
          setState({ status: 'unavailable', result: null, error: response && response.error })
        }
      } catch (error) {
        if (!cancelled) setState({ status: 'unavailable', result: null, error })
      }
    })()
    return () => {
      cancelled = true
    }
  }, [ticket])

  const reload = useCallback(() => setTicket((value) => value + 1), [])
  return { state, reload }
}

/** The backend's method registry, so a control can be absent instead of dead. */
function useRuntime(healthStatus) {
  const [implemented, setImplemented] = useState(backendWire.implemented)

  useEffect(() => {
    if (!pluginContext) return undefined
    let cancelled = false
    loadBackendWire().then((wire) => {
      if (!cancelled) setImplemented(wire.implemented)
    })
    return () => {
      cancelled = true
    }
  }, [healthStatus])

  return implemented
}

/**
 * One backend read with request tokens.
 *
 * A stale response can never overwrite newer user intent: every call takes a sequence number and
 * only the newest one is allowed to paint. `reload()` keeps the last read on screen and marks it
 * stale while the retry is in flight, which is exactly what a reconnecting UI needs — the page
 * never blanks out and never pretends the retry has already happened.
 */
function useRpcQuery(method, payload, key, enabled = true) {
  const [state, setState] = useState({ status: 'loading', data: null, error: null, stale: false })
  const sequence = useRef(0)
  const keyRef = useRef(key)
  const [ticket, setTicket] = useState(0)

  useEffect(() => {
    if (!enabled) {
      sequence.current += 1
      setState({ status: 'idle', data: null, error: null, stale: false })
      return undefined
    }
    const keyChanged = keyRef.current !== key
    keyRef.current = key
    const mine = ++sequence.current
    setState((previous) => ({
      status: 'loading',
      data: keyChanged ? null : previous.data,
      error: null,
      stale: keyChanged ? false : Boolean(previous.data)
    }))
    rpc(method, payload)
      .then((response) => {
        if (mine !== sequence.current) return
        if (response && response.ok) {
          setState({ status: 'ready', data: response.result, error: null, stale: false })
        } else {
          setState((previous) => ({
            status: 'error',
            data: previous.data,
            error: (response && response.error) || null,
            stale: Boolean(previous.data)
          }))
        }
      })
      .catch((error) => {
        if (mine !== sequence.current) return
        setState((previous) => ({
          status: 'error',
          data: previous.data,
          error: { code: 'HOST_UNAVAILABLE', message: describeError(error) },
          stale: Boolean(previous.data)
        }))
      })
    return undefined
  }, [key, enabled, ticket])

  const reload = useCallback(() => setTicket((value) => value + 1), [])
  return { ...state, reload }
}

function EmptyState({ title, description, children }) {
  return jsxs('div', {
    className: 'flex flex-col items-center gap-3',
    children: [jsx(sdk.EmptyState, { title, description }), children || null]
  })
}

function openCapabilities() {
  if (!pluginContext) return
  const outcome = pluginContext.runAction('nav.capabilities')
  if (!outcome || !outcome.ok) {
    sdk.host.notify({ kind: 'warning', message: 'Open Capabilities → Plugins and enable Coursebook.' })
  }
}

function StatusRow({ label, value, detail }) {
  return jsxs('div', {
    className: 'flex items-baseline justify-between gap-4 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
    children: [
      jsxs('div', {
        className: 'min-w-0',
        children: [
          jsx('div', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: label }),
          detail
            ? jsx('div', { className: 'mt-0.5 text-xs text-(--ui-text-tertiary)', children: detail })
            : null
        ]
      }),
      jsx('div', { className: 'shrink-0 text-right text-xs text-(--ui-text-secondary)', children: value })
    ]
  })
}

/** A warning is text, never color alone. */
const WARNING_COPY = {
  detached_chat: {
    label: 'Detached chat',
    detail: 'This lesson’s chat binding is detached. Submitting is disabled until it is rebound.'
  },
  pack_frozen: {
    label: 'Pack frozen',
    detail: 'The imported pack this course came from is frozen; its content will not change.'
  },
  stale_source: {
    label: 'Source stale',
    detail: 'A source behind this course changed. Existing evidence is kept; the source needs review.'
  },
  plan_update: {
    label: 'Plan update',
    detail: 'A newer plan draft is waiting for review.'
  }
}

function WarningBadge({ warning }) {
  const copy = WARNING_COPY[warning]
  if (!copy) return null
  return jsx(sdk.Badge, { variant: 'warn', children: copy.label })
}

function EvidenceLine({ summary }) {
  if (!summary) return null
  const independent = Number(summary.independent || 0)
  const reviewDue = Number(summary.review_due || 0)
  const total = Number(summary.total_objectives || 0)
  const parts = [
    `${independent} independent`,
    reviewDue > 0 ? `${reviewDue} due` : null,
    total > 0 ? `${total} objective${total === 1 ? '' : 's'}` : null
  ].filter(Boolean)
  return jsx('div', {
    className: 'mt-1.5 text-xs text-(--ui-text-tertiary)',
    children: parts.join(' · ')
  })
}

function ErrorLine({ error }) {
  if (!error) return null
  const code = error.code ? `${error.code}: ` : ''
  return jsx('div', {
    className: 'mt-2 text-xs text-(--ui-text-tertiary)',
    children: `${code}${describeError(error)}`
  })
}

/** Shared page chrome: a destination body never re-implements its own header. */
function PageBody({ children }) {
  return jsx('div', { className: 'min-h-0 flex-1 overflow-auto px-4 pb-6', children })
}

function backendCopy(status) {
  if (status === 'degraded') return 'Database not migrated'
  if (status === 'unavailable') return 'Backend off'
  return null
}

function BackendUnavailable({ error, reload }) {
  return jsx('div', {
    className: 'mx-auto flex w-full max-w-xl flex-col gap-4 py-8',
    children: [
      jsx(sdk.ErrorState, {
        title: 'Coursebook needs its agent plugin',
        description:
          'The Desktop half is enabled but its Python backend is not answering for this profile. ' +
          'Enable Coursebook under Capabilities → Plugins, then restart the gateway. ' +
          'Desktop and backend halves are enabled separately.',
        children: jsxs('div', {
          className: 'flex flex-wrap items-center justify-center gap-2',
          children: [
            jsx(sdk.Button, { variant: 'default', onClick: openCapabilities, children: 'Open Capabilities' }),
            jsx(sdk.Button, { variant: 'secondary', onClick: reload, children: 'Check again' })
          ]
        })
      }),
      jsx('div', {
        className: 'text-center text-xs text-(--ui-text-tertiary)',
        children: error && error.code
          ? `${error.code}: ${describeError(error)}`
          : describeError(error)
      })
    ]
  })
}

/** The backend answered, but its database has no schema: nothing can be stored or listed yet. */
function DegradedBody({ result, reload }) {
  const db = result && result.db ? result.db : {}
  return jsx('div', {
    className: 'mx-auto flex w-full max-w-xl flex-col gap-4 py-8',
    children: [
      jsx(sdk.ErrorState, {
        title: 'The course database is not migrated yet',
        description:
          'The backend is connected and its contract is loaded, but this profile has no course ' +
          'tables, so there is nowhere to store a course and nothing honest to list. This page ' +
          'will not show an empty library as if you had no courses.',
        children: jsxs('div', {
          className: 'flex flex-wrap items-center justify-center gap-2',
          children: [
            jsx(sdk.Button, { variant: 'default', onClick: reload, children: 'Check again' }),
            jsx(sdk.Button, { variant: 'secondary', onClick: openCapabilities, children: 'Open Capabilities' })
          ]
        })
      }),
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(StatusRow, {
            label: 'Backend contract',
            value: `cb.rpc v${result && result.contract_version ? result.contract_version : backendWire.contractVersion}`,
            detail: `plugin ${result && result.plugin_version ? result.plugin_version : 'unknown'}`
          }),
          jsx(StatusRow, {
            label: 'Database',
            value: db.ready ? `schema v${db.schema_version}` : 'not migrated',
            detail: db.ready ? 'Profile-scoped SQLite is ready.' : 'No course tables exist for this profile yet.'
          })
        ]
      })
    ]
  })
}

/** The three plain-sentence orientation lines from the spec. Flat: no cards inside cards. */
function Orientation() {
  const items = [
    ['Create or import', 'Start from a goal you can describe, or from a prepared pack.'],
    ['Practice with evidence', 'Your answers change the next step; nothing advances on its own.'],
    ['Reuse and share', 'Export teaching material without exporting your learning history.']
  ]
  return jsx('div', {
    className: 'mt-6 flex flex-col gap-3 border-t border-(--ui-stroke-tertiary) pt-4',
    children: items.map(([title, description]) =>
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx('div', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: title }),
          jsx('div', { className: 'mt-0.5 max-w-prose text-xs text-(--ui-text-tertiary)', children: description })
        ]
      })
    )
  })
}

function supportNote(implemented) {
  if (!implemented) return null
  const missing = []
  if (!implemented || !implemented.has('pack.preview')) missing.push('pack preview')
  if (!implemented || !implemented.has('pack.import')) missing.push('pack import')
  if (!implemented || !implemented.has('jobs.create')) missing.push('plan generation jobs')
  if (missing.length === 0) return null
  return jsx('div', {
    className: 'mt-4 text-xs text-(--ui-text-tertiary)',
    children: `Not in this backend build yet: ${missing.join(', ')}. Nothing here is sample data, so those actions are absent rather than faked.`
  })
}

/** The honest welcome: real state, real actions, no marketing hero and no fake sample progress. */
function FirstRun({ implemented, onCreate }) {
  const canCreate = Boolean(implemented && implemented.has('course.create')) && typeof onCreate === 'function'
  const canImport = Boolean(IMPORT_FLOW_WIRED && implemented && implemented.has('pack.import'))
  return jsxs('div', {
    className: 'mx-auto flex w-full max-w-2xl flex-col py-2',
    children: [
      jsx('h2', {
        className: 'text-[length:var(--conversation-text-font-size)] font-semibold',
        children: 'Build a course around what you want to do.'
      }),
      jsx('p', {
        className: 'mt-1 max-w-prose text-xs leading-relaxed text-(--ui-text-tertiary)',
        children:
          'Your courses will appear here. Progress and personal answers stay on this profile.'
      }),
      canCreate || canImport
        ? jsxs('div', {
            className: 'mt-4 flex flex-wrap items-center gap-2',
            children: [
              canCreate
                ? jsx(sdk.Button, { variant: 'default', onClick: onCreate, children: 'Create a course' })
                : null,
              canImport
                ? jsx(sdk.Button, { variant: 'secondary', onClick: onImportPlaceholder, children: 'Import a pack' })
                : null
            ]
          })
        : null,
      Orientation(),
      supportNote(implemented)
    ]
  })
}

function onImportPlaceholder() {
  requestIntent({ kind: 'import' })
}

// ── Packs: intake, trust/rights review, export review, tombstone (CB-010) ─────────────
//
// A pack is untrusted data, so this half never claims more than the backend answered:
//
//   intake   the host grants a local archive; the backend mints a staged_id (a path never
//            travels over the wire, and this build shows an honest state when the host route
//            is absent instead of a picker that cannot deliver);
//   review   every fact comes from `pack.preview` — author, outcomes, sources/support, licence,
//            notes, media size, versions and the four trust labels kept separate;
//   import   the learner chooses resume (continue the existing classroom) or fresh (new
//            progress over the same immutable content); the pack's recipe is never a choice;
//   export   the reviewed content hash is echoed back, and a mismatch refuses the export;
//   delete   `pack.delete` previews a data scope, then freezes the pack and keeps evidence.
const TRUST_COPY = {
  integrity_verified: 'Integrity only: each file matches the hash in the manifest. Says nothing about the teaching.',
  automated_checks_passed: 'Automated checks passed: structure, minima and content audit. No human read it for this label.',
  human_review_recorded: 'A named reviewer and date are recorded in the manifest.',
  model_assessed_support: 'At least one source support status was assessed by a model, not by a document.'
}

const PACK_RECIPE_COPY = {
  one_off: 'One-off task',
  casual: 'Casual self-study',
  committed: 'Committed course',
  companion: 'Companion to a course',
  parent: 'Parent blueprint — never a graded child course'
}

/** The last reviewed preview per pack, so an export can echo the exact hash that was shown. */
const previewCache = new Map()

function cachePreview(manifest) {
  if (!manifest || !manifest.pack_id) return
  previewCache.set(`${manifest.pack_id}@${manifest.pack_version}`, manifest)
}

function bytesLabel(value) {
  const bytes = Number(value || 0)
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * Host intake capability. The backend cannot accept a path from the wire; the host adapter mints
 * the grant. Until that route exists, the import action is absent and this state says why.
 */
function usePackIntake(enabled) {
  const [state, setState] = useState({ status: enabled ? 'loading' : 'off', info: null, error: null })
  useEffect(() => {
    let cancelled = false
    if (!enabled || !pluginContext) {
      setState({ status: 'off', info: null, error: null })
      return undefined
    }
    ;(async () => {
      try {
        const response = await rest('/packs/intake')
        if (cancelled) return
        const available = Boolean(response && (response.can_grant || response.available))
        setState({ status: available ? 'available' : 'unsupported', info: response || null, error: null })
      } catch (error) {
        if (!cancelled) setState({ status: 'unsupported', info: null, error })
      }
    })()
    return () => {
      cancelled = true
    }
  }, [enabled])
  return state
}

function PackReviewLine({ label, value }) {
  return jsxs('div', {
    className: 'flex items-baseline justify-between gap-4 border-b border-(--ui-stroke-tertiary) py-1.5 last:border-b-0',
    children: [
      jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: label }),
      jsx('div', { className: 'min-w-0 break-words text-xs text-(--ui-text-secondary)', children: value })
    ]
  })
}

function PackPreview({ preview, existing }) {
  const manifest = preview.manifest
  const labels = (preview.trust && preview.trust.labels) || []
  const sources = manifest.sources || []
  const objectives = manifest.objectives || []
  const files = manifest.files || []
  return jsxs('div', {
    className: 'flex flex-col gap-4',
    children: [
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx('h3', { className: 'text-sm font-semibold', children: manifest.title }),
          manifest.subtitle
            ? jsx('div', { className: 'mt-0.5 text-xs text-(--ui-text-tertiary)', children: manifest.subtitle })
            : null,
          jsxs('div', {
            className: 'mt-2 flex flex-wrap items-center gap-2',
            children: [
              jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: manifest.pack_id }),
              jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: `v${manifest.pack_version}` }),
              jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: PACK_RECIPE_COPY[manifest.recipe] || manifest.recipe }),
              manifest.minimum_coursebook_version
                ? jsx(sdk.Badge, {
                    size: 'xs',
                    variant: 'muted',
                    children: `needs Coursebook ${manifest.minimum_coursebook_version}`
                  })
                : null
            ]
          }),
          existing.length
            ? jsx('div', {
                className: 'mt-2 text-xs text-(--ui-text-tertiary)',
                children:
                  `Installed on this profile as ${existing.map((row) => `v${row.pack_version || '?'}`).join(', ')}. ` +
                  'Importing this version adds content, never a second copy; progress is chosen in the next step.'
              })
            : null
        ]
      }),
      jsx(sdk.PanelSectionLabel, { children: 'AUTHOR AND RIGHTS' }),
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(PackReviewLine, {
            label: 'Author / attribution',
            value: `${(manifest.contributors || []).map((person) => `${person.name} (${person.role})`).join(', ') || 'not recorded'} — ${manifest.attribution}`
          }),
          jsx(PackReviewLine, {
            label: 'License',
            value: `${manifest.license.id} · redistribution ${manifest.license.redistribution}${manifest.license.note ? ` · ${manifest.license.note}` : ''}`
          }),
          jsx(PackReviewLine, {
            label: 'Locale / level',
            value: `${manifest.locale || 'not stated'}${manifest.level_label ? ` · ${manifest.level_label}` : ''}`
          })
        ]
      }),
      jsx(sdk.PanelSectionLabel, { children: 'INTEGRITY AND SIZE' }),
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(PackReviewLine, {
            label: 'Content hash',
            value: jsx('code', { className: 'text-[11px]', children: manifest.content_hash })
          }),
          jsx(PackReviewLine, {
            label: 'Files',
            value: `${preview.integrity.file_count} file(s) · ${bytesLabel(preview.integrity.expanded_bytes)} expanded`
          }),
          jsx(PackReviewLine, {
            label: 'Hashes match the manifest',
            value: preview.integrity.hashes_match ? 'yes' : 'no — this import would be refused'
          })
        ]
      }),
      jsx(sdk.PanelSectionLabel, { children: 'TRUST, KEPT SEPARATE' }),
      jsxs('div', {
        className: 'flex flex-col gap-1.5',
        children: labels.length
          ? labels.map((label) =>
              jsxs(
                'div',
                {
                  className: 'flex flex-col',
                  children: [
                    jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: label.replaceAll('_', ' ') }),
                    jsx('div', { className: 'mt-0.5 text-xs text-(--ui-text-tertiary)', children: TRUST_COPY[label] || '' })
                  ]
                },
                label
              )
            )
          : jsx('div', { className: 'text-xs text-(--ui-text-tertiary)', children: 'No trust label was recorded. That is not a pass.' })
      }),
      labels.includes('human_review_recorded')
        ? null
        : jsx('div', {
            className: 'text-xs text-(--ui-text-tertiary)',
            children:
              'No human review is recorded for this pack. Passing automated checks is not a claim that the content is true.'
          }),
      manifest.content_notes && manifest.content_notes.length
        ? jsxs('div', {
            className: 'flex flex-col',
            children: [
              jsx(sdk.PanelSectionLabel, { children: 'CONTENT NOTES' }),
              ...manifest.content_notes.map((note, index) =>
                jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-tertiary)', children: note }, `note-${index}`)
              )
            ]
          })
        : null,
      manifest.safety_notes && manifest.safety_notes.length
        ? jsxs('div', {
            className: 'flex flex-col',
            children: [
              jsx(sdk.PanelSectionLabel, { children: 'SAFETY NOTES' }),
              ...manifest.safety_notes.map((note, index) =>
                jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-tertiary)', children: note }, `safety-${index}`)
              )
            ]
          })
        : null,
      jsx(sdk.PanelSectionLabel, { children: `OUTCOMES (${objectives.length})` }),
      jsx('div', {
        className: 'flex flex-col',
        children: objectives.map((objective) =>
          jsxs(
            'div',
            {
              className: 'border-b border-(--ui-stroke-tertiary) py-1.5 last:border-b-0',
              children: [
                jsxs('div', {
                  className: 'flex flex-wrap items-baseline gap-2',
                  children: [
                    jsx('span', { className: 'text-xs font-medium', children: `${objective.ordinal}. ${objective.title}` }),
                    jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: objective.evidence_target }),
                    jsx(sdk.Badge, {
                      size: 'xs',
                      variant: 'outline',
                      children: `${(objective.checks || []).length} check(s)`
                    })
                  ]
                }),
                jsx('div', { className: 'mt-0.5 text-xs text-(--ui-text-tertiary)', children: (objective.evidence_criteria || []).join(' · ') })
              ]
            },
            objective.objective_id
          )
        )
      }),
      sources.length
        ? jsxs('div', {
            className: 'flex flex-col',
            children: [
              jsx(sdk.PanelSectionLabel, { children: `SOURCES AND SUPPORT (${sources.length})` }),
              ...sources.map((source) =>
                jsxs(
                  'div',
                  {
                    className: 'border-b border-(--ui-stroke-tertiary) py-1.5 last:border-b-0',
                    children: [
                      jsx('div', { className: 'text-xs', children: source.title }),
                      jsxs('div', {
                        className: 'mt-0.5 flex flex-wrap items-center gap-2 text-xs text-(--ui-text-tertiary)',
                        children: [
                          jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: source.support_status || 'unassessed' }),
                          jsx('span', { children: source.publisher || source.source_type }),
                          jsx('span', { children: source.bundled ? 'bundled' : 'linked, not bundled' }),
                          source.url ? jsx('code', { className: 'break-all text-[10px]', children: source.url }) : null
                        ]
                      })
                    ]
                  },
                  source.source_id
                )
              )
            ]
          })
        : null,
      jsx(sdk.PanelSectionLabel, { children: `FILES (${files.length})` }),
      jsxs('div', {
        className: 'flex flex-col',
        children: files.map((file) =>
          jsxs(
            'div',
            {
              className: 'flex flex-wrap items-baseline justify-between gap-2 border-b border-(--ui-stroke-tertiary) py-1.5 last:border-b-0',
              children: [
                jsx('div', { className: 'min-w-0 break-all text-xs', children: file.path }),
                jsxs('div', {
                  className: 'flex shrink-0 items-center gap-2 text-xs text-(--ui-text-tertiary)',
                  children: [
                    jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: file.role }),
                    jsx('span', { children: file.mime }),
                    jsx('span', { children: bytesLabel(file.bytes) })
                  ]
                })
              ]
            },
            file.path
          )
        )
      })
    ]
  })
}

function PackImportFlow({ implemented, onCancel, onImported }) {
  const intake = usePackIntake(Boolean(implemented && implemented.has('pack.preview')))
  const [step, setStep] = useState('choose')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [staged, setStaged] = useState(null)
  const [preview, setPreview] = useState(null)
  const [folder, setFolder] = useState(null)
  const [entries, setEntries] = useState([])
  const [result, setResult] = useState(null)

  const libraryKey = JSON.stringify({ filter: 'all', limit: 50, sort: 'title' })
  const library = useRpcQuery(
    'library.list',
    { filter: 'all', limit: 50, sort: 'title' },
    libraryKey,
    backendSupports('library.list')
  )
  const installedRows = library.data && Array.isArray(library.data.items) ? library.data.items : []

  const files = pluginContext && pluginContext.files

  const chooseFolder = useCallback(async () => {
    if (!files || typeof files.requestFolder !== 'function') {
      setError({ message: 'This Hermes Desktop build has no file door, so a pack archive cannot be granted.' })
      return
    }
    setBusy(true)
    setError(null)
    try {
      const picked = await files.requestFolder()
      if (!picked || !picked.ok) {
        setError({ message: (picked && picked.message) || 'The folder picker did not return a folder.' })
        return
      }
      if (!picked.folder) return
      const listing = await files.list(picked.folder.id)
      if (!listing || !listing.ok) {
        setError({ message: (listing && listing.message) || 'The folder could not be read.' })
        return
      }
      setFolder(picked.folder)
      setEntries((listing.entries || []).filter((entry) => !entry.isDirectory && /\.zip$/i.test(entry.name)))
    } catch (failure) {
      setError({ message: describeError(failure) })
    } finally {
      setBusy(false)
    }
  }, [files])

  const grantAndPreview = useCallback(
    async (entry) => {
      setBusy(true)
      setError(null)
      try {
        if (!folder) throw new Error('Choose a folder first.')
        const path = `${folder.path.replace(/\/$/, '')}/${entry.path}`
        const granted = await rest('/packs/grant', { method: 'POST', body: { path } })
        if (!granted || !granted.ok || !granted.staged_id) {
          throw new Error((granted && granted.message) || 'The backend did not mint a staged pack.')
        }
        setStaged(granted.staged_id)
        const response = await rpc('pack.preview', { staged_id: granted.staged_id })
        if (!response.ok) throw new Error(`${response.error.code}: ${describeError(response.error)}`)
        cachePreview(response.result.manifest)
        setPreview(response.result)
        setStep('review')
      } catch (failure) {
        setError({ message: describeError(failure) })
      } finally {
        setBusy(false)
      }
    },
    [folder]
  )

  const runImport = useCallback(
    async (mode) => {
      if (!staged) return
      setBusy(true)
      setError(null)
      try {
        const response = await rpc(
          'pack.import',
          { staged_id: staged, mode },
          { idempotencyKey: `cb-pack-import-${staged}-${mode}` }
        )
        if (!response.ok) throw new Error(`${response.error.code}: ${describeError(response.error)}`)
        setResult(response.result)
        setStep('done')
      } catch (failure) {
        setError({ message: describeError(failure) })
      } finally {
        setBusy(false)
      }
    },
    [staged]
  )

  const existing = installedRows.filter(
    (row) => preview && (row.provenance || {}).pack_id === preview.manifest.pack_id
  )
  const parentPack = Boolean(preview && preview.manifest.recipe === 'parent')

  let body
  if (intake.status === 'loading') {
    body = jsx('div', { className: 'py-8', children: jsx(sdk.Loader, { label: 'Asking the host how packs are granted' }) })
  } else if (intake.status === 'unsupported') {
    body = jsx(EmptyState, {
      title: 'This backend build cannot receive a local pack',
      description:
        'A pack is untrusted data, so a filesystem path never travels over the wire. The host must mint a local ' +
        'file grant and the backend must expose it; this profile’s backend does not, so no picker is shown and ' +
        'nothing here pretends to import.'
    })
  } else if (step === 'choose') {
    body = jsxs('div', {
      className: 'flex flex-col gap-3',
      children: [
        jsxs('div', {
          className: 'flex flex-col gap-1',
          children: [
            jsx('div', { className: 'text-sm font-medium', children: 'Choose a pack archive' }),
            jsx('div', {
              className: 'max-w-prose text-xs text-(--ui-text-tertiary)',
              children:
                'Pick the folder that holds the .zip a pack arrived in. Coursebook reads it in a staging area, ' +
                'checks every file and hash, and shows the review below before anything is adopted.'
            })
          ]
        }),
        jsxs('div', {
          className: 'flex flex-wrap items-center gap-2',
          children: [
            jsx(sdk.Button, {
              disabled: busy || !files,
              onClick: chooseFolder,
              size: 'sm',
              variant: 'default',
              children: folder ? 'Choose another folder' : 'Choose folder…'
            }),
            folder ? jsx('span', { className: 'text-xs text-(--ui-text-tertiary)', children: folder.name }) : null,
            jsx(sdk.Button, { onClick: onCancel, size: 'sm', variant: 'secondary', children: 'Cancel' })
          ]
        }),
        folder && entries.length === 0
          ? jsx('div', { className: 'text-xs text-(--ui-text-tertiary)', children: 'No .zip archive in that folder.' })
          : null,
        entries.length
          ? jsxs('div', {
              className: 'flex flex-col',
              children: entries.map((entry) =>
                jsxs(
                  'div',
                  {
                    className: 'flex items-center justify-between gap-3 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
                    children: [
                      jsx('span', { className: 'min-w-0 break-all text-xs', children: entry.path }),
                      jsx(sdk.Button, {
                        disabled: busy,
                        onClick: () => grantAndPreview(entry),
                        size: 'sm',
                        variant: 'secondary',
                        children: 'Review'
                      })
                    ]
                  },
                  entry.path
                )
              )
            })
          : null
      ]
    })
  } else if (step === 'review') {
    body = jsxs('div', {
      className: 'flex flex-col gap-4',
      children: [
        jsx(sdk.Button, { className: 'self-start', onClick: () => setStep('choose'), size: 'sm', variant: 'text', children: 'Choose a different file' }),
        jsx(PackPreview, { existing, preview }),
        parentPack
          ? jsx('div', {
              className: 'rounded border border-(--ui-stroke-secondary) p-3 text-xs leading-relaxed',
              children:
                'This is a parent blueprint. Importing it creates a Parent Studio lesson plan for an adult to teach ' +
                'from. Its checks are observations, never graded child answers, and the recipe cannot be changed here.'
            })
          : null,
        jsx(sdk.Button, {
          onClick: () => setStep('mode'),
          size: 'sm',
          variant: 'default',
          children: parentPack ? 'Continue to Parent Studio import' : 'Continue'
        })
      ]
    })
  } else if (step === 'mode') {
    body = jsxs('div', {
      className: 'flex flex-col gap-4',
      children: [
        jsx('div', { className: 'text-sm font-medium', children: 'Resume or start fresh' }),
        jsx('div', {
          className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-tertiary)',
          children:
            'The pack content is immutable and shared. The choice is about progress only: resume continues the ' +
            'classroom already on this profile, fresh starts a new course with its own evidence.'
        }),
        existing.length
          ? jsx(sdk.Button, {
              disabled: busy,
              onClick: () => runImport('resume'),
              variant: 'secondary',
              children: `Resume the existing classroom (${existing.length} on this profile)`
            })
          : jsx('div', {
              className: 'text-xs text-(--ui-text-tertiary)',
              children: 'No classroom for this pack is on this profile yet, so there is nothing to resume.'
            }),
        jsx(sdk.Button, {
          disabled: busy,
          onClick: () => runImport('fresh'),
          variant: 'default',
          children: existing.length ? 'Start fresh progress' : 'Import and start learning'
        }),
        jsx(sdk.Button, { onClick: () => setStep('review'), size: 'sm', variant: 'text', children: 'Back to the review' })
      ]
    })
  } else {
    const parentResult = parentPack
    body = jsxs('div', {
      className: 'flex flex-col gap-3',
      children: [
        jsx('div', { className: 'text-sm font-medium', children: parentResult ? 'Blueprint imported into Parent Studio' : 'Pack imported' }),
        jsxs('div', {
          className: 'flex flex-col',
          children: [
            jsx(PackReviewLine, { label: 'Pack', value: `${result.pack_id}` }),
            jsx(PackReviewLine, { label: 'Course', value: result.course_id }),
            jsx(PackReviewLine, { label: 'Enrollment', value: result.enrollment_id || 'none' })
          ]
        }),
        jsx('div', {
          className: 'text-xs text-(--ui-text-tertiary)',
          children: parentResult
            ? 'It appears under Parent Studio with the parent guide and answer guide; learner pages carry no answers.'
            : 'It appears in Courses and Library. Lesson pages are the pack’s own text, not a rephrasing.'
        }),
        jsx(sdk.Button, { onClick: onImported, size: 'sm', variant: 'default', children: 'Back to the library' })
      ]
    })
  }

  return jsxs('div', {
    className: 'flex flex-col gap-3',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between',
        children: [
          jsx('div', { className: 'text-sm font-semibold', children: 'Import a pack' }),
          jsx(sdk.Button, { onClick: onCancel, size: 'sm', variant: 'text', children: 'Close' })
        ]
      }),
      busy ? jsx(sdk.Loader, { label: 'Working on the pack' }) : null,
      error
        ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: error.code ? `${error.code}: ${error.message}` : error.message })
        : null,
      body
    ]
  })
}

/** Export review and artifact facts. The exported bytes are the reviewed bytes. */
function PackExportPanel({ row, onClose }) {
  const key = row.provenance ? `${row.provenance.pack_id}@${row.provenance.pack_version}` : ''
  const manifest = key ? previewCache.get(key) : null
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [exported, setExported] = useState(null)
  const [artifact, setArtifact] = useState(null)

  const run = useCallback(async () => {
    if (!manifest) return
    setBusy(true)
    setError(null)
    try {
      const response = await rpc('pack.export', {
        enrollment_id: row.enrollment_id,
        options: { expected_content_hash: manifest.content_hash }
      })
      if (!response.ok) throw new Error(`${response.error.code}: ${describeError(response.error)}`)
      if (response.result.content_hash !== manifest.content_hash) {
        throw new Error('The backend exported a different hash than the one reviewed. Nothing should be shared from this.')
      }
      setExported(response.result)
      const facts = await rpc('artifact.get', { artifact_id: response.result.artifact_id })
      if (facts.ok) setArtifact(facts.result)
    } catch (failure) {
      setError({ message: describeError(failure) })
    } finally {
      setBusy(false)
    }
  }, [manifest, row.enrollment_id])

  if (!manifest) {
    return jsxs('div', {
      className: 'flex flex-col gap-2',
      children: [
        jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-tertiary)', children:
          'The file list for this pack was not reviewed in this session. A pack is exported only against the ' +
          'content hash that was shown at review, so this build will not export blind. Re-import the same archive ' +
          'to review it again; the installed content is immutable, so nothing is duplicated.' }),
        jsx(sdk.Button, { onClick: onClose, size: 'sm', variant: 'secondary', children: 'Close' })
      ]
    })
  }

  return jsxs('div', {
    className: 'flex flex-col gap-3',
    children: [
      jsx('div', { className: 'text-sm font-semibold', children: 'Review the export' }),
      jsx('div', {
        className: 'text-xs text-(--ui-text-tertiary)',
        children:
          'Every file below is included. Transcripts, attempts, notebook notes, evidence and provider settings ' +
          'are not part of a pack and are excluded by construction.'
      }),
      jsxs('div', {
        className: 'flex flex-col',
        children: (manifest.files || []).map((file) =>
          jsxs(
            'div',
            {
              className: 'flex flex-wrap items-baseline justify-between gap-2 border-b border-(--ui-stroke-tertiary) py-1.5 last:border-b-0',
              children: [
                jsx('div', { className: 'min-w-0 break-all text-xs', children: file.path }),
                jsxs('div', {
                  className: 'flex shrink-0 items-center gap-2 text-xs text-(--ui-text-tertiary)',
                  children: [
                    jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: file.role }),
                    jsx('span', { children: bytesLabel(file.bytes) })
                  ]
                })
              ]
            },
            file.path
          )
        )
      }),
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(PackReviewLine, { label: 'Files', value: String((manifest.files || []).length) }),
          jsx(PackReviewLine, { label: 'Content hash', value: jsx('code', { className: 'text-[11px]', children: manifest.content_hash }) })
        ]
      }),
      jsx(sdk.Button, {
        disabled: busy || !confirmed,
        onClick: run,
        size: 'sm',
        variant: 'default',
        children: 'Export exactly these files'
      }),
      jsxs('label', {
        className: 'flex items-start gap-2 text-xs text-(--ui-text-secondary)',
        children: [
          jsx('input', { checked: confirmed, onChange: (event) => setConfirmed(Boolean(event.target.checked)), type: 'checkbox' }),
          jsx('span', { children: 'I reviewed these files and the licence above; export them under the same identity.' })
        ]
      }),
      error ? jsx('div', { className: 'text-xs', children: error.message }) : null,
      exported
        ? jsxs('div', {
            className: 'flex flex-col',
            children: [
              jsx(sdk.PanelSectionLabel, { children: 'EXPORTED' }),
              jsx(PackReviewLine, { label: 'Content hash', value: jsx('code', { className: 'text-[11px]', children: exported.content_hash }) }),
              jsx(PackReviewLine, { label: 'Matches the reviewed hash', value: 'yes' }),
              jsx(PackReviewLine, { label: 'Files', value: String(exported.file_count) }),
              jsx(PackReviewLine, { label: 'Archive bytes', value: bytesLabel(exported.bytes) }),
              artifact
                ? jsxs('div', {
                    className: 'flex flex-col',
                    children: [
                      jsx(PackReviewLine, { label: 'Artifact', value: artifact.artifact_id }),
                      jsx(PackReviewLine, {
                        label: 'File hash',
                        value: jsx('code', { className: 'text-[11px]', children: artifact.content_hash })
                      }),
                      jsx(PackReviewLine, { label: 'Download handle', value: jsx('code', { className: 'text-[11px]', children: artifact.download.handle }) }),
                      jsx(PackReviewLine, {
                        label: 'Download',
                        value: artifact.download.requires_session
                          ? 'session-bound, expiring — served by this host’s artifact route'
                          : 'host route'
                      }),
                      jsx('a', {
                        className: 'mt-1 self-start rounded-md border border-(--ui-stroke-tertiary) px-3 py-1 text-xs',
                        download: `${manifest.pack_id}-${manifest.pack_version}.zip`,
                        href: artifact.download.url,
                        children: 'Download archive'
                      }),
                      jsx('div', {
                        className: 'mt-1 text-xs leading-relaxed text-(--ui-text-tertiary)',
                        children:
                          'The link is the host route the backend named: the session is checked there, the handle ' +
                          'expires in five minutes, and a filesystem path never leaves the backend. The file you ' +
                          'receive is byte-identical to the reviewed hash above.'
                      })
                    ]
                  })
                : null
            ]
          })
        : null,
      jsx(sdk.Button, { onClick: onClose, size: 'sm', variant: 'text', children: 'Close' })
    ]
  })
}

/** Pack tombstone: preview the scope, then freeze. Evidence is never cascaded away. */
function PackDeletePanel({ row, onClose, onDeleted }) {
  const [scope, setScope] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const packId = row.provenance && row.provenance.pack_id

  const preview = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      const response = await rpc(
        'pack.delete',
        { pack_id: packId, dry_run: true },
        { expectedRevision: 0, idempotencyKey: `cb-pack-delete-preview-${packId}` }
      )
      if (!response.ok) throw new Error(`${response.error.code}: ${describeError(response.error)}`)
      setScope(response.result.data_scope)
    } catch (failure) {
      setError({ message: describeError(failure) })
    } finally {
      setBusy(false)
    }
  }, [packId])

  const remove = useCallback(async () => {
    if (!scope) return
    setBusy(true)
    setError(null)
    try {
      const response = await rpc(
        'pack.delete',
        { pack_id: packId, dry_run: false, data_scope_hash: scope.scope_hash },
        { expectedRevision: scopeRevision, idempotencyKey: `cb-pack-delete-${packId}-${scope.scope_hash.slice(7, 19)}` }
      )
      if (!response.ok) throw new Error(`${response.error.code}: ${describeError(response.error)}`)
      onDeleted()
    } catch (failure) {
      setError({ message: describeError(failure) })
    } finally {
      setBusy(false)
    }
  }, [packId, scope, onDeleted])

  // The kernel fences pack.delete on the pack record's revision; a fresh install is 0.
  const scopeRevision = 0

  return jsxs('div', {
    className: 'flex flex-col gap-3',
    children: [
      jsx('div', { className: 'text-sm font-semibold', children: 'Remove this pack' }),
      jsx('div', {
        className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-tertiary)',
        children:
          'Deleting a pack freezes its content so it cannot be imported again. Courses, attempts, notebook notes ' +
          'and earlier exports are kept, so evidence does not disappear with the pack.'
      }),
      !scope
        ? jsx(sdk.Button, { disabled: busy, onClick: preview, size: 'sm', variant: 'secondary', children: 'Preview what stays and what goes' })
        : jsxs('div', {
            className: 'flex flex-col',
            children: [
              jsx(PackReviewLine, { label: 'Courses from this pack', value: String((scope.counts || {}).courses || 0) }),
              jsx(PackReviewLine, { label: 'Enrollments', value: String((scope.counts || {}).enrollments || 0) }),
              jsx(PackReviewLine, { label: 'Artifacts', value: String((scope.counts || {}).artifacts || 0) }),
              jsx(PackReviewLine, { label: 'Evidence kept', value: (scope.preserved || {}).evidence ? 'yes' : 'no' }),
              jsx(PackReviewLine, { label: 'Attempts kept', value: (scope.preserved || {}).attempts ? 'yes' : 'no' }),
              jsx(PackReviewLine, { label: 'Notebook notes kept', value: (scope.preserved || {}).notebook_entries ? 'yes' : 'no' }),
              jsx('div', { className: 'mt-2 text-xs text-(--ui-text-tertiary)', children: scope.summary })
            ]
          }),
      error ? jsx('div', { className: 'text-xs', children: error.message }) : null,
      scope
        ? jsx(sdk.Button, { disabled: busy, onClick: remove, size: 'sm', variant: 'default', children: 'Freeze this pack' })
        : null,
      jsx(sdk.Button, { onClick: onClose, size: 'sm', variant: 'text', children: 'Close' })
    ]
  })
}

function CourseMenu({ row, supports, onArchive, onDelete }) {
  const archived = row.enrollment_status === 'archived' || row.course_status === 'archived'
  const items = []
  if (supports('enrollment.update')) {
    items.push(
      jsx(
        sdk.DropdownMenuItem,
        {
          onSelect: () => onArchive(row, archived ? 'unarchive' : 'archive'),
          children: archived ? 'Unarchive course' : 'Archive course'
        },
        'archive'
      )
    )
  }
  if (supports('enrollment.delete')) {
    items.push(
      jsx(
        sdk.DropdownMenuItem,
        {
          onSelect: () => onDelete(row),
          variant: 'destructive',
          children: 'Delete enrollment…'
        },
        'delete'
      )
    )
  }
  if (items.length === 0) return null
  return jsxs(sdk.DropdownMenu, {
    children: [
      jsx(sdk.DropdownMenuTrigger, {
        asChild: true,
        children: jsx(sdk.Button, {
          'aria-label': `Actions for ${row.title}`,
          size: 'icon-sm',
          variant: 'ghost',
          children: jsx(sdk.Codicon, { name: 'kebab-vertical', size: '0.875rem' })
        })
      }),
      jsx(sdk.DropdownMenuContent, { align: 'end', children: items })
    ]
  })
}

function CourseRow({ row, implemented, onResume, onArchive, onDelete, onOpen }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const next = row.next_step || {}
  const canResume = next.kind === 'resume_lesson' && supports('binding.get')
  const warning = WARNING_COPY[row.warning]
  return jsx(sdk.ListRow, {
    title: jsxs('span', {
      className: 'flex min-w-0 flex-wrap items-center gap-2',
      children: [
        jsx('span', { className: 'min-w-0 break-words', children: row.title }),
        jsx(sdk.Badge, { variant: 'muted', size: 'xs', children: RECIPE_COPY[row.recipe] ? RECIPE_COPY[row.recipe].title : row.recipe }),
        warning ? jsx(WarningBadge, { warning: row.warning }) : null
      ]
    }),
    description: next.label
      ? jsx('span', { children: next.label })
      : jsx('span', { children: 'No next step recorded' }),
    below: jsxs('div', {
      className: 'flex flex-col',
      children: [
        jsx(EvidenceLine, { summary: row.evidence_summary }),
        warning
          ? jsx('div', {
              className: 'mt-1 max-w-prose text-xs text-(--ui-text-tertiary)',
              children: warning.detail
            })
          : null,
        row.provenance && row.provenance.pack_id
          ? jsx('div', {
              className: 'mt-1 text-xs text-(--ui-text-tertiary)',
              children: `From ${row.provenance.source === 'bundled' ? 'a bundled pack' : row.provenance.source === 'community' ? 'a community pack' : 'a local pack'}${
                row.provenance.pack_version ? ` · v${row.provenance.pack_version}` : ''
              }`
            })
          : null
      ]
    }),
    action: jsxs('div', {
      className: 'flex items-center gap-1',
      children: [
        onOpen
          ? jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: () => onOpen(row), children: 'Open' })
          : null,
        canResume
          ? jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: () => onResume(row), children: 'Resume lesson' })
          : null,
        jsx(CourseMenu, { row, supports, onArchive, onDelete })
      ]
    })
  })
}

function CoursesView({ implemented, onStartCreate, createOpen, onOpen }) {
  const [filter, setFilter] = useState('all')
  const [searchInput, setSearchInput] = useState('')
  const [query, setQuery] = useState('')

  useEffect(() => {
    if (!pluginContext) return undefined
    const timer = pluginContext.setTimeout(() => setQuery(searchInput.trim()), 250)
    return timer
  }, [searchInput])

  const payload = { filter, limit: 50, sort: 'recent' }
  if (query) payload.query = query
  const key = JSON.stringify(payload)
  const { status, data, error, stale, reload } = useRpcQuery(
    'library.list',
    payload,
    key,
    !createOpen && backendSupports('library.list')
  )

  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleteScope, setDeleteScope] = useState(null)
  const [actionError, setActionError] = useState(null)

  const onResume = useCallback(async (row) => {
    const response = await loadBinding({ enrollmentId: row.enrollment_id })
    if (!response || !response.ok) {
      host.notify({
        kind: 'warning',
        message: response && response.error ? `${response.error.code}: ${describeError(response.error)}` : 'Could not read this course’s binding.'
      })
      return
    }
    const outcome = await resumeBoundSession(response.result.binding)
    if (!outcome.ok) host.notify({ kind: 'warning', message: outcome.message })
  }, [])

  const onArchive = useCallback(
    async (row, action) => {
      const response = await rpc(
        'enrollment.update',
        { enrollment_id: row.enrollment_id, action },
        { expectedRevision: row.revision }
      )
      if (!response.ok) {
        setActionError(`${response.error.code}: ${describeError(response.error)}`)
        return
      }
      setActionError(null)
      reload()
    },
    [reload]
  )

  const onDelete = useCallback(async (row) => {
    const response = await rpc('enrollment.delete', { enrollment_id: row.enrollment_id, dry_run: true })
    if (!response.ok) {
      host.notify({
        kind: 'warning',
        message: `${response.error.code}: ${describeError(response.error)}`
      })
      return
    }
    setPendingDelete(row)
    setDeleteScope(response.result.data_scope)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete || !deleteScope) return
    const response = await rpc(
      'enrollment.delete',
      {
        enrollment_id: pendingDelete.enrollment_id,
        dry_run: false,
        data_scope_hash: deleteScope.scope_hash
      },
      {
        idempotencyKey: `cb-delete-${pendingDelete.enrollment_id}-${deleteScope.scope_id}`,
        expectedRevision: pendingDelete.revision
      }
    )
    if (!response.ok) {
      throw new Error(`${response.error.code}: ${describeError(response.error)}`)
    }
    setPendingDelete(null)
    setDeleteScope(null)
    reload()
  }, [pendingDelete, deleteScope, reload])

  const rows = data && Array.isArray(data.items) ? data.items : []
  const noCourses = data && Number(data.total || 0) === 0
  // A search is a filter too: with rows present on the profile, an empty result set caused by the
  // search box must never be presented as first-run. `applied_filter` alone missed that case.
  const filteredEmpty =
    noCourses && (Boolean(query) || Boolean(data.applied_filter && data.applied_filter !== 'all'))

  let body
  if (status === 'idle') {
    body = null
  } else if (status === 'loading' && !data) {
    body = jsx('div', { className: 'py-10', children: jsx(sdk.Loader, { label: 'Reading your courses' }) })
  } else if (status === 'error' && !data) {
    body = jsx('div', {
      className: 'mx-auto w-full max-w-xl py-6',
      children: jsxs(sdk.ErrorState, {
        title: 'Your courses could not be read',
        description: `${error && error.code ? error.code + ': ' : ''}${describeError(error)} This page will not show an empty list in place of a failed read.`,
        children: jsxs('div', {
          className: 'flex flex-wrap items-center justify-center gap-2',
          children: [
            jsx(sdk.Button, { variant: 'default', onClick: reload, children: 'Try again' }),
            jsx(sdk.Button, { variant: 'secondary', onClick: openCapabilities, children: 'Open Capabilities' })
          ]
        })
      })
    })
  } else if (noCourses) {
    body = filteredEmpty
      ? jsx('div', {
          className: 'py-6',
          children: jsxs('div', {
            className: 'mx-auto flex w-full max-w-xl flex-col items-center gap-3',
            children: [
              jsx(EmptyState, {
                title: query ? 'No courses match your search' : 'No courses match this filter',
                description: query
                  ? 'Your courses are still here; the search just excludes them right now.'
                  : 'Your courses are still here; this filter just excludes them right now.'
              }),
              jsx(sdk.Button, {
                variant: 'secondary',
                onClick: () => {
                  setFilter('all')
                  setSearchInput('')
                },
                children: query ? 'Clear search' : 'Clear filter'
              })
            ]
          })
        })
      : jsx(FirstRun, { implemented, onCreate: onStartCreate })
  } else {
    body = jsxs('div', {
      className: 'flex flex-col',
      children: [
        stale
          ? jsxs('div', {
              className: 'mb-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-(--ui-stroke-tertiary) px-3 py-2',
              children: [
                jsx('div', {
                  className: 'text-xs text-(--ui-text-tertiary)',
                  children: 'Reconnecting. Showing the last courses that were read; changes are paused.'
                }),
                jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: reload, children: 'Retry now' })
              ]
            })
          : null,
        actionError ? jsx(ErrorLine, { error: { message: actionError } }) : null,
        rows.some((row) => Number((row.evidence_summary || {}).review_due || 0) > 0)
          ? jsxs('div', {
              className: 'mb-2 flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) pb-2',
              children: [
                jsx(sdk.PanelSectionLabel, { children: 'REVIEW DUE' }),
                rows
                  .filter((row) => Number((row.evidence_summary || {}).review_due || 0) > 0)
                  .map((row) =>
                    jsxs(
                      'div',
                      {
                        className: 'flex flex-wrap items-center justify-between gap-2 text-xs',
                        children: [
                          jsx('span', {
                            className: 'min-w-0 break-words text-(--ui-text-secondary)',
                            children: `${row.title} · ${Number(row.evidence_summary.review_due)} due`
                          }),
                          jsx(sdk.Button, {
                            variant: 'text',
                            size: 'sm',
                            onClick: () => onOpen(row),
                            children: 'Review'
                          })
                        ]
                      },
                      `review-${row.enrollment_id}`
                    )
                  )
              ]
            })
          : null,
        rows.map((row) =>
          jsx(
            CourseRow,
            {
              row,
              implemented,
              onResume,
              onArchive,
              onDelete,
              onOpen
            },
            row.enrollment_id
          )
        ),
        Number(data.total || 0) > rows.length
          ? jsx('div', {
              className: 'pt-3 text-xs text-(--ui-text-tertiary)',
              children: `${rows.length} of ${data.total} courses shown. Narrow the filter to see the rest.`
            })
          : null
      ]
    })
  }

  const toolsDisabled = createOpen
  return jsxs('div', {
    className: 'flex flex-col',
    children: [
      jsxs('div', {
        className: 'mb-2 flex flex-wrap items-center justify-between gap-2',
        children: [
          jsx(sdk.SearchField, {
            'aria-label': 'Search courses',
            containerClassName: 'max-w-sm min-w-0 flex-1',
            onChange: setSearchInput,
            placeholder: 'Search courses',
            value: searchInput
          }),
          jsx(sdk.SegmentedControl, {
            onChange: setFilter,
            options: FILTERS,
            sizing: 'content',
            value: filter,
            disabled: toolsDisabled
          })
        ]
      }),
      body,
      jsx(sdk.ConfirmDialog, {
        confirmLabel: 'Delete enrollment',
        description: pendingDelete
          ? `This deletes the learning data for “${pendingDelete.title}” on this profile. The course content and the pack it came from are kept.`
          : '',
        destructive: true,
        onClose: () => {
          setPendingDelete(null)
          setDeleteScope(null)
        },
        onConfirm: confirmDelete,
        open: Boolean(pendingDelete),
        title: 'Delete this enrollment?',
        children: deleteScope
          ? jsxs('div', {
              className: 'flex flex-col',
              children: [
                jsx(StatusRow, { label: 'Attempts', value: String((deleteScope.counts || {}).attempts || 0) }),
                jsx(StatusRow, { label: 'Notebook entries', value: String((deleteScope.counts || {}).notebook_entries || 0) }),
                jsx(StatusRow, { label: 'Lesson runs', value: String((deleteScope.counts || {}).lesson_runs || 0) }),
                jsx(StatusRow, { label: 'Jobs', value: String((deleteScope.counts || {}).jobs || 0) }),
                jsx(StatusRow, { label: 'Course and plan kept', value: (deleteScope.preserved || {}).course ? 'yes' : 'no' }),
                jsx(StatusRow, { label: 'Hermes transcripts kept', value: (deleteScope.preserved || {}).hermes_transcripts ? 'yes' : 'no' })
              ]
            })
          : null
      })
    ]
  })
}

function sourceLabel(source) {
  if (source === 'bundled') return 'Bundled'
  if (source === 'community') return 'Community'
  if (source === 'local') return 'Local pack'
  if (source === 'authored') return 'Authored here'
  return source || 'Unknown source'
}

function PackFacts({ row, implemented, onResume, onArchive, onDelete, onExportPack, onDeletePack, onBack, showBack }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const next = row.next_step || {}
  const warning = WARNING_COPY[row.warning]
  return jsxs('div', {
    className: 'flex min-w-0 flex-1 flex-col gap-3',
    children: [
      showBack
        ? jsx(sdk.Button, { className: 'self-start', onClick: onBack, size: 'sm', variant: 'text', children: 'All packs' })
        : null,
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx('h3', { className: 'text-sm font-semibold', children: row.title }),
          jsxs('div', {
            className: 'mt-1 flex flex-wrap items-center gap-2',
            children: [
              jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: sourceLabel(row.provenance && row.provenance.source) }),
              row.provenance && row.provenance.pack_id
                ? jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: row.provenance.pack_id })
                : null,
              row.provenance && row.provenance.pack_version
                ? jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: `v${row.provenance.pack_version}` })
                : null,
              warning ? jsx(WarningBadge, { warning: row.warning }) : null
            ]
          })
        ]
      }),
      jsx(sdk.PanelSectionLabel, { children: 'WHAT THE BACKEND RECORDED' }),
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(StatusRow, { label: 'Next step', value: next.label || '—' }),
          jsx(StatusRow, {
            label: 'Enrollment',
            value: row.enrollment_status,
            detail: `revision ${row.revision}`
          }),
          jsx(StatusRow, {
            label: 'Evidence',
            value: `${Number((row.evidence_summary || {}).independent || 0)} independent`,
            detail: `${Number((row.evidence_summary || {}).total_objectives || 0)} objectives · ${Number((row.evidence_summary || {}).review_due || 0)} due`
          }),
          jsx(StatusRow, {
            label: 'Last change',
            value: formatWhen(row.updated_at)
          })
        ]
      }),
      warning
        ? jsx('div', {
            className: 'text-xs text-(--ui-text-tertiary)',
            children: warning.detail
          })
        : null,
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2 pt-1',
        children: [
          next.kind === 'resume_lesson' && supports('binding.get')
            ? jsx(sdk.Button, { onClick: () => onResume(row), size: 'sm', variant: 'default', children: 'Resume lesson' })
            : null,
          supports('enrollment.update')
            ? jsx(sdk.Button, {
                onClick: () => onArchive(row, row.enrollment_status === 'archived' ? 'unarchive' : 'archive'),
                size: 'sm',
                variant: 'secondary',
                children: row.enrollment_status === 'archived' ? 'Unarchive' : 'Archive'
              })
            : null,
          supports('enrollment.delete')
            ? jsx(sdk.Button, { onClick: () => onDelete(row), size: 'sm', variant: 'secondary', children: 'Delete enrollment…' })
            : null,
          row.provenance && row.provenance.pack_id && supports('pack.export')
            ? jsx(sdk.Button, { onClick: () => onExportPack(row), size: 'sm', variant: 'secondary', children: 'Export pack…' })
            : null,
          row.provenance && row.provenance.pack_id && supports('pack.delete') && row.warning !== 'pack_frozen'
            ? jsx(sdk.Button, { onClick: () => onDeletePack(row), size: 'sm', variant: 'secondary', children: 'Remove pack…' })
            : null
        ]
      }),
      row.recipe === 'parent'
        ? jsx('div', {
            className: 'rounded border border-(--ui-stroke-secondary) p-2 text-xs leading-relaxed',
            children:
              'Parent Studio blueprint: the adult prepares and teaches from this plan. Checks are observations, ' +
              'not graded child answers, and this course is never offered as an adult graded course.'
          })
        : null,
      jsx('div', {
        className: 'mt-2 text-xs leading-relaxed text-(--ui-text-tertiary)',
        children:
          'Sources, rights, checks and file integrity come from the pack preview command. This build ' +
          'shows only what the backend recorded for this pack, so nothing here is inferred.'
      })
    ]
  })
}

function formatWhen(value) {
  if (!value) return 'not recorded'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value)
  return parsed.toLocaleString()
}

function LibraryView({ implemented, createOpen }) {
  const [view, setView] = useState('all')
  const [selected, setSelected] = useState(null)
  const [packPanel, setPackPanel] = useState(null)
  const [packPanelRow, setPackPanelRow] = useState(null)

  const payload = { filter: 'all', limit: 50, sort: 'title' }
  const key = JSON.stringify(payload)
  const { status, data, error, stale, reload } = useRpcQuery(
    'library.list',
    payload,
    key,
    !createOpen && backendSupports('library.list')
  )

  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleteScope, setDeleteScope] = useState(null)

  const onResume = useCallback(async (row) => {
    const response = await loadBinding({ enrollmentId: row.enrollment_id })
    if (!response || !response.ok) {
      host.notify({ kind: 'warning', message: 'Could not read this pack’s lesson binding.' })
      return
    }
    const outcome = await resumeBoundSession(response.result.binding)
    if (!outcome.ok) host.notify({ kind: 'warning', message: outcome.message })
  }, [])

  const onArchive = useCallback(
    async (row, action) => {
      const response = await rpc(
        'enrollment.update',
        { enrollment_id: row.enrollment_id, action },
        { expectedRevision: row.revision }
      )
      if (!response.ok) host.notify({ kind: 'warning', message: `${response.error.code}: ${describeError(response.error)}` })
      reload()
    },
    [reload]
  )

  const onDelete = useCallback(async (row) => {
    const response = await rpc('enrollment.delete', { enrollment_id: row.enrollment_id, dry_run: true })
    if (!response.ok) {
      host.notify({ kind: 'warning', message: `${response.error.code}: ${describeError(response.error)}` })
      return
    }
    setPendingDelete(row)
    setDeleteScope(response.result.data_scope)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete || !deleteScope) return
    const response = await rpc(
      'enrollment.delete',
      {
        enrollment_id: pendingDelete.enrollment_id,
        dry_run: false,
        data_scope_hash: deleteScope.scope_hash
      },
      {
        idempotencyKey: `cb-pack-delete-${pendingDelete.enrollment_id}-${deleteScope.scope_id}`,
        expectedRevision: pendingDelete.revision
      }
    )
    if (!response.ok) throw new Error(`${response.error.code}: ${describeError(response.error)}`)
    setPendingDelete(null)
    setDeleteScope(null)
    setSelected(null)
    reload()
  }, [pendingDelete, deleteScope, reload])

  const allRows = data && Array.isArray(data.items) ? data.items : []
  const rows = allRows.filter((row) => {
    const source = (row.provenance && row.provenance.source) || 'authored'
    if (view === 'bundled') return source === 'bundled'
    if (view === 'local') return source === 'local' || source === 'community'
    return true
  })

  const detailRow = selected ? allRows.find((row) => row.enrollment_id === selected) || null : null
  const narrowDetailOnly = Boolean(detailRow)

  let listBody
  if (status === 'loading' && !data) {
    listBody = jsx('div', { className: 'py-8', children: jsx(sdk.Loader, { label: 'Reading installed packs' }) })
  } else if (status === 'error' && !data) {
    listBody = jsxs('div', {
      className: 'flex flex-col gap-3 py-4',
      children: [
        jsx(EmptyState, {
          title: 'Installed packs could not be read',
          description: `${error && error.code ? error.code + ': ' : ''}${describeError(error)}`
        }),
        jsx(sdk.Button, { className: 'self-start', onClick: reload, size: 'sm', variant: 'secondary', children: 'Try again' })
      ]
    })
  } else if (rows.length === 0) {
    listBody = jsx(EmptyState, {
      title: view === 'bundled' ? 'No bundled pack is installed on this profile' : view === 'local' ? 'No local pack is installed' : 'No packs installed on this profile',
      description:
        'A pack appears here once it exists on this profile. Bundled packs ship with the Coursebook ' +
        'package; importing one needs the backend’s pack import command, which this build does not have.'
    })
  } else {
    listBody = jsxs('div', {
      className: 'flex flex-col',
      children: [
        stale
          ? jsx('div', {
              className: 'mb-2 text-xs text-(--ui-text-tertiary)',
              children: 'Reconnecting. Showing the last packs that were read.'
            })
          : null,
        rows.map((row) =>
          jsxs(
            'div',
            {
              className: 'flex items-center gap-1',
              children: [
                jsx(sdk.ListRow, {
                  action: null,
                  className: 'min-w-0 flex-1',
                  description: jsxs('span', {
                    className: 'flex flex-wrap items-center gap-2',
                    children: [
                      jsx('span', { children: sourceLabel(row.provenance && row.provenance.source) }),
                      row.provenance && row.provenance.pack_version
                        ? jsx('span', { children: `v${row.provenance.pack_version}` })
                        : null,
                      jsx('span', { children: `${Number((row.evidence_summary || {}).total_objectives || 0)} objectives` })
                    ]
                  }),
                  title: jsx('span', { className: 'break-words', children: row.title })
                }),
                jsx(sdk.Button, {
                  'aria-label': `Open ${row.title}`,
                  onClick: () => setSelected(row.enrollment_id),
                  size: 'sm',
                  variant: row.enrollment_id === selected ? 'secondary' : 'ghost',
                  children: 'Preview'
                })
              ]
            },
            row.enrollment_id
          )
        )
      ]
    })
  }

  return jsxs('div', {
    className: 'flex flex-col',
    children: [
      jsxs('div', {
        className: 'mb-2 flex flex-wrap items-center justify-between gap-2',
        children: [
          jsx('div', {
            className: 'max-w-prose text-xs text-(--ui-text-tertiary)',
            children: 'Packs installed on this profile, by where they came from. No marketplace ranking and no verified badge.'
          }),
          jsx(sdk.SegmentedControl, {
            onChange: setView,
            options: [
              { id: 'all', label: 'All' },
              { id: 'bundled', label: 'Bundled' },
              { id: 'local', label: 'Local' }
            ],
            sizing: 'content',
            value: view
          })
        ]
      }),
      jsxs('div', {
        className: 'flex flex-col gap-4 min-[47.5rem]:flex-row',
        children: [
          jsx('div', {
            className: `${narrowDetailOnly ? 'hidden min-[47.5rem]:flex' : 'flex'} min-w-0 flex-col min-[47.5rem]:w-72 min-[47.5rem]:shrink-0`,
            children: listBody
          }),
          detailRow
            ? jsx(PackFacts, {
                implemented,
                onArchive,
                onBack: () => setSelected(null),
                onDelete,
                onDeletePack: (row) => {
                  setPackPanelRow(row)
                  setPackPanel('delete')
                },
                onExportPack: (row) => {
                  setPackPanelRow(row)
                  setPackPanel('export')
                },
                onResume,
                row: detailRow,
                showBack: true
              })
            : jsx('div', {
                className: 'hidden min-[47.5rem]:flex min-w-0 flex-1 items-start',
                children: jsx(EmptyState, {
                  className: 'w-full',
                  title: 'Choose a pack to see what the backend recorded',
                  description: 'Preview shows the pack’s provenance, enrolment state and evidence summary — nothing inferred.'
                })
              })
        ]
      }),
      packPanel && packPanelRow
        ? jsxs('div', {
            className: 'mt-4 flex flex-col gap-3 border-t border-(--ui-stroke-tertiary) pt-3',
            children: [
              packPanel === 'export'
                ? jsx(PackExportPanel, { onClose: () => setPackPanel(null), row: packPanelRow })
                : jsx(PackDeletePanel, {
                    onClose: () => setPackPanel(null),
                    onDeleted: () => {
                      setPackPanel(null)
                      setSelected(null)
                      reload()
                    },
                    row: packPanelRow
                  })
            ]
          })
        : null,
      jsx(sdk.ConfirmDialog, {
        confirmLabel: 'Delete enrollment',
        description: pendingDelete
          ? `This deletes the learning data for “${pendingDelete.title}” on this profile. The pack content itself is kept.`
          : '',
        destructive: true,
        onClose: () => {
          setPendingDelete(null)
          setDeleteScope(null)
        },
        onConfirm: confirmDelete,
        open: Boolean(pendingDelete),
        title: 'Delete this enrollment?',
        children: deleteScope
          ? jsxs('div', {
              className: 'flex flex-col',
              children: [
                jsx(StatusRow, { label: 'Attempts', value: String((deleteScope.counts || {}).attempts || 0) }),
                jsx(StatusRow, { label: 'Notebook entries', value: String((deleteScope.counts || {}).notebook_entries || 0) }),
                jsx(StatusRow, { label: 'Lesson runs', value: String((deleteScope.counts || {}).lesson_runs || 0) }),
                jsx(StatusRow, { label: 'Pack provenance kept', value: (deleteScope.preserved || {}).pack_provenance ? 'yes' : 'no' })
              ]
            })
          : null
      })
    ]
  })
}

/** A compact staged create flow; every step is editable before the one mutation. */
function CreateCourseFlow({ onCancel, onCreated }) {
  const [step, setStep] = useState(1)
  const [goal, setGoal] = useState('')
  const [title, setTitle] = useState('')
  const [recipe, setRecipe] = useState('casual')
  const [dials, setDials] = useState({ pace: 'light', depth: 'survey', assessment: 'self_check', autonomy: 'guided' })
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const keyRef = useRef(null)

  const goalInvalid = step >= 1 && goal.trim().length === 0
  const canAdvance = goal.trim().length > 0 && title.trim().length > 0

  const submit = useCallback(async () => {
    if (submitting) return
    if (!keyRef.current) keyRef.current = `cb-course-create-${newOperationId('create')}`
    setSubmitting(true)
    setError(null)
    const response = await rpc(
      'course.create',
      {
        title: title.trim(),
        recipe,
        goal: goal.trim(),
        dials
      },
      { idempotencyKey: keyRef.current, expectedRevision: null }
    )
    if (!response.ok) {
      setSubmitting(false)
      setError(response.error)
      return
    }
    const enrollment = await rpc(
      'enrollment.create',
      { course_id: response.result.course_id, learner_label: title.trim() },
      { idempotencyKey: `${keyRef.current}-enroll`, expectedRevision: null }
    )
    setSubmitting(false)
    if (!enrollment.ok) {
      setError(enrollment.error)
      return
    }
    setResult({
      courseId: response.result.course_id,
      planId: response.result.plan_id,
      enrollmentId: enrollment.result.enrollment_id
    })
    onCreated()
  }, [dials, goal, onCreated, recipe, submitting, title])

  const onKeyDown = useCallback(
    (event) => {
      if (event.key !== 'Escape' || event.defaultPrevented || submitting) return
      event.stopPropagation()
      if (step > 1) setStep(step - 1)
      else onCancel()
    },
    [onCancel, step, submitting]
  )

  if (result) {
    return jsxs('div', {
      className: 'mx-auto flex w-full max-w-2xl flex-col gap-3 py-4',
      children: [
        jsx('h2', { className: 'text-sm font-semibold', children: 'Course created' }),
        jsxs('div', {
          className: 'text-xs leading-relaxed text-(--ui-text-tertiary)',
          children: [
            'Your course and its enrolment exist on this profile. The plan is a draft: objective ' +
              'generation is not wired in this build, so no lesson can start yet. Nothing was generated ' +
              'and no model was called.'
          ]
        }),
        jsxs('div', {
          className: 'flex flex-col',
          children: [
            jsx(StatusRow, { label: 'Course', value: result.courseId }),
            jsx(StatusRow, { label: 'Plan', value: `${result.planId} (draft)` }),
            jsx(StatusRow, { label: 'Enrollment', value: result.enrollmentId })
          ]
        }),
        jsxs('div', {
          className: 'flex flex-wrap items-center gap-2 pt-1',
          children: [
            jsx(sdk.Button, { onClick: onCancel, variant: 'default', children: 'Open in Courses' }),
            jsx(sdk.Button, {
              onClick: () => {
                setResult(null)
                setStep(1)
                setGoal('')
                setTitle('')
                keyRef.current = null
              },
              variant: 'secondary',
              children: 'Create another'
            })
          ]
        })
      ]
    })
  }

  const stepTitle = step === 1 ? 'What do you want to be able to do?' : step === 2 ? 'Shape the course' : 'Review and create'

  return jsxs('div', {
    className: 'mx-auto flex w-full max-w-2xl flex-col gap-4 py-2',
    onKeyDown,
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-start justify-between gap-2',
        children: [
          jsxs('div', {
            className: 'min-w-0',
            children: [
              jsx('div', { className: 'text-[0.6rem] font-medium uppercase tracking-wider text-(--ui-text-tertiary)', children: `STEP ${step} OF 3` }),
              jsx('h2', { className: 'mt-1 text-sm font-semibold', children: stepTitle })
            ]
          }),
          jsx(sdk.Button, { onClick: onCancel, size: 'sm', variant: 'text', children: 'Cancel' })
        ]
      }),
      step === 1
        ? jsxs('div', {
            className: 'flex flex-col gap-4',
            children: [
              jsxs('div', {
                className: 'flex flex-col gap-1.5',
                children: [
                  jsx('label', { className: 'text-xs font-medium text-(--ui-text-secondary)', htmlFor: 'cb-goal', children: 'Your goal' }),
                  jsx(sdk.Textarea, {
                    'aria-describedby': 'cb-goal-help',
                    'aria-invalid': goalInvalid ? true : undefined,
                    id: 'cb-goal',
                    onChange: (event) => setGoal(event.target.value),
                    placeholder: 'Explain the register difference between a friend and a manager.',
                    rows: 4,
                    value: goal
                  }),
                  jsx('div', {
                    className: 'text-xs text-(--ui-text-tertiary)',
                    id: 'cb-goal-help',
                    children: goal.trim().length === 0 ? 'Be specific about the situation you want to handle.' : `${goal.trim().length} characters`
                  })
                ]
              }),
              jsxs('div', {
                className: 'flex flex-col gap-1.5',
                children: [
                  jsx('label', { className: 'text-xs font-medium text-(--ui-text-secondary)', htmlFor: 'cb-title', children: 'Course title' }),
                  jsx(sdk.Input, {
                    id: 'cb-title',
                    onChange: (event) => setTitle(event.target.value),
                    placeholder: 'Japanese register with friends and managers',
                    value: title
                  })
                ]
              }),
              jsxs('div', {
                className: 'flex flex-col',
                children: [
                  jsx('div', { className: 'mb-1 text-xs font-medium text-(--ui-text-secondary)', children: 'Recipe' }),
                  RECIPES.filter((id) => id !== 'parent').map((id) =>
                    jsx(sdk.ListRow, {
                      action: jsx(sdk.Button, {
                        'aria-pressed': recipe === id,
                        onClick: () => setRecipe(id),
                        size: 'sm',
                        variant: recipe === id ? 'secondary' : 'outline',
                        children: recipe === id ? 'Selected' : 'Choose'
                      }),
                      description: RECIPE_COPY[id].description,
                      title: RECIPE_COPY[id].title
                    }, id)
                  ),
                  jsx('div', {
                    className: 'mt-1 text-xs text-(--ui-text-tertiary)',
                    children: 'Preparing lessons for a child goes to Parent Studio, not a learner course.'
                  })
                ]
              })
            ]
          })
        : null,
      step === 2
        ? jsx('div', {
            className: 'flex flex-col gap-4',
            children: Object.keys(DIALS).map((dial) =>
              jsxs('div', {
                className: 'flex flex-col gap-1.5',
                children: [
                  jsx('div', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: DIALS[dial].label }),
                  jsx(sdk.SegmentedControl, {
                    onChange: (value) => setDials((current) => ({ ...current, [dial]: value })),
                    options: DIALS[dial].options,
                    sizing: 'content',
                    value: dials[dial]
                  })
                ]
              }, dial)
            )
          })
        : null,
      step === 3
        ? jsxs('div', {
            className: 'flex flex-col gap-3',
            children: [
              jsxs('div', {
                className: 'flex flex-col',
                children: [
                  jsx(StatusRow, { label: 'Goal', value: jsx('span', { className: 'max-w-[36ch] break-words', children: goal.trim() }) }),
                  jsx(StatusRow, { label: 'Title', value: title.trim() }),
                  jsx(StatusRow, { label: 'Recipe', value: RECIPE_COPY[recipe].title }),
                  jsx(StatusRow, { label: 'Pace', value: dials.pace }),
                  jsx(StatusRow, { label: 'Depth', value: dials.depth }),
                  jsx(StatusRow, { label: 'Assessment', value: dials.assessment }),
                  jsx(StatusRow, { label: 'Autonomy', value: dials.autonomy })
                ]
              }),
              jsx('div', {
                className: 'text-xs leading-relaxed text-(--ui-text-tertiary)',
                children:
                  'Creating this course writes one course and one draft plan on this profile, then an ' +
                  'enrolment for you. It makes no model call and fetches nothing from the network. ' +
                  'Nothing is generated until you approve a plan, and plan generation is not part of this build.'
              }),
              error ? jsx(ErrorLine, { error }) : null
            ]
          })
        : null,
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2 border-t border-(--ui-stroke-tertiary) pt-3',
        children: [
          step > 1
            ? jsx(sdk.Button, { onClick: () => setStep(step - 1), size: 'sm', variant: 'secondary', disabled: submitting, children: 'Back' })
            : null,
          step < 3
            ? jsx(sdk.Button, {
                disabled: step === 1 ? !canAdvance : false,
                onClick: () => setStep(step + 1),
                size: 'sm',
                variant: 'default',
                children: 'Continue'
              })
            : jsx(sdk.Button, {
                disabled: submitting,
                onClick: submit,
                size: 'sm',
                variant: 'default',
                children: submitting ? 'Creating course' : 'Create course'
              })
        ]
      })
    ]
  })
}

// ══ CB-009 — the learning workspace: course detail, lessons, notebook, quizzes ══
//
// Every read below is a real cb.rpc command named in the mounted contract. Where a surface the
// UX spec requires has no command (course outline, check stimulus, pane-side hint/answer events)
// the UI gates on `/runtime.implemented_methods`, says which command is missing, and keeps the
// working control instead of rendering a dead button. See docs/REVIEW_CB009.md.

const LEARNING_VIEWS = [
  { id: 'overview', label: 'Overview' },
  { id: 'textbook', label: 'Textbook' },
  { id: 'notebook', label: 'Notebook' },
  { id: 'quizzes', label: 'Quizzes' },
  { id: 'plan', label: 'Plan' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'sources', label: 'Sources' }
]

/** A section or quiz row is never colour-only: this is the text that carries the state. */
const OBJECTIVE_STATE_COPY = {
  not_started: 'Not started',
  introduced: 'Introduced',
  independent_evidence: 'Independent evidence',
  delayed_evidence: 'Delayed evidence',
  review_due: 'Review due',
  needs_review: 'Needs review',
  overridden: 'Overridden'
}

const EVIDENCE_CLASS_COPY = {
  cold: 'Cold attempt',
  hinted: 'Hinted',
  answer_shown: 'Answer shown',
  override: 'Override — not independent evidence'
}

const VERDICT_COPY = {
  pass: 'Passed',
  partial: 'Partly there',
  not_yet: 'Not yet',
  needs_retry: 'Grading failed'
}

const NEXT_ACTION_COPY = {
  complete_objective: 'This objective is complete. Move to the next section when you are ready.',
  continue: 'Continue the lesson when you are ready.',
  review_objective: 'Access advanced, but this was not independent evidence. It will come back for review.',
  retry_grading: 'The answer is saved. Retry grading does not consume a new attempt.'
}

const REVIEW_ACTION_COPY = {
  snooze: 'Snooze',
  stretch: 'Stretch',
  drop: 'Drop',
  resume: 'Resume'
}

const WARNING_COPY_LEARNING = {
  stale_source: 'A source behind this course changed. Old evidence is kept; the source needs review.',
  detached_chat: 'This lesson’s chat binding is detached. Submitting is disabled until it is reconciled.',
  plan_update: 'A newer plan draft is waiting for review.',
  provider_unavailable: 'A provider needed by this course is unavailable. Nothing is being generated.',
  pending_migration: 'This database needs a migration before every control can run.',
  pack_frozen: 'The imported pack this course came from is frozen; its content will not change.'
}

function StateText({ state }) {
  return jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: OBJECTIVE_STATE_COPY[state] || state || 'unknown' })
}

function EvidenceClassText({ value }) {
  return jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: EVIDENCE_CLASS_COPY[value] || value || 'unknown' })
}

function Hairline() {
  return jsx('div', { className: 'h-px w-full bg-(--ui-stroke-tertiary)' })
}

function QuietNote({ children }) {
  return jsx('p', { className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-tertiary)', children })
}

function whenLabel(value) {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value)
  const now = Date.now()
  const delta = now - parsed.getTime()
  const day = 86400000
  if (delta < 60000) return 'just now'
  if (delta < 3600000) return `${Math.max(1, Math.round(delta / 60000))} min ago`
  if (delta < day) return `${Math.round(delta / 3600000)} hr ago`
  if (delta < day * 7) return `${Math.round(delta / day)} d ago`
  return parsed.toISOString().slice(0, 10)
}

/**
 * The current check for one objective.
 *
 * `check.open` is the contract's command: it returns the open check or creates one from the
 * objective's audited spec. The revision fence travels in the envelope, so a check opened against
 * an older intent is refused as STALE_REVISION rather than silently winning.
 */
function useOpenCheck({ enrollmentId, objectiveId, revision, enabled }) {
  const [state, setState] = useState({ status: 'idle', check: null, error: null })
  const [ticket, setTicket] = useState(0)

  useEffect(() => {
    if (!enabled || !enrollmentId || !objectiveId) {
      setState({ status: 'idle', check: null, error: null })
      return undefined
    }
    let cancelled = false
    setState((previous) => ({ status: 'loading', check: previous.check, error: null }))
    rpc(
      'check.open',
      { enrollment_id: enrollmentId, objective_id: objectiveId },
      { expectedRevision: Number(revision) || 0 }
    )
      .then((response) => {
        if (cancelled) return
        if (response && response.ok) setState({ status: 'ready', check: response.result, error: null })
        else setState({ status: 'error', check: null, error: (response && response.error) || null })
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            status: 'error',
            check: null,
            error: { code: 'HOST_UNAVAILABLE', message: describeError(error) }
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [enrollmentId, objectiveId, revision, enabled, ticket])

  return { ...state, reload: () => setTicket((value) => value + 1) }
}

/**
 * One attempt, started and finished in the pane or on the lesson page.
 *
 * Idempotency is enrollment + check + a per-view nonce: retrying a failed grade re-sends the SAME
 * nonce, so the backend returns the stored attempt instead of writing a second one. The answer
 * carries both `text` and a one-element `selection`, because a closed-form check may be graded on
 * either field and the contract permits both.
 */
function AttemptControls({ enrollmentId, objectiveId, check, revision, implemented, bindingState, onCommitted }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const [text, setText] = useState('')
  const [phase, setPhase] = useState('awaiting_input')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [overrideOpen, setOverrideOpen] = useState(false)
  const nonceRef = useRef(null)
  const detached = Boolean(bindingState && bindingState !== 'active')

  useEffect(() => {
    setText('')
    setPhase('awaiting_input')
    setResult(null)
    setError(null)
    nonceRef.current = null
  }, [check && check.check_id])

  const submit = useCallback(async () => {
    if (!check) return
    const answer = text.trim()
    if (!answer) {
      setError({ code: 'VALIDATION_FAILED', message: 'Write an answer before submitting.' })
      return
    }
    if (!nonceRef.current) nonceRef.current = newOperationId('attempt')
    setPhase('submitting')
    setError(null)
    const response = await rpc(
      'attempt.submit',
      {
        enrollment_id: enrollmentId,
        check_id: check.check_id,
        check_version: check.check_version,
        attempt_nonce: nonceRef.current,
        answer: { kind: 'text', text: answer, selection: [answer] }
      },
      {
        idempotencyKey: `cb-attempt-${check.check_id}-${nonceRef.current}`,
        expectedRevision: Number(revision) || 0
      }
    )
    if (!response.ok) {
      const code = response.error && response.error.code
      setError(response.error)
      setPhase(code === 'STALE_REVISION' || code === 'CHECK_STALE' ? 'stale' : 'awaiting_input')
      return
    }
    const graded = response.result
    setResult(graded)
    setPhase(graded.verdict === 'needs_retry' ? 'needs_retry' : 'graded')
    if (onCommitted) onCommitted(graded)
  }, [check, text, enrollmentId, revision, onCommitted])

  const retryGrading = useCallback(async () => {
    if (!check || !nonceRef.current) return
    setPhase('submitting')
    setError(null)
    const response = await rpc(
      'attempt.submit',
      {
        enrollment_id: enrollmentId,
        check_id: check.check_id,
        check_version: check.check_version,
        attempt_nonce: nonceRef.current,
        answer: { kind: 'text', text: text.trim(), selection: [text.trim()] }
      },
      {
        idempotencyKey: `cb-attempt-${check.check_id}-${nonceRef.current}`,
        expectedRevision: Number(revision) || 0
      }
    )
    if (!response.ok) {
      setError(response.error)
      setPhase('needs_retry')
      return
    }
    setResult(response.result)
    setPhase(response.result.verdict === 'needs_retry' ? 'needs_retry' : 'graded')
    if (onCommitted) onCommitted(response.result)
  }, [check, text, enrollmentId, revision, onCommitted])

  const moveOn = useCallback(async () => {
    if (!check) return
    const response = await rpc(
      'attempt.override',
      {
        enrollment_id: enrollmentId,
        check_id: check.check_id,
        reason: 'Moved on after a grading failure (recorded from the Coursebook pane).'
      },
      { expectedRevision: Number(revision) || 0 }
    )
    setOverrideOpen(false)
    if (!response.ok) {
      setError(response.error)
      return
    }
    setResult({ verdict: 'overridden', evidence_class: 'override', criteria: [], next_action: 'complete_objective' })
    setPhase('overridden')
    if (onCommitted) onCommitted(response.result)
  }, [check, enrollmentId, revision, onCommitted])

  if (!check) {
    return jsx(QuietNote, {
      children: 'There is no open check for this objective yet. Opening the section asks the backend for one.'
    })
  }

  const locked = phase === 'submitting'
  const showForm = phase === 'awaiting_input' || phase === 'stale'
  const criteria = (result && result.criteria) || []

  return jsxs('div', {
    className: 'flex flex-col gap-2',
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: `Check v${check.check_version}` }),
          jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: check.evidence_target || 'evidence' }),
          result && result.evidence_class ? jsx(EvidenceClassText, { value: result.evidence_class }) : null
        ]
      }),

      showForm
        ? jsxs('div', {
            className: 'flex flex-col gap-2',
            children: [
              jsx('label', {
                className: 'text-xs font-medium text-(--ui-text-secondary)',
                htmlFor: 'cb-attempt-answer',
                children: 'Your answer'
              }),
              jsx(sdk.Textarea, {
                id: 'cb-attempt-answer',
                'aria-describedby': 'cb-attempt-help',
                disabled: locked || detached,
                onChange: (event) => setText(event.target.value),
                placeholder: 'Type the answer you would give in the lesson.',
                rows: 3,
                value: text
              }),
              jsx('p', {
                id: 'cb-attempt-help',
                className: 'text-xs leading-relaxed text-(--ui-text-tertiary)',
                children: supports('check.get')
                  ? 'The question and any choices are shown above; this field records what you answered.'
                  : 'The question and any choices are in the teaching chat. This field records your answer and the backend grades it once.'
              }),
              detached
                ? jsx(QuietNote, {
                    children: 'This lesson’s chat binding is detached, so Submit is disabled until it is reconciled.'
                  })
                : null,
              jsxs('div', {
                className: 'flex flex-wrap items-center gap-2',
                children: [
                  jsx(sdk.Button, {
                    variant: 'default',
                    size: 'sm',
                    disabled: locked || detached || !text.trim(),
                    onClick: submit,
                    children: locked ? 'Submitting' : 'Submit answer'
                  }),
                  jsx(sdk.Button, {
                    variant: 'text',
                    size: 'sm',
                    disabled: locked || !text,
                    onClick: () => {
                      setText('')
                      setError(null)
                    },
                    children: 'Edit answer'
                  })
                ]
              })
            ]
          })
        : null,

      phase === 'submitting'
        ? jsx('div', {
            className: 'flex items-center gap-2 text-xs text-(--ui-text-secondary)',
            children: [
              jsx(sdk.Loader, { label: 'Grading this answer' }),
              jsx('span', { children: 'Answer locked. No second attempt is created while this runs.' })
            ]
          })
        : null,

      phase === 'graded' && result
        ? jsxs('div', {
            className: 'flex flex-col gap-2',
            children: [
              jsx('div', { className: 'text-sm font-medium', children: VERDICT_COPY[result.verdict] || result.verdict }),
              criteria.length > 0
                ? jsx('ul', {
                    className: 'flex flex-col gap-1',
                    children: criteria.map((item, index) =>
                      jsxs(
                        'li',
                        {
                          className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                          children: [
                            jsx(sdk.Codicon, { name: item.met ? 'pass' : 'circle-slash', size: '0.75rem' }),
                            jsx('span', { className: 'ml-1', children: item.observed || item.id })
                          ]
                        },
                        `${item.id}-${index}`
                      )
                    )
                  })
                : jsx(QuietNote, { children: 'No criterion detail was returned for this verdict.' }),
              jsx(QuietNote, { children: NEXT_ACTION_COPY[result.next_action] || 'The backend recorded the next action.' }),
              jsxs('div', {
                className: 'flex flex-wrap items-center gap-2',
                children: [
                  jsx(sdk.Button, {
                    variant: 'secondary',
                    size: 'sm',
                    onClick: () => {
                      setText('')
                      setResult(null)
                      setPhase('awaiting_input')
                      nonceRef.current = null
                    },
                    children: 'Try a new example'
                  }),
                  jsx(sdk.Button, {
                    variant: 'text',
                    size: 'sm',
                    onClick: () => {
                      setPhase('awaiting_input')
                    },
                    children: 'Explain the difference'
                  })
                ]
              })
            ]
          })
        : null,

      phase === 'needs_retry'
        ? jsxs('div', {
            className: 'flex flex-col gap-2',
            children: [
              jsx('div', {
                className: 'text-sm font-medium',
                children: 'I couldn’t grade this attempt.'
              }),
              jsx(QuietNote, {
                children: 'Your answer is saved; no progress was changed. Retrying does not create a second attempt.'
              }),
              error ? jsx(ErrorLine, { error }) : null,
              jsxs('div', {
                className: 'flex flex-wrap items-center gap-2',
                children: [
                  jsx(sdk.Button, { variant: 'default', size: 'sm', onClick: retryGrading, children: 'Retry grading' }),
                  jsx(sdk.Button, {
                    variant: 'secondary',
                    size: 'sm',
                    onClick: () => setPhase('awaiting_input'),
                    children: 'Edit answer'
                  }),
                  jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: () => setOverrideOpen(true), children: 'Move on…' })
                ]
              })
            ]
          })
        : null,

      phase === 'overridden'
        ? jsxs('div', {
            className: 'flex flex-col gap-2',
            children: [
              jsx('div', { className: 'text-sm font-medium', children: 'Access granted — not independent evidence' }),
              jsx(QuietNote, {
                children: 'The override is recorded against this objective. It advances access and is never counted as a pass.'
              }),
              jsx(sdk.Button, {
                variant: 'secondary',
                size: 'sm',
                onClick: () => {
                  setResult(null)
                  setPhase('awaiting_input')
                  nonceRef.current = null
                },
                children: 'Back to the check'
              })
            ]
          })
        : null,

      phase === 'stale'
        ? jsxs('div', {
            className: 'flex flex-col gap-2',
            children: [
              jsx('div', { className: 'text-sm font-medium', children: 'This check moved on while you were answering.' }),
              jsx(QuietNote, {
                children: 'No attempt was created and nothing was overwritten. Re-read the section to get the current check.'
              }),
              error ? jsx(ErrorLine, { error }) : null
            ]
          })
        : null,

      error && phase !== 'needs_retry' && phase !== 'stale' ? jsx(ErrorLine, { error }) : null,

      jsx(QuietNote, {
        children: supports('lesson.assist')
          ? 'Hints and shown answers are recorded against the next attempt.'
          : 'Hint and Show answer are not registered by this build yet; asking for a hint in the teaching chat records it against your next answer.'
      }),

      jsx(sdk.ConfirmDialog, {
        open: overrideOpen,
        title: 'Move on without a grade?',
        description:
          'This records an override: access advances, but the objective is marked overridden and this attempt is never counted as independent evidence. The saved answer is kept.',
        confirmLabel: 'Record override',
        onClose: () => setOverrideOpen(false),
        onConfirm: moveOn,
        children: null
      })
    ]
  })
}

/** Save one moment into the notebook: excerpt preview, note, tags, destination. */
function NotebookSaveDialog({ open, onClose, enrollmentId, objectiveId, lessonRunId, seed, implemented, onSaved }) {
  const [note, setNote] = useState('')
  const [tags, setTags] = useState('')
  const [excerpt, setExcerpt] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const supports = (method) => Boolean(implemented && implemented.has(method))

  useEffect(() => {
    if (!open) return
    setNote('')
    setTags('')
    setExcerpt((seed && seed.excerpt) || '')
    setError(null)
    setBusy(false)
  }, [open, seed])

  const save = useCallback(async () => {
    setBusy(true)
    setError(null)
    const tagList = tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean)
      .slice(0, 20)
    const response = await rpc('notebook.save', {
      enrollment_id: enrollmentId,
      objective_id: objectiveId,
      lesson_run_id: lessonRunId || null,
      kind: (seed && seed.kind) || 'lesson_segment',
      excerpt: excerpt.trim() || null,
      note: note.trim() || null,
      tags: tagList,
      source_ref: (seed && seed.source_ref) || null
    })
    setBusy(false)
    if (!response.ok) {
      setError(response.error)
      return
    }
    setBusy(false)
    onSaved()
    onClose()
  }, [enrollmentId, objectiveId, lessonRunId, seed, excerpt, note, tags, onSaved, onClose])

  return jsx(sdk.ConfirmDialog, {
    open,
    title: 'Save to notebook',
    description: 'Saved excerpts and personal notes stay on this profile. They never enter a shared pack.',
    confirmLabel: busy ? 'Saving' : 'Save to notebook',
    onClose,
    onConfirm: save,
    children: jsxs('div', {
      className: 'flex flex-col gap-3',
      children: [
        jsx('label', {
          htmlFor: 'cb-note-excerpt',
          className: 'text-xs font-medium text-(--ui-text-secondary)',
          children: 'Excerpt'
        }),
        jsx(sdk.Textarea, {
          id: 'cb-note-excerpt',
          rows: 3,
          value: excerpt,
          onChange: (event) => setExcerpt(event.target.value)
        }),
        jsx('label', {
          htmlFor: 'cb-note-note',
          className: 'text-xs font-medium text-(--ui-text-secondary)',
          children: 'Your note (optional)'
        }),
        jsx(sdk.Textarea, {
          id: 'cb-note-note',
          rows: 2,
          value: note,
          onChange: (event) => setNote(event.target.value),
          placeholder: 'Why this matters to you.'
        }),
        jsx('label', {
          htmlFor: 'cb-note-tags',
          className: 'text-xs font-medium text-(--ui-text-secondary)',
          children: 'Tags (comma separated)'
        }),
        jsx(sdk.Input, {
          id: 'cb-note-tags',
          value: tags,
          onChange: (event) => setTags(event.target.value),
          placeholder: 'register, politeness'
        }),
        supports('notebook.save') ? null : jsx(QuietNote, { children: 'notebook.save is not registered on this backend.' }),
        error ? jsx(ErrorLine, { error }) : null
      ]
    })
  })
}

/** The section index. Uses `course.outline` when the backend has it; otherwise names what it can. */
function sectionRows({ row, review, notebooks, outline, page }) {
  const seen = new Map()
  const add = (entry) => {
    if (!entry || !entry.objective_id) return
    const existing = seen.get(entry.objective_id) || {}
    // A later source (a notebook save, a review row) can carry the id without the label. Merge
    // field-by-field so a missing title never erases one an earlier source already named.
    const merged = { ...existing }
    Object.keys(entry).forEach((field) => {
      const value = entry[field]
      if (value !== null && value !== undefined) merged[field] = value
    })
    seen.set(entry.objective_id, merged)
  }
  if (outline && Array.isArray(outline.objectives)) {
    outline.objectives.forEach((objective) =>
      add({
        objective_id: objective.objective_id,
        title: objective.title,
        ordinal: objective.ordinal,
        state: objective.state,
        evidence_target: objective.evidence_target,
        attempt_count: objective.attempt_count,
        last_opened_at: objective.last_opened_at
      })
    )
  }
  if (review && Array.isArray(review.items)) {
    review.items.forEach((item) =>
      add({
        objective_id: item.objective_id,
        title: item.title,
        ordinal: item.ordinal,
        state: item.state,
        evidence_target: item.evidence_target,
        due_at: item.due_at,
        overdue: item.overdue
      })
    )
  }
  const current = row && row.evidence_summary && row.evidence_summary.current_objective_id
  if (current) {
    add({
      objective_id: current,
      title: (page && page.section && page.section.objective_id === current && page.section.title) || 'Current section',
      ordinal: page && page.section ? page.section.ordinal : 0,
      state: (page && page.section && page.section.state) || undefined,
      evidence_target: page && page.section ? page.section.evidence_target : undefined
    })
  }
  if (notebooks && Array.isArray(notebooks.entries)) {
    notebooks.entries.forEach((entry) => {
      if (entry.objective_id) add({ objective_id: entry.objective_id, title: null })
    })
  }
  return Array.from(seen.values())
    .map((entry) => ({ ...entry, title: entry.title || 'Saved section' }))
    .sort((left, right) => (left.ordinal || 0) - (right.ordinal || 0))
}

function SectionPage({ row, objectiveId, page, pageStatus, pageError, onRetryPage, implemented, onBack, onChanged, review }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const section = page && page.section
  const runtime = page && page.runtime
  const bindingActive = Boolean(runtime && runtime.binding_status === 'active')
  const [saveSeed, setSaveSeed] = useState(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  const check = useOpenCheck({
    enrollmentId: row.enrollment_id,
    objectiveId,
    revision: page ? page.revision : 0,
    enabled: Boolean(page) && supports('check.open') && Boolean(section)
  })

  const begin = useCallback(
    async (mode) => {
      setBusy(true)
      setNotice(null)
      const response = await rpc(
        'lesson.begin',
        { enrollment_id: row.enrollment_id, objective_id: objectiveId, mode },
        { idempotencyKey: `cb-lesson-${objectiveId}-${mode}-${mode === 'fresh' ? newOperationId('run') : 'resume'}` }
      )
      setBusy(false)
      if (!response.ok) {
        setNotice(`${response.error.code}: ${describeError(response.error)}`)
        return
      }
      const outcome = response.result
      if (mode === 'resume' && outcome.resume && outcome.resume.available && outcome.binding) {
        const opened = await resumeBoundSession(outcome.binding)
        setNotice(opened.ok ? 'Resumed the existing bound chat.' : opened.message)
        return
      }
      // The chat that is about to open has no stored id yet: arm the exact run and let the pane
      // bind it on the first turn. A resume path already had a binding, so it never arms.
      armPendingBind({
        enrollmentId: row.enrollment_id,
        objectiveId,
        lessonRunId: outcome.lesson_run_id,
        profile: row.profile || currentScope().profile
      })
      const started = startLessonChat(row.profile || currentScope().profile)
      setNotice(
        started
          ? 'A fresh governed run is ready. Its chat binds after your first message.'
          : 'This Desktop build cannot open a new chat; start one from the sidebar, then resume this section.'
      )
      if (onChanged) onChanged()
    },
    [row, objectiveId, onChanged]
  )

  const saveSegment = useCallback((segment) => {
    setSaveSeed({ excerpt: segment.text, kind: segment.artifact_id ? 'artifact' : 'lesson_segment', source_ref: segment.source_id || null })
  }, [])

  let body
  if (!page) {
    body =
      pageStatus === 'error'
        ? jsx(sdk.ErrorState, {
            title: 'This section could not be read',
            description: `${pageError && pageError.code ? pageError.code + ': ' : ''}${describeError(pageError)}`,
            children: jsx(sdk.Button, {
              variant: 'secondary',
              size: 'sm',
              onClick: onRetryPage,
              children: 'Try again'
            })
          })
        : jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading this section' }) })
  } else {
    body = jsxs('div', {
      className: 'flex flex-col gap-4',
      children: [
        jsxs('div', {
          className: 'flex flex-col gap-1',
          children: [
            jsx('div', { className: 'text-sm font-semibold', children: section ? section.title : 'Section' }),
            jsxs('div', {
              className: 'flex flex-wrap items-center gap-2',
              children: [
                section ? jsx(StateText, { state: section.state }) : null,
                section && section.evidence_target
                  ? jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: section.evidence_target })
                  : null,
                section && section.last_opened_at
                  ? jsx('span', {
                      className: 'text-xs text-(--ui-text-tertiary)',
                      children: `Last opened ${whenLabel(section.last_opened_at)}`
                    })
                  : null,
                runtime ? jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: runtime.session_state }) : null
              ]
            })
          ]
        }),

        runtime && !bindingActive
          ? jsxs('div', {
              className: 'flex flex-wrap items-center justify-between gap-2 border border-(--ui-stroke-tertiary) px-3 py-2',
              children: [
                jsx('div', {
                  className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                  children: `This section’s chat binding is ${runtime.binding_status}. Submit stays disabled until it is reconciled.`
                }),
                jsx(sdk.Button, {
                  variant: 'secondary',
                  size: 'sm',
                  disabled: busy,
                  onClick: () => begin('resume'),
                  children: 'Reattach'
                })
              ]
            })
          : null,

        jsxs('div', {
          className: 'flex flex-wrap items-center gap-2',
          children: [
            jsx(sdk.Button, {
              variant: 'default',
              size: 'sm',
              disabled: busy,
              onClick: () => begin('resume'),
              children: runtime && bindingActive ? 'Continue here' : 'Resume this section'
            }),
            jsx(sdk.Button, {
              variant: 'secondary',
              size: 'sm',
              disabled: busy,
              onClick: () => begin('fresh'),
              children: 'Start a fresh run'
            }),
            jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: onBack, children: 'All sections' })
          ]
        }),
        notice ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: notice }) : null,

        jsx(sdk.PanelSectionLabel, { children: 'TEACHING SEGMENTS' }),
        page.segments && page.segments.length > 0
          ? jsx('div', {
              className: 'flex flex-col',
              children: page.segments.map((segment) =>
                jsxs(
                  'div',
                  {
                    className: 'flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
                    children: [
                      jsxs('div', {
                        className: 'flex items-center justify-between gap-2',
                        children: [
                          jsx('span', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: segment.kind }),
                          jsxs('div', {
                            className: 'flex items-center gap-1',
                            children: [
                              segment.artifact_id && supports('artifact.get')
                                ? jsx(sdk.Button, {
                                    variant: 'text',
                                    size: 'sm',
                                    onClick: async () => {
                                      const response = await rpc('artifact.get', { artifact_id: segment.artifact_id })
                                      if (!response.ok) {
                                        host.notify({ kind: 'warning', message: `${response.error.code}: ${describeError(response.error)}` })
                                        return
                                      }
                                      host.notify({ kind: 'info', message: `Artifact ready: ${response.result.mime}, ${response.result.bytes} bytes.` })
                                    },
                                    children: 'View media'
                                  })
                                : null,
                              supports('notebook.save')
                                ? jsx(sdk.Button, {
                                    variant: 'text',
                                    size: 'sm',
                                    onClick: () => saveSegment(segment),
                                    children: 'Save to notebook'
                                  })
                                : null
                            ]
                          })
                        ]
                      }),
                      jsx('p', {
                        className: 'max-w-prose whitespace-pre-wrap break-words text-sm leading-relaxed',
                        children: segment.text
                      }),
                      segment.source_id
                        ? jsx('div', { className: 'text-xs text-(--ui-text-tertiary)', children: `Source ${segment.source_id}` })
                        : null
                    ]
                  },
                  segment.segment_id
                )
              )
            })
          : jsx(EmptyState, {
              title: 'No teaching segments yet',
              description: 'Segments appear here after a teaching turn in the bound chat. Coursebook does not write them for you.'
            }),

        jsx(sdk.PanelSectionLabel, { children: 'CURRENT CHECK' }),
        check.status === 'error'
          ? jsx(QuietNote, {
              children: check.error
                ? `${check.error.code}: ${describeError(check.error)}`
                : 'The current check could not be opened.'
            })
          : jsx(AttemptControls, {
              enrollmentId: row.enrollment_id,
              objectiveId,
              check: check.check,
              revision: page.revision,
              implemented,
              bindingState: runtime ? runtime.binding_status : 'detached',
              onCommitted: () => {
                if (onChanged) onChanged()
              }
            }),

        page.attempts && page.attempts.length > 0
          ? jsxs('div', {
              className: 'flex flex-col',
              children: [
                jsx(sdk.PanelSectionLabel, { children: 'ATTEMPTS ON THIS SECTION' }),
                page.attempts.slice(0, 5).map((attempt) =>
                  jsxs(
                    'div',
                    {
                      className: 'flex flex-wrap items-center justify-between gap-2 border-b border-(--ui-stroke-tertiary) py-1.5 last:border-b-0 text-xs',
                      children: [
                        jsx('span', { className: 'text-(--ui-text-secondary)', children: whenLabel(attempt.committed_at || attempt.created_at) }),
                        jsxs('span', {
                          className: 'flex items-center gap-2',
                          children: [
                            jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: VERDICT_COPY[attempt.verdict] || attempt.verdict }),
                            jsx(EvidenceClassText, { value: attempt.evidence_class })
                          ]
                        })
                      ]
                    },
                    attempt.attempt_id
                  )
                )
              ]
            })
          : null,

        page.notebook_entries && page.notebook_entries.length > 0
          ? jsxs('div', {
              className: 'flex flex-col gap-1',
              children: [
                jsx(sdk.PanelSectionLabel, { children: 'SAVED FROM THIS SECTION' }),
                page.notebook_entries.map((entry) =>
                  jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: entry.excerpt || entry.note || entry.kind }, entry.entry_id)
                )
              ]
            })
          : null,

        jsxs('div', {
          className: 'flex flex-col gap-1',
          children: [
            jsx(sdk.PanelSectionLabel, { children: 'SOURCES ON THIS COURSE' }),
            (page.sources || []).length === 0
              ? jsx(QuietNote, { children: 'The backend recorded no sources for this course.' })
              : (page.sources || []).slice(0, 6).map((source) =>
                  jsxs(
                    'div',
                    {
                      className: 'flex flex-wrap items-baseline justify-between gap-2 border-b border-(--ui-stroke-tertiary) py-1.5 text-xs last:border-b-0',
                      children: [
                        jsx('span', { className: 'min-w-0 break-words text-(--ui-text-secondary)', children: source.title }),
                        jsxs('span', {
                          className: 'flex items-center gap-2 text-(--ui-text-tertiary)',
                          children: [
                            jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: source.support_status }),
                            jsx('span', { children: source.fetched_at ? `fetched ${whenLabel(source.fetched_at)}` : '' })
                          ]
                        })
                      ]
                    },
                    source.source_id
                  )
                )
          ]
        })
      ]
    })
  }

  return jsxs('div', {
    className: 'flex flex-col gap-3',
    children: [
      page ? null : jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: onBack, children: 'All sections' }),
      body,
      jsx(NotebookSaveDialog, {
        open: Boolean(saveSeed),
        seed: saveSeed,
        onClose: () => setSaveSeed(null),
        enrollmentId: row.enrollment_id,
        objectiveId,
        lessonRunId: runtime ? runtime.lesson_run_id : null,
        implemented,
        onSaved: () => {
          if (onChanged) onChanged()
        }
      })
    ]
  })
}
/** Overview: what to do next, one review row, recent meaningful event, action banners only. */
function OverviewView({ row, page, review, quizzes, implemented, onOpenSection, onResume }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const next = row.next_step || {}
  const section = page && page.section
  const due = review && Array.isArray(review.items) ? review.items.filter((item) => item.overdue) : []
  const recent = quizzes && Array.isArray(quizzes.attempts) ? quizzes.attempts[0] : null
  const warning = row.warning ? WARNING_COPY_LEARNING[row.warning] : null

  return jsxs('div', {
    className: 'flex max-w-2xl flex-col gap-4',
    children: [
      warning ? jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: warning }) : null,

      jsxs('div', {
        className: 'flex flex-col gap-1',
        children: [
          jsx(sdk.PanelSectionLabel, { children: 'CURRENT OBJECTIVE' }),
          jsx('div', { className: 'text-sm font-medium', children: section ? section.title : next.label || 'No objective recorded yet' }),
          section
            ? jsxs('div', {
                className: 'flex flex-wrap items-center gap-2',
                children: [
                  jsx(StateText, { state: section.state }),
                  section.evidence_target
                    ? jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: section.evidence_target })
                    : null
                ]
              })
            : null,
          jsx(QuietNote, { children: next.label || 'The backend did not return a next step for this course.' })
        ]
      }),

      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(sdk.Button, {
            variant: 'default',
            size: 'sm',
            disabled: !section,
            onClick: () => onResume(section ? section.objective_id : null),
            children: next.kind === 'resume_lesson' ? 'Resume lesson' : 'Start lesson'
          }),
          jsx(sdk.Button, {
            variant: 'secondary',
            size: 'sm',
            disabled: !section,
            onClick: () => onOpenSection(section ? section.objective_id : null),
            children: 'Open this section'
          })
        ]
      }),

      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(sdk.PanelSectionLabel, { children: 'REVIEW' }),
          due.length === 0
            ? jsx(QuietNote, { children: 'Nothing due. The review queue stays quiet until evidence is scheduled.' })
            : jsxs('div', {
                className: 'flex flex-wrap items-center justify-between gap-2 py-1',
                children: [
                  jsx('div', {
                    className: 'text-xs text-(--ui-text-secondary)',
                    children: `${due.length} due${review.total_overdue > due.length ? ` · ${review.total_overdue} overdue in total` : ''}`
                  }),
                  jsx(sdk.Button, {
                    variant: 'secondary',
                    size: 'sm',
                    onClick: () => onOpenSection(due[0].objective_id),
                    children: 'Open the oldest'
                  })
                ]
              })
        ]
      }),

      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(sdk.PanelSectionLabel, { children: 'RECENT EVENT' }),
          recent
            ? jsxs('div', {
                className: 'flex flex-wrap items-center justify-between gap-2 text-xs',
                children: [
                  jsx('span', {
                    className: 'text-(--ui-text-secondary)',
                    children: `${VERDICT_COPY[recent.verdict] || recent.verdict} · ${whenLabel(recent.committed_at || recent.created_at)}`
                  }),
                  jsx(EvidenceClassText, { value: recent.evidence_class })
                ]
              })
            : jsx(QuietNote, { children: 'No attempt has been recorded on this course yet.' })
        ]
      }),

      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(sdk.PanelSectionLabel, { children: 'THIS COURSE' }),
          jsx(StatusRow, { label: 'Recipe', value: row.recipe }),
          jsx(StatusRow, { label: 'Enrollment', value: row.enrollment_status, detail: `revision ${row.revision}` }),
          jsx(StatusRow, {
            label: 'Evidence',
            value: `${Number((row.evidence_summary || {}).independent || 0)} independent`,
            detail: `${Number((row.evidence_summary || {}).total_objectives || 0)} objectives · ${Number((row.evidence_summary || {}).review_due || 0)} due`
          }),
          jsx(StatusRow, {
            label: 'Provenance',
            value: sourceLabel(row.provenance && row.provenance.source),
            detail: row.provenance && row.provenance.pack_id ? `${row.provenance.pack_id}${row.provenance.pack_version ? ` v${row.provenance.pack_version}` : ''}` : 'authored on this profile'
          }),
          supports('pack.export') && row.provenance && row.provenance.pack_id
            ? jsx(QuietNote, { children: 'Exporting the pack is a Library action; it never includes your answers or notes.' })
            : null
        ]
      })
    ]
  })
}

/** Textbook — a scannable section list, not one endless thread. */
function TextbookView({ row, page, pageState, review, notebooks, outline, implemented, openSectionId, onOpenSection, onCloseSection, onChanged }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const rows = sectionRows({ row, review, notebooks, outline, page })
  const hasOutline = Boolean(outline && Array.isArray(outline.objectives))

  // Opening a section is owned by CourseDetail, so a route in from Overview, Notebook or Quizzes
  // ("Continue from here") lands on the same durable page as a click in this list, and the
  // `lesson.page` request that backs it is always aimed at the section being shown.
  if (openSectionId) {
    return jsx(SectionPage, {
      row,
      objectiveId: openSectionId,
      page: page && page.section && page.section.objective_id === openSectionId ? page : null,
      pageStatus: pageState.status,
      pageError: pageState.error,
      onRetryPage: pageState.reload,
      implemented,
      review,
      onBack: onCloseSection,
      onChanged
    })
  }

  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-3',
    children: [
      hasOutline
        ? null
        : jsx(QuietNote, {
            children:
              'This build can name the current section and every section with scheduled evidence. The complete ' +
              'section list needs course.outline (cb.rpc v5); rows light up here automatically once that ' +
              'command is registered.'
          }),
      rows.length === 0
        ? jsx(EmptyState, {
            title: 'No sections yet',
            description: 'A section appears once the course has an approved plan with objectives. Approve the plan first.'
          })
        : jsx('div', {
            className: 'flex flex-col',
            children: rows.map((entry) =>
              jsx(
                'div',
                {
                  className: 'flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
                  children: jsxs('div', {
                    className: 'flex flex-wrap items-start justify-between gap-2',
                    children: [
                      jsxs('div', {
                        className: 'flex min-w-0 flex-col gap-0.5',
                        children: [
                          jsx('div', {
                            className: 'min-w-0 break-words text-sm font-medium',
                            children: entry.title
                          }),
                          jsxs('div', {
                            className: 'flex flex-wrap items-center gap-2',
                            children: [
                              jsx(StateText, { state: entry.state || 'not_started' }),
                              entry.evidence_target
                                ? jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: entry.evidence_target })
                                : null,
                              entry.overdue ? jsx(sdk.Badge, { size: 'xs', variant: 'warn', children: `overdue ${entry.overdue_days || 0}d` }) : null,
                              entry.last_opened_at
                                ? jsx('span', {
                                    className: 'text-xs text-(--ui-text-tertiary)',
                                    children: `last opened ${whenLabel(entry.last_opened_at)}`
                                  })
                                : null
                            ]
                          })
                        ]
                      }),
                      jsx(sdk.Button, {
                        variant: 'secondary',
                        size: 'sm',
                        onClick: () => onOpenSection(entry.objective_id),
                        children: 'Open section'
                      })
                    ]
                  })
                },
                entry.objective_id
              )
            )
          }),
      !hasOutline
        ? jsx(QuietNote, {
            children:
              'Jumping backward never erases later evidence: each section keeps its own lesson runs, attempts and notebook saves.'
          })
        : null
    ]
  })
}

/** Notebook — saved moments, searchable, editable, with a route back to the exact section. */
function NotebookView({ row, notebooks, implemented, onOpenSection, onChanged }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const [searchInput, setSearchInput] = useState('')
  const [query, setQuery] = useState('')
  const [tag, setTag] = useState('all')
  const [order, setOrder] = useState('recent')
  const [editing, setEditing] = useState(null)
  const [editNote, setEditNote] = useState('')
  const [editTags, setEditTags] = useState('')
  const [pendingRemove, setPendingRemove] = useState(null)
  const [undo, setUndo] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!pluginContext) return undefined
    const timer = pluginContext.setTimeout(() => setQuery(searchInput.trim()), 250)
    return timer
  }, [searchInput])

  const entries = notebooks && Array.isArray(notebooks.entries) ? notebooks.entries : []
  const tags = Array.from(new Set(entries.flatMap((entry) => entry.tags || []))).sort()
  const filtered = entries
    .filter((entry) => {
      if (tag !== 'all' && !(entry.tags || []).includes(tag)) return false
      if (!query) return true
      const needle = query.toLowerCase()
      return [entry.excerpt, entry.note, entry.kind, (entry.tags || []).join(' ')]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle))
    })
    .slice()
    .sort((left, right) =>
      order === 'recent'
        ? String(right.created_at || '').localeCompare(String(left.created_at || ''))
        : String(left.created_at || '').localeCompare(String(right.created_at || ''))
    )

  const saveEdit = useCallback(async () => {
    if (!editing) return
    const payload = { entry_id: editing.entry_id }
    payload.note = editNote.trim() || null
    payload.tags = editTags
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean)
      .slice(0, 20)
    const response = await rpc('notebook.update', payload, {
      // The entry carries its own revision fence (0 for a fresh save), so the edit is fenced on the
      // row the user is editing rather than on the enrollment.
      expectedRevision: typeof editing.revision === 'number' ? editing.revision : 0,
      idempotencyKey: newOperationId('notebook-update')
    })
    if (!response.ok) {
      setError(response.error)
      return
    }
    setError(null)
    setEditing(null)
    onChanged()
  }, [editing, editNote, editTags, onChanged])

  const removeEntry = useCallback(async () => {
    if (!pendingRemove) return
    const entry = pendingRemove
    const response = await rpc('notebook.delete', { entry_id: entry.entry_id })
    setPendingRemove(null)
    if (!response.ok) {
      setError(response.error)
      return
    }
    setError(null)
    setUndo(entry)
    onChanged()
  }, [pendingRemove, onChanged])

  const undoRemove = useCallback(async () => {
    if (!undo) return
    const response = await rpc('notebook.save', {
      enrollment_id: undo.enrollment_id,
      objective_id: undo.objective_id,
      lesson_run_id: undo.lesson_run_id || null,
      kind: undo.kind,
      excerpt: undo.excerpt,
      note: undo.note,
      tags: undo.tags || [],
      source_ref: undo.source_ref || null
    })
    if (!response.ok) {
      setError(response.error)
      return
    }
    setUndo(null)
    onChanged()
  }, [undo, onChanged])

  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-3',
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(sdk.SearchField, {
            'aria-label': 'Search the notebook',
            containerClassName: 'max-w-sm min-w-0 flex-1',
            onChange: setSearchInput,
            placeholder: 'Search notes and excerpts',
            value: searchInput
          }),
          jsxs(sdk.Select, {
            value: tag,
            onValueChange: setTag,
            children: [
              jsx(
                sdk.SelectTrigger,
                {
                  'aria-label': 'Filter by tag',
                  className: 'w-40',
                  children: jsx(sdk.SelectValue, { placeholder: 'All tags' })
                },
                'trigger'
              ),
              jsx(
                sdk.SelectContent,
                {
                  children: [{ id: 'all', label: 'All tags' }]
                    .concat(tags.map((item) => ({ id: item, label: item })))
                    .map((option) => jsx(sdk.SelectItem, { value: option.id, children: option.label }, option.id))
                },
                'content'
              )
            ]
          }),
          jsx(sdk.SegmentedControl, {
            onChange: setOrder,
            options: [
              { id: 'recent', label: 'Recently saved' },
              { id: 'oldest', label: 'Oldest first' }
            ],
            sizing: 'content',
            value: order
          })
        ]
      }),
      error ? jsx(ErrorLine, { error }) : null,
      undo
        ? jsxs('div', {
            className: 'flex flex-wrap items-center justify-between gap-2 border border-(--ui-stroke-tertiary) px-3 py-2',
            children: [
              jsx('div', {
                className: 'text-xs text-(--ui-text-secondary)',
                children: 'Removed from the notebook. The lesson and any media it referenced are untouched.'
              }),
              jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: undoRemove, children: 'Undo (restores as a new entry)' })
            ]
          })
        : null,

      filtered.length === 0
        ? jsx(EmptyState, {
            title: entries.length === 0 ? 'Nothing saved yet' : 'No saved moment matches',
            description:
              entries.length === 0
                ? 'Save an explanation, visual or quiz moment and it will appear here.'
                : 'Your saved moments are still here; this search or tag just excludes them.',
            children:
              entries.length === 0
                ? jsx(sdk.Button, {
                    variant: 'secondary',
                    size: 'sm',
                    onClick: () => onOpenSection(row.evidence_summary && row.evidence_summary.current_objective_id),
                    children: 'Go to the current lesson'
                  })
                : jsx(sdk.Button, {
                    variant: 'secondary',
                    size: 'sm',
                    onClick: () => {
                      setSearchInput('')
                      setQuery('')
                      setTag('all')
                    },
                    children: 'Clear search and tag'
                  })
          })
        : jsx('div', {
            className: 'flex flex-col',
            children: filtered.map((entry) =>
              jsxs(
                'div',
                {
                  className: 'flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
                  children: [
                    jsx('p', {
                      className: 'max-w-prose whitespace-pre-wrap break-words text-sm leading-relaxed',
                      children: entry.excerpt || entry.note || entry.kind
                    }),
                    entry.note && entry.excerpt
                      ? jsx('p', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: entry.note })
                      : null,
                    jsxs('div', {
                      className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-tertiary)',
                      children: [
                        jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: entry.kind }),
                        (entry.tags || []).map((item) => jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: item }, item)),
                        jsx('span', { children: `saved ${whenLabel(entry.created_at)}` })
                      ]
                    }),
                    jsxs('div', {
                      className: 'flex flex-wrap items-center gap-1',
                      children: [
                        jsx(sdk.Button, {
                          variant: 'text',
                          size: 'sm',
                          onClick: () => onOpenSection(entry.objective_id),
                          children: 'Open in textbook'
                        }),
                        jsx(sdk.Button, {
                          variant: 'text',
                          size: 'sm',
                          onClick: () => onOpenSection(entry.objective_id),
                          children: 'Continue from here'
                        }),
                        supports('notebook.update')
                          ? jsx(sdk.Button, {
                              variant: 'text',
                              size: 'sm',
                              onClick: () => {
                                setEditing(entry)
                                setEditNote(entry.note || '')
                                setEditTags((entry.tags || []).join(', '))
                              },
                              children: 'Edit note and tags'
                            })
                          : null,
                        jsx(sdk.Button, {
                          variant: 'text',
                          size: 'sm',
                          onClick: () => setPendingRemove(entry),
                          children: 'Remove from notebook'
                        })
                      ]
                    }),
                    editing && editing.entry_id === entry.entry_id
                      ? jsxs('div', {
                          className: 'flex flex-col gap-2 border-t border-(--ui-stroke-tertiary) pt-2',
                          children: [
                            jsx('label', {
                              htmlFor: 'cb-edit-note',
                              className: 'text-xs font-medium text-(--ui-text-secondary)',
                              children: 'Your note'
                            }),
                            jsx(sdk.Textarea, {
                              id: 'cb-edit-note',
                              rows: 2,
                              value: editNote,
                              onChange: (event) => setEditNote(event.target.value)
                            }),
                            jsx('label', {
                              htmlFor: 'cb-edit-tags',
                              className: 'text-xs font-medium text-(--ui-text-secondary)',
                              children: 'Tags (comma separated)'
                            }),
                            jsx(sdk.Input, {
                              id: 'cb-edit-tags',
                              value: editTags,
                              onChange: (event) => setEditTags(event.target.value)
                            }),
                            jsxs('div', {
                              className: 'flex items-center gap-2',
                              children: [
                                jsx(sdk.Button, { variant: 'default', size: 'sm', onClick: saveEdit, children: 'Save changes' }),
                                jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: () => setEditing(null), children: 'Cancel' })
                              ]
                            })
                          ]
                        })
                      : null
                  ]
                },
                entry.entry_id
              )
            )
          }),

      jsx(sdk.ConfirmDialog, {
        open: Boolean(pendingRemove),
        title: 'Remove this moment from the notebook?',
        description:
          'Only the notebook entry is removed. The lesson, its attempts and any media it referenced are kept.',
        confirmLabel: 'Remove entry',
        onClose: () => setPendingRemove(null),
        onConfirm: removeEntry,
        children: null
      })
    ]
  })
}

/** Quizzes — past attempts with their original feedback, read-only until an explicit new version. */
function QuizzesView({ row, quizzes, implemented, onOpenSection, onChanged }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const [verdict, setVerdict] = useState('all')
  const [klass, setKlass] = useState('all')
  const [selectedId, setSelectedId] = useState(null)
  const [disputeNote, setDisputeNote] = useState('')
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [saveSeed, setSaveSeed] = useState(null)

  const attempts = quizzes && Array.isArray(quizzes.attempts) ? quizzes.attempts : []
  const filtered = attempts.filter((attempt) => {
    if (verdict !== 'all' && attempt.verdict !== verdict) return false
    if (klass !== 'all' && attempt.evidence_class !== klass) return false
    return true
  })
  const selected = filtered.find((attempt) => attempt.attempt_id === selectedId) || null

  const newVersion = useCallback(
    async (attempt) => {
      setError(null)
      setNotice(null)
      const response = await rpc(
        'progression.challenge_out',
        { enrollment_id: row.enrollment_id, objective_id: attempt.objective_id },
        { expectedRevision: row.revision }
      )
      if (!response.ok) {
        setError(response.error)
        return
      }
      setNotice('A new audited version of this check is open. The original attempt stays inspectable.')
      onChanged()
    },
    [row, onChanged]
  )

  const dispute = useCallback(async () => {
    if (!selected) return
    if (disputeNote.trim().length < 3) {
      setError({ code: 'VALIDATION_FAILED', message: 'Write at least a sentence explaining the dispute.' })
      return
    }
    const response = await rpc('attempt.dispute', { attempt_id: selected.attempt_id, note: disputeNote.trim() })
    if (!response.ok) {
      setError(response.error)
      return
    }
    setError(null)
    setDisputeNote('')
    setNotice('Dispute recorded. The original verdict is unchanged and the history is append-only.')
    onChanged()
  }, [selected, disputeNote, onChanged])

  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-3',
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(sdk.SegmentedControl, {
            onChange: setVerdict,
            options: [
              { id: 'all', label: 'All results' },
              { id: 'pass', label: 'Passed' },
              { id: 'partial', label: 'Partly there' },
              { id: 'not_yet', label: 'Not yet' },
              { id: 'needs_retry', label: 'Grading failed' }
            ],
            sizing: 'content',
            value: verdict
          }),
          jsx(sdk.SegmentedControl, {
            onChange: setKlass,
            options: [
              { id: 'all', label: 'All assistance' },
              { id: 'cold', label: 'Cold' },
              { id: 'hinted', label: 'Hinted' },
              { id: 'answer_shown', label: 'Answer shown' },
              { id: 'override', label: 'Override' }
            ],
            sizing: 'content',
            value: klass
          })
        ]
      }),

      notice ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: notice }) : null,
      error ? jsx(ErrorLine, { error }) : null,

      filtered.length === 0
        ? jsx(EmptyState, {
            title: attempts.length === 0 ? 'No quiz attempts yet' : 'No attempt matches',
            description:
              attempts.length === 0
                ? 'Answers you give in a lesson are recorded here with their original feedback.'
                : 'Your attempts are still here; these filters just exclude them.',
            children:
              attempts.length === 0
                ? null
                : jsx(sdk.Button, {
                    variant: 'secondary',
                    size: 'sm',
                    onClick: () => {
                      setVerdict('all')
                      setKlass('all')
                    },
                    children: 'Clear filters'
                  })
          })
        : jsx('div', {
            className: 'flex flex-col',
            children: filtered.map((attempt) =>
              jsxs(
                'div',
                {
                  className: 'flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
                  children: [
                    jsxs('div', {
                      className: 'flex flex-wrap items-center justify-between gap-2',
                      children: [
                        jsxs('div', {
                          className: 'flex flex-wrap items-center gap-2',
                          children: [
                            jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: VERDICT_COPY[attempt.verdict] || attempt.verdict }),
                            jsx(EvidenceClassText, { value: attempt.evidence_class }),
                            jsx('span', { className: 'text-xs text-(--ui-text-tertiary)', children: whenLabel(attempt.committed_at || attempt.created_at) })
                          ]
                        }),
                        jsx(sdk.Button, {
                          variant: 'text',
                          size: 'sm',
                          onClick: () => setSelectedId(attempt.attempt_id === selectedId ? null : attempt.attempt_id),
                          children: attempt.attempt_id === selectedId ? 'Close' : 'Open attempt'
                        })
                      ]
                    }),
                    attempt.answer && attempt.answer.text
                      ? jsx('p', { className: 'max-w-prose whitespace-pre-wrap break-words text-xs text-(--ui-text-secondary)', children: attempt.answer.text })
                      : null,
                    selectedId === attempt.attempt_id && selected
                      ? jsxs('div', {
                          className: 'flex flex-col gap-2 border-t border-(--ui-stroke-tertiary) pt-2',
                          children: [
                            jsx(QuietNote, { children: 'Reviewing is read-only. Nothing here consumes a retry or changes the old grade.' }),
                            (attempt.criteria || []).length > 0
                              ? jsx('ul', {
                                  className: 'flex flex-col gap-1',
                                  children: attempt.criteria.map((item, index) =>
                                    jsx(
                                      'li',
                                      {
                                        className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                                        children: `${item.met ? 'Met' : 'Not met'}: ${item.observed || item.id}`
                                      },
                                      `${item.id}-${index}`
                                    )
                                  )
                                })
                              : jsx(QuietNote, { children: 'No criterion detail was stored for this attempt.' }),
                            jsxs('div', {
                              className: 'flex flex-col',
                              children: [
                                jsx(StatusRow, {
                                  label: 'Grader',
                                  value: (attempt.grading_provenance && attempt.grading_provenance.grader) || 'not recorded'
                                }),
                                jsx(StatusRow, { label: 'Check version', value: `v${attempt.check_version}` }),
                                jsx(StatusRow, {
                                  label: 'Disputes',
                                  value: String((attempt.disputes || []).length)
                                })
                              ]
                            }),
                            (attempt.disputes || []).length > 0
                              ? jsxs('div', {
                                  className: 'flex flex-col gap-1',
                                  children: [
                                    jsx(sdk.PanelSectionLabel, { children: 'DISPUTE HISTORY' }),
                                    attempt.disputes.map((item) =>
                                      jsx(
                                        'div',
                                        { className: 'text-xs text-(--ui-text-secondary)', children: `${item.state} · ${whenLabel(item.created_at)} · ${item.note}` },
                                        item.id
                                      )
                                    )
                                  ]
                                })
                              : null,
                            jsxs('div', {
                              className: 'flex flex-wrap items-center gap-2',
                              children: [
                                jsx(sdk.Button, {
                                  variant: 'secondary',
                                  size: 'sm',
                                  onClick: () => onOpenSection(attempt.objective_id),
                                  children: 'Review lesson'
                                }),
                                supports('progression.challenge_out')
                                  ? jsx(sdk.Button, {
                                      variant: 'secondary',
                                      size: 'sm',
                                      onClick: () => newVersion(attempt),
                                      children: 'Try a new version'
                                    })
                                  : null,
                                supports('notebook.save')
                                  ? jsx(sdk.Button, {
                                      variant: 'secondary',
                                      size: 'sm',
                                      onClick: () =>
                                        setSaveSeed({
                                          excerpt: attempt.answer && attempt.answer.text ? attempt.answer.text : 'Quiz moment',
                                          kind: 'quiz_moment',
                                          source_ref: attempt.check_id
                                        }),
                                      children: 'Save to notebook'
                                    })
                                  : null
                              ]
                            }),
                            supports('attempt.dispute')
                              ? jsxs('div', {
                                  className: 'flex flex-col gap-2',
                                  children: [
                                    jsx('label', {
                                      htmlFor: 'cb-dispute',
                                      className: 'text-xs font-medium text-(--ui-text-secondary)',
                                      children: 'Dispute this grade'
                                    }),
                                    jsx(sdk.Textarea, {
                                      id: 'cb-dispute',
                                      rows: 2,
                                      value: disputeNote,
                                      onChange: (event) => setDisputeNote(event.target.value),
                                      placeholder: 'What did the grader get wrong?'
                                    }),
                                    jsx(sdk.Button, {
                                      variant: 'secondary',
                                      size: 'sm',
                                      disabled: !disputeNote.trim(),
                                      onClick: dispute,
                                      children: 'Record dispute'
                                    }),
                                    jsx(QuietNote, {
                                      children: 'A dispute never overwrites the original verdict; a re-grade would be a new operation.'
                                    })
                                  ]
                                })
                              : null
                          ]
                        })
                      : null
                  ]
                },
                attempt.attempt_id
              )
            )
          }),

      jsx(NotebookSaveDialog, {
        open: Boolean(saveSeed),
        seed: saveSeed,
        onClose: () => setSaveSeed(null),
        enrollmentId: row.enrollment_id,
        objectiveId: selected ? selected.objective_id : row.evidence_summary.current_objective_id,
        lessonRunId: null,
        implemented,
        onSaved: onChanged
      })
    ]
  })
}

/** Plan — the same objective state vocabulary, one flat list, no progress ring. */
function PlanView({ row, review, notebooks, outline, page, implemented, onOpenSection, onChanged }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const rows = sectionRows({ row, review, notebooks, outline, page })
  const reviewById = new Map(((review && review.items) || []).map((item) => [item.objective_id, item]))
  const [challengeError, setChallengeError] = useState(null)

  const challenge = useCallback(
    async (objectiveId) => {
      const response = await rpc(
        'progression.challenge_out',
        { enrollment_id: row.enrollment_id, objective_id: objectiveId },
        { expectedRevision: row.revision }
      )
      if (!response.ok) {
        setChallengeError(`${response.error.code}: ${describeError(response.error)}`)
        return
      }
      setChallengeError(null)
      onChanged()
    },
    [row, onChanged]
  )

  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-3',
    children: [
      jsx(QuietNote, {
        children:
          'Estimated sessions are planning aids, not promises. Only a cold independent result moves an objective to independent evidence.'
      }),
      challengeError ? jsx(ErrorLine, { error: { message: challengeError } }) : null,
      rows.length === 0
        ? jsx(EmptyState, {
            title: 'No objectives to show',
            description: 'The plan is not approved, or this build cannot read the objective list.'
          })
        : jsx('div', {
            className: 'flex flex-col',
            children: rows.map((entry) => {
              const item = reviewById.get(entry.objective_id)
              return jsxs(
                'div',
                {
                  className: 'flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
                  children: [
                    jsxs('div', {
                      className: 'flex flex-wrap items-center justify-between gap-2',
                      children: [
                        jsx('div', { className: 'min-w-0 break-words text-sm font-medium', children: entry.title }),
                        jsx(StateText, { state: entry.state || (item && item.state) || 'not_started' })
                      ]
                    }),
                    jsxs('div', {
                      className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-tertiary)',
                      children: [
                        entry.evidence_target ? jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: entry.evidence_target }) : null,
                        item ? jsx('span', { children: `next review ${whenLabel(item.due_at)}` }) : null,
                        item ? jsx('span', { children: `interval ${item.interval_days}d · step ${item.step}` }) : null
                      ]
                    }),
                    jsxs('div', {
                      className: 'flex flex-wrap items-center gap-1',
                      children: [
                        jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: () => onOpenSection(entry.objective_id), children: 'Open section' }),
                        supports('progression.challenge_out')
                          ? jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: () => challenge(entry.objective_id), children: 'Challenge out' })
                          : null
                      ]
                    })
                  ]
                },
                entry.objective_id
              )
            })
          }),
      jsx(QuietNote, {
        children:
          'Evidence criteria, attempt counts and dial edits need the objective read/write commands that this build does not publish yet; nothing is invented to fill the gap.'
      })
    ]
  })
}

/** Evidence — three linked layers, actual verdicts and provenance, no personality claims. */
function EvidenceView({ evidence, implemented, onOpenSection }) {
  if (!evidence) {
    return jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading the evidence layers' }) })
  }
  const l1 = evidence.l1 || { attempts: [], events: [] }
  const l2 = evidence.l2 || { objectives: [] }
  const l3 = evidence.l3 || { recommendations: [], as_of: null, is_persona: false }
  const disputes = (evidence.disputes && evidence.disputes.disputes) || []
  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-4',
    children: [
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(sdk.PanelSectionLabel, { children: 'L3 · CURRENT RECOMMENDATION' }),
          (l3.recommendations || []).length === 0
            ? jsx(QuietNote, { children: 'No recommendation was derived from the recorded evidence.' })
            : (l3.recommendations || []).map((item, index) =>
                jsxs(
                  'div',
                  {
                    className: 'flex flex-col gap-0.5 py-1',
                    children: [
                      jsx('div', { className: 'text-sm text-(--ui-text-secondary)', children: item.text }),
                      jsx('div', { className: 'text-xs text-(--ui-text-tertiary)', children: `basis: ${item.basis}` })
                    ]
                  },
                  `${item.kind}-${index}`
                )
              ),
          jsx(QuietNote, { children: `Revisable and derived from layer 2. Not a persona claim. As of ${whenLabel(l3.as_of)}.` })
        ]
      }),

      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(sdk.PanelSectionLabel, { children: 'L2 · OBJECTIVE EVIDENCE' }),
          (l2.objectives || []).length === 0
            ? jsx(QuietNote, { children: 'No approved-plan objective has evidence yet.' })
            : jsx('div', {
                className: 'flex flex-col',
                children: (l2.objectives || []).map((objective) =>
                  jsxs(
                    'div',
                    {
                      className: 'flex flex-wrap items-center justify-between gap-2 border-b border-(--ui-stroke-tertiary) py-1.5 last:border-b-0',
                      children: [
                        jsx('span', { className: 'min-w-0 break-words text-xs text-(--ui-text-secondary)', children: objective.title }),
                        jsxs('span', {
                          className: 'flex items-center gap-2',
                          children: [
                            jsx(sdk.Badge, { size: 'xs', variant: objective.independent ? 'outline' : 'muted', children: objective.independent ? 'independent' : 'no cold result' }),
                            jsx('button', {
                              type: 'button',
                              className: 'text-xs text-(--ui-text-secondary) underline-offset-2 hover:underline',
                              onClick: () => onOpenSection(objective.objective_id),
                              children: 'Open'
                            })
                          ]
                        })
                      ]
                    },
                    objective.objective_id
                  )
                )
              })
        ]
      }),

      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(sdk.PanelSectionLabel, { children: 'L1 · ATTEMPTS AND EVENTS' }),
          jsxs('div', {
            className: 'flex flex-col',
            children: [
              (l1.attempts || []).slice(0, 12).map((attempt) =>
                jsxs(
                  'div',
                  {
                    className: 'flex flex-wrap items-center justify-between gap-2 border-b border-(--ui-stroke-tertiary) py-1.5 text-xs last:border-b-0',
                    children: [
                      jsx('span', { className: 'text-(--ui-text-secondary)', children: whenLabel(attempt.committed_at || attempt.created_at) }),
                      jsxs('span', {
                        className: 'flex items-center gap-2',
                        children: [
                          jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: VERDICT_COPY[attempt.verdict] || attempt.verdict }),
                          jsx(EvidenceClassText, { value: attempt.evidence_class })
                        ]
                      })
                    ]
                  },
                  attempt.attempt_id
                )
              ),
              (l1.events || []).filter((event) => event.is_action).slice(0, 8).map((event) =>
                jsx(
                  'div',
                  {
                    className: 'flex flex-wrap items-center justify-between gap-2 py-1 text-xs text-(--ui-text-tertiary)',
                    children: jsxs('span', {
                      className: 'flex items-center gap-2',
                      children: [jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: event.kind }), jsx('span', { children: whenLabel(event.created_at) })]
                    })
                  },
                  event.evidence_id
                )
              )
            ]
          }),
          disputes.length > 0
            ? jsxs('div', {
                className: 'flex flex-col',
                children: [
                  jsx(sdk.PanelSectionLabel, { children: 'DISPUTES' }),
                  disputes.slice(0, 8).map((item) =>
                    jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: `${item.state} · ${whenLabel(item.created_at)} · ${item.note}` }, item.id)
                  )
                ]
              })
            : null
        ]
      })
    ]
  })
}

/** Sources — support status in words; unverified is never a green "verified". */
function SourcesView({ page }) {
  const sources = (page && page.sources) || []
  if (!page) return jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading this course’s sources' }) })
  if (sources.length === 0) {
    return jsx(EmptyState, {
      title: 'No sources recorded',
      description: 'The backend recorded no source rows for this course. Nothing is being presented as cited.'
    })
  }
  return jsx('div', {
    className: 'flex max-w-3xl flex-col',
    children: sources.map((source) =>
      jsxs(
        'div',
        {
          className: 'flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
          children: [
            jsx('div', { className: 'text-sm font-medium', children: source.title }),
            jsxs('div', {
              className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-tertiary)',
              children: [
                jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: source.source_type }),
                jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: source.support_status }),
                jsx('span', { children: source.fetched_at ? `fetched ${whenLabel(source.fetched_at)}` : 'fetch date unknown' }),
                source.published_at ? jsx('span', { children: `published ${whenLabel(source.published_at)}` }) : null
              ]
            }),
            source.url
              ? jsx('div', {
                  className: 'text-xs text-(--ui-text-tertiary)',
                  children: 'External content opens only when you choose it; the URL is shown, not fetched.'
                })
              : null
          ]
        },
        source.source_id
      )
    )
  })
}
/**
 * Course detail — the durable page for one enrollment.
 *
 * Local tabs, not more sidebar destinations. At wide widths the view switcher is a segmented
 * control; below ~47.5rem it collapses into one labelled picker so the strip can never clip.
 */
function CourseDetail({ row, implemented, profile, onBack, onChanged }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const [view, setView] = useState('overview')
  const [objectiveId, setObjectiveId] = useState(
    (row.evidence_summary && row.evidence_summary.current_objective_id) || null
  )
  const [openSectionId, setOpenSectionId] = useState(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)

  const outline = useRpcQuery(
    'course.outline',
    { enrollment_id: row.enrollment_id },
    `outline-${row.enrollment_id}`,
    supports('course.outline')
  )
  const review = useRpcQuery(
    'review.queue',
    { enrollment_id: row.enrollment_id, cap: 25, include_upcoming: true },
    `review-${row.enrollment_id}`,
    supports('review.queue')
  )
  const notebooks = useRpcQuery(
    'notebook.list',
    { enrollment_id: row.enrollment_id },
    `notebook-${row.enrollment_id}`,
    supports('notebook.list')
  )
  const quizzes = useRpcQuery(
    'quiz.history',
    { enrollment_id: row.enrollment_id },
    `quiz-${row.enrollment_id}`,
    supports('quiz.history')
  )
  const evidence = useRpcQuery(
    'evidence.inspect',
    { enrollment_id: row.enrollment_id, limit: 100 },
    `evidence-${row.enrollment_id}`,
    supports('evidence.inspect')
  )
  const page = useRpcQuery(
    'lesson.page',
    { enrollment_id: row.enrollment_id, objective_id: objectiveId },
    `page-${row.enrollment_id}-${objectiveId}`,
    supports('lesson.page') && Boolean(objectiveId)
  )

  const refresh = useCallback(() => {
    review.reload()
    notebooks.reload()
    quizzes.reload()
    evidence.reload()
    page.reload()
    if (outline) outline.reload()
    if (onChanged) onChanged()
  }, [review, notebooks, quizzes, evidence, page, outline, onChanged])

  const openSection = useCallback((nextObjectiveId) => {
    if (nextObjectiveId) setObjectiveId(nextObjectiveId)
    setOpenSectionId(nextObjectiveId || null)
    setView('textbook')
  }, [])

  const closeSection = useCallback(() => setOpenSectionId(null), [])

  const selectView = useCallback((nextView) => {
    setView(nextView)
    if (nextView === 'textbook') setOpenSectionId(null)
  }, [])

  const startLesson = useCallback(
    async (mode) => {
      const target = objectiveId || (row.evidence_summary && row.evidence_summary.current_objective_id)
      if (!target) {
        setNotice('This course has no current objective yet; approve the plan first.')
        return
      }
      setBusy(true)
      setNotice(null)
      const response = await rpc(
        'lesson.begin',
        { enrollment_id: row.enrollment_id, objective_id: target, mode },
        {
          idempotencyKey: `cb-lesson-${target}-${mode}-${
            mode === 'fresh' ? newOperationId('run') : 'resume'
          }`
        }
      )
      setBusy(false)
      if (!response.ok) {
        setNotice(`${response.error.code}: ${describeError(response.error)}`)
        return
      }
      const outcome = response.result
      if (mode === 'resume' && outcome.resume && outcome.resume.available && outcome.binding) {
        const opened = await resumeBoundSession(outcome.binding)
        setNotice(opened.ok ? 'Resumed the bound lesson chat.' : opened.message)
        return
      }
      armPendingBind({
        enrollmentId: row.enrollment_id,
        objectiveId: target,
        lessonRunId: outcome.lesson_run_id,
        profile: profile || currentScope().profile
      })
      const started = startLessonChat(profile || currentScope().profile)
      setNotice(
        started
          ? 'A governed run is ready. Its chat binds after your first message.'
          : 'This Desktop build cannot open a new chat. Start one from the sidebar, then resume this section.'
      )
      refresh()
    },
    [objectiveId, row, profile, refresh]
  )

  const rows = sectionRows({ row, review: review.data, notebooks: notebooks.data, outline: outline.data, page: page.data })
  const currentTitle =
    page.data && page.data.section && page.data.section.title
      ? page.data.section.title
      : (row.next_step && row.next_step.label) || 'No objective recorded yet'

  let body
  if (view === 'overview') {
    body = jsx(OverviewView, {
      row,
      page: page.data,
      review: review.data,
      quizzes: quizzes.data,
      implemented,
      onOpenSection: openSection,
      onResume: () => startLesson(row.next_step && row.next_step.kind === 'resume_lesson' ? 'resume' : 'resume')
    })
  } else if (view === 'textbook') {
    body = jsx(TextbookView, {
      row,
      page: page.data,
      pageState: page,
      review: review.data,
      notebooks: notebooks.data,
      outline: outline.data,
      implemented,
      openSectionId,
      onOpenSection: openSection,
      onCloseSection: closeSection,
      onChanged: refresh
    })
  } else if (view === 'notebook') {
    body = notebooks.status === 'error' && !notebooks.data
      ? jsx(sdk.ErrorState, {
          title: 'The notebook could not be read',
          description: `${notebooks.error && notebooks.error.code ? notebooks.error.code + ': ' : ''}${describeError(notebooks.error)}`,
          children: jsx(sdk.Button, { variant: 'secondary', onClick: notebooks.reload, children: 'Try again' })
        })
      : jsx(NotebookView, {
          row,
          notebooks: notebooks.data,
          implemented,
          onOpenSection: openSection,
          onChanged: refresh
        })
  } else if (view === 'quizzes') {
    body = jsx(QuizzesView, {
      row,
      quizzes: quizzes.data,
      implemented,
      onOpenSection: openSection,
      onChanged: refresh
    })
  } else if (view === 'plan') {
    body = jsx(PlanView, {
      row,
      review: review.data,
      notebooks: notebooks.data,
      outline: outline.data,
      page: page.data,
      implemented,
      onOpenSection: openSection,
      onChanged: refresh
    })
  } else if (view === 'evidence') {
    body = jsx(EvidenceView, { evidence: evidence.data, implemented, onOpenSection: openSection })
  } else {
    body = jsx(SourcesView, { page: page.data })
  }

  const nextKind = (row.next_step && row.next_step.kind) || 'start_lesson'

  return jsxs('div', {
    className: 'flex flex-col gap-3',
    children: [
      jsx(sdk.Button, { className: 'self-start', variant: 'text', size: 'sm', onClick: onBack, children: 'All courses' }),
      jsxs('div', {
        className: 'flex flex-wrap items-start justify-between gap-3',
        children: [
          jsxs('div', {
            className: 'flex min-w-0 flex-col gap-1',
            children: [
              jsx('h2', { className: 'min-w-0 break-words text-sm font-semibold', children: row.title }),
              jsxs('div', {
                className: 'flex flex-wrap items-center gap-2',
                children: [
                  jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: (RECIPE_COPY[row.recipe] || {}).title || row.recipe }),
                  row.warning ? jsx(WarningBadge, { warning: row.warning }) : null,
                  jsx('span', { className: 'text-xs text-(--ui-text-tertiary)', children: currentTitle })
                ]
              })
            ]
          }),
          jsxs('div', {
            className: 'flex shrink-0 flex-wrap items-center justify-end gap-2',
            children: [
              jsx(sdk.Button, {
                variant: 'default',
                size: 'sm',
                disabled: busy,
                onClick: () => startLesson(nextKind === 'resume_lesson' ? 'resume' : 'fresh'),
                children: busy ? 'Opening' : nextKind === 'resume_lesson' ? 'Resume lesson' : 'Start lesson'
              })
            ]
          })
        ]
      }),
      notice ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: notice }) : null,

      jsx('div', {
        className: 'hidden min-[47.5rem]:block',
        children: jsx(sdk.SegmentedControl, {
          onChange: selectView,
          options: LEARNING_VIEWS,
          sizing: 'content',
          value: view
        })
      }),
      jsxs('div', {
        className: 'flex items-center gap-2 min-[47.5rem]:hidden',
        children: [
          jsx('label', {
            htmlFor: 'cb-view-picker',
            className: 'text-xs font-medium text-(--ui-text-secondary)',
            children: 'View'
          }),
          jsxs(sdk.Select, {
            value: view,
            onValueChange: selectView,
            children: [
              jsx(
                sdk.SelectTrigger,
                {
                  id: 'cb-view-picker',
                  className: 'w-44',
                  'aria-label': 'Course view',
                  children: jsx(sdk.SelectValue, {})
                },
                'trigger'
              ),
              jsx(
                sdk.SelectContent,
                {
                  children: LEARNING_VIEWS.map((option) =>
                    jsx(sdk.SelectItem, { value: option.id, children: option.label }, option.id)
                  )
                },
                'content'
              )
            ]
          })
        ]
      }),

      review.data && review.data.total_overdue > 0 && view !== 'overview'
        ? jsx('div', {
            className: 'text-xs text-(--ui-text-secondary)',
            children: `${review.data.total_overdue} objective(s) are due for review.`
          })
        : null,
      rows.length > 0 ? null : null,
      body
    ]
  })
}

/**
 * The bound lesson pane.
 *
 * Scope is the focused chat's stored session id → binding → enrollment. Nothing here falls back to
 * "the most recent lesson", and an unrelated chat gets an explicit entry action, never a stale
 * objective from another enrollment.
 */
function LessonPaneBody({ binding, storedId }) {
  const profile = binding.profile || currentScope().profile
  const library = useRpcQuery(
    'library.list',
    { filter: 'all', limit: 100 },
    `pane-library-${binding.enrollment_id}`,
    backendSupports('library.list')
  )
  const row =
    library.data && Array.isArray(library.data.items)
      ? library.data.items.find((item) => item.enrollment_id === binding.enrollment_id)
      : null
  // The chat is bound to ONE objective. Showing the enrollment's current objective instead would
  // make a chat bound to section 3 display section 1 (and section 1's detached run) as its lesson.
  const objectiveId =
    binding.objective_id || (row && row.evidence_summary ? row.evidence_summary.current_objective_id : null)
  const page = useRpcQuery(
    'lesson.page',
    { enrollment_id: binding.enrollment_id, objective_id: objectiveId },
    `pane-page-${binding.enrollment_id}-${objectiveId}`,
    backendSupports('lesson.page') && Boolean(objectiveId)
  )
  const review = useRpcQuery(
    'review.queue',
    { enrollment_id: binding.enrollment_id, cap: 1, include_upcoming: false },
    `pane-review-${binding.enrollment_id}`,
    backendSupports('review.queue')
  )
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  const [overrideOpen, setOverrideOpen] = useState(false)

  const revision = page.data ? page.data.revision : row ? row.revision : 0
  const check = useOpenCheck({
    enrollmentId: binding.enrollment_id,
    objectiveId,
    revision,
    enabled: Boolean(objectiveId) && backendSupports('check.open') && Boolean(page.data)
  })

  const section = page.data && page.data.section
  const runtime = page.data && page.data.runtime
  const bindingStatus = (runtime && runtime.binding_status) || binding.status

  const resume = useCallback(async () => {
    const outcome = await resumeBoundSession(binding)
    if (!outcome.ok) {
      host.notify({ kind: 'warning', message: outcome.message })
      return
    }
    setNotice('Focused the bound lesson chat.')
  }, [binding])

  const freshRun = useCallback(async () => {
    if (!objectiveId) return
    setBusy(true)
    setNotice(null)
    const response = await rpc(
      'lesson.begin',
      { enrollment_id: binding.enrollment_id, objective_id: objectiveId, mode: 'fresh' },
      { idempotencyKey: `cb-pane-run-${objectiveId}-${newOperationId('run')}` }
    )
    setBusy(false)
    if (!response.ok) {
      setNotice(`${response.error.code}: ${describeError(response.error)}`)
      return
    }
    const outcome = response.result
    armPendingBind({
      enrollmentId: binding.enrollment_id,
      objectiveId,
      lessonRunId: outcome.lesson_run_id,
      profile
    })
    const started = startLessonChat(profile)
    setNotice(
      started
        ? 'A fresh governed run is ready. Its chat binds after your first message.'
        : 'This Desktop build cannot open a new chat; start one from the sidebar.'
    )
    page.reload()
    library.reload()
  }, [objectiveId, binding, profile, page, library])

  const abandon = useCallback(async () => {
    if (!runtime || !runtime.binding_id) return
    const response = await rpc('binding.abandon', {
      binding_id: runtime.binding_id,
      reason: 'Abandoned from the Coursebook pane.'
    })
    if (!response.ok) {
      setNotice(`${response.error.code}: ${describeError(response.error)}`)
      return
    }
    setNotice('Binding abandoned. Start a new governed run when you are ready.')
    page.reload()
  }, [runtime, page])

  if (library.status === 'error' && !library.data) {
    return jsx(sdk.PanelEmpty, {
      icon: 'warning',
      title: 'Cannot read this lesson',
      description: library.error ? `${library.error.code}: ${describeError(library.error)}` : 'The course list could not be read.',
      action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: library.reload, children: 'Try again' })
    })
  }
  if (!row) {
    return jsx(sdk.PanelEmpty, {
      icon: 'book',
      title: 'Bound, but not listed',
      description:
        'This chat is bound to an enrollment the library did not return. Nothing is guessed from that: reopen Coursebook to reconcile.',
      action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: () => host.navigate(ROUTE_PATH), children: 'Open Coursebook' })
    })
  }

  return jsxs('div', {
    className: 'flex flex-col gap-2',
    children: [
      jsxs('div', {
        className: 'flex flex-col gap-1',
        children: [
          jsx('div', { className: 'min-w-0 break-words text-xs font-medium text-(--ui-text-secondary)', children: row.title }),
          section ? jsx('div', { className: 'text-sm font-medium leading-snug', children: section.title }) : null,
          jsxs('div', {
            className: 'flex flex-wrap items-center gap-1.5',
            children: [
              section ? jsx(StateText, { state: section.state }) : null,
              bindingStatus !== 'active'
                ? jsx(sdk.Badge, { size: 'xs', variant: 'warn', children: `binding ${bindingStatus}` })
                : null
            ]
          })
        ]
      }),

      bindingStatus !== 'active'
        ? jsxs('div', {
            className: 'flex flex-col gap-1 border border-(--ui-stroke-tertiary) px-2 py-1.5',
            children: [
              jsx('div', {
                className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                children: `This lesson’s chat binding is ${bindingStatus}. Submit is disabled until it is reconciled.`
              }),
              jsxs('div', {
                className: 'flex flex-wrap items-center gap-1',
                children: [
                  jsx(sdk.Button, { variant: 'secondary', size: 'sm', disabled: busy, onClick: resume, children: 'Reattach' }),
                  jsx(sdk.Button, { variant: 'text', size: 'sm', disabled: busy, onClick: freshRun, children: 'Start a new run' }),
                  runtime && runtime.binding_id && backendSupports('binding.abandon')
                    ? jsx(sdk.Button, { variant: 'text', size: 'sm', disabled: busy, onClick: abandon, children: 'Abandon binding' })
                    : null
                ]
              })
            ]
          })
        : null,

      notice ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: notice }) : null,

      jsx(sdk.PanelSectionLabel, { children: 'CURRENT CHECK' }),
      page.status === 'error'
        ? jsx('div', {
            className: 'text-xs text-(--ui-text-secondary)',
            children: page.error ? `${page.error.code}: ${describeError(page.error)}` : 'The lesson page could not be read.'
          })
        : check.status === 'error'
          ? jsx('div', {
              className: 'text-xs text-(--ui-text-secondary)',
              children: check.error ? `${check.error.code}: ${describeError(check.error)}` : 'No check could be opened.'
            })
          : check.status === 'loading' && !check.check
            ? jsx(sdk.Loader, { label: 'Opening the current check' })
            : jsx(AttemptControls, {
                enrollmentId: binding.enrollment_id,
                objectiveId,
                check: check.check,
                revision,
                implemented: backendWire.implemented,
                bindingState: bindingStatus,
                onCommitted: () => {
                  page.reload()
                  library.reload()
                  review.reload()
                }
              }),

      jsxs('div', {
        className: 'flex flex-wrap items-center gap-1.5 border-t border-(--ui-stroke-tertiary) pt-2',
        children: [
          jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: resume, children: 'Open lesson chat' }),
          jsx(sdk.Button, {
            variant: 'text',
            size: 'sm',
            onClick: async () => {
              const sent = await continueLesson(binding)
              setNotice(sent)
            },
            children: 'Continue lesson'
          }),
          jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: () => host.navigate(ROUTE_PATH), children: 'Full course' })
        ]
      }),

      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-tertiary)',
        children: [
          jsx('span', {
            children: review.data
              ? review.data.total_overdue > 0
                ? `${review.data.total_overdue} due for review`
                : 'Nothing due'
              : 'Review queue unavailable'
          }),
          jsx('span', { children: '·' }),
          jsx('span', { children: `${Number((row.evidence_summary || {}).independent || 0)} independent` }),
          jsx('span', { children: '·' }),
          jsx('span', { children: `${(page.data && page.data.sources ? page.data.sources.length : 0)} sources` })
        ]
      })
    ]
  })
}

/**
 * "Continue lesson" is a real user turn, not automation: the chat keeps teaching, and the backend
 * gate decides whether anything is graded. If no mounted composer owns the bound chat, the action
 * reports that instead of pretending a message was sent.
 */
async function continueLesson(binding) {
  if (!binding || !binding.stored_session_id) return 'This lesson has no durable chat to continue yet.'
  if (binding.status !== 'active') return `This lesson’s chat binding is ${binding.status}; reconcile it first.`
  if (typeof host.openSession === 'function') {
    try {
      await host.openSession(binding.stored_session_id, { profile: binding.profile || undefined })
    } catch (error) {
      return `Opening the lesson chat failed: ${describeError(error)}`
    }
  }
  const composer = host.composer
  if (composer && typeof composer.submit === 'function') {
    const sent = composer.submit(binding.stored_session_id, 'Continue the lesson.')
    if (sent) return 'Asked the lesson chat to continue.'
    return 'The lesson chat is not on screen, so nothing was sent. Open it and continue there.'
  }
  return 'This Desktop build cannot send a message; open the lesson chat and continue there.'
}
/**
 * Parent Studio (UX_SPEC §10) — the parent-led authoring surface.
 *
 * This is not a chat persona and never a child-facing surface. The parent is the operator: they
 * write a brief, review and approve the plan, generate the pages, approve the exact lesson set by
 * hash, export the printable files and record a reflection. Every screen here reads from cb.rpc v6
 * (`parent.*`); a control exists only when the method behind it is in `/runtime`.
 *
 * Two rules are load-bearing and deliberately visible in the UI rather than assumed:
 *   - the learner pages tab can never contain an answer key (`answer_guide` is a different role,
 *     served in its own tab, and export keeps it out of `LEARNER_FACING_ROLES`);
 *   - plan approval and final approval are different gates, with different hashes and different
 *     consequences, so they are two differently-labelled actions and two different badges.
 */

const STUDIO_SETTINGS = [
  { id: 'home', label: 'Home' },
  { id: 'classroom', label: 'Classroom' },
  { id: 'outdoors', label: 'Outdoors' },
  { id: 'car', label: 'Car' },
  { id: 'library', label: 'Library' },
  { id: 'community', label: 'Community' },
  { id: 'other', label: 'Other' }
]
const STUDIO_VISUALS = [
  { id: 'none', label: 'No visuals' },
  { id: 'diagrams', label: 'Diagrams' },
  { id: 'illustrations', label: 'Illustrations' }
]
const STUDIO_NARRATION = [
  { id: 'none', label: 'No narration' },
  { id: 'script', label: 'A script I read aloud' }
]
const STUDIO_AGE_BANDS = ['3-5', '5-7', '7-9', '8-10', '10-12', '12-14', '14-16', '16+'].map((band) => ({
  id: band,
  label: band
}))
const STUDIO_DIFFICULTIES = [
  { id: 'easy', label: 'Too easy' },
  { id: 'about_right', label: 'About right' },
  { id: 'too_hard', label: 'Too hard' }
]
const STUDIO_VIEWS = [
  { id: 'brief', label: 'Brief' },
  { id: 'plan', label: 'Plan' },
  { id: 'blueprint', label: 'Pages' },
  { id: 'export', label: 'Export' },
  { id: 'reflection', label: 'Reflection' }
]
const STUDIO_TABS = [
  { id: 'parent_guide', label: 'Parent guide' },
  { id: 'learner_pages', label: 'Learner pages' },
  { id: 'answers', label: 'Answers' },
  { id: 'narration', label: 'Audio & visuals' },
  { id: 'sources', label: 'Sources' }
]
const EVIDENCE_TARGET_OPTIONS = [
  { id: 'recall', label: 'Recall' },
  { id: 'comprehension', label: 'Comprehension' },
  { id: 'production', label: 'Production' },
  { id: 'discrimination', label: 'Discrimination' },
  { id: 'procedure', label: 'Procedure' },
  { id: 'transfer', label: 'Transfer' }
]
const PLAN_STATE_COPY = {
  draft: 'Plan draft',
  approved: 'Plan approved',
  superseded: 'Plan superseded'
}
const APPROVAL_STATE_COPY = {
  none: 'Lesson set not approved',
  active: 'Lesson set approved',
  superseded: 'Changes need review'
}
/** `parent_export_status.blocked_reason` → the sentence the export panel shows. */
const EXPORT_BLOCKED_COPY = {
  no_final_approval: 'The generated lesson set has not been approved. Approval is a separate step from approving the plan.',
  changes_need_review: 'Changes need review. The approved lesson set no longer matches the pages shown, so export is blocked until you approve them again.',
  plan_not_approved: 'The plan is not approved, so there are no pages to export.',
  no_generated_content: 'No lesson pages have been generated yet.'
}
/** `parent.export` refusals include ones the blueprint read cannot predict. */
const EXPORT_REFUSAL_COPY = {
  plan_not_approved: 'The plan is not approved.',
  no_final_approval: 'Approve the exact lesson set first.',
  changes_need_review: 'The pages changed after approval; review and approve them again.',
  no_generated_content: 'There is no generated content to export.',
  course_pack_backed: 'This course came from an imported pack. Use Library → Export pack for it.',
  export_not_exportable: 'The generated lessons do not meet the pack’s teaching minima yet.',
  export_write_failed: 'The files could not be written. Nothing was exported.'
}
const JOB_TERMINAL_STATES = new Set([
  'completed',
  'failed',
  'cancelled',
  'completed_late',
  'interrupted_requires_retry'
])

function blankBrief() {
  return {
    title: '',
    goal: '',
    starting_point: '',
    age_band: '8-10',
    reading_level: '',
    duration_minutes: 25,
    setting: 'home',
    materials: [],
    exclusions: [],
    supervision: '',
    desired_pages: 3,
    desired_visuals: 'diagrams',
    narration: 'script',
    locale: null,
    egress_acknowledged: false,
    redaction_requested: false
  }
}

/** The typed brief from `parent.brief.get`, defaulted field by field for the form. */
function briefForForm(brief) {
  const base = blankBrief()
  if (!brief || typeof brief !== 'object') return base
  return {
    ...base,
    ...brief,
    materials: Array.isArray(brief.materials) ? brief.materials : [],
    exclusions: Array.isArray(brief.exclusions) ? brief.exclusions : [],
    // A copied brief still has to be acknowledged in this form: the disclosure is shown again.
    egress_acknowledged: false
  }
}

/** One item per line → a bounded string array the contract accepts. */
function linesToList(value, maxItems, maxLength) {
  const items = String(value || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, maxItems)
    .map((line) => line.slice(0, maxLength))
  return items
}

/** A stale fence is recoverable: the backend names the revision it expects next. */
function staleRevision(response) {
  const error = (response && response.error) || {}
  const value = error.current_revision !== undefined ? error.current_revision : (error.details || {}).current_revision
  return typeof value === 'number' ? value : null
}

function StudioField({ id, label, hint, children, error }) {
  return jsxs('div', {
    className: 'flex flex-col gap-1',
    children: [
      jsx('label', { className: 'text-xs font-medium text-(--ui-text-secondary)', htmlFor: id, children: label }),
      children,
      error
        ? jsx('p', { className: 'text-xs text-(--ui-text-secondary)', children: error })
        : hint
          ? jsx('p', { className: 'text-xs text-(--ui-text-tertiary)', children: hint })
          : null
    ]
  })
}

function StudioSelect({ id, label, value, options, onChange, hint }) {
  return jsx(StudioField, {
    id,
    label,
    hint,
    children: jsxs(sdk.Select, {
      value,
      onValueChange: onChange,
      children: [
        jsx(sdk.SelectTrigger, { id, className: 'w-full', children: jsx(sdk.SelectValue, {}) }, 'trigger'),
        jsx(
          sdk.SelectContent,
          {
            children: options.map((option) => jsx(sdk.SelectItem, { value: option.id, children: option.label }, option.id))
          },
          'content'
        )
      ]
    })
  })
}

function StudioCheck({ id, checked, onChange, children }) {
  return jsxs('label', {
    className: 'flex items-start gap-2 text-xs leading-relaxed text-(--ui-text-secondary)',
    htmlFor: id,
    children: [
      jsx('input', { id, type: 'checkbox', checked, onChange: (event) => onChange(Boolean(event.target.checked)) }),
      jsx('span', { children })
    ]
  })
}

/** Plan-level badge: this is the outline gate, never the lesson-set gate. */
function PlanStateBadge({ plan }) {
  const state = plan && plan.state
  if (!state) return jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: 'No plan yet' })
  return jsx(sdk.Badge, {
    size: 'xs',
    variant: state === 'approved' ? 'muted' : 'outline',
    children: `${PLAN_STATE_COPY[state] || state} · v${plan.version}`
  })
}

/** Lesson-set badge: `active` binds exact bytes, `superseded` means the pages moved on. */
function ApprovalBadge({ approval }) {
  const state = (approval && approval.state) || 'none'
  return jsx(sdk.Badge, {
    size: 'xs',
    variant: state === 'active' ? 'muted' : state === 'superseded' ? 'warn' : 'outline',
    children: APPROVAL_STATE_COPY[state] || state
  })
}

function JobStateText({ job }) {
  if (!job) return null
  const progress = job.progress || {}
  const message = progress.message ? ` — ${progress.message}` : ''
  if (job.state === 'queued') {
    return jsx('div', { className: 'text-xs text-(--ui-text-tertiary)', children: 'Queued. The job runner picks it up on its next tick; nothing is spent until it starts.' })
  }
  if (job.state === 'running' || job.state === 'cancel_requested' || job.state === 'cancelling') {
    return jsx('div', {
      className: 'text-xs text-(--ui-text-secondary)',
      children: `Working${progress.stage ? ` (${progress.stage})` : ''}${message}`
    })
  }
  if (job.state === 'completed' || job.state === 'completed_late') {
    return jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: `Finished${message}` })
  }
  if (job.state === 'interrupted_requires_retry') {
    return jsx('div', {
      className: 'text-xs text-(--ui-text-secondary)',
      children: 'Interrupted: the worker stopped mid-job. Its checkpoint was kept; run the stage again to finish it.'
    })
  }
  const error = job.error || {}
  return jsxs('div', {
    className: 'flex flex-col gap-1 text-xs text-(--ui-text-secondary)',
    children: [
      jsx('div', { children: `Failed${error.code ? ` (${error.code})` : ''}.` }),
      error.message ? jsx('div', { className: 'text-(--ui-text-tertiary)', children: error.message }) : null
    ]
  })
}

/**
 * Poll one job until it settles. The poll never navigates and never focuses anything: it re-renders
 * the line the parent is already looking at and calls `onSettled` so the caller can re-read.
 */
function useStudioJob(jobId, onSettled) {
  const [job, setJob] = useState(null)
  const settled = useRef(null)
  const settledHandler = useRef(onSettled)
  settledHandler.current = onSettled

  useEffect(() => {
    if (!jobId) {
      setJob(null)
      return undefined
    }
    let cancelled = false
    let cancelTimer = null
    settled.current = null
    const poll = async () => {
      const response = await rpc('jobs.get', { job_id: jobId })
      if (cancelled) return
      if (!response.ok) {
        setJob({ job_id: jobId, state: 'unknown', error: response.error })
        cancelTimer = pluginContext.setTimeout(poll, 5000)
        return
      }
      const next = response.result.job
      setJob(next)
      if (JOB_TERMINAL_STATES.has(next.state)) {
        if (settled.current !== next.state) {
          settled.current = next.state
          if (settledHandler.current) settledHandler.current(next)
        }
        return
      }
      cancelTimer = pluginContext.setTimeout(poll, 3000)
    }
    cancelTimer = pluginContext.setTimeout(poll, 0)
    return () => {
      cancelled = true
      if (cancelTimer) cancelTimer()
    }
  }, [jobId])

  return job
}

function StudioJobLine({ jobId, onSettled }) {
  const job = useStudioJob(jobId, onSettled)
  if (!jobId) return null
  return jsx('div', { className: 'flex flex-col gap-1', 'data-cb-job-id': jobId, children: jsx(JobStateText, { job }) })
}

/** The studio list: authored parent courses only. Imported packs stay in Library. */
function StudioList({ implemented, onCreate, onOpen, reloadSignal }) {
  const supported = Boolean(implemented && implemented.has('library.list'))
  const query = useRpcQuery(
    'library.list',
    { filter: 'all', recipe: 'parent', limit: 50, sort: 'recent' },
    `studio-list-${reloadSignal}`,
    supported
  )
  const rows = query.data && Array.isArray(query.data.items) ? query.data.items : []

  if (!supported) {
    return jsx(EmptyState, {
      title: 'Parent Studio needs the v6 authoring methods',
      description:
        'This backend does not list library.list, so no authored course can be read. Update the plugin instead of using a placeholder screen.',
      children: jsx(sdk.Button, { variant: 'secondary', onClick: openCapabilities, children: 'Open Capabilities' })
    })
  }
  if (query.status === 'loading' && !query.data) {
    return jsx('div', { className: 'py-10', children: jsx(sdk.Loader, { label: 'Reading your parent courses' }) })
  }
  if (query.status === 'error' && !query.data) {
    return jsx(sdk.ErrorState, {
      title: 'Your parent courses could not be read',
      description: `${query.error && query.error.code ? query.error.code + ': ' : ''}${describeError(query.error)}`,
      children: jsx(sdk.Button, { variant: 'secondary', onClick: query.reload, children: 'Try again' })
    })
  }
  if (rows.length === 0) {
    return jsx(EmptyState, {
      title: 'No parent lesson packs yet',
      description:
        'A brief describes the child’s age and reading level, the setting and materials, what to leave out, and what you want to teach. Coursebook drafts a plan for you to review before anything is generated.',
      children: jsx(sdk.Button, { onClick: onCreate, variant: 'default', children: 'Write a lesson brief' })
    })
  }

  return jsxs('div', {
    className: 'flex flex-col',
    children: [
      jsx('div', { className: 'pb-1 text-xs text-(--ui-text-tertiary)', children: `${rows.length} authored course${rows.length === 1 ? '' : 's'}` }),
      ...rows.map((row) =>
        jsx(
          sdk.ListRow,
          {
            action: jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: () => onOpen(row), children: 'Open studio' }),
            description: jsxs('span', {
              className: 'flex flex-wrap items-center gap-2',
              children: [
                jsx('span', { children: 'Parent preparation' }),
                jsx('span', { children: `updated ${whenLabel(row.updated_at)}` })
              ]
            }),
            onClick: () => onOpen(row),
            title: jsx('span', { className: 'min-w-0 break-words', children: row.title })
          },
          row.enrollment_id
        )
      )
    ]
  })
}

/**
 * The §10 brief. Every field the contract requires is here, in the order a parent thinks in:
 * what they want, who it is for, where it happens and with what, what to avoid, and only then the
 * provider/egress disclosure that must be acknowledged before submit is possible.
 */
function StudioBriefForm({ initial, note, supported, onCancel, onCreated }) {
  const [form, setForm] = useState(() => briefForForm(initial))
  const [materialsText, setMaterialsText] = useState(() => (initial && initial.materials ? initial.materials.join('\n') : ''))
  const [exclusionsText, setExclusionsText] = useState(() => (initial && initial.exclusions ? initial.exclusions.join('\n') : ''))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const update = useCallback((key, value) => setForm((previous) => ({ ...previous, [key]: value })), [])

  const materials = linesToList(materialsText, 20, 120)
  const exclusions = linesToList(exclusionsText, 20, 200)
  const problems = []
  if (!form.title.trim()) problems.push('A title is required.')
  if (!form.goal.trim()) problems.push('Say what you want the child to be able to do.')
  if (!form.age_band) problems.push('Pick an age band.')
  if (!form.reading_level.trim()) problems.push('Say the reading level in your own words.')
  const duration = Number(form.duration_minutes)
  if (!Number.isFinite(duration) || duration < 5 || duration > 600) problems.push('Duration must be between 5 and 600 minutes.')
  const pages = Number(form.desired_pages)
  if (!Number.isFinite(pages) || pages < 1 || pages > 40) problems.push('Desired pages must be between 1 and 40.')
  if (!form.egress_acknowledged) problems.push('Acknowledge the provider/egress disclosure before submitting.')

  const submit = useCallback(async () => {
    setBusy(true)
    setError(null)
    const brief = {
      ...form,
      title: form.title.trim(),
      goal: form.goal.trim(),
      starting_point: form.starting_point.trim() ? form.starting_point.trim() : null,
      reading_level: form.reading_level.trim(),
      duration_minutes: Number(form.duration_minutes),
      desired_pages: Number(form.desired_pages),
      materials,
      exclusions,
      supervision: form.supervision.trim(),
      locale: form.locale || null,
      egress_acknowledged: true,
      redaction_requested: Boolean(form.redaction_requested)
    }
    const response = await rpc('parent.brief.create', { brief }, { idempotencyKey: newOperationId('brief') })
    setBusy(false)
    if (!response.ok) {
      setError({ code: response.error && response.error.code, message: describeError(response.error) })
      return
    }
    onCreated({ ...response.result, title: brief.title })
  }, [form, materials, exclusions, onCreated])

  return jsxs('div', {
    className: 'flex max-w-2xl flex-col gap-4',
    children: [
      jsxs('div', {
        className: 'flex flex-col gap-1',
        children: [
          jsx('h2', { className: 'text-sm font-semibold', children: initial ? 'Duplicate this brief' : 'Write a lesson brief' }),
          jsx(QuietNote, {
            children:
              'You are the operator. Coursebook prepares the material for you to teach: there is no child chat, no child persona and no grading of the child. Everything here is a plan you review before any page is generated.'
          }),
          note
            ? jsx('div', {
                className: 'mt-1 border-l border-(--ui-stroke-tertiary) pl-3 text-xs leading-relaxed text-(--ui-text-secondary)',
                children: `From your last reflection: ${note}`
              })
            : null
        ]
      }),

      jsx(sdk.PanelSectionLabel, { children: 'WHAT AND WHO' }),
      jsx(StudioField, {
        id: 'cb-brief-title',
        label: 'Title',
        hint: 'How this course appears in your list.',
        children: jsx(sdk.Input, {
          id: 'cb-brief-title',
          maxLength: 200,
          value: form.title,
          onChange: (event) => update('title', event.target.value),
          placeholder: 'Kitchen fractions for a 9-year-old'
        })
      }),
      jsx(StudioField, {
        id: 'cb-brief-goal',
        label: 'What should the child be able to do afterwards?',
        hint: 'Concrete beats aspirational. One skill, described as an action you can watch.',
        children: jsx(sdk.Textarea, {
          id: 'cb-brief-goal',
          rows: 3,
          value: form.goal,
          onChange: (event) => update('goal', event.target.value),
          placeholder: 'Halve and quarter a real object and explain each cut.'
        })
      }),
      jsx(StudioField, {
        id: 'cb-brief-start',
        label: 'Starting point and content prerequisites',
        hint: 'What they can already do, and anything they must have read or seen first.',
        children: jsx(sdk.Textarea, {
          id: 'cb-brief-start',
          rows: 2,
          value: form.starting_point || '',
          onChange: (event) => update('starting_point', event.target.value),
          placeholder: 'Counts to 100, follows a recipe with help.'
        })
      }),
      jsxs('div', {
        className: 'grid gap-3 sm:grid-cols-2',
        children: [
          jsx(StudioSelect, {
            id: 'cb-brief-age',
            label: 'Age band',
            value: form.age_band,
            options: STUDIO_AGE_BANDS,
            onChange: (value) => update('age_band', value)
          }),
          jsx(StudioField, {
            id: 'cb-brief-reading',
            label: 'Reading level',
            hint: 'Your words are enough: “Year 3, short sentences”.',
            children: jsx(sdk.Input, {
              id: 'cb-brief-reading',
              maxLength: 120,
              value: form.reading_level,
              onChange: (event) => update('reading_level', event.target.value),
              placeholder: 'Year 3, short decodable sentences'
            })
          })
        ]
      }),

      jsx(sdk.PanelSectionLabel, { children: 'WHERE, HOW LONG, WITH WHAT' }),
      jsxs('div', {
        className: 'grid gap-3 sm:grid-cols-3',
        children: [
          jsx(StudioSelect, {
            id: 'cb-brief-setting',
            label: 'Setting',
            value: form.setting,
            options: STUDIO_SETTINGS,
            onChange: (value) => update('setting', value)
          }),
          jsx(StudioField, {
            id: 'cb-brief-duration',
            label: 'Minutes',
            children: jsx(sdk.Input, {
              id: 'cb-brief-duration',
              type: 'number',
              min: 5,
              max: 600,
              value: String(form.duration_minutes),
              onChange: (event) => update('duration_minutes', event.target.value)
            })
          }),
          jsx(StudioField, {
            id: 'cb-brief-pages',
            label: 'Pages',
            children: jsx(sdk.Input, {
              id: 'cb-brief-pages',
              type: 'number',
              min: 1,
              max: 40,
              value: String(form.desired_pages),
              onChange: (event) => update('desired_pages', event.target.value)
            })
          })
        ]
      }),
      jsx(StudioField, {
        id: 'cb-brief-materials',
        label: 'Materials you have',
        hint: 'One per line. Up to 20. Safety notes are written against this list.',
        children: jsx(sdk.Textarea, {
          id: 'cb-brief-materials',
          rows: 3,
          value: materialsText,
          onChange: (event) => setMaterialsText(event.target.value),
          placeholder: 'one apple\nplastic knife\nmeasuring cup'
        })
      }),
      jsx(StudioSelect, {
        id: 'cb-brief-visuals',
        label: 'Visuals',
        value: form.desired_visuals,
        options: STUDIO_VISUALS,
        onChange: (value) => update('desired_visuals', value)
      }),
      jsx(StudioSelect, {
        id: 'cb-brief-narration',
        label: 'Narration',
        value: form.narration,
        options: STUDIO_NARRATION,
        onChange: (value) => update('narration', value),
        hint: 'A narration script is text you read aloud; it is not an audio file.'
      }),

      jsx(sdk.PanelSectionLabel, { children: 'EXCLUSIONS AND SUPERVISION' }),
      jsx(StudioField, {
        id: 'cb-brief-exclusions',
        label: 'Leave these out',
        hint: 'One per line: foods, topics, activities, anything the child must not meet here.',
        children: jsx(sdk.Textarea, {
          id: 'cb-brief-exclusions',
          rows: 3,
          value: exclusionsText,
          onChange: (event) => setExclusionsText(event.target.value),
          placeholder: 'no nuts\nno timed pressure'
        })
      }),
      jsx(StudioField, {
        id: 'cb-brief-supervision',
        label: 'Supervision and safety',
        hint: 'Who holds what, what the adult must do, what the child may not do alone.',
        children: jsx(sdk.Textarea, {
          id: 'cb-brief-supervision',
          rows: 2,
          value: form.supervision,
          onChange: (event) => update('supervision', event.target.value),
          placeholder: 'An adult holds the knife; the child places the pieces.'
        })
      }),

      jsx(sdk.PanelSectionLabel, { children: 'BEFORE YOU PASTE: PROVIDER AND EGRESS' }),
      jsxs('div', {
        className: 'flex flex-col gap-2 border-l-2 border-(--ui-stroke-secondary) pl-3',
        children: [
          jsx('p', {
            className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
            children:
              'This brief is sent to the model provider configured for this Hermes profile so the plan can be drafted. Coursebook stores no provider key and sends the brief nowhere else. Anything you paste can appear in the generated pages — do not paste a child’s full name, address, school or anything you would not hand to a provider.'
          }),
          jsx(StudioCheck, {
            id: 'cb-brief-egress',
            checked: form.egress_acknowledged,
            onChange: (value) => update('egress_acknowledged', value),
            children: 'I have read this and want to send this brief to the provider.'
          }),
          jsx(StudioCheck, {
            id: 'cb-brief-redaction',
            checked: Boolean(form.redaction_requested),
            onChange: (value) => update('redaction_requested', value),
            children: 'Ask for identifying details to be redacted where it is possible.'
          })
        ]
      }),

      problems.length > 0
        ? jsxs('div', {
            className: 'flex flex-col gap-1',
            children: [
              jsx(sdk.PanelSectionLabel, { children: 'BEFORE SUBMITTING' }),
              ...problems.map((problem) => jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: problem }, problem))
            ]
          })
        : null,
      error
        ? jsxs('div', {
            className: 'flex flex-col gap-1 text-xs text-(--ui-text-secondary)',
            children: [
              jsx('div', { children: `${error.code ? error.code + ': ' : ''}${error.message}` }),
              jsx('div', { className: 'text-(--ui-text-tertiary)', children: 'The brief was not saved and no job was queued.' })
            ]
          })
        : null,

      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(sdk.Button, {
            variant: 'default',
            disabled: busy || problems.length > 0 || !supported,
            onClick: submit,
            children: busy ? 'Saving the brief' : 'Create the course and queue the plan'
          }),
          jsx(sdk.Button, { variant: 'secondary', onClick: onCancel, children: 'Cancel' })
        ]
      }),
      !supported
        ? jsx('div', { className: 'text-xs text-(--ui-text-tertiary)', children: 'This backend does not register parent.brief.create.' })
        : null
    ]
  })
}

/** The view switcher: canonical tab strip when there is width, labelled Select when there is not. */
function StudioViewPicker({ id, label, value, options, onChange }) {
  return jsxs('div', {
    className: 'flex flex-col gap-2',
    children: [
      jsx('div', {
        className: 'hidden min-[47.5rem]:block',
        children: jsx(sdk.SegmentedControl, { onChange, options, sizing: 'content', value })
      }),
      jsxs('div', {
        className: 'flex items-center gap-2 min-[47.5rem]:hidden',
        children: [
          jsx('label', { htmlFor: id, className: 'text-xs font-medium text-(--ui-text-secondary)', children: label }),
          jsxs(sdk.Select, {
            value,
            onValueChange: onChange,
            children: [
              jsx(sdk.SelectTrigger, { id, className: 'w-44', 'aria-label': label, children: jsx(sdk.SelectValue, {}) }, 'trigger'),
              jsx(
                sdk.SelectContent,
                { children: options.map((option) => jsx(sdk.SelectItem, { value: option.id, children: option.label }, option.id)) },
                'content'
              )
            ]
          })
        ]
      })
    ]
  })
}

const APPROVAL_INVALIDATION_COPY = {
  plan_edited: 'You edited the plan after approving the lesson set.',
  content_changed: 'The generated pages changed after you approved them.',
  course_edited: 'You changed the course title or goal after approving the lesson set.',
  replaced: 'A newer approval replaced this one.'
}

/** "Changes need review" — the banner is derived from the approval row, never from local state. */
function StudioReviewBanner({ approval, exportStatus }) {
  if (!approval || approval.state !== 'superseded') return null
  return jsxs('div', {
    className: 'flex flex-col gap-1 border-l-2 border-(--ui-stroke-secondary) pl-3',
    role: 'status',
    children: [
      jsx('div', { className: 'text-xs font-semibold', children: 'Changes need review' }),
      jsx('div', {
        className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
        children:
          APPROVAL_INVALIDATION_COPY[approval.invalidated_reason] ||
          'The lesson set you approved no longer matches the current pages.'
      }),
      jsx('div', {
        className: 'text-xs text-(--ui-text-tertiary)',
        children: exportStatus && exportStatus.blocked_reason
          ? EXPORT_BLOCKED_COPY[exportStatus.blocked_reason] || `Export is blocked (${exportStatus.blocked_reason}).`
          : 'Approve the current lesson set before exporting.'
      })
    ]
  })
}

/** The brief recap. It is a read: v6 has no brief edit verb, so the honest action is Duplicate. */
function StudioBriefView({ briefQuery, course, planJobId, onJobSettled, onDuplicate, reflections }) {
  const brief = briefQuery.data && briefQuery.data.brief
  if (briefQuery.status === 'loading' && !briefQuery.data) {
    return jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading the brief' }) })
  }
  if (!brief) {
    return jsx(sdk.ErrorState, {
      title: 'This course has no parent brief',
      description:
        'It was not created by parent.brief.create, or the job row that stores it is gone. Nothing is reconstructed from a form.',
      children: jsx(sdk.Button, { variant: 'secondary', onClick: briefQuery.reload, children: 'Try again' })
    })
  }
  const settingsLabel = (STUDIO_SETTINGS.find((item) => item.id === brief.setting) || {}).label || brief.setting
  const rows = [
    { label: 'Goal', value: brief.goal },
    { label: 'Starting point', value: brief.starting_point || '—' },
    { label: 'Age band', value: brief.age_band },
    { label: 'Reading level', value: brief.reading_level },
    { label: 'Setting', value: settingsLabel },
    { label: 'Duration', value: `${brief.duration_minutes} minutes` },
    { label: 'Materials', value: (brief.materials || []).join(', ') || 'None listed' },
    { label: 'Exclusions', value: (brief.exclusions || []).join(', ') || 'None listed' },
    { label: 'Supervision', value: brief.supervision || '—' },
    { label: 'Pages / visuals / narration', value: `${brief.desired_pages} pages · ${brief.desired_visuals} · ${brief.narration}` },
    { label: 'Provider disclosure acknowledged', value: brief.egress_acknowledged ? 'yes' : 'no' },
    { label: 'Redaction requested', value: brief.redaction_requested ? 'yes' : 'no' }
  ]
  const plane = (briefQuery.data && briefQuery.data.plan_job) || {}
  const latestProposal =
    reflections && Array.isArray(reflections.reflections)
      ? reflections.reflections.find((item) => item.apply_to_next_draft && item.revisit_note)
      : null

  return jsxs('div', {
    className: 'flex max-w-2xl flex-col gap-4',
    children: [
      jsx(QuietNote, {
        children:
          'You are the operator of this course. Coursebook drafted material for you to teach; the child never chats with it. A brief is immutable once stored — changing the teaching comes from editing the plan, and copying this brief makes a new course.'
      }),
      jsx(sdk.PanelSectionLabel, { children: 'THE BRIEF' }),
      jsxs('div', {
        className: 'flex flex-col',
        children: rows.map((row) => jsx(PackReviewLine, { label: row.label, value: row.value }, row.label))
      }),
      jsx(sdk.PanelSectionLabel, { children: 'PLAN JOB' }),
      jsxs('div', {
        className: 'flex flex-col gap-1',
        children: [
          jsx(PackReviewLine, { label: 'Job', value: plane.job_id || '—' }),
          jsx(PackReviewLine, { label: 'Submitted', value: plane.submitted_at ? whenLabel(plane.submitted_at) : '—' }),
          jsx(StudioJobLine, { jobId: planJobId, onSettled: onJobSettled })
        ]
      }),
      latestProposal
        ? jsxs('div', {
            className: 'flex flex-col gap-1 border-l border-(--ui-stroke-tertiary) pl-3',
            children: [
              jsx('div', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: 'A note from your last reflection' }),
              jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: latestProposal.revisit_note }),
              jsx('div', {
                className: 'text-xs text-(--ui-text-tertiary)',
                children: 'It is shown here as a proposal. It is not applied to any brief unless you copy one.'
              })
            ]
          })
        : null,
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(sdk.Button, { variant: 'default', onClick: () => onDuplicate(brief, null), children: 'Duplicate brief' }),
          latestProposal
            ? jsx(sdk.Button, {
                variant: 'secondary',
                onClick: () => onDuplicate(brief, latestProposal.revisit_note),
                children: 'Duplicate with the reflection note'
              })
            : null
        ]
      })
    ]
  })
}

/**
 * The plan working view: outline and activities on the left, sources and review notes on the
 * right. The parent can edit every meaningful field of a **draft** plan; an approved plan is only
 * changed by starting a new plan version, so approval always binds exact bytes.
 */
function StudioPlanView({
  course,
  revision,
  onRevision,
  outline,
  book,
  brief,
  planJobId,
  onJobSettled,
  onChanged,
  supported
}) {
  const plan = outline.data && outline.data.plan
  const objectives = (outline.data && outline.data.objectives) || []
  // `course.outline.plan.plan_hash` echoes the digest generation stored with the plan document,
  // while `plan.approve` / `parent.plan.edit` fence on the digest recomputed from the plan rows.
  // `parent.blueprint.read` serves the recomputed one, so that is the value the studio sends.
  const planHash =
    (book && book.data && book.data.plan && book.data.plan.plan_hash) || (plan && plan.plan_hash) || null
  const [order, setOrder] = useState(null)
  const [editing, setEditing] = useState(false)
  const [drafts, setDrafts] = useState({})
  const [added, setAdded] = useState([])
  const [removed, setRemoved] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [lessonJobId, setLessonJobId] = useState(null)

  // The editor's displayed order. Local until Save changes sends it as a permutation.
  useEffect(() => setOrder(null), [outline.data])
  const displayObjectives = order
    ? order.map((id) => objectives.find((objective) => objective.objective_id === id)).filter(Boolean)
    : objectives

  const startEditing = useCallback(() => {
    const next = {}
    for (const objective of displayObjectives) {
      next[objective.objective_id] = {
        title: objective.title,
        evidence_target: objective.evidence_target
      }
    }
    setDrafts(next)
    setAdded([])
    setRemoved([])
    setError(null)
    setEditing(true)
  }, [displayObjectives])

  const cancelEditing = useCallback(() => {
    setEditing(false)
    setError(null)
  }, [])

  const savePlan = useCallback(async () => {
    if (!outline.data || !plan) return
    const edits = []
    for (const objective of displayObjectives) {
      const draft = drafts[objective.objective_id]
      if (!draft) continue
      const changedTitle = draft.title.trim() && draft.title.trim() !== objective.title
      const changedTarget = draft.evidence_target && draft.evidence_target !== objective.evidence_target
      if (changedTitle || changedTarget) {
        edits.push({
          objective_id: objective.objective_id,
          ...(changedTitle ? { title: draft.title.trim().slice(0, 300) } : {}),
          ...(changedTarget ? { evidence_target: draft.evidence_target } : {})
        })
      }
    }
    const survivingOrder = displayObjectives.map((objective) => objective.objective_id).filter((id) => !removed.includes(id))
    const orderChanged = displayObjectives.map((objective) => objective.objective_id).join('|') !== objectives.map((objective) => objective.objective_id).join('|')
    const payload = {
      enrollment_id: course.enrollment_id,
      plan_id: plan.plan_id,
      expected_plan_hash: planHash
    }
    if (edits.length > 0) payload.objective_edits = edits
    if (removed.length > 0) payload.remove_objective_ids = removed
    if (added.length > 0) {
      payload.add_objectives = added
        .filter((item) => item.title.trim())
        .map((item) => ({
          title: item.title.trim().slice(0, 300),
          evidence_target: item.evidence_target
        }))
    }
    if (removed.length > 0 || orderChanged) payload.order = survivingOrder
    if (!payload.objective_edits && !payload.remove_objective_ids && !payload.add_objectives && !payload.order) {
      setError('Nothing changed yet.')
      return
    }
    setBusy(true)
    setError(null)
    const response = await rpc('parent.plan.edit', payload, {
      expectedRevision: revision,
      idempotencyKey: newOperationId('plan-edit')
    })
    setBusy(false)
    if (!response.ok) {
      const details = (response.error && response.error.details) || {}
      const nextRevision = staleRevision(response)
      if (nextRevision !== null) onRevision(nextRevision)
      setError(
        `${response.error && response.error.code ? response.error.code + ': ' : ''}${describeError(response.error)}` +
          (nextRevision !== null ? ' The course revision was refreshed; press Save changes again.' : '') +
          (details.reason === 'plan_not_draft'
            ? ' This plan is approved; start a new plan version to change it.'
            : details.reason === 'objective_in_use'
              ? ' That objective already has content or learning state, so it cannot be removed.'
              : '')
      )
      return
    }
    onRevision(response.result.revision)
    setEditing(false)
    setNotice('Plan saved. The edit marks the lesson set as needing review until it is approved again.')
    onChanged()
  }, [outline.data, plan, objectives, drafts, removed, added, course.enrollment_id, revision, onRevision, onChanged])

  const approvePlan = useCallback(async () => {
    if (!plan) return
    setBusy(true)
    setError(null)
    const response = await rpc(
      'plan.approve',
      { enrollment_id: course.enrollment_id, plan_id: plan.plan_id, plan_hash: planHash },
      { expectedRevision: revision, idempotencyKey: newOperationId('plan-approve') }
    )
    setBusy(false)
    if (!response.ok) {
      const nextRevision = staleRevision(response)
      if (nextRevision !== null) onRevision(nextRevision)
      setError(
        `${response.error.code}: ${describeError(response.error)}` +
          (nextRevision !== null ? ' The course revision was refreshed; press Approve plan again.' : '')
      )
      return
    }
    onRevision(response.result.revision)
    setNotice('Plan approved. The outline and activities are now fixed; the generated pages are a separate approval.')
    onChanged()
  }, [plan, course.enrollment_id, revision, onRevision, onChanged])

  const generateLessons = useCallback(async () => {
    if (!plan) return
    setBusy(true)
    setError(null)
    const response = await rpc(
      'jobs.create',
      { kind: 'plan', brief: { stage: 'lessons', plan_id: plan.plan_id } },
      { idempotencyKey: newOperationId('lessons') }
    )
    setBusy(false)
    if (!response.ok) {
      setError(`${response.error.code}: ${describeError(response.error)}`)
      return
    }
    setLessonJobId(response.result.job_id)
  }, [plan])

  const startRevision = useCallback(async () => {
    if (!plan || objectives.length === 0) return
    setBusy(true)
    setError(null)
    const response = await rpc(
      'plan.replan',
      {
        enrollment_id: course.enrollment_id,
        objective_changes: objectives.map((objective) => ({ objective_id: objective.objective_id, change: 'keep' }))
      },
      { expectedRevision: revision, idempotencyKey: newOperationId('replan') }
    )
    setBusy(false)
    if (!response.ok) {
      const nextRevision = staleRevision(response)
      if (nextRevision !== null) onRevision(nextRevision)
      setError(
        `${response.error.code}: ${describeError(response.error)}` +
          (nextRevision !== null ? ' The course revision was refreshed; press Start a new plan version again.' : '')
      )
      return
    }
    onRevision(response.result.revision)
    setNotice('A new draft plan version was created. The approved lesson set stops applying until the new plan and its pages are approved.')
    onChanged()
    startEditing()
  }, [plan, objectives, course.enrollment_id, revision, onRevision, onChanged, startEditing])

  const settled = useCallback(
    (job) => {
      if (job && (job.state === 'completed' || job.state === 'completed_late')) onChanged()
      else onJobSettled(job)
    },
    [onChanged, onJobSettled]
  )

  if (outline.status === 'loading' && !outline.data) {
    return jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading the plan' }) })
  }
  if (outline.status === 'error' && !outline.data) {
    return jsx(sdk.ErrorState, {
      title: 'The plan could not be read',
      description: `${outline.error && outline.error.code ? outline.error.code + ': ' : ''}${describeError(outline.error)}`,
      children: jsx(sdk.Button, { variant: 'secondary', onClick: outline.reload, children: 'Try again' })
    })
  }
  if (!plan || objectives.length === 0) {
    return jsx(EmptyState, {
      title: 'No plan yet',
      description: planJobId
        ? 'The plan job is still working. This screen fills itself when the plan is written; nothing is shown from a template.'
        : 'No plan job is attached to this course, so there is nothing to review. Start a new brief.',
      children: planJobId ? jsx(StudioJobLine, { jobId: planJobId, onSettled }) : null
    })
  }

  const isDraft = plan.state === 'draft'
  const contentReady = Boolean(book && book.data && book.data.tabs && (book.data.tabs.learner_pages || []).length > 0)
  const setting = brief && brief.brief ? brief.brief.setting : null
  const sources = (book && book.data && book.data.sources) || []

  return jsxs('div', {
    className: 'flex flex-col gap-4',
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-center justify-between gap-2',
        children: [
          jsxs('div', {
            className: 'flex flex-wrap items-center gap-2',
            children: [
              jsx(PlanStateBadge, { plan }),
              jsx('span', { className: 'text-xs text-(--ui-text-tertiary)', children: `plan ${String(planHash || '').slice(0, 19)}…` })
            ]
          }),
          jsxs('div', {
            className: 'flex flex-wrap items-center gap-2',
            children: [
              isDraft && !editing
                ? jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: startEditing, children: 'Edit plan' })
                : null,
              editing
                ? jsx(sdk.Button, { size: 'sm', variant: 'default', disabled: busy, onClick: savePlan, children: busy ? 'Saving' : 'Save changes' })
                : null,
              editing ? jsx(sdk.Button, { size: 'sm', variant: 'text', onClick: cancelEditing, children: 'Cancel' }) : null,
              isDraft && !editing
                ? jsx(sdk.Button, {
                    size: 'sm',
                    variant: 'default',
                    disabled: busy || !supported('plan.approve'),
                    onClick: approvePlan,
                    children: 'Approve plan'
                  })
                : null,
              !isDraft && !editing
                ? jsx(sdk.Button, {
                    size: 'sm',
                    variant: 'default',
                    disabled: busy || !supported('jobs.create'),
                    onClick: generateLessons,
                    children: contentReady ? 'Generate missing lessons' : 'Generate lessons'
                  })
                : null,
              !isDraft && !editing
                ? jsx(sdk.Button, {
                    size: 'sm',
                    variant: 'secondary',
                    disabled: busy || !supported('plan.replan'),
                    onClick: startRevision,
                    children: 'Start a new plan version'
                  })
                : null
            ]
          })
        ]
      }),

      jsx(QuietNote, {
        children:
          'Approving the plan approves this outline and these activities. It does not approve a single generated page: the lesson set is approved later, by its own hash.'
      }),
      notice ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: notice }) : null,
      error ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: error }) : null,
      planJobId ? jsx(StudioJobLine, { jobId: planJobId, onSettled: onJobSettled }) : null,
      lessonJobId ? jsx(StudioJobLine, { jobId: lessonJobId, onSettled: settled }) : null,

      !isDraft && contentReady
        ? jsx('div', {
            className: 'text-xs text-(--ui-text-tertiary)',
            children:
              'Re-running generation reuses every lesson already authored at this plan version and only authors what is missing. Nothing is paid for twice.'
          })
        : null,

      jsxs('div', {
        className: 'flex flex-col gap-4 min-[60rem]:flex-row min-[60rem]:items-start',
        children: [
          jsxs('div', {
            className: 'flex min-w-0 flex-1 flex-col gap-2',
            children: [
              jsx(sdk.PanelSectionLabel, { children: `OUTLINE AND ACTIVITIES (${objectives.length})` }),
              ...displayObjectives.map((objective, index) => {
                const draft = drafts[objective.objective_id] || {}
                const isRemoved = removed.includes(objective.objective_id)
                return jsxs(
                  'div',
                  {
                    className: `flex flex-col gap-1 border-t border-(--ui-stroke-tertiary) pt-2${isRemoved ? ' opacity-60' : ''}`,
                    'data-cb-objective': objective.objective_id,
                    children: [
                      jsxs('div', {
                        className: 'flex flex-wrap items-baseline justify-between gap-2',
                        children: [
                          jsx('div', {
                            className: 'flex min-w-0 items-baseline gap-2',
                            children: [
                              jsx('span', { className: 'shrink-0 text-xs tabular-nums text-(--ui-text-tertiary)', children: String(objective.ordinal).padStart(2, '0') }),
                              editing
                                ? jsx(sdk.Input, {
                                    'aria-label': `Objective ${objective.ordinal} title`,
                                    value: draft.title || '',
                                    onChange: (event) =>
                                      setDrafts((previous) => ({
                                        ...previous,
                                        [objective.objective_id]: { ...draft, title: event.target.value }
                                      })),
                                    className: 'min-w-0 flex-1'
                                  })
                                : jsx('span', { className: 'min-w-0 break-words text-sm', children: objective.title })
                            ]
                          }),
                          jsxs('div', {
                            className: 'flex shrink-0 items-center gap-2',
                            children: [
                              editing
                                ? jsx(sdk.Select, {
                                    value: draft.evidence_target || objective.evidence_target,
                                    onValueChange: (value) =>
                                      setDrafts((previous) => ({
                                        ...previous,
                                        [objective.objective_id]: { ...draft, evidence_target: value }
                                      })),
                                    children: [
                                      jsx(sdk.SelectTrigger, {
                                        'aria-label': `Objective ${objective.ordinal} evidence target`,
                                        className: 'w-36',
                                        children: jsx(sdk.SelectValue, {})
                                      }, 'trigger'),
                                      jsx(
                                        sdk.SelectContent,
                                        {
                                          children: EVIDENCE_TARGET_OPTIONS.map((option) =>
                                            jsx(sdk.SelectItem, { value: option.id, children: option.label }, option.id)
                                          )
                                        },
                                        'content'
                                      )
                                    ]
                                  })
                                : jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: objective.evidence_target }),
                              editing
                                ? jsxs('div', {
                                    className: 'flex items-center gap-1',
                                    children: [
                                      jsx(sdk.Button, {
                                        size: 'sm',
                                        variant: 'text',
                                        disabled: index === 0,
                                        onClick: () => {
                                          const ids = displayObjectives.map((item) => item.objective_id)
                                          const [moved] = ids.splice(index, 1)
                                          ids.splice(index - 1, 0, moved)
                                          setOrder(ids)
                                        },
                                        children: 'Up'
                                      }),
                                      jsx(sdk.Button, {
                                        size: 'sm',
                                        variant: 'text',
                                        disabled: index === displayObjectives.length - 1,
                                        onClick: () => {
                                          const ids = displayObjectives.map((item) => item.objective_id)
                                          const [moved] = ids.splice(index, 1)
                                          ids.splice(index + 1, 0, moved)
                                          setOrder(ids)
                                        },
                                        children: 'Down'
                                      }),
                                      jsx(sdk.Button, {
                                        size: 'sm',
                                        variant: 'text',
                                        onClick: () =>
                                          setRemoved((previous) =>
                                            previous.includes(objective.objective_id)
                                              ? previous.filter((id) => id !== objective.objective_id)
                                              : [...previous, objective.objective_id]
                                          ),
                                        children: isRemoved ? 'Keep' : 'Remove'
                                      })
                                    ]
                                  })
                                : null
                            ]
                          })
                        ]
                      }),
                      jsx('div', {
                        className: 'text-xs text-(--ui-text-tertiary)',
                        children: `State: ${objective.state} · check: ${objective.check_state}`
                      })
                    ]
                  },
                  objective.objective_id
                )
              }),
              editing
                ? jsxs('div', {
                    className: 'flex flex-col gap-2 border-t border-(--ui-stroke-tertiary) pt-2',
                    children: [
                      jsx(sdk.PanelSectionLabel, { children: 'ADD AN OBJECTIVE' }),
                      added.map((item, index) =>
                        jsxs(
                          'div',
                          {
                            className: 'flex flex-wrap items-center gap-2',
                            children: [
                              jsx(sdk.Input, {
                                'aria-label': `New objective ${index + 1} title`,
                                value: item.title,
                                onChange: (event) =>
                                  setAdded((previous) =>
                                    previous.map((entry, position) =>
                                      position === index ? { ...entry, title: event.target.value } : entry
                                    )
                                  ),
                                placeholder: 'Objective title',
                                className: 'min-w-0 flex-1'
                              }),
                              jsx(sdk.Select, {
                                value: item.evidence_target,
                                onValueChange: (value) =>
                                  setAdded((previous) =>
                                    previous.map((entry, position) =>
                                      position === index ? { ...entry, evidence_target: value } : entry
                                    )
                                  ),
                                children: [
                                  jsx(sdk.SelectTrigger, {
                                    'aria-label': `New objective ${index + 1} evidence target`,
                                    className: 'w-36',
                                    children: jsx(sdk.SelectValue, {})
                                  }, 'trigger'),
                                  jsx(
                                    sdk.SelectContent,
                                    {
                                      children: EVIDENCE_TARGET_OPTIONS.map((option) =>
                                        jsx(sdk.SelectItem, { value: option.id, children: option.label }, option.id)
                                      )
                                    },
                                    'content'
                                  )
                                ]
                              }),
                              jsx(sdk.Button, {
                                size: 'sm',
                                variant: 'text',
                                onClick: () => setAdded((previous) => previous.filter((_entry, position) => position !== index)),
                                children: 'Remove'
                              })
                            ]
                          },
                          `added-${index}`
                        )
                      ),
                      jsx(sdk.Button, {
                        size: 'sm',
                        variant: 'secondary',
                        className: 'self-start',
                        onClick: () => setAdded((previous) => [...previous, { title: '', evidence_target: 'recall' }]),
                        children: 'Add objective'
                      })
                    ]
                  })
                : null
            ]
          }),
          jsxs('div', {
            className: 'flex w-full shrink-0 flex-col gap-2 min-[60rem]:w-[20rem]',
            children: [
              jsx(sdk.PanelSectionLabel, { children: 'SOURCES AND REVIEW NOTES' }),
              jsx(QuietNote, {
                children:
                  'Sources come from the research run the plan job recorded. If research was unavailable the plan says so; no citation is invented here.'
              }),
              sources.length === 0
                ? jsx('div', { className: 'text-xs text-(--ui-text-tertiary)', children: 'No sources recorded for this course.' })
                : jsxs('div', {
                    className: 'flex flex-col',
                    children: sources.slice(0, 8).map((source) =>
                      jsx(
                        'div',
                        {
                          className: 'flex flex-col gap-0.5 border-b border-(--ui-stroke-tertiary) py-1.5 last:border-b-0',
                          children: [
                            jsx('div', { className: 'min-w-0 break-words text-xs', children: source.title }),
                            jsxs('div', {
                              className: 'flex flex-wrap items-center gap-2 text-[11px] text-(--ui-text-tertiary)',
                              children: [
                                jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: source.support_status }),
                                source.url ? jsx('span', { className: 'min-w-0 break-all', children: source.url }) : null
                              ]
                            })
                          ]
                        },
                        source.source_id
                      )
                    )
                  }),
              setting === 'car'
                ? jsx('div', {
                    className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                    children: 'Car activities are passenger-only. The driver never handles material.'
                  })
                : null,
              jsx('div', {
                className: 'text-xs leading-relaxed text-(--ui-text-tertiary)',
                children: 'A draft plan can be edited freely. An approved plan is changed only by starting a new version, so what you approved stays exact.'
              })
            ]
          })
        ]
      })
    ]
  })
}

/** The five tabs of §10, as declared text. Sources is its own tab and is always answered. */
function StudioBlueprintView({ book }) {
  const [tab, setTab] = useState('learner_pages')
  if (!book || book.status === 'loading') {
    return jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading the pages' }) })
  }
  if (book.status === 'error' && !book.data) {
    return jsx(sdk.ErrorState, {
      title: 'The pages could not be read',
      description: `${book.error && book.error.code ? book.error.code + ' : ' : ''}${describeError(book.error)}`,
      children: jsx(sdk.Button, { variant: 'secondary', onClick: book.reload, children: 'Try again' })
    })
  }
  const data = book.data || {}
  const tabs = data.tabs || {}
  const files = tabs[tab] || []
  const sources = data.sources || []
  const notice = {
    parent_guide: 'The parent guide is what you follow while teaching. It can quote the answer guide; the learner pages never do.',
    learner_pages: 'These are the learner pages. No answer key is included here — answers live in their own tab and are a different file role.',
    answers: 'The answer guide. It is served by course id only, so it is never reachable from a learner’s lesson surface, and export keeps it out of the learner pages.',
    narration: 'The narration script you read aloud. It is text, not an audio file, and it is also inside the parent guide.',
    sources: 'Every source the plan job recorded, with the support verdict it earned.'
  }[tab]

  return jsxs('div', {
    className: 'flex flex-col gap-3',
    children: [
      jsx(StudioViewPicker, { id: 'cb-studio-tab', label: 'Tab', value: tab, options: STUDIO_TABS, onChange: setTab }),
      jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: notice }),
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-tertiary)',
        children: [
          jsx('span', { children: `${files.length} file${files.length === 1 ? '' : 's'} in this tab` }),
          jsx('span', { children: `content hash ${String(data.content_hash || '').slice(0, 19)}…` })
        ]
      }),
      tab === 'sources'
        ? sources.length === 0
          ? jsx('div', { className: 'py-4 text-xs text-(--ui-text-tertiary)', children: 'No sources were recorded for this course.' })
          : jsx('div', {
              className: 'flex flex-col',
              children: sources.map((source) =>
                jsxs(
                  'div',
                  {
                    className: 'flex flex-col gap-0.5 border-t border-(--ui-stroke-tertiary) py-2',
                    children: [
                      jsx('div', { className: 'min-w-0 break-words text-sm', children: source.title }),
                      jsxs('div', {
                        className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-tertiary)',
                        children: [
                          jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: source.support_status }),
                          source.url ? jsx('a', { className: 'min-w-0 break-all underline', href: source.url, children: source.url }) : null,
                          jsx('span', { children: source.fetched_at ? whenLabel(source.fetched_at) : '' })
                        ]
                      })
                    ]
                  },
                  source.source_id
                )
              )
            })
        : files.length === 0
          ? jsx(EmptyState, {
              title: 'Nothing generated for this tab yet',
              description:
                tab === 'narration'
                  ? 'This course asked for no narration, or no lesson has been generated yet.'
                  : 'The plan must be approved and its lessons generated before this tab has text.',
              children: null
            })
          : jsx('div', {
              className: 'flex flex-col gap-4',
              children: files.map((file, index) =>
                jsxs(
                  'article',
                  {
                    className: 'flex flex-col gap-1.5 border-t border-(--ui-stroke-tertiary) pt-3',
                    'data-cb-blueprint-role': file.role,
                    children: [
                      jsxs('div', {
                        className: 'flex flex-wrap items-baseline justify-between gap-2',
                        children: [
                          jsx('h3', { className: 'min-w-0 break-words text-sm font-semibold', children: file.title }),
                          jsxs('div', {
                            className: 'flex shrink-0 items-center gap-2 text-xs text-(--ui-text-tertiary)',
                            children: [
                              jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: file.role }),
                              jsx('span', { children: bytesLabel(file.bytes) }),
                              file.truncated ? jsx(sdk.Badge, { size: 'xs', variant: 'warn', children: 'clipped' }) : null
                            ]
                          })
                        ]
                      }),
                      jsx('div', {
                        className: 'max-w-prose whitespace-pre-wrap break-words text-sm leading-relaxed',
                        children: file.text
                      }),
                      jsxs('div', {
                        className: 'text-[11px] break-all text-(--ui-text-tertiary)',
                        children: [`sha256 ${file.sha256}`, file.truncated ? ' · the served text was clipped at the tab limit' : '']
                      })
                    ]
                  },
                  `${file.role}-${index}`
                )
              )
            })
    ]
  })
}

/** Export: gated on the backend's own `export.blocked_reason`, files and downloads from the response. */
function StudioExportPanel({ course, book, supported, onChanged }) {
  const [formats, setFormats] = useState({ pack: true, pdf: true })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [exported, setExported] = useState(null)
  const [artifacts, setArtifacts] = useState({})
  const [approving, setApproving] = useState(false)
  const [approveError, setApproveError] = useState(null)

  const status = (book && book.data && book.data.export) || { ready: false, blocked_reason: 'no_generated_content' }
  const approval = (book && book.data && book.data.approval) || { state: 'none' }
  const plan = (book && book.data && book.data.plan) || {}
  const planHash = plan.plan_hash || null
  const contentHash = (book && book.data && book.data.content_hash) || null
  const chosen = [formats.pack ? 'pack' : null, formats.pdf ? 'pdf' : null].filter(Boolean)

  // Final approval is its own gate: the plan approved an outline, this approves the exact
  // generated lesson set, fenced by the content hash the backend served (never computed here).
  const approveFinal = useCallback(async () => {
    setApproving(true)
    setApproveError(null)
    const response = await rpc(
      'parent.final.approve',
      {
        enrollment_id: course.enrollment_id,
        plan_id: plan.plan_id,
        plan_hash: planHash,
        content_hash: contentHash
      },
      { idempotencyKey: newOperationId('parent-final-approve') }
    )
    setApproving(false)
    if (!response.ok) {
      setApproveError(describeError(response.error))
      return
    }
    if (typeof onChanged === 'function') onChanged()
  }, [course.enrollment_id, plan.plan_id, planHash, contentHash, onChanged])

  const run = useCallback(async () => {
    setBusy(true)
    setError(null)
    setExported(null)
    setArtifacts({})
    const response = await rpc(
      'parent.export',
      { enrollment_id: course.enrollment_id, formats: chosen },
      { idempotencyKey: newOperationId('parent-export') }
    )
    if (!response.ok) {
      setBusy(false)
      const details = (response.error && response.error.details) || {}
      setError({
        code: response.error && response.error.code,
        reason: details.reason,
        message: describeError(response.error),
        problems: Array.isArray(details.problems) ? details.problems : null
      })
      return
    }
    setExported(response.result)
    const next = {}
    for (const artifact of response.result.artifacts || []) {
      const facts = await rpc('artifact.get', { artifact_id: artifact.artifact_id })
      if (facts.ok) next[artifact.artifact_id] = facts.result
    }
    setArtifacts(next)
    setBusy(false)
  }, [course.enrollment_id, formats.pack, formats.pdf])

  return jsxs('div', {
    className: 'flex max-w-2xl flex-col gap-4',
    children: [
      jsx(sdk.PanelSectionLabel, { children: 'EXPORT GATE' }),
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(PackReviewLine, { label: 'Plan', value: (book && book.data && book.data.plan && `${book.data.plan.state} · v${book.data.plan.version}`) || '—' }),
          jsx(PackReviewLine, { label: 'Lesson set approval', value: APPROVAL_STATE_COPY[approval.state] || approval.state }),
          jsx(PackReviewLine, {
            label: 'Approved content hash',
            value: jsx('code', { className: 'text-[11px] break-all', children: approval.content_hash || '—' })
          }),
          jsx(PackReviewLine, {
            label: 'Current content hash',
            value: jsx('code', { className: 'text-[11px] break-all', children: (book && book.data && book.data.content_hash) || '—' })
          })
        ]
      }),
      jsx(sdk.PanelSectionLabel, { children: 'FINAL APPROVAL' }),
      jsx('div', {
        className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
        children:
          'Approving the plan approved the outline and its activities. This gate is separate: it approves the generated lesson set by its content hash, and any later edit to the plan, the pages or the course title clears it.'
      }),
      approval.state === 'active'
        ? jsx('div', {
            className: 'text-xs text-(--ui-text-secondary)',
            children: `Lesson set approved${approval.approved_at ? ' on ' + whenLabel(approval.approved_at) : ''}${
              approval.content_hash ? ' for content hash ' + approval.content_hash : ''
            }.`
          })
        : jsxs('div', {
            className: 'flex flex-col gap-2',
            children: [
              !planHash || !contentHash
                ? jsx('div', {
                    className: 'text-xs text-(--ui-text-secondary)',
                    children: !planHash
                      ? 'There is no approved plan to approve a lesson set for yet.'
                      : 'No generated pages exist yet, so there is nothing to approve. Generate the lessons from the Plan view first.'
                  })
                : !supported('parent.final.approve')
                  ? jsx('div', {
                      className: 'text-xs text-(--ui-text-secondary)',
                      children: 'This backend does not implement parent.final.approve yet.'
                    })
                  : null,
              jsx(sdk.Button, {
                variant: 'secondary',
                size: 'sm',
                className: 'self-start',
                disabled: approving || !planHash || !contentHash || !supported('parent.final.approve'),
                onClick: approveFinal,
                children: approving ? 'Approving the lesson set' : 'Approve this lesson set'
              }),
              approveError ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: approveError }) : null
            ]
          }),
      status.ready
        ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'Export is available: the approved lesson set matches the pages shown.' })
        : jsx('div', {
            className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
            children: EXPORT_BLOCKED_COPY[status.blocked_reason] || `Export is blocked (${status.blocked_reason}).`
          }),

      jsx(sdk.PanelSectionLabel, { children: 'FORMATS' }),
      jsx(StudioCheck, {
        id: 'cb-export-pack',
        checked: formats.pack,
        onChange: (value) => setFormats((previous) => ({ ...previous, pack: value })),
        children: 'Pack archive (parent guide, learner pages, answer guide).'
      }),
      jsx(StudioCheck, {
        id: 'cb-export-pdf',
        checked: formats.pdf,
        onChange: (value) => setFormats((previous) => ({ ...previous, pdf: value })),
        children: 'Printable PDF: selectable text, low-ink layout, no color-only answers.'
      }),
      jsx(sdk.Button, {
        variant: 'default',
        disabled: busy || !status.ready || chosen.length === 0 || !supported('parent.export'),
        onClick: run,
        children: busy ? 'Exporting' : 'Export the approved files'
      }),
      error
        ? jsxs('div', {
            className: 'flex flex-col gap-1 text-xs text-(--ui-text-secondary)',
            children: [
              jsx('div', {
                children: `${error.code ? error.code + ': ' : ''}${error.reason ? (EXPORT_REFUSAL_COPY[error.reason] || error.reason) : ''} ${error.message}`
              }),
              error.problems
                ? jsxs('div', {
                    className: 'flex flex-col gap-0.5 text-(--ui-text-tertiary)',
                    children: [
                      jsx('div', { children: 'The pack minima reported these problems:' }),
                      ...error.problems.map((problem, index) =>
                        jsx('div', { children: typeof problem === 'string' ? problem : JSON.stringify(problem) }, `problem-${index}`)
                      )
                    ]
                  })
                : null
            ]
          })
        : null,
      exported
        ? jsxs('div', {
            className: 'flex flex-col gap-3',
            children: [
              jsx(sdk.PanelSectionLabel, { children: 'EXPORTED FILES' }),
              jsx('div', {
                className: 'text-xs text-(--ui-text-tertiary)',
                children: `Export ${exported.export_id} · ${whenLabel(exported.exported_at)} · content hash ${exported.content_hash}`
              }),
              jsxs('div', {
                className: 'flex flex-col',
                children: (exported.files || []).map((file) =>
                  jsx(PackReviewLine, {
                    label: `${file.role} · ${file.name}`,
                    value: `${bytesLabel(file.bytes)} · ${file.mime}`
                  }, file.name)
                )
              }),
              jsxs('div', {
                className: 'flex flex-col gap-1 text-xs leading-relaxed text-(--ui-text-tertiary)',
                children: [
                  jsx('div', {
                    children:
                      'The pack carries parent guide, learner pages and answer guide. Narration stays an audio role, so an authored text script is not exported as a narration file: it is the Audio & visuals tab and part of the parent guide.'
                  }),
                  jsx('div', { children: 'Exported files never include attempts, notebook notes, reflections, transcripts or provider settings.' })
                ]
              }),
              ...(exported.artifacts || []).map((artifact) => {
                const facts = artifacts[artifact.artifact_id]
                return jsxs(
                  'div',
                  {
                    className: 'flex flex-col gap-1 border-t border-(--ui-stroke-tertiary) pt-2',
                    children: [
                      jsxs('div', {
                        className: 'flex flex-wrap items-baseline justify-between gap-2',
                        children: [
                          jsx('div', { className: 'text-xs font-medium', children: `${artifact.kind} · ${artifact.mime} · ${bytesLabel(artifact.bytes)}` }),
                          jsx('div', { className: 'min-w-0 break-all text-[11px] text-(--ui-text-tertiary)', children: artifact.content_hash })
                        ]
                      }),
                      facts && facts.download
                        ? jsx('a', {
                            className: 'self-start rounded-md border border-(--ui-stroke-tertiary) px-3 py-1 text-xs',
                            download: artifact.kind === 'pdf' ? 'parent-lesson-pack.pdf' : artifact.kind === 'pack' ? 'parent-lesson-pack.zip' : 'parent-export.json',
                            href: facts.download.url,
                            children: artifact.kind === 'pdf' ? 'Download PDF' : artifact.kind === 'pack' ? 'Download pack archive' : 'Download export record'
                          })
                        : null,
                      facts && facts.download
                        ? jsx('div', {
                            className: 'text-[11px] text-(--ui-text-tertiary)',
                            children: facts.download.requires_session
                              ? 'Session-bound, expiring link served by this host’s artifact route. A filesystem path never leaves the backend.'
                              : 'Host artifact route.'
                          })
                        : null
                    ]
                  },
                  artifact.artifact_id
                )
              })
            ]
          })
        : null
    ]
  })
}

/** §10 reflection: parent-reported, easy/about right/too hard plus a revisit note. */
function StudioReflectionView({ course, reflections, supported, onDuplicate, onSaved }) {
  const [difficulty, setDifficulty] = useState('about_right')
  const [note, setNote] = useState('')
  const [applyToNext, setApplyToNext] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(null)

  const record = useCallback(async () => {
    setBusy(true)
    setError(null)
    const response = await rpc(
      'parent.reflection.record',
      {
        course_id: course.course_id,
        enrollment_id: course.enrollment_id,
        difficulty,
        revisit_note: note.trim() ? note.trim() : null,
        apply_to_next_draft: applyToNext
      },
      { idempotencyKey: newOperationId('reflection') }
    )
    setBusy(false)
    if (!response.ok) {
      setError(`${response.error.code}: ${describeError(response.error)}`)
      return
    }
    setSaved(response.result)
    setNote('')
    onSaved()
  }, [course.course_id, course.enrollment_id, difficulty, note, applyToNext, onSaved])

  const list = (reflections && Array.isArray(reflections.reflections) ? reflections.reflections : []).slice()
  const latest = list.find((item) => item.apply_to_next_draft && item.revisit_note)

  return jsxs('div', {
    className: 'flex max-w-2xl flex-col gap-4',
    children: [
      jsx(QuietNote, {
        children:
          'A reflection is parent-reported. It is not evidence of learning, it is never graded, and it is excluded from every exported pack. Its only job is to seed your next brief.'
      }),
      jsx(sdk.PanelSectionLabel, { children: 'HOW DID IT GO?' }),
      jsx(StudioViewPicker, {
        id: 'cb-studio-difficulty',
        label: 'Difficulty',
        value: difficulty,
        options: STUDIO_DIFFICULTIES,
        onChange: setDifficulty
      }),
      jsx(StudioField, {
        id: 'cb-reflection-note',
        label: 'What would you revisit?',
        hint: 'Optional. This note is offered to your next draft as a proposal, never applied silently.',
        children: jsx(sdk.Textarea, {
          id: 'cb-reflection-note',
          rows: 3,
          value: note,
          onChange: (event) => setNote(event.target.value),
          placeholder: 'The quarter-to-eighth cut needed a second demonstration.'
        })
      }),
      jsx(StudioCheck, {
        id: 'cb-reflection-apply',
        checked: applyToNext,
        onChange: setApplyToNext,
        children: 'Offer this note to my next draft.'
      }),
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(sdk.Button, {
            variant: 'default',
            disabled: busy || !supported('parent.reflection.record'),
            onClick: record,
            children: busy ? 'Saving' : 'Record reflection'
          }),
          latest
            ? jsx(sdk.Button, {
                variant: 'secondary',
                onClick: () => onDuplicate(null, latest.revisit_note),
                children: 'Start the next brief from this note'
              })
            : null
        ]
      }),
      error ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: error }) : null,
      saved
        ? jsxs('div', {
            className: 'flex flex-col',
            children: [
              jsx(sdk.PanelSectionLabel, { children: 'RECORDED' }),
              jsx(PackReviewLine, { label: 'Difficulty', value: (STUDIO_DIFFICULTIES.find((item) => item.id === saved.difficulty) || {}).label || saved.difficulty }),
              jsx(PackReviewLine, { label: 'When', value: whenLabel(saved.created_at) }),
              jsx(PackReviewLine, { label: 'Plan hash', value: jsx('code', { className: 'text-[11px] break-all', children: saved.plan_hash || '—' }) })
            ]
          })
        : null,
      jsx(sdk.PanelSectionLabel, { children: `REFLECTIONS (${list.length})` }),
      list.length === 0
        ? jsx('div', { className: 'text-xs text-(--ui-text-tertiary)', children: 'No reflections recorded for this course yet.' })
        : jsx('div', {
            className: 'flex flex-col',
            children: list.map((item, index) =>
              jsxs(
                'div',
                {
                  className: 'flex flex-col gap-0.5 border-t border-(--ui-stroke-tertiary) py-2',
                  children: [
                    jsxs('div', {
                      className: 'flex flex-wrap items-center gap-2 text-xs',
                      children: [
                        jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: (STUDIO_DIFFICULTIES.find((entry) => entry.id === item.difficulty) || {}).label || item.difficulty }),
                        jsx('span', { className: 'text-(--ui-text-tertiary)', children: `parent-reported · ${whenLabel(item.created_at)}` }),
                        item.apply_to_next_draft ? jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: 'for next draft' }) : null
                      ]
                    }),
                    item.revisit_note ? jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: item.revisit_note }) : null
                  ]
                },
                item.reflection_id || `reflection-${index}`
              )
            )
          })
    ]
  })
}

/**
 * One authored course, one studio. The header states the two approvals separately because they
 * are separate gates; the body is only ever read from the backend's own rows.
 */
function StudioDetail({ course, implemented, revision, onRevision, onBack, onChanged, onDuplicate }) {
  const supports = useCallback((method) => Boolean(implemented && implemented.has(method)), [implemented])
  const [view, setView] = useState('brief')
  const [notice, setNotice] = useState(null)

  const brief = useRpcQuery('parent.brief.get', { course_id: course.course_id }, `studio-brief-${course.course_id}`, supports('parent.brief.get'))
  const outline = useRpcQuery(
    'course.outline',
    { enrollment_id: course.enrollment_id },
    `studio-outline-${course.course_id}`,
    supports('course.outline') && Boolean(course.enrollment_id)
  )
  const book = useRpcQuery('parent.blueprint.read', { course_id: course.course_id }, `studio-book-${course.course_id}`, supports('parent.blueprint.read'))
  const reflections = useRpcQuery(
    'parent.reflection.list',
    { course_id: course.course_id },
    `studio-reflections-${course.course_id}`,
    supports('parent.reflection.list')
  )

  const reloadAll = useCallback(() => {
    brief.reload()
    outline.reload()
    book.reload()
    reflections.reload()
    if (onChanged) onChanged()
  }, [brief.reload, outline.reload, book.reload, reflections.reload, onChanged])

  const planJobId = (brief.data && brief.data.plan_job && brief.data.plan_job.job_id) || null
  const onPlanJobSettled = useCallback(() => reloadAll(), [reloadAll])

  const plan = outline.data && outline.data.plan
  const approval = book.data && book.data.approval
  const exportStatus = book.data && book.data.export

  let body
  if (view === 'brief') {
    body = jsx(StudioBriefView, {
      briefQuery: brief,
      course,
      planJobId,
      onJobSettled: onPlanJobSettled,
      onDuplicate,
      reflections: reflections.data
    })
  } else if (view === 'plan') {
    body = jsx(StudioPlanView, {
      course,
      revision,
      onRevision,
      outline,
      book,
      brief: brief.data,
      planJobId,
      onJobSettled: onPlanJobSettled,
      onChanged: reloadAll,
      supported: supports
    })
  } else if (view === 'blueprint') {
    body = jsx(StudioBlueprintView, { book })
  } else if (view === 'export') {
    body = jsx(StudioExportPanel, { course, book, supported: supports, onChanged: reloadAll })
  } else {
    body = jsx(StudioReflectionView, {
      course,
      reflections: reflections.data,
      supported: supports,
      onDuplicate,
      onSaved: reloadAll
    })
  }

  return jsxs('div', {
    className: 'flex flex-col gap-3',
    children: [
      jsx(sdk.Button, { className: 'self-start', variant: 'text', size: 'sm', onClick: onBack, children: 'All parent courses' }),
      jsxs('div', {
        className: 'flex flex-wrap items-start justify-between gap-3',
        children: [
          jsxs('div', {
            className: 'flex min-w-0 flex-col gap-1',
            children: [
              jsx('h2', { className: 'min-w-0 break-words text-sm font-semibold', children: course.title || 'Parent course' }),
              jsxs('div', {
                className: 'flex flex-wrap items-center gap-2',
                children: [
                  jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: 'Parent preparation' }),
                  jsx(PlanStateBadge, { plan }),
                  jsx(ApprovalBadge, { approval }),
                  exportStatus && exportStatus.ready
                    ? jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: 'Export ready' })
                    : null
                ]
              })
            ]
          }),
          jsx('div', {
            className: 'text-xs text-(--ui-text-tertiary)',
            children: `You are the operator · revision ${revision}`
          })
        ]
      }),
      notice ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: notice }) : null,
      jsx(StudioReviewBanner, { approval, exportStatus }),
      jsx(StudioViewPicker, { id: 'cb-studio-view', label: 'Studio view', value: view, options: STUDIO_VIEWS, onChange: setView }),
      body
    ]
  })
}

function CoursebookPage() {
  const { state: health, reload: reloadHealth } = useHealth()
  const implemented = useRuntime(health.status)
  const [destination, setDestination] = useState(rememberedDestination)
  const [creating, setCreating] = useState(false)
  const [importing, setImporting] = useState(false)
  const [openCourse, setOpenCourse] = useState(null)
  const [studioCourse, setStudioCourse] = useState(null)
  const [studioSeed, setStudioSeed] = useState(null)
  const [studioRevision, setStudioRevision] = useState(0)
  const [studioReload, setStudioReload] = useState(0)

  const changeDestination = useCallback((next) => {
    rememberedDestination = next
    setCreating(false)
    setImporting(false)
    setOpenCourse(null)
    setStudioCourse(null)
    setStudioSeed(null)
    setDestination(next)
  }, [])

  useRouteIntent(
    useCallback((intent) => {
      if (!intent) return
      if (intent.kind === 'create') {
        rememberedDestination = 'courses'
        setDestination('courses')
        setCreating(true)
        setImporting(false)
        setStudioCourse(null)
        setStudioSeed(null)
      } else if (intent.kind === 'import') {
        rememberedDestination = 'library'
        setDestination('library')
        setCreating(false)
        setImporting(true)
        setStudioCourse(null)
        setStudioSeed(null)
      } else if (intent.kind === 'library') {
        rememberedDestination = 'library'
        setDestination('library')
        setCreating(false)
        setImporting(false)
        setStudioCourse(null)
        setStudioSeed(null)
      } else if (intent.kind === 'studio') {
        rememberedDestination = 'studio'
        setDestination('studio')
        setCreating(false)
        setImporting(false)
        setOpenCourse(null)
        setStudioCourse(null)
        setStudioSeed(null)
      } else if (intent.kind === 'studio-new') {
        rememberedDestination = 'studio'
        setDestination('studio')
        setCreating(false)
        setImporting(false)
        setStudioCourse(null)
        setStudioSeed({ initial: null, note: null })
      }
    }, [])
  )

  const canCreate = Boolean(implemented && implemented.has('course.create'))
  const canImport = Boolean(IMPORT_FLOW_WIRED && implemented && implemented.has('pack.import'))
  const canAuthor = Boolean(implemented && implemented.has('parent.brief.create'))

  let body
  if (health.status === 'loading' && !health.result) {
    body = jsx('div', { className: 'py-10', children: jsx(sdk.Loader, { label: 'Reading the Coursebook backend' }) })
  } else if (health.status === 'unavailable') {
    body = jsx(BackendUnavailable, { error: health.error, reload: reloadHealth })
  } else if (health.status === 'degraded') {
    body = jsx(DegradedBody, { reload: reloadHealth, result: health.result })
  } else if (creating) {
    body = jsx(CreateCourseFlow, {
      onCancel: () => setCreating(false),
      onCreated: () => reloadHealth()
    })
  } else if (importing) {
    body = jsx(PackImportFlow, {
      implemented,
      onCancel: () => setImporting(false),
      onImported: () => {
        setImporting(false)
        reloadHealth()
      }
    })
  } else if (destination === 'studio') {
    if (studioSeed) {
      body = jsx(StudioBriefForm, {
        initial: studioSeed.initial,
        note: studioSeed.note,
        supported: canAuthor,
        onCancel: () => setStudioSeed(null),
        onCreated: (created) => {
          setStudioSeed(null)
          setStudioCourse({
            course_id: created.course_id,
            enrollment_id: created.enrollment_id,
            title: created.title,
            revision: Number(created.revision || 0)
          })
          setStudioRevision(Number(created.revision || 0))
          setStudioReload((value) => value + 1)
        }
      })
    } else if (studioCourse) {
      body = jsx(StudioDetail, {
        course: studioCourse,
        implemented,
        revision: studioRevision,
        onRevision: setStudioRevision,
        onBack: () => setStudioCourse(null),
        onChanged: () => setStudioReload((value) => value + 1),
        onDuplicate: (brief, note) => setStudioSeed({ initial: brief, note })
      })
    } else {
      body = jsx(StudioList, {
        implemented,
        reloadSignal: studioReload,
        onCreate: () => setStudioSeed({ initial: null, note: null }),
        onOpen: (row) => {
          setStudioCourse(row)
          setStudioRevision(Number(row.revision || 0))
        }
      })
    }
  } else if (destination === 'library') {
    body = jsx(LibraryView, { createOpen: creating, implemented })
  } else if (openCourse) {
    body = jsx(CourseDetail, {
      row: openCourse,
      implemented,
      profile: currentScope().profile,
      onBack: () => setOpenCourse(null),
      onChanged: () => reloadHealth()
    })
  } else {
    body = jsx(CoursesView, {
      createOpen: creating,
      implemented,
      onStartCreate: () => setCreating(true),
      onOpen: (row) => setOpenCourse(row)
    })
  }

  const statusCopy = backendCopy(health.status)
  const showDestinationNav = health.status === 'ready' && !creating && !importing

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col',
    children: [
      jsxs('header', {
        className: 'flex shrink-0 flex-col gap-2 px-4 pt-3',
        children: [
          jsxs('div', {
            className: 'flex flex-wrap items-start justify-between gap-3',
            children: [
              jsxs('div', {
                className: 'min-w-0',
                children: [
                  jsx('div', { className: 'text-sm font-semibold', children: ROUTE_TITLE }),
                  jsx('div', {
                    className: 'mt-0.5 text-xs text-(--ui-text-tertiary)',
                    children:
                      destination === 'studio' && !studioSeed
                        ? studioCourse
                          ? 'One authored course: brief, plan, pages, export and reflection.'
                          : 'Parent-led lesson packs: write the brief, review it, then teach it.'
                        : destination === 'library' && !creating
                          ? 'Packs you can teach from, with the provenance the backend recorded.'
                          : openCourse
                            ? 'One objective, its evidence and the next permitted action.'
                            : 'A governed learning workspace: one objective, real evidence, honest next steps.'
                  })
                ]
              }),
              jsxs('div', {
                className: 'flex shrink-0 flex-wrap items-center justify-end gap-2',
                children: [
                  statusCopy ? jsx(sdk.Badge, { variant: health.status === 'unavailable' ? 'warn' : 'muted', children: statusCopy }) : null,
                  health.status === 'ready' && !creating && !importing && destination === 'courses' && canCreate
                    ? jsx(sdk.Button, { onClick: () => setCreating(true), size: 'sm', variant: 'default', children: 'New course' })
                    : null,
                  health.status === 'ready' && !creating && !importing && destination === 'library' && canImport
                    ? jsx(sdk.Button, { onClick: onImportPlaceholder, size: 'sm', variant: 'default', children: 'Import pack' })
                    : null,
                  health.status === 'ready' && !studioSeed && destination === 'studio' && !studioCourse && canAuthor
                    ? jsx(sdk.Button, { onClick: () => setStudioSeed({ initial: null, note: null }), size: 'sm', variant: 'default', children: 'New lesson brief' })
                    : null
                ]
              })
            ]
          }),
          showDestinationNav
            ? jsx(sdk.SegmentedControl, {
                onChange: changeDestination,
                options: DESTINATIONS,
                sizing: 'content',
                value: destination
              })
            : null
        ]
      }),
      jsx(PageBody, { children: body })
    ]
  })
}

/**
 * Lesson-context pane. Registered globally, but scoped: it reads the focused chat's stored id
 * and asks the backend for that exact binding. It never shows a lesson from another chat and
 * never guesses one from recency.
 */
function CoursebookPane() {
  const { state, storedId, reload } = useSessionBinding()
  const scopeProfile = currentScope().profile
  const [bindNote, setBindNote] = useState(null)
  const attemptedBind = useRef(null)

  useEffect(() => {
    // A run this Desktop opened is armed. Bind it to the focused chat once that chat has a
    // durable id and no binding of its own — by the exact stored id, never the runtime id and
    // never "the newest chat". One attempt per stored id; the seam decides legality.
    if (!storedId || attemptedBind.current === storedId) return undefined
    if (state.status !== 'ready' || state.binding) return undefined
    if (!pendingBindFor(scopeProfile)) return undefined
    let cancelled = false
    attemptedBind.current = storedId
    bindPendingChat(storedId, scopeProfile).then((response) => {
      if (cancelled || !response) return
      if (response.ok) {
        setBindNote('This lesson is bound to this chat.')
        reload()
      } else {
        setBindNote(`${response.code}: ${response.message || 'this chat could not be bound.'}`)
      }
    })
    return () => {
      cancelled = true
    }
  }, [storedId, state.status, state.binding, scopeProfile, reload])

  const openCoursebook = useCallback(() => {
    host.navigate(ROUTE_PATH)
  }, [])

  const resume = useCallback(async () => {
    const outcome = await resumeBoundSession(state.binding)
    if (!outcome.ok) {
      host.notify({ kind: 'warning', message: outcome.message })
      return
    }
  }, [state.binding])

  let body
  if (state.status === 'no-session' || state.status === 'idle') {
    body = jsx(sdk.PanelEmpty, {
      icon: 'book',
      title: 'No durable chat yet',
      description:
        'A new chat gets its stored session id after its first turn. Coursebook binds a lesson to that ' +
        'stored id — never to the live runtime id and never to "the most recent chat".',
      action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: openCoursebook, children: 'Open Coursebook' })
    })
  } else if (state.status === 'loading') {
    body = jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading this chat’s binding' }) })
  } else if (state.status === 'unavailable') {
    const code = state.error && state.error.code
    body =
      code === 'NOT_IMPLEMENTED'
        ? jsx(sdk.PanelEmpty, {
            icon: 'book',
            title: 'Lessons arrive with the learning kernel',
            description:
              'The backend is connected and answering, but this build has no kernel schema, so no ' +
              'session binding can exist yet. Nothing here is being guessed.',
            action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: openCoursebook, children: 'Open Coursebook' })
          })
        : jsx(sdk.PanelEmpty, {
            icon: 'warning',
            title: 'Cannot read this chat’s binding',
            description: code ? `${code}: ${describeError(state.error)}` : describeError(state.error),
            action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: openCoursebook, children: 'Open Coursebook' })
          })
  } else if (state.binding && storedId && state.binding.stored_session_id && state.binding.stored_session_id !== storedId) {
    // a binding for a chat that is no longer on screen is never rendered as this chat's lesson
    body = jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading this chat’s binding' }) })
  } else if (!state.binding) {
    body = jsx(sdk.PanelEmpty, {
      icon: 'book',
      title: 'Not a Coursebook lesson',
      description: 'This chat has no lesson binding. A bound chat shows its current objective and check here.',
      action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: openCoursebook, children: 'Open Coursebook' })
    })
  } else {
    body = jsx(LessonPaneBody, { binding: state.binding, storedId })
  }

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col px-3 py-2',
    'data-cb-stored-id': storedId || '',
    'data-cb-binding-id': (state.binding && state.binding.binding_id) || '',
    children: [
      jsx(sdk.PanelSectionLabel, { children: 'COURSEBOOK' }),
      bindNote ? jsx('div', { className: 'pb-2 text-xs text-(--ui-text-tertiary)', children: bindNote }) : null,
      body
    ]
  })
}

/**
 * Reactive read of a host atom. The host's own `useValue` did not re-render this pane when the
 * focused chat changed (the pane stayed pinned to the binding of the chat it first mounted with,
 * so a bound lesson could outlive its chat), so subscribe directly and keep the value in local
 * state. Falls back to the host hook when the atom exposes no subscription.
 */
function useHostValue(atom) {
  const read = useCallback(() => (atom && typeof atom.get === 'function' ? atom.get() : atom), [atom])
  const [value, setValue] = useState(read)
  useEffect(() => {
    setValue(read())
    if (!atom) return undefined
    if (typeof atom.subscribe === 'function') return atom.subscribe((next) => setValue(next))
    if (typeof atom.listen === 'function') return atom.listen((next) => setValue(next))
    if (typeof sdk.useValue === 'function') return undefined
    return undefined
  }, [atom, read])
  return value
}

/**
 * The focused chat's binding, read by its STORED id only.
 *
 * Four honest states: no durable chat yet, loading, could-not-ask, and answered (bound or not).
 * `runtimeId` is returned for diagnostics; it is never sent to `binding.get`.
 */
function useSessionBinding() {
  const storedId = useHostValue(host.state.focusedStoredSessionId)
  const runtimeId = useHostValue(host.state.focusedSessionId)
  const [state, setState] = useState({ status: 'idle', binding: null, error: null })
  const [ticket, setTicket] = useState(0)
  const reload = useCallback(() => setTicket((value) => value + 1), [])

  useEffect(() => {
    if (!storedId) {
      setState({ status: 'no-session', binding: null, error: null })
      return undefined
    }
    let cancelled = false
    setState({ status: 'loading', binding: null, error: null })
    loadBinding({ storedSessionId: storedId })
      .then((response) => {
        if (cancelled) return
        if (response && response.ok) {
          setState({ status: 'ready', binding: response.result.binding, error: null })
        } else {
          setState({ status: 'unavailable', binding: null, error: (response && response.error) || null })
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            status: 'unavailable',
            binding: null,
            error: { code: 'HOST_UNAVAILABLE', message: describeError(error) }
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [storedId, ticket])

  return { storedId, runtimeId, state, reload }
}

function ContractList() {
  const [state, setState] = useState({ status: 'loading', contracts: [], error: null })

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const response = await fetchSchema()
        if (cancelled) return
        if (response && response.ok) {
          setState({ status: 'ready', contracts: response.result.contracts, error: null })
        } else {
          setState({ status: 'unavailable', contracts: [], error: response && response.error })
        }
      } catch (error) {
        if (!cancelled) setState({ status: 'unavailable', contracts: [], error })
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  if (state.status === 'loading') return jsx(sdk.Loader, { label: 'Reading the contract inventory' })
  if (state.status === 'unavailable') {
    return jsx('div', {
      className: 'text-xs text-(--ui-text-tertiary)',
      children: `Contract inventory unavailable. ${describeError(state.error)}`
    })
  }
  return jsx('div', {
    className: 'flex flex-col',
    children: state.contracts.map((entry) =>
      jsx(StatusRow, {
        key: entry.id,
        label: entry.id,
        value: `v${entry.version}`,
        detail: `${entry.file} · ${String(entry.sha256).slice(7, 19)}…`
      })
    )
  })
}

function SessionDiagnostics() {
  const runtimeId = useHostValue(host.state.focusedSessionId)
  const storedId = useHostValue(host.state.focusedStoredSessionId)
  const scope = currentScope()
  const implemented = backendWire.implemented ? Array.from(backendWire.implemented).sort() : null
  return jsxs('div', {
    className: 'flex flex-col',
    children: [
      jsx(StatusRow, {
        label: 'Runtime session id',
        value: runtimeId ? `${String(runtimeId).slice(0, 12)}…` : 'none',
        detail: 'Live gateway id. Valid for this turn only; never sent to binding.get.'
      }),
      jsx(StatusRow, {
        label: 'Stored session id',
        value: storedId ? `${String(storedId).slice(0, 12)}…` : 'none',
        detail: storedId
          ? 'Durable id used for bindings and for opening a lesson chat.'
          : 'A fresh chat has none until its first turn. Nothing falls back to the runtime id.'
      }),
      jsx(StatusRow, {
        label: 'Scope',
        value: scope.profile || 'unknown profile',
        detail: scope.connectionId ? `connection ${scope.connectionId}` : 'local source'
      }),
      jsx(StatusRow, {
        label: 'Wire contract',
        value: `cb.rpc v${backendWire.contractVersion}`,
        detail: implemented
          ? `${implemented.length} implemented command(s): ${implemented.join(', ')}`
          : 'Backend method registry unavailable; commands are attempted, not assumed.'
      })
    ]
  })
}

function CoursebookSettings() {
  return jsxs('div', {
    className: 'flex flex-col gap-3',
    children: [
      jsx('div', {
        className: 'text-xs text-(--ui-text-tertiary)',
        children:
          'Preferences appear here only when the code that reads them ships. The inventory below is ' +
          'read-only and shows the exact contracts this backend speaks.'
      }),
      jsx(sdk.PanelSectionLabel, { children: 'SESSION BINDING' }),
      jsx(SessionDiagnostics, {}),
      jsx(sdk.PanelSectionLabel, { children: 'CONTRACTS' }),
      jsx(ContractList, {})
    ]
  })
}

export default {
  id: PLUGIN_ID,
  name: 'Coursebook',
  defaultEnabled: true,

  register(ctx) {
    pluginContext = ctx

    // `host.profileRoutes()` is async in current Desktop builds (CB-021): resolve it once into a
    // cache instead of calling it from render, where a Promise is not an array.
    profileRouteCache = []
    try {
      Promise.resolve(typeof host.profileRoutes === 'function' ? host.profileRoutes() : [])
        .then((routes) => {
          if (Array.isArray(routes)) profileRouteCache = routes
        })
        .catch(() => {
          profileRouteCache = []
        })
    } catch (error) {
      profileRouteCache = []
    }

    // Read the mounted backend's wire version + method registry. Best-effort and non-blocking:
    // a backend that is off leaves the defaults in place, and the page renders "unavailable".
    loadBackendWire()

    ctx.register({
      id: 'page',
      area: AREAS.routes,
      data: { path: ROUTE_PATH },
      render: () => jsx(CoursebookPage, {})
    })

    ctx.register({
      id: 'nav',
      area: AREAS.sidebarNav,
      data: { path: ROUTE_PATH, label: ROUTE_TITLE, codicon: 'book' }
    })

    ctx.register({
      id: 'pane',
      area: AREAS.panes,
      title: 'coursebook',
      data: { placement: 'right', width: '340px' },
      render: () => jsx(CoursebookPane, {})
    })

    if (typeof AREAS.palette === 'string') {
      ctx.register({
        id: 'open',
        area: AREAS.palette,
        data: {
          id: 'coursebook.open',
          label: 'Open Coursebook',
          keywords: ['coursebook', 'course', 'lesson', 'learn'],
          run: () => host.navigate(ROUTE_PATH)
        }
      })
      ctx.register({
        id: 'studio',
        area: AREAS.palette,
        data: {
          id: 'coursebook.studio',
          label: 'Open Parent Studio',
          keywords: ['parent', 'studio', 'lesson pack', 'teach', 'author', 'brief'],
          run: () => requestIntent({ kind: 'studio' })
        }
      })
      ctx.register({
        id: 'studio-new',
        area: AREAS.palette,
        data: {
          id: 'coursebook.studio.new',
          label: 'Write a parent lesson brief',
          keywords: ['parent', 'brief', 'new lesson', 'author', 'prepare'],
          run: () => requestIntent({ kind: 'studio-new' })
        }
      })
    }

    // Keybind: a rebindable default, never a synthetic KeyboardEvent.
    if (typeof AREAS.keybinds === 'string') {
      ctx.register({
        id: 'focus',
        area: AREAS.keybinds,
        data: {
          id: 'coursebook.focus',
          label: 'Open Coursebook',
          category: 'Coursebook',
          defaults: ['mod+shift+k'],
          run: () => host.navigate(ROUTE_PATH)
        }
      })
    }

    if (typeof ctx.registerSettingsPage === 'function') {
      ctx.registerSettingsPage({
        id: 'coursebook-settings',
        title: 'Coursebook',
        icon: 'book',
        render: () => jsx(CoursebookSettings, {})
      })
    }

    ctx.onDispose(() => {
      pluginContext = null
      intentListeners.clear()
      pendingIntent = null
    })
  }
}
