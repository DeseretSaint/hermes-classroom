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
 * Front the Coursebook pane (chat and pane are one surface — DEMO.md's learning shots need both
 * on screen). The pane is a contributed pane, so the SDK wants its contribution-scoped id
 * `<pluginId>:<paneId>`; older desktops have no `revealPane`, and there this stays a no-op.
 * Called only from an explicit lesson-start action, never from a background effect.
 */
function revealCoursebookPane() {
  if (typeof host.revealPane !== 'function') return false
  const paneId = `${PLUGIN_ID}:pane`
  try {
    host.revealPane(paneId)
    return true
  } catch (error) {
    return false
  }
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
  // The chat is now the focused surface; front the lesson pane beside it so a resumed lesson
  // never lands on a chat-only screen.
  revealCoursebookPane()
  return { ok: true, storedSessionId: binding.stored_session_id }
}

/** Start a fresh chat draft. A draft has no session id until its first turn — callers must not
 * treat the return value as one. */
function startLessonChat(profile) {
  if (typeof host.newChat !== 'function') return false
  host.newChat(profile || null)
  // `newChat` swaps the route to the draft and unmounts the Coursebook page; front the pane so
  // the fresh chat keeps the lesson surface beside it.
  revealCoursebookPane()
  return true
}

/**
 * Start or resume one governed lesson run and put the learner in front of it.
 *
 * Shared by the course detail and the Field Desk so both next-step buttons take exactly the same
 * path: `lesson.begin` under an idempotency key, the bound chat when the backend says a resume is
 * available, otherwise an armed pending bind plus a fresh chat draft. It returns a message rather
 * than notifying, so each surface can place it where it belongs.
 */
async function beginLessonFor({ row, objectiveId, mode, profile }) {
  if (!row || !row.enrollment_id) return { ok: false, message: 'No course was read for this action.' }
  const target = objectiveId || (row.evidence_summary && row.evidence_summary.current_objective_id)
  if (!target) {
    return { ok: false, message: 'This course has no current objective yet; approve the plan first.' }
  }
  const response = await rpc(
    'lesson.begin',
    { enrollment_id: row.enrollment_id, objective_id: target, mode },
    {
      idempotencyKey: `cb-lesson-${target}-${mode}-${
        mode === 'fresh' ? newOperationId('run') : 'resume'
      }`
    }
  )
  if (!response.ok) {
    return { ok: false, message: `${response.error.code}: ${describeError(response.error)}` }
  }
  const outcome = response.result
  if (mode === 'resume' && outcome.resume && outcome.resume.available && outcome.binding) {
    const opened = await resumeBoundSession(outcome.binding)
    return { ok: opened.ok, message: opened.ok ? 'Resumed the bound lesson chat.' : opened.message }
  }
  armPendingBind({
    enrollmentId: row.enrollment_id,
    objectiveId: target,
    lessonRunId: outcome.lesson_run_id,
    profile: profile || currentScope().profile
  })
  const started = startLessonChat(profile || currentScope().profile)
  return {
    ok: true,
    started,
    message: started
      ? 'A governed run is ready. Its chat binds after your first message.'
      : 'This Desktop build cannot open a new chat. Start one from the sidebar, then resume this section.'
  }
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

/**
 * True while the renderer reports a live connection.
 *
 * Offline is a state, not an error: this page keeps showing what it already read and says which
 * work is paused. It is driven by the browser's own online/offline events, so an emulated
 * disconnect (CDP `Network.emulateNetworkConditions`) is the same signal a real one produces.
 */
function useOnline() {
  const read = () => (typeof navigator === 'undefined' ? true : navigator.onLine !== false)
  const [online, setOnline] = useState(read)
  useEffect(() => {
    const sync = () => setOnline(read())
    window.addEventListener('online', sync)
    window.addEventListener('offline', sync)
    return () => {
      window.removeEventListener('online', sync)
      window.removeEventListener('offline', sync)
    }
  }, [])
  return online
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
            ? jsx('div', { className: 'mt-0.5 text-xs text-(--ui-text-secondary)', children: detail })
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
    className: 'mt-1.5 text-xs text-(--ui-text-secondary)',
    children: parts.join(' · ')
  })
}

function ErrorLine({ error }) {
  if (!error) return null
  const code = error.code ? `${error.code}: ` : ''
  return jsx('div', {
    className: 'mt-2 text-xs text-(--ui-text-secondary)',
    children: `${code}${describeError(error)}`
  })
}

/** Shared page chrome: a destination body never re-implements its own header. */
function PageBody({ children }) {
  return jsx('div', { className: 'min-h-0 flex-1 overflow-auto pb-6', children })
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
        className: 'text-center text-xs text-(--ui-text-secondary)',
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
          jsx('div', { className: 'mt-0.5 max-w-prose text-xs text-(--ui-text-secondary)', children: description })
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
    className: 'mt-4 text-xs text-(--ui-text-secondary)',
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
        className: 'text-lg font-semibold tracking-tight',
        children: 'Build a course around what you want to do.'
      }),
      jsx('p', {
        className: 'mt-2 max-w-prose text-sm leading-relaxed text-(--ui-text-secondary)',
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
            ? jsx('div', { className: 'mt-0.5 text-xs text-(--ui-text-secondary)', children: manifest.subtitle })
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
                className: 'mt-2 text-xs text-(--ui-text-secondary)',
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
            value: jsx('code', { className: 'text-xs', children: manifest.content_hash })
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
                    jsx('div', { className: 'mt-0.5 text-xs text-(--ui-text-secondary)', children: TRUST_COPY[label] || '' })
                  ]
                },
                label
              )
            )
          : jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'No trust label was recorded. That is not a pass.' })
      }),
      labels.includes('human_review_recorded')
        ? null
        : jsx('div', {
            className: 'text-xs text-(--ui-text-secondary)',
            children:
              'No human review is recorded for this pack. Passing automated checks is not a claim that the content is true.'
          }),
      manifest.content_notes && manifest.content_notes.length
        ? jsxs('div', {
            className: 'flex flex-col',
            children: [
              jsx(sdk.PanelSectionLabel, { children: 'CONTENT NOTES' }),
              ...manifest.content_notes.map((note, index) =>
                jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: note }, `note-${index}`)
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
                jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: note }, `safety-${index}`)
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
                jsx('div', { className: 'mt-0.5 text-xs text-(--ui-text-secondary)', children: (objective.evidence_criteria || []).join(' · ') })
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
                        className: 'mt-0.5 flex flex-wrap items-center gap-2 text-xs text-(--ui-text-secondary)',
                        children: [
                          jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: source.support_status || 'unassessed' }),
                          jsx('span', { children: source.publisher || source.source_type }),
                          jsx('span', { children: source.bundled ? 'bundled' : 'linked, not bundled' }),
                          source.url ? jsx('code', { className: 'break-all text-xs', children: source.url }) : null
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
                  className: 'flex shrink-0 items-center gap-2 text-xs text-(--ui-text-secondary)',
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
              className: 'max-w-prose text-xs text-(--ui-text-secondary)',
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
            folder ? jsx('span', { className: 'text-xs text-(--ui-text-secondary)', children: folder.name }) : null,
            jsx(sdk.Button, { onClick: onCancel, size: 'sm', variant: 'secondary', children: 'Cancel' })
          ]
        }),
        folder && entries.length === 0
          ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'No .zip archive in that folder.' })
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
              className: 'border-l border-(--ui-stroke-secondary) pl-3 text-xs leading-relaxed text-(--ui-text-secondary)',
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
          className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
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
              className: 'text-xs text-(--ui-text-secondary)',
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
          className: 'text-xs text-(--ui-text-secondary)',
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
        jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children:
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
        className: 'text-xs text-(--ui-text-secondary)',
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
                  className: 'flex shrink-0 items-center gap-2 text-xs text-(--ui-text-secondary)',
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
          jsx(PackReviewLine, { label: 'Content hash', value: jsx('code', { className: 'text-xs', children: manifest.content_hash }) })
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
              jsx(PackReviewLine, { label: 'Content hash', value: jsx('code', { className: 'text-xs', children: exported.content_hash }) }),
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
                        value: jsx('code', { className: 'text-xs', children: artifact.content_hash })
                      }),
                      jsx(PackReviewLine, { label: 'Download handle', value: jsx('code', { className: 'text-xs', children: artifact.download.handle }) }),
                      jsx(PackReviewLine, {
                        label: 'Download',
                        value: artifact.download.requires_session
                          ? 'session-bound, expiring — served by this host’s artifact route'
                          : 'host route'
                      }),
                      jsx(sdk.Button, {
                        asChild: true,
                        size: 'sm',
                        variant: 'secondary',
                        children: jsx('a', {
                          download: `${manifest.pack_id}-${manifest.pack_version}.zip`,
                          href: artifact.download.url,
                          children: 'Download archive'
                        })
                      }),
                      jsx('div', {
                        className: 'mt-1 text-xs leading-relaxed text-(--ui-text-secondary)',
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
        className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
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
              jsx('div', { className: 'mt-2 text-xs text-(--ui-text-secondary)', children: scope.summary })
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
              className: 'mt-1 max-w-prose text-xs text-(--ui-text-secondary)',
              children: warning.detail
            })
          : null,
        row.provenance && row.provenance.pack_id
          ? jsx('div', {
              className: 'mt-1 text-xs text-(--ui-text-secondary)',
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

// ══ M2 — the Field Desk home ═══════════════════════════════════════════════════════════════
//
// The home answers one question: what do I do next? It is assembled only from reads the contract
// already has:
//
//   library.list       the row: next_step, evidence_summary, updated_at and pack provenance
//   course.outline     the path: every objective with its state and last_opened_at
//   lesson.page        the current section's sources, fetched only when the drawer is opened
//   pack.inspect / parent.brief.get   the estimate the backend already recorded
//
// There is no sample course, no invented minutes and no vanity metric. A read that fails is
// rendered as a failure with its code and a retry; a value the backend never recorded is rendered
// as "not recorded" rather than guessed.

const DESK_STATE_WORD = {
  not_started: 'Not started',
  introduced: 'Started',
  independent_evidence: 'Evidence',
  delayed_evidence: 'Delayed evidence',
  review_due: 'Review due',
  needs_review: 'Needs review',
  overridden: 'Overridden'
}

/** The tone is a token name, never a colour literal: `done`/`due`/`active`/`quiet`. */
const DESK_STATE_TONE = {
  not_started: 'quiet',
  introduced: 'active',
  independent_evidence: 'done',
  delayed_evidence: 'done',
  review_due: 'due',
  needs_review: 'due',
  overridden: 'quiet'
}

const DESK_PRIMARY_LABEL = {
  start_lesson: 'Start the lesson',
  resume_lesson: 'Resume the lesson',
  resolve_review_due: 'Start the review',
  rebind_session: 'Reconnect the chat',
  review_plan: 'Review the plan',
  review_pack: 'Review the pack'
}

function deskToneColor(tone) {
  if (tone === 'done') return 'var(--cb-field)'
  if (tone === 'due') return 'var(--cb-ochre)'
  if (tone === 'active') return 'var(--cb-accent)'
  return 'var(--cb-ink-soft)'
}

/**
 * The section the desk continues. A due review wins when the backend's own `next_step` says so;
 * otherwise the row's `current_objective_id` decides; otherwise the first objective without
 * independent evidence. No title matching, no recency guess.
 */
function mainlineObjective(row, objectives) {
  const list = Array.isArray(objectives) ? objectives : []
  if (list.length === 0) return null
  const kind = row && row.next_step ? row.next_step.kind : null
  if (kind === 'resolve_review_due') {
    const due = list.find((entry) => entry.state === 'review_due' || entry.state === 'needs_review')
    if (due) return due
  }
  const currentId = row && row.evidence_summary ? row.evidence_summary.current_objective_id : null
  const byId = currentId ? list.find((entry) => entry.objective_id === currentId) : null
  if (byId) return byId
  return list.find((entry) => !entry.independent) || list[list.length - 1]
}

/** "Estimated minutes" is either recorded by the backend or said to be missing. Never derived. */
function deskEstimateLabel(estimate) {
  if (estimate && (estimate.status === 'loading' || estimate.status === 'idle')) return 'Reading the estimate'
  if (estimate && estimate.status === 'ready' && Number(estimate.minutes) > 0) {
    return `≈ ${Number(estimate.minutes)} min`
  }
  return 'Session length not recorded'
}

/** Pure projection of the three reads into what the desk renders. Tested without a DOM. */
function buildDeskModel({ library, outline, estimate }) {
  const rows = library && Array.isArray(library.items) ? library.items : []
  const row = rows[0] || null
  if (!row) {
    return {
      rows: [],
      row: null,
      current: null,
      objectives: [],
      total: 0,
      settled: 0,
      dueCount: 0,
      sectionLabel: null,
      nextLabel: null,
      primaryLabel: null,
      primaryKind: null,
      estimateLabel: deskEstimateLabel(estimate),
      lastTouched: null,
      touchedSource: null
    }
  }
  const objectives = outline && Array.isArray(outline.objectives) ? outline.objectives : []
  const current = mainlineObjective(row, objectives)
  const total = outline && Number(outline.total) ? Number(outline.total) : objectives.length
  const settled = objectives.filter((entry) => entry.independent).length
  const dueCount = objectives.filter(
    (entry) => entry.state === 'review_due' || entry.state === 'needs_review'
  ).length
  const next = row.next_step || {}
  return {
    rows,
    row,
    current,
    objectives,
    total,
    settled,
    dueCount,
    sectionLabel: current ? `Section ${current.ordinal} of ${total}` : null,
    nextLabel: next.label || 'The backend did not record a next step for this course.',
    primaryLabel: DESK_PRIMARY_LABEL[next.kind] || 'Open the lesson',
    primaryKind: next.kind || 'start_lesson',
    estimateLabel: deskEstimateLabel(estimate),
    // `last_opened_at` is this section's newest lesson run; `updated_at` is the enrollment's own
    // write. The section wins when it exists, and the label says which clock was read.
    lastTouched: (current && current.last_opened_at) || row.updated_at || null,
    touchedSource: current && current.last_opened_at ? 'section' : 'course'
  }
}

function DeskLabel({ children }) {
  return jsx('div', {
    style: {
      fontSize: '0.65rem',
      fontWeight: 600,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      color: 'var(--cb-ink-soft)'
    },
    children
  })
}

/** One raised frame, not a card in a card: the Continue card is the only surface on the desk. */
function ContinueCard({ desk, busy, onPrimary, onOpenSection }) {
  const current = desk.current
  const title = current ? current.title : desk.nextLabel
  return jsxs('section', {
    'data-cb-continue': '',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
      padding: '1rem 1.1rem 1.05rem',
      background: 'var(--cb-paper-raised)',
      border: '1px solid var(--cb-rule)',
      maxWidth: '46rem'
    },
    children: [
      jsx(DeskLabel, { children: 'Continue' }),
      jsx('h3', {
        'data-cb-continue-section': '',
        style: {
          margin: 0,
          fontSize: 'clamp(1.1rem, 1rem + 0.7vw, 1.5rem)',
          lineHeight: 1.25,
          letterSpacing: '-0.005em',
          color: 'var(--cb-ink)',
          overflowWrap: 'anywhere'
        },
        children: title
      }),
      jsxs('div', {
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          gap: '0.2rem 0.85rem',
          fontSize: '0.75rem',
          color: 'var(--cb-ink-soft)'
        },
        children: [
          desk.sectionLabel
            ? jsx('span', { 'data-cb-continue-position': '', children: desk.sectionLabel })
            : null,
          jsx('span', { 'data-cb-continue-minutes': '', children: desk.estimateLabel }),
          jsx('span', {
            'data-cb-continue-touched': desk.touchedSource || 'none',
            children: desk.lastTouched ? `Last touched ${whenLabel(desk.lastTouched)}` : 'Nothing touched yet'
          })
        ]
      }),
      jsxs('p', {
        'data-cb-continue-next': '',
        style: { margin: 0, fontSize: '0.9rem', lineHeight: 1.55, color: 'var(--cb-ink)' },
        children: [
          jsx('span', { style: { color: 'var(--cb-ink-soft)' }, children: 'Next · ' }),
          desk.nextLabel
        ]
      }),
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', gap: '0.4rem', paddingTop: '0.2rem' },
        children: [
          jsx(sdk.Button, {
            variant: 'default',
            disabled: Boolean(busy) || !current,
            onClick: onPrimary,
            children: busy ? 'Opening' : desk.primaryLabel
          }),
          jsx(sdk.Button, {
            variant: 'secondary',
            disabled: !current,
            onClick: () => onOpenSection(current ? current.objective_id : null),
            children: 'Open the section'
          })
        ]
      })
    ]
  })
}

/**
 * The path is a route, not a table: ordinal, title and the state word, with the current section
 * marked `aria-current="step"`. Every row is a real button into that section.
 */
function PathPreview({ desk, onOpenSection }) {
  const objectives = desk.objectives.slice(0, 8)
  const remaining = Math.max(0, desk.total - objectives.length)
  return jsxs('section', {
    'data-cb-path': '',
    style: { display: 'flex', flexDirection: 'column', gap: '0.25rem', maxWidth: '46rem' },
    children: [
      jsxs('div', {
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: '0.25rem 0.75rem'
        },
        children: [
          jsx(DeskLabel, { children: 'Path' }),
          jsx('span', {
            'data-cb-path-summary': '',
            style: { fontSize: '0.72rem', color: 'var(--cb-ink-soft)' },
            children: objectives.length
              ? `${desk.settled} of ${desk.total} sections have evidence${desk.dueCount ? ` · ${desk.dueCount} due` : ''}`
              : 'No path read yet'
          })
        ]
      }),
      jsx('ol', {
        style: { listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column' },
        children: objectives.map((objective) => {
          const tone = DESK_STATE_TONE[objective.state] || 'quiet'
          const isCurrent = Boolean(desk.current && desk.current.objective_id === objective.objective_id)
          return jsx(
            'li',
            {
              style: { borderTop: '1px solid var(--cb-rule)' },
              children: jsx(sdk.Button, {
                variant: 'text',
                className: 'w-full justify-start',
                'aria-current': isCurrent ? 'step' : undefined,
                onClick: () => onOpenSection(objective.objective_id),
                children: jsxs('span', {
                  'data-cb-path-item': objective.objective_id,
                  'data-cb-path-state': objective.state,
                  'data-cb-path-current': isCurrent ? 'true' : 'false',
                  style: {
                    display: 'flex',
                    alignItems: 'baseline',
                    gap: '0.7rem',
                    width: '100%',
                    padding: '0.4rem 0.1rem',
                    textAlign: 'left',
                    color: 'var(--cb-ink)',
                    fontSize: '0.85rem',
                    borderLeft: isCurrent ? '2px solid var(--cb-accent)' : '2px solid transparent',
                    paddingLeft: '0.55rem'
                  },
                  children: [
                    jsx('span', {
                      style: {
                        flex: '0 0 1.6rem',
                        color: deskToneColor(tone),
                        fontVariantNumeric: 'tabular-nums',
                        fontSize: '0.75rem'
                      },
                      children: String(objective.ordinal).padStart(2, '0')
                    }),
                    jsx('span', {
                      style: { flex: '1 1 auto', minWidth: 0, overflowWrap: 'anywhere' },
                      children: objective.title
                    }),
                    jsx('span', {
                      style: { flex: '0 0 auto', fontSize: '0.7rem', color: deskToneColor(tone), fontWeight: 500 },
                      children: DESK_STATE_WORD[objective.state] || objective.state
                    })
                  ]
                })
              })
            },
            objective.objective_id
          )
        })
      }),
      remaining > 0
        ? jsx('div', { style: { fontSize: '0.72rem', color: 'var(--cb-ink-soft)', paddingTop: '0.2rem' }, children: `${remaining} more section${remaining === 1 ? '' : 's'} in the path` })
        : null,
      objectives.length === 0
        ? jsx('p', {
            style: { margin: 0, fontSize: '0.8rem', lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
            children: 'The backend returned no objectives for this course, so there is no path to show yet.'
          })
        : null
    ]
  })
}

/**
 * Sources are collapsed by default and read only when opened. The read is `lesson.page` for the
 * section the desk continues, so the drawer names exactly whose sources these are.
 */
function SourcesDrawer({ open, onToggle, sectionTitle, status, error, sources, onRetry }) {
  const items = Array.isArray(sources) ? sources : []
  return jsxs('section', {
    'data-cb-sources-drawer': open ? 'open' : 'closed',
    style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', maxWidth: '46rem' },
    children: [
      jsx(sdk.Button, {
        variant: 'text',
        size: 'sm',
        className: 'self-start',
        'aria-expanded': open ? 'true' : 'false',
        'aria-controls': 'cb-desk-sources',
        onClick: onToggle,
        children: open ? 'Hide sources' : 'Show sources'
      }),
      jsx('div', {
        style: { fontSize: '0.72rem', color: 'var(--cb-ink-soft)' },
        children: sectionTitle ? `Sources for “${sectionTitle}”` : 'Sources'
      }),
      open
        ? jsx('div', {
            id: 'cb-desk-sources',
            role: 'region',
            'aria-label': 'Sources for the current section',
            style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', borderTop: '1px solid var(--cb-rule)', paddingTop: '0.45rem' },
            children:
              status === 'loading'
                ? jsx(sdk.Loader, { label: 'Reading this section’s sources' })
                : status === 'error'
                  ? jsxs('div', {
                      style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', color: 'var(--cb-ink-soft)' },
                      children: [
                        jsx('span', {
                          children: `${error && error.code ? error.code + ': ' : ''}${describeError(error)} The sources were not read.`
                        }),
                        jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: onRetry, children: 'Try again' })
                      ]
                    })
                  : items.length === 0
                    ? jsx('p', { style: { margin: 0, fontSize: '0.8rem', color: 'var(--cb-ink-soft)' }, children: 'The backend recorded no sources for this section.' })
                    : jsx('ul', {
                        style: { listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.4rem' },
                        children: items.map((source) =>
                          jsxs(
                            'li',
                            {
                              'data-cb-desk-source': source.source_id || '',
                              style: { borderLeft: '2px solid var(--cb-rule)', paddingLeft: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.05rem' },
                              children: [
                                jsx('span', { style: { fontSize: '0.85rem', color: 'var(--cb-ink)' }, children: source.title || 'Untitled source' }),
                                jsx('span', { style: { fontSize: '0.7rem', color: 'var(--cb-ink-soft)' }, children: source.support_status || 'status unrecorded' })
                              ]
                            },
                            source.source_id || source.title
                          )
                        )
                      })
          })
        : null
    ]
  })
}

/** The secondary list: the other courses on this profile, by their own next step. */
function AllCoursesList({ rows, onOpen, onShowAll }) {
  const others = rows.slice(1)
  // The desk stays one glance: three more courses, then the honest count and the full list.
  const shown = others.slice(0, 3)
  const hidden = others.length - shown.length
  return jsxs('section', {
    'data-cb-all-courses': '',
    style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', maxWidth: '46rem' },
    children: [
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.25rem 0.75rem' },
        children: [
          jsx(DeskLabel, { children: `All courses · ${rows.length}` }),
          jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: onShowAll, children: 'Search and manage courses' })
        ]
      }),
      others.length === 0
        ? jsx('p', {
            style: { margin: 0, fontSize: '0.8rem', lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
            children: 'This is the only course on this profile.'
          })
        : jsx('div', {
            style: { display: 'flex', flexDirection: 'column' },
            children: shown.map((row) =>
              jsx(
                'div',
                {
                  'data-cb-all-courses-row': row.enrollment_id,
                  style: { borderTop: '1px solid var(--cb-rule)', padding: '0.35rem 0' },
                  children: jsx(sdk.ListRow, {
                    title: jsx('span', { style: { overflowWrap: 'anywhere' }, children: row.title }),
                    description: jsx('span', {
                      children: (row.next_step && row.next_step.label) || 'No next step recorded'
                    }),
                    action: jsx(sdk.Button, {
                      variant: 'secondary',
                      size: 'sm',
                      onClick: () => onOpen(row),
                      children: 'Open'
                    })
                  })
                },
                row.enrollment_id
              )
            )
          }),
      hidden > 0
        ? jsx('div', {
            'data-cb-all-courses-more': String(hidden),
            style: { fontSize: '0.72rem', color: 'var(--cb-ink-soft)', paddingTop: '0.1rem' },
            children: `+${hidden} more course${hidden === 1 ? '' : 's'} on this profile`
          })
        : null
    ]
  })
}

/**
 * The strip is a glance surface, not the notebook: the saved excerpt is summarised to plain text
 * and clipped here only. Plain text means the authored markdown syntax is removed for this one
 * line, not re-rendered — the strip does not grow a second markdown surface. The saved row keeps
 * its whole excerpt and the Notebook renders it unfiltered.
 */
const STRIP_EXCERPT_CHARS = 240
function stripExcerpt(entry) {
  const raw = String(entry.excerpt || entry.note || entry.kind || '')
  const plain = raw
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^>\s?/gm, '')
    .replace(/^\s*\|/gm, '')
    .replace(/\|\s*$/gm, '')
    .replace(/\|/g, ' · ')
    .replace(/[*_`~]{1,3}/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  return plain.length > STRIP_EXCERPT_CHARS ? `${plain.slice(0, STRIP_EXCERPT_CHARS - 1).trimEnd()}…` : plain
}

/**
 * The Field Notes strip on the Field Desk.
 *
 * A saved moment is a first-class learning surface, not a settings side list: the desk shows the
 * last few things this course saved, each one able to return to its exact block. It reads only
 * `notebook.list`; it never writes, never invents an empty row and never hides a failed read.
 */
function FieldNotesStrip({ notes, courseTitle, current, sections, stale, onOpenSection, onShowNotebook, onRetry }) {
  const status = notes && notes.status ? notes.status : 'idle'
  const entries = notes && notes.data && Array.isArray(notes.data.entries) ? notes.data.entries : []
  const recent = entries.slice(0, 4)
  const error = notes ? notes.error : null
  const reload = notes && notes.reload ? notes.reload : onRetry
  const sectionTitles = {}
  ;(sections || []).forEach((entry) => {
    if (entry && entry.objective_id && entry.title) sectionTitles[entry.objective_id] = entry.title
  })

  if (!notes) return null

  const action = current
    ? jsx(sdk.Button, {
        variant: 'secondary',
        size: 'sm',
        onClick: () => onOpenSection(current.objective_id),
        children: 'Go to the current lesson'
      })
    : null

  const quietText = { margin: 0, fontSize: '0.75rem', lineHeight: 1.55, color: 'var(--cb-ink-soft)' }

  return jsxs('section', {
    'data-cb-field-notes': status === 'ready' && recent.length > 0 ? 'ready' : status,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.45rem',
      maxWidth: '46rem',
      borderTop: '1px solid var(--cb-rule)',
      paddingTop: '0.7rem'
    },
    children: [
      jsxs('div', {
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: '0.25rem 0.75rem'
        },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.5rem' },
            children: [
              jsx(DeskLabel, { children: 'Field Notes' }),
              entries.length > 0
                ? jsx('span', {
                    style: { fontSize: '0.72rem', color: 'var(--cb-ink-soft)' },
                    children: `${entries.length} saved${entries.length > recent.length ? ` · showing the last ${recent.length}` : ''}`
                  })
                : null
            ]
          }),
          jsx(sdk.Button, {
            variant: 'text',
            size: 'sm',
            onClick: onShowNotebook,
            children: 'All field notes'
          })
        ]
      }),
      stale
        ? jsx('p', {
            style: { ...quietText, fontSize: '0.72rem' },
            children: 'These are the notes last read. A save or an edit is paused until the desk reconnects.'
          })
        : null,
      status === 'error' && !notes.data
        ? jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' },
            children: [
              jsx('span', {
                style: quietText,
                children: `${error && error.code ? error.code + ': ' : ''}${describeError(error)} Saved moments are still stored; this strip just could not read them.`
              }),
              jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: reload, children: 'Try again' })
            ]
          })
        : status === 'loading' && !notes.data
          ? jsx('div', { style: { padding: '0.35rem 0' }, children: jsx(sdk.Loader, { label: 'Reading your field notes' }) })
          : recent.length === 0
            ? jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' },
                children: [
                  jsx('p', {
                    style: { ...quietText, maxWidth: '34rem' },
                    children: 'Save an explanation, visual or quiz moment and it will appear here.'
                  }),
                  action
                ]
              })
            : jsx('div', {
                style: { display: 'flex', flexDirection: 'column' },
                children: recent.map((entry) => {
                  const ref = readNotebookRef(entry.source_ref)
                  return jsxs(
                    'div',
                    {
                      'data-cb-field-note': entry.entry_id,
                      style: {
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.2rem',
                        borderTop: '1px solid var(--cb-rule)',
                        padding: '0.5rem 0 0.55rem'
                      },
                      children: [
                        jsx('p', {
                          style: {
                            margin: 0,
                            fontSize: '0.9rem',
                            lineHeight: 1.55,
                            color: 'var(--cb-ink)',
                            whiteSpace: 'pre-wrap',
                            overflowWrap: 'anywhere'
                          },
                          children: stripExcerpt(entry)
                        }),
                        entry.note && entry.excerpt
                          ? jsx('p', {
                              style: { margin: 0, fontSize: '0.75rem', lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                              children: entry.note
                            })
                          : null,
                        jsxs('div', {
                          style: {
                            display: 'flex',
                            flexWrap: 'wrap',
                            alignItems: 'baseline',
                            gap: '0.25rem 0.8rem',
                            fontSize: '0.72rem',
                            color: 'var(--cb-ink-soft)'
                          },
                          children: [
                            jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: entry.kind }),
                            (entry.tags || []).map((item) =>
                              jsx(
                                'span',
                                {
                                  style: {
                                    border: '1px solid var(--cb-rule)',
                                    padding: '0 0.3rem',
                                    fontSize: '0.68rem',
                                    color: 'var(--cb-ink-soft)'
                                  },
                                  children: item
                                },
                                item
                              )
                            ),
                            sectionTitles[entry.objective_id]
                              ? jsx('span', { children: `Section · ${sectionTitles[entry.objective_id]}` })
                              : null,
                            courseTitle ? jsx('span', { children: courseTitle }) : null,
                            jsx('span', { children: `saved ${whenLabel(entry.created_at)}` }),
                            jsx(sdk.Button, {
                              variant: 'text',
                              size: 'sm',
                              'aria-label': `Open the saved moment “${(entry.excerpt || entry.kind).slice(0, 60)}” in Textbook`,
                              onClick: () => onOpenSection(entry.objective_id, ref.block_id),
                              children: 'Open in textbook'
                            })
                          ]
                        })
                      ]
                    },
                    entry.entry_id
                  )
                })
              })
    ]
  })
}

/** The pure desk view. The container below owns the reads; this owns the geometry. */
function FieldDeskHome({
  desk,
  notes,
  onShowNotebook,
  libraryStatus,
  libraryError,
  stale,
  busy,
  notice,
  onRetry,
  onCreate,
  onPrimary,
  onOpenSection,
  onOpen,
  onShowAll,
  sourcesOpen,
  onToggleSources,
  sourcesStatus,
  sourcesError,
  sources,
  onRetrySources,
  implemented
}) {
  const root = 'flex flex-col gap-4'

  if (libraryStatus === 'loading' && !desk.row) {
    return jsx('div', { 'data-cb-desk': 'loading', className: 'py-10', children: jsx(sdk.Loader, { label: 'Reading your courses' }) })
  }
  if (libraryStatus === 'error' && !desk.row) {
    return jsx('div', {
      'data-cb-desk': 'error',
      className: 'mx-auto w-full max-w-xl py-6',
      children: jsxs(sdk.ErrorState, {
        title: 'The Field Desk could not read your courses',
        description: `${libraryError && libraryError.code ? libraryError.code + ': ' : ''}${describeError(libraryError)} This desk will not show an empty course in place of a failed read.`,
        children: jsxs('div', {
          className: 'flex flex-wrap items-center justify-center gap-2',
          children: [
            jsx(sdk.Button, { variant: 'default', onClick: onRetry, children: 'Try again' }),
            jsx(sdk.Button, { variant: 'secondary', onClick: openCapabilities, children: 'Open Capabilities' })
          ]
        })
      })
    })
  }
  if (!desk.row) {
    return jsx('div', {
      'data-cb-desk': 'empty',
      children: jsx(FirstRun, { implemented, onCreate })
    })
  }

  return jsxs('div', {
    'data-cb-desk': 'ready',
    className: root,
    children: [
      stale
        ? jsxs('div', {
            className: 'flex flex-wrap items-center justify-between gap-2 border-b border-(--ui-stroke-tertiary) pb-2',
            children: [
              jsx('div', {
                className: 'text-xs text-(--ui-text-secondary)',
                children: 'Reconnecting. Showing the courses that were last read; the desk is paused.'
              }),
              jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: onRetry, children: 'Retry now' })
            ]
          })
        : null,
      notice ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: notice }) : null,
      jsx(ContinueCard, { desk, busy, onPrimary, onOpenSection }),
      jsx(FieldNotesStrip, {
        notes,
        courseTitle: desk.row && desk.row.title ? desk.row.title : null,
        current: desk.current || null,
        sections: desk.objectives || [],
        stale,
        onOpenSection,
        onShowNotebook,
        onRetry
      }),
      jsx(PathPreview, { desk, onOpenSection }),
      jsx(SourcesDrawer, {
        open: sourcesOpen,
        onToggle: onToggleSources,
        sectionTitle: desk.current ? desk.current.title : null,
        status: sourcesStatus,
        error: sourcesError,
        sources,
        onRetry: onRetrySources
      }),
      jsx(AllCoursesList, { rows: desk.rows, onOpen, onShowAll })
    ]
  })
}

/**
 * The estimate the backend already recorded: a pack manifest's per-objective `estimated_minutes`,
 * or the parent brief's `duration_minutes`. It never computes one from a count of sections.
 */
function useSessionEstimate({ row, current, enabled }) {
  const [state, setState] = useState({ status: 'none', minutes: null, source: null, error: null })
  const courseId = row ? row.course_id : null
  const packId = row && row.provenance ? row.provenance.pack_id : null
  const packVersion = row && row.provenance ? row.provenance.pack_version : null
  const ordinal = current ? current.ordinal : null
  const key = [courseId, packId, packVersion, ordinal].join('|')

  useEffect(() => {
    if (!enabled || !courseId || !ordinal) {
      setState({ status: 'none', minutes: null, source: null, error: null })
      return undefined
    }
    let cancelled = false
    setState({ status: 'loading', minutes: null, source: null, error: null })
    let read
    if (packId && packVersion && backendSupports('pack.inspect')) {
      read = rpc('pack.inspect', { pack_id: packId, pack_version: packVersion }).then((response) => {
        if (!response.ok) return null
        const manifest = response.result && response.result.manifest
        const entries = manifest && Array.isArray(manifest.objectives) ? manifest.objectives : []
        const match = entries.find((entry) => Number(entry.ordinal) === Number(ordinal))
        const minutes = match && Number(match.estimated_minutes) > 0 ? Number(match.estimated_minutes) : null
        return minutes ? { minutes, source: 'pack_manifest' } : null
      })
    } else if (backendSupports('parent.brief.get')) {
      read = rpc('parent.brief.get', { course_id: courseId }).then((response) => {
        if (!response.ok) return null
        const brief = response.result && response.result.brief
        const minutes = brief && Number(brief.duration_minutes) > 0 ? Number(brief.duration_minutes) : null
        return minutes ? { minutes, source: 'parent_brief' } : null
      })
    } else {
      read = Promise.resolve(null)
    }
    read
      .then((found) => {
        if (cancelled) return
        setState(
          found
            ? { status: 'ready', minutes: found.minutes, source: found.source, error: null }
            : { status: 'none', minutes: null, source: null, error: null }
        )
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'none', minutes: null, source: null, error: null })
      })
    return () => {
      cancelled = true
    }
  }, [enabled, courseId, packId, packVersion, ordinal, key])

  return state
}

/**
 * The Field Desk container. One `library.list` read picks the course to continue (the most
 * recently written row), `course.outline` supplies the path, and the section's sources are read
 * only when the drawer opens. A failure in any of those is shown, never papered over.
 */
function FieldDesk({ implemented, onOpen, onShowAll, onStartCreate, profile }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const payload = { filter: 'all', limit: 50, sort: 'recent' }
  const key = JSON.stringify(payload)
  const library = useRpcQuery('library.list', payload, key, backendSupports('library.list'))

  const provisional = buildDeskModel({ library: library.data, outline: null, estimate: null })
  const row = provisional.row
  const outline = useRpcQuery(
    'course.outline',
    { enrollment_id: row ? row.enrollment_id : null },
    `desk-outline-${row ? row.enrollment_id : 'none'}`,
    Boolean(row) && supports('course.outline')
  )
  const withOutline = buildDeskModel({ library: library.data, outline: outline.data, estimate: null })
  const current = withOutline.current
  const estimate = useSessionEstimate({ row, current, enabled: Boolean(row) && Boolean(current) })
  const desk = buildDeskModel({ library: library.data, outline: outline.data, estimate })

  const [sourcesOpen, setSourcesOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)

  // A different continued course must not inherit the previous course's open drawer.
  useEffect(() => {
    setSourcesOpen(false)
  }, [row ? row.enrollment_id : 'none'])

  const page = useRpcQuery(
    'lesson.page',
    {
      enrollment_id: row ? row.enrollment_id : null,
      objective_id: current ? current.objective_id : null
    },
    `desk-page-${row ? row.enrollment_id : 'none'}-${current ? current.objective_id : 'none'}`,
    sourcesOpen && Boolean(row) && Boolean(current) && supports('lesson.page')
  )

  const notes = useRpcQuery(
    'notebook.list',
    { enrollment_id: row ? row.enrollment_id : null },
    `desk-notes-${row ? row.enrollment_id : 'none'}`,
    Boolean(row) && supports('notebook.list')
  )

  const onPrimary = useCallback(async () => {
    if (!desk.row || !desk.current) return
    const kind = desk.primaryKind
    if (kind === 'start_lesson' || kind === 'resume_lesson') {
      setBusy(true)
      setNotice(null)
      const outcome = await beginLessonFor({
        row: desk.row,
        objectiveId: desk.current.objective_id,
        mode: kind === 'resume_lesson' ? 'resume' : 'fresh',
        profile: profile || currentScope().profile
      })
      setBusy(false)
      setNotice(outcome.message)
      if (outcome.ok) library.reload()
      return
    }
    // Review, plan and pack states are course-detail actions, not a second lesson path.
    onOpen(desk.row)
  }, [desk, profile, onOpen, library])

  return jsx(FieldDeskHome, {
    desk,
    libraryStatus: library.status,
    libraryError: library.error,
    stale: Boolean(library.stale),
    busy,
    notice,
    onRetry: library.reload,
    onCreate: onStartCreate,
    onPrimary,
    onOpenSection: (objectiveId, blockId) => onOpen(desk.row, objectiveId, blockId),
    notes,
    onShowNotebook: () => onOpen(desk.row, null, null, 'notebook'),
    onOpen,
    onShowAll,
    sourcesOpen,
    onToggleSources: () => setSourcesOpen((value) => !value),
    sourcesStatus: page.status,
    sourcesError: page.error,
    sources: page.data && page.data.sources,
    onRetrySources: page.reload,
    implemented
  })
}

function CoursesView({ implemented, onStartCreate, createOpen, onOpen, onShowDesk }) {
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
    // A preview is still a contract call: cb.rpc requires idempotency_key at the root. Without it
    // this dry run was refused (VALIDATION_FAILED: 'idempotency_key' is a required property) and
    // the confirm never opened — the destructive path was unreachable from the UI. The key is
    // derived from the row, so re-opening the same preview is the same operation.
    const response = await rpc(
      'enrollment.delete',
      { enrollment_id: row.enrollment_id, dry_run: true },
      {
        idempotencyKey: `cb-enrollment-delete-preview-${row.enrollment_id}`,
        expectedRevision: row.revision
      }
    )
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
              className: 'mb-2 flex flex-wrap items-center justify-between gap-2 border-b border-(--ui-stroke-tertiary) pb-2',
              children: [
                jsx('div', {
                  className: 'text-xs text-(--ui-text-secondary)',
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
              className: 'pt-3 text-xs text-(--ui-text-secondary)',
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
      jsx(FocusReturningDialog, {
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
            className: 'text-xs text-(--ui-text-secondary)',
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
            className: 'border-l border-(--ui-stroke-secondary) pl-3 text-xs leading-relaxed text-(--ui-text-secondary)',
            children:
              'Parent Studio blueprint: the adult prepares and teaches from this plan. Checks are observations, ' +
              'not graded child answers, and this course is never offered as an adult graded course.'
          })
        : null,
      jsx('div', {
        className: 'mt-2 text-xs leading-relaxed text-(--ui-text-secondary)',
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
    // A preview is still a contract call: cb.rpc requires idempotency_key at the root. Without it
    // this dry run was refused (VALIDATION_FAILED: 'idempotency_key' is a required property) and
    // the confirm never opened — the destructive path was unreachable from the UI. The key is
    // derived from the row, so re-opening the same preview is the same operation.
    const response = await rpc(
      'enrollment.delete',
      { enrollment_id: row.enrollment_id, dry_run: true },
      {
        idempotencyKey: `cb-enrollment-delete-preview-${row.enrollment_id}`,
        expectedRevision: row.revision
      }
    )
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
        idempotencyKey: `cb-delete-${pendingDelete.enrollment_id}-${deleteScope.scope_id}`,
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
              className: 'mb-2 text-xs text-(--ui-text-secondary)',
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
      onShowDesk
        ? jsx(sdk.Button, {
            className: 'mb-2 self-start',
            variant: 'text',
            size: 'sm',
            onClick: onShowDesk,
            children: 'Back to the Field Desk'
          })
        : null,
      jsxs('div', {
        className: 'mb-2 flex flex-wrap items-center justify-between gap-2',
        children: [
          jsx('div', {
            className: 'max-w-prose text-xs text-(--ui-text-secondary)',
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
      jsx(FocusReturningDialog, {
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

// ── learner create → plan job → plan review ────────────────────────────────
//
// H-02: `course.create` + `enrollment.create` used to be the whole learner flow, and the screen
// told the learner that generation was not wired. It is wired: the executor pumps `plan` jobs, the
// plan pipeline writes a draft plan, and `plan.approve` fences on the kernel digest. This block is
// the one place the desktop builds those payloads.

/** How much course a brief asks for. Contract enum: `single` | `short` | `full`. */
const COURSE_SCOPES = [
  { id: 'single', label: 'One lesson' },
  { id: 'short', label: 'Short course' },
  { id: 'full', label: 'Full course' }
]

/**
 * Honest time expectation per scope. No invented minutes: a plan has no `time_estimate` until it
 * exists, and no read in this contract serves one, so this says what is true before the run starts.
 */
const SCOPE_TIME_COPY = {
  single: 'One lesson. Research and drafting may take several minutes; there is no progress percentage until the plan exists.',
  short: 'A short course of a few sessions. Research and drafting may take several minutes.',
  full: 'A full course. Research and drafting may take several minutes and run longest; the plan carries its own estimate once it exists.'
}

function planTimingCopy(scope) {
  return SCOPE_TIME_COPY[scope] || 'Research and drafting may take several minutes. A plan is written before any lesson exists.'
}

/**
 * The exact `jobs.create` brief for a learner plan job (cb.rpc v10 `plan_brief`).
 *
 * Every declared input travels: ids and stage so a retry can resume, goal/recipe/dials/locale and
 * the v10 capability inputs (level, subject_domain, scope) so the policy and the planner read the
 * same decision the course row stores. Absent inputs are omitted, never sent as empty strings.
 */
function planJobBrief(input) {
  const brief = {
    stage: 'plan',
    course_id: input.courseId,
    enrollment_id: input.enrollmentId,
    goal: input.goal,
    recipe: input.recipe,
    dials: input.dials || {}
  }
  if (input.locale) brief.locale = input.locale
  if (input.level) brief.level = input.level
  if (input.subjectDomain) brief.subject_domain = input.subjectDomain
  if (input.scope) brief.scope = input.scope
  return brief
}

/** The `course.create` payload for the same decision. Only contract fields, nothing extra. */
function courseCreatePayload(input) {
  const payload = { title: input.title, recipe: input.recipe, goal: input.goal, dials: input.dials || {} }
  if (input.locale) payload.locale = input.locale
  if (input.level) payload.level = input.level
  if (input.subjectDomain) payload.subject_domain = input.subjectDomain
  if (input.scope) payload.scope = input.scope
  return payload
}

/**
 * One learner create: course → enrolment → one plan job, keyed so a retry replays.
 *
 * `call` is the rpc transport (`rpc` in the app), injected so a test can prove the exact sequence
 * and the idempotency keys rather than reading the source. A jobs.create failure keeps the ids it
 * already has: the course and its draft plan are real and the same key retries the same job, so the
 * draft is recoverable instead of abandoned.
 */
async function startLearnerPlan({ call, key, title, goal, recipe, dials, locale, level, subjectDomain, scope }) {
  const decision = { title, goal, recipe, dials, locale, level, subjectDomain, scope }
  const course = await call('course.create', courseCreatePayload(decision), {
    idempotencyKey: key,
    expectedRevision: null
  })
  if (!course || !course.ok) return { ok: false, stage: 'course.create', error: (course && course.error) || null }

  const courseId = course.result.course_id
  const planId = course.result.plan_id
  const enrollment = await call(
    'enrollment.create',
    { course_id: courseId, learner_label: title },
    { idempotencyKey: `${key}-enroll`, expectedRevision: null }
  )
  if (!enrollment || !enrollment.ok) {
    return {
      ok: false,
      stage: 'enrollment.create',
      error: (enrollment && enrollment.error) || null,
      courseId,
      planId
    }
  }
  const enrollmentId = enrollment.result.enrollment_id

  const job = await call(
    'jobs.create',
    { kind: 'plan', brief: planJobBrief({ courseId, enrollmentId, ...decision }) },
    { idempotencyKey: `${key}-plan` }
  )
  if (!job || !job.ok) {
    return {
      ok: false,
      stage: 'jobs.create',
      error: (job && job.error) || null,
      courseId,
      planId,
      enrollmentId
    }
  }
  return {
    ok: true,
    courseId,
    planId,
    enrollmentId,
    jobId: job.result.job_id,
    jobState: job.result.state
  }
}

/** A compact staged create flow; every step is editable before the one mutation. */
function CreateCourseFlow({ onCancel, onCreated }) {
  const [step, setStep] = useState(1)
  const [goal, setGoal] = useState('')
  const [title, setTitle] = useState('')
  const [recipe, setRecipe] = useState('casual')
  const [scope, setScope] = useState('short')
  const [level, setLevel] = useState('')
  const [subjectDomain, setSubjectDomain] = useState('')
  const [locale, setLocale] = useState('')
  const [dials, setDials] = useState({ pace: 'light', depth: 'survey', assessment: 'self_check', autonomy: 'guided' })
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  // The course/enrolment can already exist when the plan job fails. Those ids stay on screen so the
  // same key can retry the same job; the draft is never lost to a redraw.
  const [recoverable, setRecoverable] = useState(null)
  const [revision, setRevision] = useState(0)
  const [error, setError] = useState(null)
  const keyRef = useRef(null)

  const goalInvalid = step >= 1 && goal.trim().length === 0
  const canAdvance = goal.trim().length > 0 && title.trim().length > 0

  const submit = useCallback(async () => {
    if (submitting) return
    if (!keyRef.current) keyRef.current = `cb-course-create-${newOperationId('create')}`
    setSubmitting(true)
    setError(null)
    const outcome = await startLearnerPlan({
      call: rpc,
      key: keyRef.current,
      title: title.trim(),
      goal: goal.trim(),
      recipe,
      dials,
      locale: locale.trim() || null,
      level: level.trim() || null,
      subjectDomain: subjectDomain.trim() || null,
      scope
    })
    setSubmitting(false)
    if (!outcome.ok) {
      if (outcome.courseId) setRecoverable(outcome)
      setError({
        code: outcome.stage,
        message:
          describeError(outcome.error) +
          (outcome.stage === 'jobs.create'
            ? ' The course and its draft plan are saved. Retrying starts the same job, not a second one.'
            : '')
      })
      return
    }
    setRecoverable(null)
    setRevision(0)
    setResult(outcome)
    onCreated(outcome)
  }, [dials, goal, level, locale, onCreated, recipe, scope, subjectDomain, submitting, title])

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
        jsx('h2', { className: 'text-sm font-semibold', children: 'Course created — plan generation started' }),
        jsx('div', {
          className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
          children:
            'Your course, its draft plan and your enrolment exist on this profile. One plan job was queued; ' +
            'the agent runs it in the background, so leaving this page does not stop it.'
        }),
        jsxs('div', {
          className: 'flex flex-col',
          children: [
            jsx(StatusRow, { label: 'Course', value: result.courseId }),
            jsx(StatusRow, { label: 'Plan', value: `${result.planId} (draft)` }),
            jsx(StatusRow, { label: 'Enrollment', value: result.enrollmentId }),
            jsx(StatusRow, { label: 'Plan job', value: result.jobId })
          ]
        }),
        jsx(LearnerPlanView, {
          course: { course_id: result.courseId, enrollment_id: result.enrollmentId },
          revision,
          onRevision: setRevision,
          onOpenSection: null,
          onStartLesson: null,
          onChanged: null,
          jobHint: result.jobId,
          scopeHint: scope
        }),
        jsxs('div', {
          className: 'flex flex-wrap items-center gap-2 pt-1',
          children: [
            jsx(sdk.Button, { onClick: onCancel, variant: 'default', children: 'Open in Courses' }),
            jsx(sdk.Button, {
              onClick: () => {
                setResult(null)
                setRecoverable(null)
                setStep(1)
                setGoal('')
                setTitle('')
                setLevel('')
                setSubjectDomain('')
                setLocale('')
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
              jsx(sdk.PanelSectionLabel, { children: `STEP ${step} OF 3` }),
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
                    className: 'text-xs text-(--ui-text-secondary)',
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
                    className: 'mt-1 text-xs text-(--ui-text-secondary)',
                    children: 'Preparing lessons for a child goes to Parent Studio, not a learner course.'
                  })
                ]
              })
            ]
          })
        : null,
      step === 2
        ? jsxs('div', {
            className: 'flex flex-col gap-4',
            children: [
              jsxs('div', {
                className: 'flex flex-col gap-1.5',
                children: [
                  jsx('div', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: 'How much course' }),
                  jsx(sdk.SegmentedControl, {
                    onChange: setScope,
                    options: COURSE_SCOPES,
                    sizing: 'content',
                    value: scope
                  }),
                  jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', id: 'cb-scope-time', children: planTimingCopy(scope) })
                ]
              }),
              ...Object.keys(DIALS).map((dial) =>
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
              ),
              jsxs('div', {
                className: 'flex flex-col gap-3 border-t border-(--ui-stroke-tertiary) pt-3',
                children: [
                  jsx('div', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: 'Optional context' }),
                  jsxs('div', {
                    className: 'flex flex-col gap-1.5',
                    children: [
                      jsx('label', { className: 'text-xs text-(--ui-text-secondary)', htmlFor: 'cb-level', children: 'Your level' }),
                      jsx(sdk.Input, {
                        id: 'cb-level',
                        maxLength: 35,
                        onChange: (event) => setLevel(event.target.value),
                        placeholder: 'L0',
                        value: level
                      })
                    ]
                  }),
                  jsxs('div', {
                    className: 'flex flex-col gap-1.5',
                    children: [
                      jsx('label', { className: 'text-xs text-(--ui-text-secondary)', htmlFor: 'cb-subject', children: 'Subject domain' }),
                      jsx(sdk.Input, {
                        id: 'cb-subject',
                        maxLength: 60,
                        onChange: (event) => setSubjectDomain(event.target.value),
                        placeholder: 'language',
                        value: subjectDomain
                      })
                    ]
                  }),
                  jsxs('div', {
                    className: 'flex flex-col gap-1.5',
                    children: [
                      jsx('label', { className: 'text-xs text-(--ui-text-secondary)', htmlFor: 'cb-locale', children: 'Locale (language tag)' }),
                      jsx(sdk.Input, {
                        id: 'cb-locale',
                        maxLength: 35,
                        onChange: (event) => setLocale(event.target.value),
                        placeholder: 'ja-JP',
                        value: locale
                      })
                    ]
                  }),
                  jsx('div', {
                    className: 'text-xs text-(--ui-text-secondary)',
                    children: 'These are advisory: the planner and the media policy read them, and they never become a grade.'
                  })
                ]
              })
            ]
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
                  jsx(StatusRow, { label: 'Scope', value: (COURSE_SCOPES.find((option) => option.id === scope) || {}).label || scope }),
                  jsx(StatusRow, { label: 'Pace', value: dials.pace }),
                  jsx(StatusRow, { label: 'Depth', value: dials.depth }),
                  jsx(StatusRow, { label: 'Assessment', value: dials.assessment }),
                  jsx(StatusRow, { label: 'Autonomy', value: dials.autonomy }),
                  level.trim() ? jsx(StatusRow, { label: 'Level', value: level.trim() }) : null,
                  subjectDomain.trim() ? jsx(StatusRow, { label: 'Subject domain', value: subjectDomain.trim() }) : null,
                  locale.trim() ? jsx(StatusRow, { label: 'Locale', value: locale.trim() }) : null
                ]
              }),
              jsx('div', {
                className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                children:
                  'Creating this course writes one course, one draft plan and one enrolment on this profile, then ' +
                  'queues one plan job. Research and drafting call the model; the plan arrives as a draft you review ' +
                  'before anything is approved.'
              }),
              jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: planTimingCopy(scope) }),
              recoverable
                ? jsxs('div', {
                    className: 'flex flex-col',
                    children: [
                      jsx(StatusRow, { label: 'Course saved', value: recoverable.courseId }),
                      recoverable.enrollmentId
                        ? jsx(StatusRow, { label: 'Enrollment saved', value: recoverable.enrollmentId })
                        : null
                    ]
                  })
                : null,
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
                children: submitting ? 'Creating course' : recoverable ? 'Retry the plan job' : 'Create course'
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
  { id: 'sources', label: 'Sources' },
  { id: 'export', label: 'Export' }
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
  self_reported: 'Self-reported',
  parent_reported: 'Parent reported',
  override: 'Override — not independent evidence'
}

// Frozen copy, docs/CHECKLIST-CONFIRMATION.md §9.4. A confirmation checklist is the learner's own
// statement that they did the steps; it is never an independent observation, so neither string may
// be softened into "mastered", "verified", "passed independently" or an unqualified "complete".
const SELF_REPORTED_CONFIRM_COPY =
  'You confirmed every step. This is your own report, not an independent check.'
const SELF_REPORTED_EVIDENCE_COPY =
  'Self-reported — you told us. It cannot count as independent evidence.'

/** The notice a bare evidence-class badge cannot carry, keyed by class. */
const EVIDENCE_CLASS_NOTICE = {
  self_reported: SELF_REPORTED_EVIDENCE_COPY
}

/**
 * A self-reported attempt never renders the unqualified `Passed` label: the badge carries the
 * qualifier with it wherever attempts are listed, so a row read out of context cannot claim an
 * independent pass.
 */
function verdictLabel(verdict, evidenceClass) {
  if (evidenceClass === 'self_reported' && verdict === 'pass') return 'Self-reported pass'
  return VERDICT_COPY[verdict] || verdict || 'unknown'
}

/** Next-step copy for a self-reported verdict; the generic strings say "complete" unqualified. */
const SELF_REPORTED_NEXT_ACTION = {
  complete_objective:
    'This objective advances on your own report, not an independent check. It will come back for review.',
  review_objective:
    'Access advanced on your own report. It is not independent evidence and it will return for review.',
  continue: 'Continue when you are ready; what you confirmed here was your own report.',
  retry_attempt: 'Tick the remaining steps and submit again. This stays your own report.'
}

function nextActionCopy(result) {
  if (!result) return 'The backend recorded the next action.'
  if (result.evidence_class === 'self_reported' && SELF_REPORTED_NEXT_ACTION[result.next_action]) {
    return SELF_REPORTED_NEXT_ACTION[result.next_action]
  }
  return NEXT_ACTION_COPY[result.next_action] || 'The backend recorded the next action.'
}

/**
 * The checklist answer object sent to `attempt.submit`.
 *
 * Frozen by docs/CHECKLIST-CONFIRMATION.md §9.2: `kind: "selection"` over the check's own item ids.
 * The label is the question, never the answer — sending labels, or mixing in the typed text, is a
 * different answer than the one the kernel grades (`unknown_check_item` otherwise).
 */
function checklistAnswer(ids) {
  return { kind: 'selection', selection: (ids || []).slice() }
}

/** The items a check card may tick: a served `verification` stimulus with declared items. */
function checklistItems(stimulus) {
  if (!stimulus || stimulus.format !== 'verification') return []
  return Array.isArray(stimulus.items) ? stimulus.items.filter((item) => item && item.id && item.label) : []
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
  const label = EVIDENCE_CLASS_COPY[value] || value || 'unknown'
  const notice = EVIDENCE_CLASS_NOTICE[value]
  if (!notice) {
    return jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: label })
  }
  // The frozen §9.4 sentence travels with the class wherever it is shown; a badge alone ("Self-
  // reported") could be read as a stronger claim than the learner actually made.
  return jsxs('span', {
    className: 'flex flex-wrap items-baseline gap-1',
    'data-cb-evidence-notice': value,
    children: [
      jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: label }),
      jsx('span', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: notice })
    ]
  })
}

function Hairline() {
  return jsx('div', { className: 'h-px w-full bg-(--ui-stroke-tertiary)' })
}

function QuietNote({ children }) {
  return jsx('p', { className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)', children })
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
function useOpenCheck({ enrollmentId, objectiveId, revision, enabled, implemented }) {
  const [state, setState] = useState({ status: 'idle', check: null, error: null })
  const [ticket, setTicket] = useState(0)
  // `check.open` returns identity only; the learner-facing stimulus (prompt, choices, items) is a
  // separate read. A build that does not implement `check.get` keeps today's answer-only surface
  // rather than guessing a question.
  const canReadStimulus = Boolean(implemented && implemented.has('check.get'))

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
        if (!response || !response.ok) {
          setState({ status: 'error', check: null, error: (response && response.error) || null })
          return
        }
        const opened = response.result
        setState({ status: 'ready', check: opened, error: null })
        if (!canReadStimulus || !opened || !opened.check_id) return
        rpc('check.get', { enrollment_id: enrollmentId, check_id: opened.check_id })
          .then((detail) => {
            if (cancelled || !detail || !detail.ok || !detail.result || !detail.result.stimulus) return
            setState((previous) =>
              previous.check && previous.check.check_id === opened.check_id
                ? { ...previous, check: { ...previous.check, stimulus: detail.result.stimulus } }
                : previous
            )
          })
          .catch(() => {})
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
  }, [enrollmentId, objectiveId, revision, enabled, canReadStimulus, ticket])

  return { ...state, reload: () => setTicket((value) => value + 1) }
}

/**
 * The answer object sent to `attempt.submit`.
 *
 * `text` carries the written answer (contract max 8000). `selection` is the closed-form channel and
 * the contract caps every item at 200 characters, so a long written answer must not be copied into
 * it — a 400-character sentence was rejected as VALIDATION_FAILED before grading ever ran. Short
 * answers still travel on both channels, because a closed-form check may grade on either field.
 */
const SELECTION_MAX_CHARS = 200
function attemptAnswer(answer) {
  const payload = { kind: 'text', text: answer }
  if (answer.length <= SELECTION_MAX_CHARS) payload.selection = [answer]
  return payload
}

/**
 * The graded half of a check, as a pure component so a Node test can render it without a backend.
 *
 * A `self_reported` pass never renders the generic "Passed" label: it renders the frozen §9.4
 * sentence, which is the only claim the learner actually made. A checklist result shows the
 * returned `criteria[]` against the served items (id → label, `met` → ticked/not) and a `partial`
 * keeps the check open by inviting the remaining steps.
 */
function AttemptVerdict({ result, criteria, checklist, onResumeChecklist, onNewExample, onExplain }) {
  const selfReported = Boolean(result && result.evidence_class === 'self_reported')
  const confirmed = (checklist || []).map((item) => {
    const match = (criteria || []).find((criterion) => criterion && criterion.id === item.id)
    return { id: item.id, label: item.label, met: Boolean(match && match.met) }
  })
  const confirmedCount = confirmed.filter((item) => item.met).length
  const selfReportedPass = selfReported && result.verdict === 'pass'
  return jsxs('div', {
    className: 'flex flex-col gap-2',
    'data-cb-verdict': result.verdict,
    'data-cb-evidence-class': result.evidence_class || null,
    children: [
      selfReportedPass
        ? jsx('strong', {
            className: 'max-w-prose text-sm font-medium',
            'data-cb-self-reported': 'confirmation',
            children: SELF_REPORTED_CONFIRM_COPY
          })
        : jsx('div', { className: 'text-sm font-medium', children: verdictLabel(result.verdict, result.evidence_class) }),

      confirmed.length > 0
        ? jsxs('div', {
            className: 'flex flex-col gap-1',
            'data-cb-check-criteria': String(confirmed.length),
            children: [
              jsx(sdk.PanelSectionLabel, { children: 'STEPS YOU CONFIRMED' }),
              jsx('ul', {
                className: 'flex flex-col gap-1.5',
                children: confirmed.map((item, index) =>
                  jsxs(
                    'li',
                    {
                      className: 'flex items-start gap-2',
                      'data-cb-criterion': item.id,
                      'data-cb-criterion-met': item.met ? 'true' : 'false',
                      children: [
                        jsx(sdk.Checkbox, {
                          checked: item.met,
                          disabled: true,
                          id: `cb-result-item-${index}`,
                          'aria-label': `${item.met ? 'Confirmed' : 'Not confirmed'}: ${item.label}`
                        }),
                        jsx('label', {
                          className: 'text-sm leading-snug',
                          htmlFor: `cb-result-item-${index}`,
                          children: item.label
                        }),
                        jsx('span', {
                          className: 'ml-auto text-xs text-(--ui-text-secondary)',
                          children: item.met ? 'Confirmed' : 'Not confirmed'
                        })
                      ]
                    },
                    item.id
                  )
                )
              })
            ]
          })
        : criteria.length > 0
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
                  `${item.id || 'criterion'}-${index}`
                )
              )
            })
          : jsx(QuietNote, { children: 'No criterion detail was returned for this verdict.' }),

      confirmed.length > 0 && !selfReportedPass
        ? jsx(QuietNote, {
            children: `You confirmed ${confirmedCount} of ${confirmed.length} steps. Tick the remaining steps and submit again; this stays your own report, not an independent check.`
          })
        : null,

      jsx(QuietNote, { children: nextActionCopy(result) }),

      selfReportedPass
        ? null
        : jsxs('div', {
            className: 'flex flex-wrap items-center gap-2',
            children: [
              confirmed.length > 0
                ? jsx(sdk.Button, {
                    variant: 'default',
                    size: 'sm',
                    onClick: onResumeChecklist,
                    children: 'Tick the remaining steps'
                  })
                : jsx(sdk.Button, {
                    variant: 'secondary',
                    size: 'sm',
                    onClick: onNewExample,
                    children: 'Try a new example'
                  }),
              confirmed.length > 0
                ? null
                : jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: onExplain, children: 'Explain the difference' })
            ]
          })
    ]
  })
}

/**
 * One attempt, started and finished in the pane or on the lesson page.
 *
 * Idempotency is enrollment + check + a per-view nonce: retrying a failed grade re-sends the SAME
 * nonce, so the backend returns the stored attempt instead of writing a second one. A written
 * answer carries both `text` and a one-element `selection`; a checklist answer carries only
 * `kind: "selection"` with the ticked item ids.
 */
function AttemptControls({
  enrollmentId,
  objectiveId,
  check,
  revision,
  implemented,
  bindingState,
  onCommitted,
  parentLed = false
}) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const [text, setText] = useState('')
  const [ticked, setTicked] = useState([])
  const [phase, setPhase] = useState('awaiting_input')
  const [result, setResult] = useState(null)
  const [resultCheck, setResultCheck] = useState(null)
  const [error, setError] = useState(null)
  const [overrideOpen, setOverrideOpen] = useState(false)
  const nonceRef = useRef(null)
  const answerRef = useRef(null)
  const resultRef = useRef(null)
  const detached = Boolean(bindingState && bindingState !== 'active')

  // What this card is asking for. A `verification` stimulus with declared items is a checklist and
  // is answered with the item ids; every other stimulus keeps the written-answer path.
  const stimulus = check ? check.stimulus || null : null
  const servedItems = stimulus && Array.isArray(stimulus.items) ? stimulus.items : []
  // A parent-led lesson is observed by an adult through the observation control (H-21), never ticked here.
  const checklist = parentLed ? [] : checklistItems(stimulus)
  const readOnlyItems = parentLed ? [] : checklist.length > 0 ? [] : servedItems

  // The answer form unmounts when a verdict arrives; put focus on the verdict itself so a keyboard
  // user is not dropped back on <body> with no idea whether the submission went through.
  useEffect(() => {
    if (phase === 'graded' || phase === 'needs_retry' || phase === 'overridden') {
      resultRef.current?.focus({ preventScroll: true })
    }
  }, [phase])

  // A verdict stays on screen until the learner acts on it. Committing an attempt refreshes the
  // section and opens the next check version; that refresh must not wipe the feedback the person
  // just earned (the panel used to snap straight to an empty v3 form).
  useEffect(() => {
    if (result) return
    setText('')
    setTicked([])
    setPhase('awaiting_input')
    setResult(null)
    setResultCheck(null)
    setError(null)
    nonceRef.current = null
  }, [check && check.check_id, result])
  const displayCheck = resultCheck || check

  const submit = useCallback(async () => {
    if (!check) return
    // A checklist submits the ticked item ids, never the labels and never the typed text (§9.2).
    const answer = checklist.length > 0 ? checklistAnswer(ticked) : attemptAnswer(text.trim())
    if (checklist.length > 0 && ticked.length === 0) {
      setError({ code: 'VALIDATION_FAILED', message: 'Tick at least one step before submitting.' })
      return
    }
    if (checklist.length === 0 && !text.trim()) {
      setError({ code: 'VALIDATION_FAILED', message: 'Write an answer before submitting.' })
      return
    }
    answerRef.current = answer
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
        answer
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
    setResultCheck(check)
    setPhase(graded.verdict === 'needs_retry' ? 'needs_retry' : 'graded')
    if (onCommitted) onCommitted(graded)
  }, [check, text, ticked, checklist, enrollmentId, revision, onCommitted])

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
        answer: answerRef.current || (checklist.length > 0 ? checklistAnswer(ticked) : attemptAnswer(text.trim()))
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
    setResultCheck(check)
    setPhase(response.result.verdict === 'needs_retry' ? 'needs_retry' : 'graded')
    if (onCommitted) onCommitted(response.result)
  }, [check, text, ticked, checklist, enrollmentId, revision, onCommitted])

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
    setResultCheck(check)
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
  // The learner-facing question, projected by `check.get`. `check.open` carries identity only, so a
  // build without that read simply has no stimulus here and shows the answer form alone.
  const choices = stimulus && Array.isArray(stimulus.choices) ? stimulus.choices : []
  const toggleItem = (id, next) => {
    setTicked((previous) => {
      const already = previous.includes(id)
      if (next && !already) return [...previous, id]
      if (!next && already) return previous.filter((item) => item !== id)
      return previous
    })
  }
  const checklistEmpty = checklist.length > 0 && ticked.length === 0
  // A partial keeps the check open: tick the rest and submit again. That is a new attempt, so the
  // per-view nonce is dropped rather than replaying the stored partial.
  const resumeChecklist = () => {
    nonceRef.current = null
    setError(null)
    setPhase('awaiting_input')
  }

  return jsxs('div', {
    className: 'flex flex-col gap-2',
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: `Check v${displayCheck.check_version}` }),
          jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: displayCheck.evidence_target || 'evidence' }),
          result && result.evidence_class ? jsx(EvidenceClassText, { value: result.evidence_class }) : null
        ]
      }),

      stimulus && stimulus.prompt
        ? jsxs('div', {
            className: 'flex flex-col gap-2',
            'data-cb-check-stimulus': check.check_id,
            children: [
              jsx('div', {
                className: 'max-w-prose',
                children: jsx(sdk.MessageTextContent, { text: stimulus.prompt })
              }),
              stimulus.learner_instructions
                ? jsx('p', {
                    className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                    children: stimulus.learner_instructions
                  })
                : null,
              choices.length > 0
                ? jsx('ul', {
                    className: 'flex flex-col gap-1 text-sm leading-snug',
                    'aria-label': 'Choices',
                    children: choices.map((choice, index) =>
                      jsx('li', { key: `choice-${index}`, children: choice })
                    )
                  })
                : null,
              checklist.length > 0
                ? jsxs('div', {
                    className: 'flex flex-col gap-1',
                    'data-cb-check-items': String(checklist.length),
                    'data-cb-check-items-mode': 'selection',
                    children: [
                      jsx(sdk.PanelSectionLabel, { children: 'CHECKLIST' }),
                      // One row per declared item: the served id is the submitted value, the label
                      // is the question. Ticking is the answer; nothing is typed here.
                      jsx('ul', {
                        className: 'flex flex-col gap-1.5',
                        'aria-label': 'Checklist',
                        children: checklist.map((item, index) =>
                          jsxs(
                            'li',
                            {
                              className: 'flex items-start gap-2',
                              'data-cb-check-item': item.id,
                              children: [
                                jsx(sdk.Checkbox, {
                                  'aria-describedby': 'cb-attempt-help',
                                  checked: ticked.includes(item.id),
                                  'data-cb-check-tick': item.id,
                                  disabled: locked || detached,
                                  id: `cb-check-item-${index}`,
                                  onCheckedChange: (next) => toggleItem(item.id, next === true)
                                }),
                                jsx('label', {
                                  className: 'text-sm leading-snug',
                                  htmlFor: `cb-check-item-${index}`,
                                  children: item.label
                                })
                              ]
                            },
                            item.id
                          )
                        )
                      })
                    ]
                  })
                : readOnlyItems.length > 0
                  ? jsxs('div', {
                      className: 'flex flex-col gap-1',
                      'data-cb-check-items': String(readOnlyItems.length),
                      'data-cb-check-items-mode': 'read_only',
                      children: [
                        jsx(sdk.PanelSectionLabel, { children: 'CHECKLIST' }),
                        // One label per item, printed here and nowhere else in the lesson.
                        jsx('ul', {
                          className: 'flex flex-col gap-1',
                          'aria-label': 'Checklist',
                          children: readOnlyItems.map((item) =>
                            jsx('li', {
                              key: item.id,
                              className: 'text-sm leading-snug',
                              'data-cb-check-item': item.id,
                              children: item.label
                            })
                          )
                        })
                      ]
                    })
                  : null
            ]
          })
        : null,

      showForm
        ? jsxs('div', {
            className: 'flex flex-col gap-2',
            'data-cb-answer-kind': checklist.length > 0 ? 'selection' : 'text',
            children: [
              checklist.length > 0
                ? jsx('p', {
                    id: 'cb-attempt-help',
                    className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                    children:
                      'Tick every step you actually completed. Your ticks are recorded as your own report, not as an independent check.'
                  })
                : jsx('label', {
                    className: 'text-xs font-medium text-(--ui-text-secondary)',
                    htmlFor: 'cb-attempt-answer',
                    children: 'Your answer'
                  }),
              checklist.length > 0
                ? null
                : jsx(sdk.Textarea, {
                    id: 'cb-attempt-answer',
                    'aria-describedby': 'cb-attempt-help',
                    disabled: locked || detached,
                    onChange: (event) => setText(event.target.value),
                    placeholder: 'Type the answer you would give in the lesson.',
                    rows: 3,
                    value: text
                  }),
              checklist.length > 0
                ? null
                : jsx('p', {
                    id: 'cb-attempt-help',
                    className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
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
                    disabled: locked || detached || (checklist.length > 0 ? checklistEmpty : !text.trim()),
                    onClick: submit,
                    children: locked ? 'Submitting' : checklist.length > 0 ? 'Submit confirmation' : 'Submit answer'
                  }),
                  checklist.length > 0
                    ? jsx(sdk.Button, {
                        variant: 'text',
                        size: 'sm',
                        disabled: locked || ticked.length === 0,
                        onClick: () => {
                          setTicked([])
                          setError(null)
                        },
                        children: 'Clear ticks'
                      })
                    : jsx(sdk.Button, {
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
        ? jsxs('div', {
            className: 'flex items-center gap-2 text-xs text-(--ui-text-secondary)',
            children: [
              jsx(sdk.Loader, { label: 'Grading this answer' }),
              jsx('span', { children: 'Answer locked. No second attempt is created while this runs.' })
            ]
          })
        : null,

      phase === 'graded' && result
        ? jsxs('div', {
            className: 'flex flex-col gap-2 outline-none',
            ref: resultRef,
            tabIndex: -1,
            children: [
              jsx(AttemptVerdict, {
                result,
                criteria,
                checklist,
                onResumeChecklist: resumeChecklist,
                onNewExample: () => {
                  setText('')
                  setTicked([])
                  setResult(null)
                  setResultCheck(null)
                  setPhase('awaiting_input')
                  nonceRef.current = null
                },
                onExplain: () => setPhase('awaiting_input')
              })
            ]
          })
        : null,

      phase === 'needs_retry'
        ? jsxs('div', {
            className: 'flex flex-col gap-2 outline-none',
            ref: resultRef,
            tabIndex: -1,
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
            className: 'flex flex-col gap-2 outline-none',
            ref: resultRef,
            tabIndex: -1,
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
                  setResultCheck(null)
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

      jsx(FocusReturningDialog, {
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

/**
 * The notebook's provenance ref.
 *
 * `notebook.save` has a course/objective column pair and one opaque `source_ref` string (≤500
 * chars). A saved moment can point at a block, its artifact, several source ids and the check it
 * came from, so those refs travel as one compact JSON object in that column. A caller that only
 * has a bare id keeps passing the bare id; `readNotebookRef` reads both, so older rows still
 * resolve and the backend schema is untouched.
 */
function notebookSourceRef(seed) {
  if (!seed) return null
  const ref = {}
  if (seed.block_id) ref.block = String(seed.block_id).slice(0, 120)
  if (seed.artifact_id) ref.artifact = String(seed.artifact_id).slice(0, 120)
  if (Array.isArray(seed.source_ids) && seed.source_ids.length > 0) {
    ref.sources = seed.source_ids.filter(Boolean).slice(0, 8).map((id) => String(id).slice(0, 80))
  }
  if (seed.check_id) ref.check = String(seed.check_id).slice(0, 120)
  if (Object.keys(ref).length === 0) return seed.source_ref ? String(seed.source_ref).slice(0, 500) : null
  return JSON.stringify(ref).slice(0, 500)
}

/** Read a `source_ref` written by `notebookSourceRef`, or an older bare id. Never guesses one. */
function readNotebookRef(value) {
  const ref = { block_id: null, artifact_id: null, source_ids: [], check_id: null, legacy: null }
  if (!value) return ref
  const text = String(value)
  if (text.charAt(0) === '{') {
    try {
      const parsed = JSON.parse(text)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        ref.block_id = typeof parsed.block === 'string' ? parsed.block : null
        ref.artifact_id = typeof parsed.artifact === 'string' ? parsed.artifact : null
        ref.source_ids = Array.isArray(parsed.sources) ? parsed.sources.filter((id) => typeof id === 'string') : []
        ref.check_id = typeof parsed.check === 'string' ? parsed.check : null
        return ref
      }
    } catch (error) {
      // A hand-written or truncated value is still a reference, just not a structured one.
    }
  }
  ref.legacy = text
  return ref
}

/** Save one moment into the notebook: excerpt preview, note, tags, provenance. */
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

  const provenance = []
  if (seed && seed.course_title) provenance.push({ label: 'Course', value: seed.course_title })
  if (seed && seed.objective_title) provenance.push({ label: 'Objective', value: seed.objective_title })
  if (seed && seed.block_headline) provenance.push({ label: 'Saved from', value: seed.block_headline })
  const sourceNames = (seed && (seed.source_titles || seed.source_ids)) || []
  if (sourceNames.length > 0) {
    provenance.push({ label: sourceNames.length === 1 ? 'Source' : 'Sources', value: sourceNames.join(', ') })
  }
  if (seed && seed.artifact_id) provenance.push({ label: 'Media', value: seed.artifact_id })

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
      source_ref: notebookSourceRef(seed)
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

  return jsx(FocusReturningDialog, {
    open,
    title: 'Save to notebook',
    description: 'Saved excerpts and personal notes stay on this profile. They never enter a shared pack.',
    confirmLabel: busy ? 'Saving' : 'Save to notebook',
    onClose,
    onConfirm: save,
    children: jsxs('div', {
      className: 'flex flex-col gap-3',
      children: [
        provenance.length > 0
          ? jsxs('div', {
              className: 'flex flex-col gap-0.5',
              'data-cb-save-provenance': 'ready',
              children: provenance.map((item) =>
                jsxs(
                  'div',
                  {
                    className: 'flex flex-wrap items-baseline gap-1 text-xs',
                    children: [
                      jsx('span', { className: 'text-(--ui-text-secondary)', children: `${item.label} ·` }),
                      jsx('span', { className: 'min-w-0 break-words', children: item.value })
                    ]
                  },
                  item.label
                )
              )
            })
          : jsx('div', {
              className: 'text-xs text-(--ui-text-secondary)',
              'data-cb-save-provenance': 'none',
              children: 'This moment has no block or source attached; it is saved under the section you are reading.'
            }),
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

/**
 * ── Ink & Field Notes: the scoped Coursebook token layer ────────────────────────────────────
 *
 * The Desktop SDK has no per-route theme seam: `THEMES_AREA` registers an app-wide theme, and a
 * runtime plugin may import only `@hermes/plugin-sdk`, `react` and `react/jsx-runtime`, so a
 * second stylesheet cannot be shipped as a module. The smallest honest seam is therefore a scoped
 * route shell: the token table below is applied as CSS custom properties on the Coursebook route
 * and pane roots only, and every Coursebook surface paints from `var(--cb-*)`. Hermes chrome is
 * untouched, and the host's own `--ui-*` tokens still supply anything outside this layer.
 *
 * The table is one embedded JSON literal so `tests/test_desktop_tokens.py` can read the shipped
 * module, compare it byte-for-byte with `contracts/cb.tokens.v1.json`, and compute WCAG contrast
 * on the values that actually ship. `CB_TOKENS_JSON` is the ONLY colour literal in this file: the
 * test refuses any hex outside it.
 */
const CB_TOKENS_JSON =
  '{"light":{"paper":"#f7f3ea","paper-raised":"#fffdf7","ink":"#191713","ink-soft":"#5a5347","rule":"#d9d1c2","accent":"#2f4a8a","accent-soft":"#e4e9f4","field":"#3f5c33","ochre":"#7a4e0d","coral":"#9e2f1d"},"dark":{"paper":"#141312","paper-raised":"#1e1c19","ink":"#f2ece0","ink-soft":"#b5aa97","rule":"#3b372f","accent":"#9db5ee","accent-soft":"#232b3c","field":"#9cba87","ochre":"#d7a94e","coral":"#e38a76"}}'

const CB_TOKENS = JSON.parse(CB_TOKENS_JSON)
const CB_TOKEN_NAMES = Object.freeze([
  'paper',
  'paper-raised',
  'ink',
  'ink-soft',
  'rule',
  'accent',
  'accent-soft',
  'field',
  'ochre',
  'coral'
])

/** The rail collapses before the reading measure does. 1024px is the app's own rail breakpoint. */
const CB_WIDE_BREAKPOINT = 1024
/** A comfortable reading measure (62-72 characters) for the lesson column. */
const CB_MEASURE = '68ch'
const CB_RAIL_WIDTH = '19rem'

/** Painted light/dark, from the SDK's own theme context. Never inferred from a colour value. */
function cbModeFromTheme(theme) {
  const mode = theme && (theme.renderedMode || theme.resolvedMode)
  return mode === 'light' || mode === 'dark' ? mode : null
}

/**
 * `useTheme()` is a hook, so it may only be called when the running host exports it. The
 * fallback reads the `.dark` class the host's theme context toggles on `:root`; older hosts
 * therefore still land on the right palette, they just do not repaint mid-session.
 */
function useCbMode() {
  const theme = typeof sdk.useTheme === 'function' ? sdk.useTheme() : null
  const painted = cbModeFromTheme(theme)
  if (painted) return painted
  try {
    if (typeof document !== 'undefined' && document.documentElement) {
      return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
    }
  } catch (error) {
    // A host without a document (SSR) falls through to the light default.
  }
  return 'light'
}

/** The scoped custom properties. Inline, so the layer travels with the route and nothing leaks. */
function cbScopeStyle(mode) {
  const palette = CB_TOKENS[mode === 'dark' ? 'dark' : 'light']
  const style = {}
  for (const name of CB_TOKEN_NAMES) style[`--cb-${name}`] = palette[name]
  style.colorScheme = mode === 'dark' ? 'dark' : 'light'
  style.backgroundColor = 'var(--cb-paper)'
  style.color = 'var(--cb-ink)'
  return style
}

/** Motion is functional only; a reduced-motion reader gets none of the transitions. */
function cbMotionPreference(media) {
  return media && media.matches === true ? 'reduced' : 'full'
}

function useCbMotion() {
  const read = () => {
    try {
      if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
        return cbMotionPreference(window.matchMedia('(prefers-reduced-motion: reduce)'))
      }
    } catch (error) {
      // No matchMedia: assume the default, motion-on posture.
    }
    return 'full'
  }
  const [motion, setMotion] = useState(read)
  useEffect(() => {
    let media = null
    try {
      media = typeof window !== 'undefined' && typeof window.matchMedia === 'function'
        ? window.matchMedia('(prefers-reduced-motion: reduce)')
        : null
    } catch (error) {
      media = null
    }
    if (!media) return undefined
    const onChange = () => setMotion(cbMotionPreference(media))
    onChange()
    if (typeof media.addEventListener === 'function') media.addEventListener('change', onChange)
    else if (typeof media.addListener === 'function') media.addListener(onChange)
    return () => {
      if (typeof media.removeEventListener === 'function') media.removeEventListener('change', onChange)
      else if (typeof media.removeListener === 'function') media.removeListener(onChange)
    }
  }, [])
  return motion
}

/** Live width from `host.state.viewport`, with a static read for hosts that predate the atom. */
function useCbViewportWidth() {
  const atom = sdk.host && sdk.host.state ? sdk.host.state.viewport : null
  const read = () => {
    try {
      const rect = atom && typeof atom.get === 'function' ? atom.get() : null
      if (rect && typeof rect.width === 'number') return rect.width
    } catch (error) {
      // A host without the atom reports 0, which stacks the rail rather than overflowing.
    }
    return 0
  }
  if (atom && typeof sdk.useValue === 'function') {
    const rect = sdk.useValue(atom)
    if (rect && typeof rect.width === 'number') return rect.width
  }
  return read()
}

/** Pure so the layout decision is testable without a window: wide only when the width is known. */
function cbLayoutFor(width) {
  return typeof width === 'number' && width >= CB_WIDE_BREAKPOINT ? 'wide' : 'stacked'
}

function CbRailSection({ label, children }) {
  return jsxs('section', {
    'data-cb-rail-section': label,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.3rem',
      paddingTop: '0.6rem',
      borderTop: '1px solid var(--cb-rule)'
    },
    children: [
      jsx('div', {
        style: {
          fontSize: '0.65rem',
          fontWeight: 600,
          letterSpacing: '0.09em',
          textTransform: 'uppercase',
          color: 'var(--cb-ink-soft)'
        },
        children: label
      }),
      children
    ]
  })
}

/**
 * The Field rail: next action, the section's own facts, source cards and saved notes. It is the
 * third part of the workspace and becomes a bottom sheet (a stacked section) below 1024px.
 */
function FieldRail({ next, facts, sources, notes }) {
  const sourceRows = (sources || []).slice(0, 4)
  const noteRows = (notes || []).slice(0, 3)
  return jsxs('aside', {
    'data-cb-field-rail': '',
    style: { display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.8rem', lineHeight: 1.5 },
    children: [
      jsx(CbRailSection, {
        label: 'Next action',
        children: jsx('div', {
          'data-cb-next-action': '',
          style: { color: 'var(--cb-ink)', fontWeight: 500 },
          children: next || 'No next action was recorded for this section.'
        })
      }),
      facts && facts.length
        ? jsx(CbRailSection, {
            label: 'This section',
            children: jsx('div', {
              style: { display: 'flex', flexDirection: 'column', gap: '0.15rem', color: 'var(--cb-ink-soft)' },
              children: facts.map((fact) =>
                jsxs('div', { style: { display: 'flex', justifyContent: 'space-between', gap: '0.5rem' }, children: [
                  jsx('span', { children: fact.label }),
                  jsx('span', { style: { color: 'var(--cb-ink)', textAlign: 'right' }, children: fact.value })
                ]}, fact.label)
              )
            })
          })
        : null,
      jsx(CbRailSection, {
        label: 'Source cards',
        children: sourceRows.length
          ? jsx('div', { style: { display: 'flex', flexDirection: 'column', gap: '0.35rem' }, children: sourceRows.map((source) =>
              jsxs('div', {
                'data-cb-source-card': source.source_id || '',
                style: { display: 'flex', flexDirection: 'column', gap: '0.05rem', borderLeft: '2px solid var(--cb-rule)', paddingLeft: '0.45rem' },
                children: [
                  jsx('span', { style: { color: 'var(--cb-ink)' }, children: source.title || 'Untitled source' }),
                  jsx('span', { style: { fontSize: '0.7rem', color: 'var(--cb-ink-soft)' }, children: source.support_status || 'status unrecorded' })
                ]
              }, source.source_id || source.title)
            ) })
          : jsx('div', { style: { color: 'var(--cb-ink-soft)' }, children: 'The backend recorded no sources for this course.' })
      }),
      jsx(CbRailSection, {
        label: 'Saved notes',
        children: noteRows.length
          ? jsx('div', { style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', color: 'var(--cb-ink-soft)' }, children: noteRows.map((entry) =>
              jsx('div', { 'data-cb-rail-note': entry.entry_id || '', children: entry.excerpt || entry.note || entry.kind }, entry.entry_id || entry.excerpt)
            ) })
          : jsx('div', { style: { color: 'var(--cb-ink-soft)' }, children: 'Nothing saved from this section yet.' })
      })
    ]
  })
}

/**
 * The three-part lesson workspace: header, reading column, field rail. Layout is computed from the
 * live viewport width rather than a media query, because a runtime plugin cannot ship a stylesheet;
 * the rail stacks under the reading column at 460px instead of shrinking the text.
 */
function WorkspaceShell({ eyebrow, title, subtitle, meta, actions, rail, children }) {
  const width = useCbViewportWidth()
  const layout = cbLayoutFor(width)
  const wide = layout === 'wide'
  return jsxs('div', {
    'data-cb-workspace-shell': layout,
    style: { display: 'flex', flexDirection: 'column', gap: '0.85rem', minHeight: 0 },
    children: [
      jsxs('header', {
        'data-cb-workspace-header': '',
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: '0.5rem',
          paddingBottom: '0.5rem',
          borderBottom: '1px solid var(--cb-rule)'
        },
        children: [
          jsxs('div', {
            style: { minWidth: 0, display: 'flex', flexDirection: 'column', gap: '0.15rem' },
            children: [
              eyebrow
                ? jsx('div', {
                    style: {
                      fontSize: '0.65rem',
                      fontWeight: 600,
                      letterSpacing: '0.1em',
                      textTransform: 'uppercase',
                      color: 'var(--cb-ink-soft)'
                    },
                    children: eyebrow
                  })
                : null,
              jsx('h2', {
                'data-cb-workspace-title': '',
                style: {
                  margin: 0,
                  fontSize: 'clamp(1.45rem, 1.1rem + 1.2vw, 2rem)',
                  lineHeight: 1.15,
                  letterSpacing: '-0.01em',
                  color: 'var(--cb-ink)'
                },
                children: title
              }),
              subtitle
                ? jsx('div', { style: { fontSize: '0.85rem', color: 'var(--cb-ink-soft)' }, children: subtitle })
                : null
            ]
          }),
          actions
            ? jsx('div', {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'flex-end', gap: '0.35rem' },
                children: actions
              })
            : null
        ]
      }),
      meta && meta.length
        ? jsx('div', {
            'data-cb-route-meta': '',
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--cb-ink-soft)' },
            children: meta
          })
        : null,
      jsxs('div', {
        'data-cb-workspace-body': '',
        style: wide
          ? { display: 'grid', gridTemplateColumns: `minmax(0, 1fr) ${CB_RAIL_WIDTH}`, alignItems: 'start', gap: '1.25rem' }
          : { display: 'flex', flexDirection: 'column', gap: '1rem' },
        children: [
          jsx('div', {
            'data-cb-reading-column': '',
            style: { minWidth: 0, maxWidth: wide ? CB_MEASURE : '100%' },
            children
          }),
          rail
            ? jsx('div', {
                'data-cb-rail-slot': wide ? 'side' : 'bottom',
                style: wide ? { minWidth: 0 } : { minWidth: 0, borderTop: '1px solid var(--cb-rule)', paddingTop: '0.75rem' },
                children: rail
              })
            : null
        ]
      })
    ]
  })
}

/**
 * A field-note frame: thin rule, the media itself, a caption, a provenance line and an explicit
 * text-equivalent disclosure. It is never decoration: a media item with no teaching role does not
 * belong in a lesson document, and a failed preview keeps the text equivalent rather than
 * substituting a fake file.
 */
function MediaFrame({ artifactId, kind, label, caption, provenance, textEquivalent, children }) {
  return jsxs('figure', {
    'data-cb-media': artifactId || 'text-only',
    'data-cb-media-kind': kind || 'visual',
    style: {
      margin: '0.75rem 0',
      padding: '0.6rem 0.75rem 0.6rem 0.85rem',
      borderLeft: '2px solid var(--cb-rule)',
      background: 'var(--cb-paper-raised)',
      maxWidth: '48rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.4rem'
    },
    children: [
      children,
      caption
        ? jsx('figcaption', {
            'data-cb-media-caption': '',
            style: { fontSize: '0.85rem', lineHeight: 1.5, color: 'var(--cb-ink)' },
            children: caption
          })
        : null,
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem', fontSize: '0.7rem', color: 'var(--cb-ink-soft)' },
        children: [
          label
            ? jsx('span', {
                'data-cb-media-label': '',
                style: {
                  border: '1px solid var(--cb-rule)',
                  borderRadius: '0.25rem',
                  padding: '0 0.3rem',
                  color: 'var(--cb-ink-soft)'
                },
                children: label
              })
            : null,
          provenance
            ? jsx('span', { 'data-cb-media-provenance': '', children: provenance })
            : null
        ]
      }),
      textEquivalent
        ? jsxs('details', {
            'data-cb-media-text-equivalent': '',
            style: { fontSize: '0.75rem', color: 'var(--cb-ink-soft)' },
            children: [
              jsx('summary', { style: { cursor: 'pointer' }, children: 'Text equivalent' }),
              jsx('div', { style: { paddingTop: '0.25rem', lineHeight: 1.5 }, children: textEquivalent })
            ]
          })
        : null
    ]
  })
}

function MediaSegment({ segment }) {
  const preview = useArtifactPreview(segment.artifact_id)

  // The authored kind is the description of the item; a served MIME is the observation. The
  // observation wins once the preview is ready, but a route that refuses or is unreachable must
  // not silently turn authored narration into a visual.
  const authoredKind = segment.kind === 'audio' || segment.kind === 'visual' ? segment.kind : null
  const previewKind =
    preview.state === 'ready' && preview.mime
      ? preview.mime.startsWith('audio/')
        ? 'audio'
        : preview.mime.startsWith('image/')
          ? 'visual'
          : null
      : null
  const kind = previewKind || authoredKind || 'visual'
  const caption = segment.text || preview.text_equivalent || ''
  const label =
    preview.label ||
    segment.label ||
    (kind === 'audio' ? 'Narration' : 'Illustration')
  const provenance =
    preview.state === 'ready'
      ? [
          preview.mime,
          typeof preview.bytes === 'number' ? `${preview.bytes} bytes` : null,
          segment.purpose || 'served by this host’s artifact route'
        ].filter(Boolean).join(' · ')
      : null
  const textEquivalent =
    preview.text_equivalent || segment.text_equivalent || segment.purpose || null
  const element =
    preview.state === 'ready' && preview.mime === 'image/svg+xml'
      ? jsx('img', {
          alt: caption,
          style: { maxHeight: '380px', width: '100%', objectFit: 'contain' },
          loading: 'lazy',
          src: preview.data_url
        })
      : preview.state === 'ready' && preview.mime && preview.mime.startsWith('image/')
        ? jsx('img', {
            alt: caption,
            style: { maxHeight: '380px', width: '100%', objectFit: 'contain', borderRadius: '0.125rem' },
            loading: 'lazy',
            src: preview.data_url
          })
        : preview.state === 'ready' && preview.mime && preview.mime.startsWith('audio/')
          ? jsx('audio', {
              'aria-label': caption || 'Coursebook narration',
              style: { width: '100%' },
              controls: true,
              preload: 'metadata',
              src: preview.data_url
            })
          : preview.state === 'loading'
            ? jsx('div', { style: { padding: '0.35rem 0', fontSize: '0.75rem', color: 'var(--cb-ink-soft)' }, children: 'Loading media' })
            : jsx('div', {
                style: { padding: '0.25rem 0', fontSize: '0.75rem', lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                children: preview.message
              })
  return jsx(MediaFrame, {
    artifactId: segment.artifact_id,
    kind,
    label,
    caption,
    provenance,
    textEquivalent: textEquivalent && textEquivalent !== caption ? textEquivalent : null,
    children: jsxs('div', {
      style: { display: 'flex', flexDirection: 'column', gap: '0.35rem' },
      children: [
        element,
        segment.artifact_id && supportsArtifactGet()
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
              children: 'Artifact details'
            })
          : null
      ]
    })
  })
}

function supportsArtifactGet() {
  return backendSupports('artifact.get')
}

/**
 * One artifact preview through the plugin's own media route.
 *
 * The route is the only door this module has to media bytes, and it answers with a data URL for
 * renderable types only. `MediaSegment` and the pronunciation reference share this loader, so the
 * practice loop cannot grow a second audio source beside the lesson's own narration.
 */
function useArtifactPreview(artifactId) {
  const [preview, setPreview] = useState({ state: 'loading' })
  useEffect(() => {
    let live = true
    if (!artifactId) {
      setPreview({ state: 'text', message: 'No generated artifact is attached; the text equivalent is shown.' })
      return () => {
        live = false
      }
    }
    setPreview({ state: 'loading' })
    rest(`/media/${encodeURIComponent(artifactId)}`)
      .then((response) => {
        if (!live) return
        if (!response || response.ok !== true || typeof response.data_url !== 'string') {
          setPreview({
            state: 'text',
            message: (response && response.message) || 'This media could not be previewed; the text equivalent remains.'
          })
          return
        }
        setPreview({ state: 'ready', ...response })
      })
      .catch((error) => {
        if (live) {
          setPreview({
            state: 'text',
            message: `This media could not be previewed (${describeError(error)}); the text equivalent remains.`
          })
        }
      })
    return () => {
      live = false
    }
  }, [artifactId])
  return preview
}

/* ── Pronunciation Studio ────────────────────────────────────────────────────────────────────
 * docs/VISUAL_MEDIA_PLAN.md §7. The model phrase is the lesson's own narration artifact and its
 * authored transcript; the learner plays it, records one explicit take, and the backend compares
 * the transcript with its own recogniser.
 *
 * The honesty rules this component is built around, and why each exists:
 *   - the reference is loaded through the one media route and never autoplays — a lesson's audio
 *     is never a surprise, and there is no second audio source in this module;
 *   - capture starts only on an explicit Record press and stops on Stop/unmount; nothing listens
 *     in the background and no take is captured while the reader is doing something else;
 *   - the number on screen is the recogniser's own `confidence` and the deterministic word
 *     comparison the backend already returned. This component computes no score, so a fabricated
 *     percentage is not expressible here;
 *   - the result is labelled `model_assessed` and described as a practice measurement, never as
 *     "verified pronunciation", mastery or a graded pass;
 *   - without a recogniser the surface says "Practice only, not graded" and does not offer a
 *     Record control that would imply a grade;
 *   - the take is deleted from memory after comparison. Coursebook retains no audio at all.
 */
const PRONUNCIATION_VERDICT_COPY = {
  meets_target: 'Meets the target phrase',
  close: 'Close — another pass would help',
  needs_practice: 'Needs practice',
  unavailable: 'Not assessed'
}

const PRONUNCIATION_REASON_COPY = {
  empty_transcript: 'The recogniser did not catch any speech. Try again a little closer to the microphone.',
  transcription_failed: 'The recogniser could not transcribe this take. Nothing was recorded as evidence.',
  stt_dependency_missing: 'the local recogniser is not installed',
  ffmpeg_missing: 'the audio decoder is not installed',
  model_unavailable: 'the local model is not available',
  stt_cache_unavailable: 'the local model cache is unavailable',
  numpy_missing: 'the numeric runtime is not installed',
  decode_failed: 'the take could not be decoded',
  decode_empty: 'the take decoded to silence',
  audio_too_long: 'the take is longer than the 30 second limit'
}

/** An honest percentage: only a real 0..1 number becomes a percent, otherwise nothing prints. */
function pronPercent(value) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1) return null
  return `${Math.round(value * 100)}%`
}

function pronUnitLabel(unit) {
  return unit === 'character' ? 'characters' : 'words'
}

/** The backend's own per-unit comparison, printed as it was returned. */
function PronunciationWords({ words, unit }) {
  const list = Array.isArray(words) ? words : []
  if (list.length === 0) return null
  return jsx('ol', {
    'data-cb-pronunciation-words': String(list.length),
    'aria-label': `Comparison by ${pronUnitLabel(unit)}`,
    style: { display: 'flex', flexWrap: 'wrap', gap: '0.35rem', listStyle: 'none', margin: 0, padding: 0 },
    children: list.map((word, index) =>
      jsxs(
        'li',
        {
          'data-cb-pronunciation-word': word.match ? 'match' : 'miss',
          style: {
            display: 'inline-flex',
            alignItems: 'baseline',
            gap: '0.3rem',
            border: `1px solid ${word.match ? 'var(--cb-rule)' : 'var(--cb-ink-soft)'}`,
            borderRadius: '0.25rem',
            padding: '0.05rem 0.35rem',
            fontSize: '0.85rem'
          },
          children: [
            jsx('span', { children: word.expected || '—' }),
            word.match
              ? null
              : jsx('span', {
                  style: { fontSize: '0.7rem', color: 'var(--cb-ink-soft)' },
                  children: word.heard ? `heard “${word.heard}”` : 'not heard'
                }),
            word.match && pronPercent(word.confidence)
              ? jsx('span', {
                  'data-cb-word-confidence': pronPercent(word.confidence),
                  style: { fontSize: '0.65rem', color: 'var(--cb-ink-soft)' },
                  children: pronPercent(word.confidence)
                })
              : null
          ]
        },
        `${word.expected || 'unit'}-${index}`
      )
    )
  })
}

/** One honest status line: what would assess a take right now, and where it runs. */
function pronunciationAvailabilityCopy(status) {
  if (!status || status.state === 'loading') return { tone: 'loading', text: 'Checking for a recogniser on this machine.' }
  if (status.state === 'error') {
    return {
      tone: 'unavailable',
      text: `Practice only, not graded. The recogniser status could not be read (${status.message}).`
    }
  }
  const provider = status.provider || 'unknown provider'
  if (status.available === true) {
    return {
      tone: 'available',
      text:
        `Assessed on this machine by Coursebook’s own recogniser (provider ${provider}` +
        `${status.model ? `, model ${status.model}` : ''}). Nothing is uploaded, and the take is ` +
        'deleted after comparison.'
    }
  }
  const reason = PRONUNCIATION_REASON_COPY[status.reason] || status.reason || 'no recogniser is configured'
  return { tone: 'unavailable', text: `Practice only, not graded. Recording stays off because ${reason}.` }
}

function PronunciationStudio({ enrollmentId, objectiveId, revision, locale, block, media, implemented, onSaved }) {
  const target = String((media && media.text_equivalent) || '').trim()
  const preview = useArtifactPreview(media && media.artifact_id)
  const motion = useCbMotion()
  const [status, setStatus] = useState({ state: 'loading' })
  const [phase, setPhase] = useState('idle')
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const audioRef = useRef(null)
  const recorderRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])
  const tickRef = useRef(null)
  const nonceRef = useRef(null)

  useEffect(() => {
    let live = true
    rest('/pronunciation/status')
      .then((response) => {
        if (live) setStatus({ state: 'ready', ...(response || {}) })
      })
      .catch((failure) => {
        if (live) setStatus({ state: 'error', message: describeError(failure) })
      })
    return () => {
      live = false
    }
  }, [])

  const releaseCapture = useCallback(() => {
    const stream = streamRef.current
    streamRef.current = null
    if (stream && typeof stream.getTracks === 'function') {
      stream.getTracks().forEach((track) => {
        try {
          track.stop()
        } catch (failure) {
          // A track that is already closed needs no second stop.
        }
      })
    }
    if (tickRef.current) {
      clearInterval(tickRef.current)
      tickRef.current = null
    }
  }, [])

  // A take never outlives the surface: leaving the section closes the microphone.
  useEffect(() => releaseCapture, [releaseCapture])

  const assess = useCallback(
    async (blob) => {
      setPhase('comparing')
      setError(null)
      setResult(null)
      setSaved(false)
      let dataUrl
      try {
        dataUrl = await new Promise((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = () => resolve(String(reader.result || ''))
          reader.onerror = () => reject(reader.error || new Error('the take could not be read'))
          reader.readAsDataURL(blob)
        })
      } catch (readFailure) {
        setPhase('error')
        setError({ code: 'TAKE_UNREADABLE', message: describeError(readFailure) })
        return
      }
      let response
      try {
        response = await rest('/pronunciation/attempt', {
          method: 'POST',
          timeoutMs: 180000,
          body: {
            enrollment_id: enrollmentId,
            objective_id: objectiveId,
            attempt_nonce: nonceRef.current || newOperationId('take'),
            target,
            locale,
            audio_data_url: dataUrl,
            expected_revision: Number(revision) || 0,
            idempotency_key: `cb-pronunciation-${nonceRef.current || newOperationId('take')}`
          }
        })
      } catch (transportFailure) {
        setPhase('error')
        setError({ code: 'HOST_UNAVAILABLE', message: describeError(transportFailure) })
        return
      }
      if (!response || response.ok !== true) {
        setPhase('error')
        setError(
          (response && response.error) || {
            code: 'INTERNAL_ERROR',
            message: 'The backend answered with something that is not a contract envelope.'
          }
        )
        return
      }
      setResult(response.result || null)
      setPhase('done')
    },
    [enrollmentId, objectiveId, revision, target, locale]
  )

  const start = useCallback(async () => {
    setError(null)
    setResult(null)
    setSaved(false)
    nonceRef.current = newOperationId('take')
    const devices = typeof navigator !== 'undefined' ? navigator.mediaDevices : null
    if (!devices || typeof devices.getUserMedia !== 'function' || typeof MediaRecorder === 'undefined') {
      setPhase('error')
      setError({ code: 'MIC_UNAVAILABLE', message: 'This window has no microphone capture, so no take can be recorded.' })
      return
    }
    let stream
    try {
      stream = await devices.getUserMedia({ audio: true })
    } catch (permissionFailure) {
      setPhase('error')
      setError({ code: 'MIC_BLOCKED', message: `The microphone was not opened: ${describeError(permissionFailure)}` })
      return
    }
    streamRef.current = stream
    chunksRef.current = []
    const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/ogg'].find(
      (candidate) => typeof MediaRecorder.isTypeSupported === 'function' && MediaRecorder.isTypeSupported(candidate)
    )
    let recorder
    try {
      recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined)
    } catch (recorderFailure) {
      releaseCapture()
      setPhase('error')
      setError({ code: 'MIC_UNAVAILABLE', message: `The recorder could not start: ${describeError(recorderFailure)}` })
      return
    }
    recorderRef.current = recorder
    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) chunksRef.current.push(event.data)
    }
    recorder.onstop = () => {
      const chunks = chunksRef.current
      chunksRef.current = []
      const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
      releaseCapture()
      if (blob.size === 0) {
        setPhase('error')
        setError({ code: 'EMPTY_TAKE', message: 'The recorder produced no audio. Try again.' })
        return
      }
      assess(blob)
    }
    recorder.start()
    setSeconds(0)
    setPhase('recording')
    const startedAt = Date.now()
    tickRef.current = setInterval(() => {
      const elapsed = Math.round((Date.now() - startedAt) / 1000)
      setSeconds(elapsed)
      // The backend refuses a take longer than 30 s; the bound is enforced here too so the
      // learner is never asked to upload something the contract will reject.
      if (elapsed >= 30 && recorder.state === 'recording') {
        try {
          recorder.stop()
        } catch (stopFailure) {
          // onstop already ran or will run; nothing else to do.
        }
      }
    }, 250)
  }, [assess, releaseCapture])

  const stop = useCallback(() => {
    const recorder = recorderRef.current
    if (recorder && recorder.state === 'recording') {
      try {
        recorder.stop()
      } catch (stopFailure) {
        // A recorder that already stopped is not an error the learner needs to see.
      }
    }
    releaseCapture()
  }, [releaseCapture])

  /** Discard the take and the result. No audio was ever stored, so this only clears this surface. */
  const forget = useCallback(() => {
    nonceRef.current = null
    setResult(null)
    setError(null)
    setSaved(false)
    setSeconds(0)
    setPhase('idle')
  }, [])

  const saveResult = useCallback(async () => {
    if (!result || !result.assessment) return
    const assessment = result.assessment
    const matched = (assessment.words || []).filter((word) => word.match).length
    const total = (assessment.words || []).length
    setSaving(true)
    const response = await rpc('notebook.save', {
      enrollment_id: enrollmentId,
      objective_id: objectiveId,
      lesson_run_id: null,
      kind: 'personal_note',
      excerpt: `${assessment.target} — heard ${assessment.transcript || 'nothing'}`,
      note:
        `Pronunciation practice (${assessment.provider}). ${matched} of ${total} ` +
        `${pronUnitLabel(assessment.unit)} matched; ${PRONUNCIATION_VERDICT_COPY[assessment.verdict] || assessment.verdict}. ` +
        'model_assessed — a practice measurement, not a graded score.',
      tags: ['pronunciation_practice'],
      source_ref: notebookSourceRef({
        block_id: block && block.id,
        artifact_id: media && media.artifact_id,
        source_ids: (block && block.source_ids) || []
      })
    })
    setSaving(false)
    if (!response.ok) {
      setError(response.error)
      return
    }
    setSaved(true)
    if (onSaved) onSaved()
  }, [result, enrollmentId, objectiveId, block, media, onSaved])

  const availability = pronunciationAvailabilityCopy(status)
  const canRecord = status.state === 'ready' && status.available === true && phase !== 'comparing'
  const assessment = result && result.assessment ? result.assessment : null
  const matchedCount = assessment ? (assessment.words || []).filter((word) => word.match).length : 0
  const totalCount = assessment ? (assessment.words || []).length : 0

  const listen = () => {
    const audio = audioRef.current
    if (!audio || typeof audio.play !== 'function') return
    try {
      const started = audio.play()
      if (started && typeof started.catch === 'function') started.catch(() => {})
    } catch (playFailure) {
      // The native controls remain the fallback; a refused play() is not a lost lesson.
    }
  }

  return jsxs('section', {
    'data-cb-pronunciation': (block && block.id) || 'block',
    'data-cb-pronunciation-phase': phase,
    'data-cb-pronunciation-availability': availability.tone,
    'data-cb-pronunciation-motion': motion,
    'aria-label': `Pronunciation practice: ${target}`,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
      margin: '0.5rem 0 0.25rem',
      padding: '0.6rem 0.75rem',
      borderLeft: '2px solid var(--cb-rule)',
      background: 'var(--cb-paper-raised)',
      maxWidth: '48rem'
    },
    children: [
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.4rem' },
        children: [
          jsx('h4', {
            style: { margin: 0, fontSize: '0.9rem', fontWeight: 600 },
            children: 'Pronunciation practice'
          }),
          jsx('span', {
            'data-cb-pronunciation-target': target,
            lang: locale,
            style: { fontSize: '0.95rem' },
            children: target
          })
        ]
      }),

      // The reference: the lesson's own narration artifact, through the same media route. Native
      // controls mean Play is the explicit action; nothing here autoplays.
      preview.state === 'ready' && preview.mime && String(preview.mime).startsWith('audio/')
        ? jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' },
            children: [
              jsx('audio', {
                ref: audioRef,
                'aria-label': `Reference recording of ${target}`,
                'data-cb-pronunciation-reference': preview.mime,
                controls: true,
                preload: 'metadata',
                src: preview.data_url,
                style: { width: '100%', maxWidth: '22rem' }
              }),
              jsx(sdk.Button, {
                variant: 'secondary',
                size: 'sm',
                onClick: listen,
                children: 'Listen'
              })
            ]
          })
        : jsx('p', {
            'data-cb-pronunciation-reference': preview.state === 'loading' ? 'loading' : 'none',
            style: { margin: 0, fontSize: '0.75rem', lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
            children:
              preview.state === 'loading'
                ? 'Loading the reference recording.'
                : 'No reference recording is attached to this block; the transcript above is the model.'
          }),

      jsx('p', {
        'data-cb-pronunciation-disclosure': availability.tone,
        'aria-live': 'polite',
        style: { margin: 0, fontSize: '0.75rem', lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
        children: availability.text
      }),

      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' },
        children: [
          phase === 'recording'
            ? jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: stop, children: 'Stop' })
            : jsx(sdk.Button, {
                variant: 'default',
                size: 'sm',
                disabled: !canRecord,
                onClick: start,
                'aria-describedby': 'cb-pronunciation-availability',
                children: phase === 'done' || phase === 'error' ? 'Record again' : 'Record'
              }),
          phase === 'recording'
            ? jsx('span', {
                'data-cb-pronunciation-timer': String(seconds),
                role: 'status',
                'aria-live': 'polite',
                style: { fontSize: '0.75rem', color: 'var(--cb-ink-soft)' },
                children: `Recording — ${seconds} s of 30 s. Stop when you are done.`
              })
            : null,
          phase === 'comparing'
            ? jsx('span', {
                role: 'status',
                style: { fontSize: '0.75rem', color: 'var(--cb-ink-soft)' },
                children: 'Comparing your take with the target…'
              })
            : null,
          phase === 'recording' || phase === 'comparing' || phase === 'done' || phase === 'error'
            ? jsx(sdk.Button, {
                variant: 'text',
                size: 'sm',
                disabled: phase === 'comparing',
                onClick: forget,
                children: phase === 'comparing' ? 'Delete take' : 'Delete take and result'
              })
            : null
        ]
      }),

      error
        ? jsxs('div', {
            'data-cb-pronunciation-error': error.code || 'ERROR',
            role: 'status',
            style: { display: 'flex', flexDirection: 'column', gap: '0.25rem' },
            children: [
              jsx('span', { style: { fontSize: '0.8rem', fontWeight: 600 }, children: `${error.code}: ${describeError(error)}` }),
              jsx('span', { style: { fontSize: '0.7rem', color: 'var(--cb-ink-soft)' }, children: 'No evidence was recorded.' })
            ]
          })
        : null,

      result && result.status === 'assessed' && assessment
        ? jsxs('div', {
            'data-cb-pronunciation-result': 'assessed',
            style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' },
            children: [
              jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem' },
                children: [
                  jsx(sdk.Badge, {
                    size: 'xs',
                    variant: 'outline',
                    children: `model_assessed`
                  }),
                  jsx('span', {
                    'data-cb-pronunciation-verdict': assessment.verdict,
                    style: { fontSize: '0.85rem', fontWeight: 600 },
                    children: PRONUNCIATION_VERDICT_COPY[assessment.verdict] || assessment.verdict
                  }),
                  pronPercent(assessment.confidence)
                    ? jsx('span', {
                        'data-cb-pronunciation-confidence': pronPercent(assessment.confidence),
                        style: { fontSize: '0.75rem', color: 'var(--cb-ink-soft)' },
                        children: `Recogniser confidence ${pronPercent(assessment.confidence)}`
                      })
                    : null,
                  totalCount > 0
                    ? jsx('span', {
                        'data-cb-pronunciation-matched': `${matchedCount}/${totalCount}`,
                        style: { fontSize: '0.75rem', color: 'var(--cb-ink-soft)' },
                        children: `${matchedCount} of ${totalCount} ${pronUnitLabel(assessment.unit)} matched`
                      })
                    : null
                ]
              }),
              jsx('p', {
                style: { margin: 0, fontSize: '0.85rem', lineHeight: 1.5 },
                children: `Heard: ${assessment.transcript || 'nothing'}`
              }),
              jsx(PronunciationWords, { words: assessment.words, unit: assessment.unit }),
              jsx('p', {
                'data-cb-pronunciation-provenance': assessment.provider,
                style: { margin: 0, fontSize: '0.7rem', lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                children:
                  `Practice measurement by ${assessment.provider}` +
                  `${assessment.model ? ` (${assessment.model})` : ''} — not verified pronunciation and not a graded score.` +
                  `${result.attempt_id ? ` Attempt ${result.attempt_id}.` : ''}`
              }),
              jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' },
                children: [
                  implemented && implemented.has('notebook.save')
                    ? jsx(sdk.Button, {
                        variant: 'secondary',
                        size: 'sm',
                        disabled: saving || saved,
                        onClick: saveResult,
                        children: saved ? 'Saved to notebook' : saving ? 'Saving' : 'Save result to notebook'
                      })
                    : null,
                  saved
                    ? jsx('span', {
                        role: 'status',
                        style: { fontSize: '0.7rem', color: 'var(--cb-ink-soft)' },
                        children: 'The result is in the notebook; the audio was never stored.'
                      })
                    : null
                ]
              })
            ]
          })
        : null,

      result && result.status !== 'assessed'
        ? jsxs('div', {
            'data-cb-pronunciation-result': result.status || 'unavailable',
            role: 'status',
            style: { display: 'flex', flexDirection: 'column', gap: '0.25rem' },
            children: [
              jsx('span', { style: { fontSize: '0.85rem', fontWeight: 600 }, children: 'Practice only, not graded' }),
              jsx('span', {
                style: { fontSize: '0.75rem', lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                children:
                  PRONUNCIATION_REASON_COPY[result.reason] ||
                  result.reason ||
                  'This take was not assessed. Nothing was recorded as evidence.'
              })
            ]
          })
        : null
    ]
  })
}

/**
 * The studio's seat in a block.
 *
 * Only a block that carries a narration audio child has an authored model phrase: its transcript is
 * the authoritative target and its artifact is the reference. A block with no narration gets no
 * studio — this never invents a phrase to pronounce.
 */
function PronunciationSeat({ block, pronunciation }) {
  if (!pronunciation) return null
  const media = (block.media || []).find(
    (item) => item && item.kind === 'audio' && String(item.text_equivalent || '').trim()
  )
  if (!media) return null
  return jsx(PronunciationStudio, {
    enrollmentId: pronunciation.enrollmentId,
    objectiveId: pronunciation.objectiveId,
    revision: pronunciation.revision,
    locale: pronunciation.locale,
    block,
    media,
    implemented: pronunciation.implemented,
    onSaved: pronunciation.onSaved
  })
}

/** The three presentation views this build implements (docs/VISUAL_MEDIA_PLAN.md §3.3, §5). */
const LESSON_VIEWS = [
  { id: 'textbook', label: 'Textbook' },
  { id: 'guided', label: 'Guided' },
  { id: 'field_quest', label: 'Field Quest' }
]

/**
 * The views *this document* can render.
 *
 * Textbook is the floor. Guided needs authored `short` prose on every block. Field Quest needs the
 * same and exactly one attachable check, because its checkpoints are the document's existing
 * checks and nothing else. The switcher never offers a view that would render as a broken toggle.
 */
function lessonViewOptions(document) {
  const views = (document && document.views) || {}
  return LESSON_VIEWS.filter((view) => (view.id === 'textbook' ? true : Boolean(views[view.id])))
}

/** A role is where the block sits in the teaching sequence, never a skin or a difficulty claim. */
const BLOCK_ROLE_COPY = {
  orient: 'Orient',
  explain: 'Explain',
  example: 'Example',
  practice: 'Practice',
  recap: 'Recap'
}

/**
 * Source chips for one block.
 *
 * A chip prints the course's own source title. An id the course did not return is printed as the
 * id: the Desktop never turns an unknown id into a citation it cannot show.
 */
function BlockSourceChips({ ids, index }) {
  if (!ids || ids.length === 0) return null
  return jsx('div', {
    className: 'flex flex-wrap items-center gap-1',
    'data-cb-block-sources': String(ids.length),
    children: ids.map((id) =>
      jsx(
        'span',
        { className: 'inline-flex max-w-full min-w-0 items-center', children: jsx(sdk.Badge, {
            size: 'xs',
            variant: 'outline',
            children: (index && index[id] && index[id].title) || `Source ${id}`
          }) },
        id
      )
    )
  })
}

/**
 * Media as a child of a block.
 *
 * One artifact, one text equivalent, one label. The preview, the audio player and the honest
 * text fallback are `MediaSegment`'s own implementation: a block view re-frames the same node, it
 * does not grow a second media renderer.
 */
function BlockMedia({ media, blockId, ordinal }) {
  const segment = {
    artifact_id: media.artifact_id,
    // The authored kind travels with the media child: a failed preview still knows whether the
    // author wrote narration or an illustration, so it cannot relabel audio as visual.
    kind: media.kind,
    text: media.text_equivalent || media.purpose,
    label: media.label
  }
  return jsx(
    'div',
    {
      className: 'flex flex-col gap-1',
      'data-cb-block-media': media.artifact_id || 'text-only',
      children: [
        jsx(MediaSegment, { segment }),
        media.degraded && media.reason
          ? jsx(QuietNote, { children: `Media is degraded: ${media.reason}` })
          : null
      ]
    },
    `${blockId}-media-${ordinal}`
  )
}

/**
 * Checklist labels are check data, not prose.
 *
 * A section's `deep`/`short` prose can still carry the lines an author also wrote into the check
 * (older sections did exactly that: the teaching segment, the `check_prompt` practice block and
 * the check surface each printed the same list). The check surface prints every structured item
 * once, so the document renderer drops a prose line whose only content is that item's label. The
 * comparison ignores case, spacing and punctuation, the same rule the backend validates with.
 */
function normalizeCheckLabel(value) {
  return String(value == null ? '' : value)
    .toLowerCase()
    .replace(/[\p{P}\p{S}]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function withoutCheckLabels(text, checkLabels) {
  if (!text || !checkLabels || checkLabels.length === 0) return text
  const hidden = new Set(checkLabels.map(normalizeCheckLabel).filter(Boolean))
  if (hidden.size === 0) return text
  const kept = []
  for (const line of String(text).split('\n')) {
    if (hidden.has(normalizeCheckLabel(line))) continue
    if (line.trim() === '' && kept.length > 0 && kept[kept.length - 1].trim() === '') continue
    kept.push(line)
  }
  return kept.join('\n').trim()
}

/**
 * One save affordance per teaching block and per media child.
 *
 * The excerpt is the backend-owned structured segment: the block's own `deep` prose (or its
 * `text_equivalent` for a media child). There is no transcript selection API behind this, and the
 * Desktop does not ask the chat for text — it saves the document it was served.
 */
function BlockSaveActions({ block, checkLabels, onSaveBlock, className }) {
  if (!onSaveBlock) return null
  const buttons = [
    jsx(sdk.Button, {
      variant: 'text',
      size: 'sm',
      'aria-label': `Save ${block.headline || 'this block'} to the notebook`,
      onClick: () => onSaveBlock(block, null),
      children: 'Save to notebook'
    })
  ]
  ;(block.media || []).forEach((media, index) => {
    buttons.push(
      jsx(sdk.Button, {
        variant: 'text',
        size: 'sm',
        'aria-label': `Save ${media.label || 'this media'} from ${block.headline || 'this block'} to the notebook`,
        onClick: () => onSaveBlock(block, media),
        children: media.kind === 'audio' ? 'Save audio' : 'Save visual'
      })
    )
  })
  return jsx('div', {
    className: className || 'flex flex-wrap items-center gap-1',
    'data-cb-block-save': block.id || 'block',
    children: buttons
  })
}

/** The excerpt a save will carry: the block's own prose, never a re-summarised one. */
function blockSaveExcerpt(block, checkLabels, media) {
  if (media) return media.text_equivalent || media.purpose || block.headline || ''
  return withoutCheckLabels(block.deep, checkLabels) || block.short || block.headline || ''
}

function BlockBody({ block, sources, checkSlot, checkLabels, onSaveBlock, pronunciation }) {
  const body = withoutCheckLabels(block.deep, checkLabels)
  return jsxs('div', {
    className: 'flex flex-col gap-2',
    children: [
      body
        ? jsx('div', { className: 'max-w-prose', children: jsx(sdk.MessageTextContent, { text: body }) })
        : null,
      (block.media || []).map((media, index) =>
        jsx(BlockMedia, { media, blockId: block.id, ordinal: index }, `${block.id}-media-${index}`)
      ),
      jsx(PronunciationSeat, { block, pronunciation }),
      jsx(BlockSourceChips, { ids: block.source_ids, index: sources }),
      jsx(BlockSaveActions, { block, checkLabels, onSaveBlock }),
      checkSlot
        ? jsx('div', { className: 'flex flex-col gap-2 pt-1', 'data-cb-block-check': block.id, children: checkSlot })
        : null
    ]
  })
}

/** Textbook: every block in authored order, the full `deep` prose, inline figures. */
function TextbookBlock({ block, sources, checkSlot, checkLabels, onSaveBlock, pronunciation }) {
  return jsxs('article', {
    className: 'flex flex-col gap-2 border-b border-(--ui-stroke-tertiary) py-3 first:pt-0 last:border-b-0 last:pb-0',
    'data-cb-block': block.id,
    'data-cb-role': block.role,
    tabIndex: -1,
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-baseline gap-2',
        children: [
          jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: BLOCK_ROLE_COPY[block.role] || block.role }),
          jsx('h3', { className: 'min-w-0 text-base font-semibold leading-snug', children: block.headline })
        ]
      }),
      BlockBody({ block, sources, checkSlot, checkLabels, onSaveBlock, pronunciation })
    ]
  })
}

/** Guided: one block at a time, the authored `short` prose, progress and a check on its block. */
function GuidedBlock({ block, index, total, sources, checkSlot, checkLabels, onBack, onNext, onSaveBlock, pronunciation }) {
  const last = index >= total - 1
  const body = withoutCheckLabels(block.short || block.deep, checkLabels)
  return jsxs('section', {
    className: 'flex flex-col gap-3',
    'aria-labelledby': `cb-guided-headline-${block.id}`,
    'data-cb-block': block.id,
    'data-cb-role': block.role,
    tabIndex: -1,
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-baseline justify-between gap-2',
        children: [
          jsxs('div', {
            className: 'flex flex-wrap items-baseline gap-2',
            children: [
              jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: BLOCK_ROLE_COPY[block.role] || block.role }),
              jsx('h3', {
                className: 'min-w-0 text-base font-semibold leading-snug',
                id: `cb-guided-headline-${block.id}`,
                children: block.headline
              })
            ]
          }),
          jsx('span', {
            className: 'text-xs text-(--ui-text-secondary)',
            'aria-live': 'polite',
            'data-cb-step': `${index + 1}/${total}`,
            children: `Step ${index + 1} of ${total}`
          })
        ]
      }),
      body
        ? jsx('div', {
            className: 'max-w-prose',
            children: jsx(sdk.MessageTextContent, { text: body })
          })
        : null,
      (block.media || []).map((media, ordinal) =>
        jsx(BlockMedia, { media, blockId: block.id, ordinal }, `${block.id}-media-${ordinal}`)
      ),
      jsx(PronunciationSeat, { block, pronunciation }),
      jsx(BlockSourceChips, { ids: block.source_ids, index: sources }),
      jsx(BlockSaveActions, { block, checkLabels, onSaveBlock }),
      checkSlot ? jsx('div', { className: 'flex flex-col gap-2', 'data-cb-block-check': block.id, children: checkSlot }) : null,
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(sdk.Button, {
            variant: 'secondary',
            size: 'sm',
            disabled: index === 0,
            onClick: onBack,
            children: 'Back'
          }),
          jsx(sdk.Button, {
            variant: 'default',
            size: 'sm',
            disabled: last,
            onClick: onNext,
            children: 'Continue'
          }),
          last
            ? jsx('span', {
                className: 'text-xs text-(--ui-text-secondary)',
                children: 'End of the guided pass. The Textbook view keeps the full text.'
              })
            : null
        ]
      })
    ]
  })
}

/**
 * A mission is one block of the same document, in authored order.
 *
 * There is no second lesson here: `block` is the document's own block, `checkpoint` is a label on
 * the block that already carries the document's single check, and nothing is generated.
 */
function questMissions(document) {
  const blocks = (document && document.blocks) || []
  const checkId = document ? document.check_id : null
  return blocks.map((block, index) => ({
    index,
    total: blocks.length,
    block,
    checkpoint: Boolean(checkId && block.check_id === checkId)
  }))
}

/**
 * Progress is descriptive, never a score.
 *
 * "2 independent · 1 due" counts objectives the backend has already recorded as independent and
 * objectives it has already flagged as due. It is not a streak, an XP total or a mastery claim; a
 * course with nothing recorded says so instead of showing a zero that looks like a grade.
 */
function questProgressLabel(summary) {
  if (!summary || typeof summary !== 'object') return 'Progress not recorded'
  const total = Number(summary.total_objectives) || 0
  if (total === 0) return 'No objectives recorded yet'
  const independent = Number(summary.independent) || 0
  const due = Number(summary.review_due) || 0
  return `${independent} independent · ${due} due`
}

/** One mission: the block's short prose, its media, its sources and — on a checkpoint — its check. */
function QuestMission({ mission, sources, checkSlot, checkLabels, onReadInTextbook, onSaveBlock, pronunciation }) {
  const block = mission.block
  const body = withoutCheckLabels(block.short || block.deep, checkLabels)
  const stateWord = mission.checkpoint ? 'Checkpoint' : 'Mission'
  const tone = mission.checkpoint ? 'var(--cb-accent)' : 'var(--cb-ink-soft)'
  const headingId = `cb-mission-headline-${block.id}`
  return jsxs('li', {
    'data-cb-mission': block.id,
    'data-cb-mission-index': String(mission.index + 1),
    'data-cb-mission-role': block.role,
    'data-cb-mission-checkpoint': mission.checkpoint ? 'true' : 'false',
    'data-cb-mission-check': mission.checkpoint && block.check_id ? block.check_id : '',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.4rem',
      listStyle: 'none',
      padding: '0.65rem 0 0.75rem 0.85rem',
      borderLeft: `2px solid ${mission.checkpoint ? 'var(--cb-accent)' : 'var(--cb-rule)'}`,
      maxWidth: '46rem'
    },
    children: [
      jsxs('div', {
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: '0.2rem 0.75rem'
        },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.5rem', minWidth: 0 },
            children: [
              jsx('span', {
                'data-cb-mission-number': '',
                style: {
                  flex: '0 0 auto',
                  fontVariantNumeric: 'tabular-nums',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  color: tone
                },
                children: String(mission.index + 1).padStart(2, '0')
              }),
              jsx(sdk.Badge, {
                size: 'xs',
                variant: 'muted',
                children: BLOCK_ROLE_COPY[block.role] || block.role
              }),
              jsx('h3', {
                id: headingId,
                style: {
                  margin: 0,
                  minWidth: 0,
                  fontSize: '1rem',
                  fontWeight: 600,
                  lineHeight: 1.35,
                  color: 'var(--cb-ink)',
                  overflowWrap: 'anywhere'
                },
                children: block.headline
              })
            ]
          }),
          jsx('span', {
            'data-cb-mission-state': mission.checkpoint ? 'checkpoint' : 'mission',
            style: { flex: '0 0 auto', fontSize: '0.7rem', fontWeight: 500, color: tone },
            children: stateWord
          })
        ]
      }),
      body
        ? jsx('div', {
            style: { maxWidth: '46rem' },
            children: jsx(sdk.MessageTextContent, { text: body })
          })
        : null,
      (block.media || []).map((media, ordinal) =>
        jsx(BlockMedia, { media, blockId: block.id, ordinal }, `${block.id}-media-${ordinal}`)
      ),
      jsx(BlockSourceChips, { ids: block.source_ids, index: sources }),
      jsx(BlockSaveActions, { block, checkLabels, onSaveBlock, className: 'flex flex-wrap items-center gap-1 self-start' }),
      jsx(PronunciationSeat, { block, pronunciation }),
      mission.checkpoint
        ? jsxs('div', {
            'data-cb-mission-gate': block.check_id || 'unattached',
            style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', paddingTop: '0.15rem' },
            children: [
              jsx(DeskLabel, { children: 'Checkpoint' }),
              jsx('div', {
                style: { fontSize: '0.72rem', color: 'var(--cb-ink-soft)' },
                children: 'This is the section’s existing check — the same one Textbook and Guided use. Finishing it is not required to read anything here.'
              }),
              checkSlot
                ? jsx('div', { style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' }, children: checkSlot })
                : jsx('div', {
                    style: { fontSize: '0.8rem', color: 'var(--cb-ink-soft)' },
                    children: 'No check could be attached to this checkpoint, so the mission stays readable and ungated.'
                  })
            ]
          })
        : null,
      jsx(sdk.Button, {
        variant: 'text',
        size: 'sm',
        className: 'self-start',
        'data-cb-mission-read': block.id,
        'aria-label': `Read mission ${mission.index + 1}, ${block.headline}, in Textbook`,
        onClick: () => onReadInTextbook(block.id),
        children: 'Read in Textbook'
      })
    ]
  })
}

/**
 * Field Quest: the same block sequence drawn as a path of small missions.
 *
 * What changes is the frame — numbering, the `Mission`/`Checkpoint` word and the course's
 * descriptive evidence counts. What does not change is the teaching truth (§2, §5): every mission
 * prints the authored `short` prose, every checkpoint holds the document's own single check node,
 * every block, check and source id is the document's, and nothing is locked. There is no XP, no
 * streak, no badge that stands in for evidence and no second grading path.
 */
function FieldQuestView({ document, sources, checkSlot, checkLabels, progress, unattached, onOpenBlock, onSaveBlock, pronunciation }) {
  const missions = questMissions(document)
  const motion = useCbMotion()
  const progressLabel = questProgressLabel(progress)
  const checkpoints = missions.filter((mission) => mission.checkpoint).length
  return jsxs('div', {
    ...lessonTextAttrs(document),
    'data-cb-lesson-view': 'field_quest',
    'data-cb-document': document.document_id,
    'data-cb-motion': motion,
    'data-cb-quest-progress': progressLabel,
    'data-cb-quest-missions': String(missions.length),
    'data-cb-quest-checkpoints': String(checkpoints),
    style: { display: 'flex', flexDirection: 'column', gap: '0.6rem' },
    children: [
      jsxs('div', {
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: '0.2rem 0.75rem'
        },
        children: [
          jsx(DeskLabel, { children: 'Field Quest' }),
          jsx('span', {
            style: { fontSize: '0.72rem', color: 'var(--cb-ink-soft)' },
            children: `${progressLabel} · ${missions.length} mission${missions.length === 1 ? '' : 's'}, ${checkpoints} checkpoint${checkpoints === 1 ? '' : 's'}`
          })
        ]
      }),
      jsx('p', {
        'data-cb-quest-note': '',
        style: { margin: 0, fontSize: '0.75rem', lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
        children:
          'Counts describe evidence the backend already recorded; they are not a score. Every mission is open — a checkpoint is the section’s existing check, not a lock.'
      }),
      jsx('ol', {
        'data-cb-quest-path': '',
        style: { listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.1rem' },
        children: missions.map((mission) =>
          jsx(
            QuestMission,
            {
              mission,
              sources,
              checkLabels,
              checkSlot: mission.checkpoint ? checkSlot : null,
              onSaveBlock,
              pronunciation,
              onReadInTextbook: (blockId) => onOpenBlock && onOpenBlock(blockId)
            },
            mission.block.id
          )
        )
      }),
      unattached
    ]
  })
}

/**
 * The lesson document, rendered as one of its views.
 *
 * The document is server-owned; this component decides placement, never content. A view switch
 * re-renders the same blocks, the same ids and the same single check.
 *
 * A procedure document takes the procedure lens in Textbook: the typed header, the numbered step
 * references, the deterministic schematic and the source card. Guided and Field Quest keep their
 * existing single-block lenses over the same document.
 */
/* ── Procedure layout ───────────────────────────────────────────────────────────────────────
 * docs/VISUAL_MEDIA_PLAN.md §8. A procedure is a lens over the section's existing blocks: the
 * header is typed facts, each numbered step references one block the document already carries,
 * and the section's one check is printed once as a verification checklist. Nothing here reads
 * prose to recover a torque value, and nothing here mints a second check or a second schematic.
 *
 * The honesty rules this layout exists to keep:
 *   - a generated illustration is labelled context, never a specification, measurement, sequence
 *     or safety authority;
 *   - the only torque/clearance values on screen are the typed schematic rows and the source card
 *     they cite; the deterministic schematic is drawn from those rows, not from an image;
 *   - the stop condition is a distinct "do not proceed" callout, not decoration and never inside
 *     an illustration;
 *   - a procedure always shows its source and that source's permission status.
 */
const PROCEDURE_PERMISSION_COPY = {
  public_domain: 'Public domain',
  licensed: 'Licensed for this course',
  linked: 'Linked source — not reproduced'
}

const PROCEDURE_MEDIA_NOTE = {
  illustration: 'Context illustration — not a specification, measurement, sequence or safety authority.',
  schematic: 'Deterministic schematic drawn from the structured facts below.',
  sourced_technical: 'Sourced reference — check the cited source and its permission status.',
  narration: 'Narration — the transcript is the authoritative text.'
}

function procedureSourceMeta(sourceId, sources) {
  return (sources && sources[sourceId]) || null
}

/** Tools and parts: typed header lists, printed as written, never inferred from the prose. */
function ProcedureHeader({ procedure, sectionTitle }) {
  const tools = Array.isArray(procedure.tools) ? procedure.tools : []
  const parts = Array.isArray(procedure.parts) ? procedure.parts : []
  const columns = []
  if (tools.length > 0) {
    columns.push(
      jsxs('div', {
        key: 'tools',
        'data-cb-procedure-tools': String(tools.length),
        style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', minWidth: '12rem', flex: '1 1 12rem' },
        children: [
          jsx(DeskLabel, { children: 'Tools' }),
          jsx('ul', {
            style: { margin: 0, paddingLeft: '1.1rem', fontSize: '0.85rem', lineHeight: 1.55, color: 'var(--cb-ink)' },
            children: tools.map((item, index) => jsx('li', { children: item }, `${sectionTitle}-tool-${index}`))
          })
        ]
      })
    )
  }
  if (parts.length > 0) {
    columns.push(
      jsxs('div', {
        key: 'parts',
        'data-cb-procedure-parts': String(parts.length),
        style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', minWidth: '12rem', flex: '1 1 12rem' },
        children: [
          jsx(DeskLabel, { children: 'Parts' }),
          jsx('ul', {
            style: { margin: 0, paddingLeft: '1.1rem', fontSize: '0.85rem', lineHeight: 1.55, color: 'var(--cb-ink)' },
            children: parts.map((item, index) => jsx('li', { children: item }, `${sectionTitle}-part-${index}`))
          })
        ]
      })
    )
  }
  return jsxs('section', {
    'data-cb-procedure-header': '',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.6rem',
      padding: '0.85rem 1rem 0.95rem',
      background: 'var(--cb-paper-raised)',
      border: '1px solid var(--cb-rule)',
      maxWidth: '48rem'
    },
    children: [
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem' },
        children: [
          jsx(DeskLabel, { children: 'Procedure' }),
          jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: 'Ordered steps' })
        ]
      }),
      columns.length > 0
        ? jsx('div', { style: { display: 'flex', flexWrap: 'wrap', gap: '1rem' }, children: columns })
        : jsx('p', {
            style: { margin: 0, fontSize: '0.85rem', color: 'var(--cb-ink-soft)' },
            children: 'The author listed no tools or parts for this procedure.'
          })
    ]
  })
}

/**
 * The stop condition, as a callout that cannot be mistaken for a step or a generated image.
 *
 * `role="note"` and the coral rule are the signal; the hazards are the author's own strings. The
 * callout is not an illustration and carries no image.
 */
function ProcedureHazardCallout({ hazards, stopCondition }) {
  const list = Array.isArray(hazards) ? hazards : []
  return jsxs('section', {
    role: 'note',
    'aria-label': 'Do not proceed',
    'data-cb-procedure-hazard': '',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.35rem',
      margin: '0 0 0.25rem',
      padding: '0.7rem 0.85rem 0.75rem 0.9rem',
      borderLeft: '3px solid var(--cb-coral)',
      background: 'var(--cb-paper-raised)',
      maxWidth: '48rem'
    },
    children: [
      jsx('div', {
        style: {
          fontSize: '0.7rem',
          fontWeight: 700,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: 'var(--cb-coral)'
        },
        children: 'Do not proceed'
      }),
      list.length > 0
        ? jsx('ul', {
            style: { margin: 0, paddingLeft: '1.1rem', fontSize: '0.9rem', lineHeight: 1.55, color: 'var(--cb-ink)' },
            children: list.map((item, index) => jsx('li', { children: item }, `hazard-${index}`))
          })
        : null,
      jsxs('p', {
        'data-cb-procedure-stop': '',
        style: { margin: 0, fontSize: '0.9rem', lineHeight: 1.6, color: 'var(--cb-ink)' },
        children: [jsx('strong', { children: 'Stop if: ' }), stopCondition]
      })
    ]
  })
}

/**
 * A torque or sequence schematic, deterministic from typed rows.
 *
 * The rows are the authority and are always printed, sorted by the backend's own `row` then
 * label rule. An attached SVG artifact is this same drawing and is shown through the one
 * `MediaSegment` preview; when that artifact cannot be reached the rows remain, so the value is
 * never lost behind an image.
 */
function ProcedureSchematic({ schematic, sources, blockId }) {
  if (!schematic) return null
  const rows = (Array.isArray(schematic.rows) ? schematic.rows : [])
    .slice()
    .sort((left, right) => (Number(left.row) || 0) - (Number(right.row) || 0) || String(left.label).localeCompare(String(right.label)))
  const source = procedureSourceMeta(schematic.source_id, sources)
  return jsxs('section', {
    'data-cb-procedure-schematic': '',
    'aria-labelledby': `cb-procedure-schematic-${blockId || 'document'}`,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.4rem',
      padding: '0.7rem 0.85rem',
      border: '1px solid var(--cb-rule)',
      background: 'var(--cb-paper)',
      maxWidth: '48rem'
    },
    children: [
      jsx('h3', {
        id: `cb-procedure-schematic-${blockId || 'document'}`,
        style: { margin: 0, fontSize: '0.95rem', fontWeight: 600, color: 'var(--cb-ink)' },
        children: schematic.title
      }),
      jsx('div', {
        style: { fontSize: '0.7rem', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--cb-ink-soft)' },
        children: 'Deterministic schematic · structured facts'
      }),
      jsx('table', {
        'data-cb-procedure-rows': String(rows.length),
        style: { borderCollapse: 'collapse', width: '100%', fontSize: '0.85rem', color: 'var(--cb-ink)' },
        children: jsxs('tbody', {
          children: rows.map((row, index) =>
            jsxs(
              'tr',
              {
                style: { borderTop: index === 0 ? 'none' : '1px solid var(--cb-rule)' },
                children: [
                  jsx('th', {
                    scope: 'row',
                    style: { textAlign: 'left', padding: '0.25rem 0.5rem 0.25rem 0', fontWeight: 500 },
                    children: row.label
                  }),
                  jsx('td', {
                    style: { textAlign: 'right', padding: '0.25rem 0', fontVariantNumeric: 'tabular-nums' },
                    children: row.value
                  })
                ]
              },
              `${blockId || 'schematic'}-row-${index}`
            )
          )
        })
      }),
      jsx('p', {
        style: { margin: 0, fontSize: '0.8rem', lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
        children: schematic.text_equivalent
      }),
      schematic.source_id
        ? jsx('p', {
            'data-cb-procedure-schematic-source': schematic.source_id,
            style: { margin: 0, fontSize: '0.75rem', color: 'var(--cb-ink-soft)' },
            children: `Facts from ${(source && source.title) || schematic.source_id}`
          })
        : null,
      schematic.artifact_id
        ? jsx(BlockMedia, {
            media: {
              artifact_id: schematic.artifact_id,
              role: 'schematic',
              label: 'Deterministic schematic rendered from structured facts.',
              text_equivalent: schematic.text_equivalent,
              purpose: schematic.title
            },
            blockId: blockId || 'procedure',
            ordinal: 'schematic'
          })
        : null
    ]
  })
}

/** The cited manual with its permission status; never an unlabelled link. */
function ProcedureSourceCard({ source, sources }) {
  const meta = procedureSourceMeta(source.source_id, sources)
  const permission = PROCEDURE_PERMISSION_COPY[source.permission] || source.permission
  return jsxs('section', {
    'data-cb-procedure-source': source.source_id,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.25rem',
      padding: '0.65rem 0.85rem',
      borderLeft: '2px solid var(--cb-rule)',
      background: 'var(--cb-paper-raised)',
      maxWidth: '48rem'
    },
    children: [
      jsx(DeskLabel, { children: 'Source' }),
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem' },
        children: [
          jsx('span', { style: { fontSize: '0.9rem', fontWeight: 600, color: 'var(--cb-ink)' }, children: (meta && meta.title) || source.source_id }),
          jsx(sdk.Badge, { size: 'xs', variant: source.permission === 'licensed' ? 'muted' : 'outline', children: permission })
        ]
      }),
      meta && meta.url
        ? jsx('a', {
            href: meta.url,
            rel: 'noreferrer noopener',
            target: '_blank',
            style: { fontSize: '0.8rem', color: 'var(--cb-accent)', overflowWrap: 'anywhere' },
            children: meta.url
          })
        : null,
      jsx('p', {
        style: { margin: 0, fontSize: '0.75rem', lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
        children: 'Torque values and sequence come from this reference and the structured schematic; the illustration is context only.'
      })
    ]
  })
}

/** One numbered step. The action is the referenced block's own prose; the check is the author's step cue. */
function ProcedureStepCard({ step, index, block, sources, checkSlot, checkLabels, onSaveBlock, pronunciation }) {
  const body = withoutCheckLabels(block.deep, checkLabels)
  const media = (block.media || []).map((item, ordinal) => {
    const note = PROCEDURE_MEDIA_NOTE[item.role]
    return jsxs(
      'div',
      {
        key: `${block.id}-procedure-media-${ordinal}`,
        'data-cb-procedure-media': item.role || 'media',
        style: { display: 'flex', flexDirection: 'column', gap: '0.25rem' },
        children: [
          note
            ? jsx('p', {
                'data-cb-procedure-media-note': item.role || '',
                style: { margin: 0, fontSize: '0.75rem', lineHeight: 1.5, color: item.role === 'illustration' ? 'var(--cb-ochre)' : 'var(--cb-ink-soft)' },
                children: note
              })
            : null,
          jsx(BlockMedia, { media: item, blockId: block.id, ordinal })
        ]
      }
    )
  })
  return jsxs('li', {
    'data-cb-procedure-step': String(index + 1),
    'data-cb-block': block.id,
    'data-cb-role': block.role,
    tabIndex: -1,
    style: {
      display: 'flex',
      gap: '0.7rem',
      padding: '0.7rem 0 0.7rem 0.85rem',
      borderLeft: '2px solid var(--cb-rule)',
      listStyle: 'none'
    },
    children: [
      jsx('span', {
        'aria-hidden': 'true',
        style: {
          fontSize: '0.8rem',
          fontWeight: 700,
          fontVariantNumeric: 'tabular-nums',
          color: 'var(--cb-accent)',
          minWidth: '1.4rem'
        },
        children: String(index + 1).padStart(2, '0')
      }),
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', minWidth: 0, flex: '1 1 auto' },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.4rem' },
            children: [
              jsx('span', { className: 'sr-only', children: `Step ${index + 1}` }),
              jsx('h3', {
                style: { margin: 0, fontSize: '1rem', fontWeight: 600, lineHeight: 1.35, color: 'var(--cb-ink)' },
                children: block.headline
              })
            ]
          }),
          body
            ? jsx('div', { style: { maxWidth: '44rem' }, children: jsx(sdk.MessageTextContent, { text: body }) })
            : null,
          step.check
            ? jsxs('p', {
                'data-cb-procedure-step-check': block.id,
                style: { margin: 0, fontSize: '0.82rem', lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
                children: [jsx('strong', { children: 'Check: ' }), step.check]
              })
            : null,
          media.length > 0 ? jsx('div', { style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' }, children: media }) : null,
          jsx(PronunciationSeat, { block, pronunciation }),
          jsx(BlockSourceChips, { ids: block.source_ids, index: sources }),
          jsx(BlockSaveActions, { block, checkLabels, onSaveBlock }),
          checkSlot
            ? jsx('div', { style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', paddingTop: '0.15rem' }, 'data-cb-block-check': block.id, children: checkSlot })
            : null
        ]
      })
    ]
  })
}

/**
 * The procedure lens: header, hazard callout, numbered steps, one verification checklist, source.
 *
 * Blocks the author did not place in `steps` are still taught: they render after the numbered
 * list in the ordinary textbook frame, so a procedure can never silently hide authored material.
 */
function ProcedureDocument({ document, sources, checkSlot, checkLabels, onSaveBlock, pronunciation }) {
  const procedure = document.procedure
  const blocks = document.blocks || []
  const byId = {}
  blocks.forEach((block) => {
    byId[block.id] = block
  })
  const steps = (procedure.steps || [])
    .map((step, index) => ({ step, index, block: byId[step.block_id] }))
    .filter((entry) => Boolean(entry.block))
  const placed = new Set(steps.map((entry) => entry.block.id))
  const leftover = blocks.filter((block) => !placed.has(block.id))
  const checkId = document.check_id
  const attachedIndex = checkId ? steps.findIndex((entry) => entry.block.check_id === checkId) : -1
  return jsxs('div', {
    className: 'flex flex-col gap-3',
    ...lessonTextAttrs(document),
    'data-cb-lesson-view': 'procedure',
    'data-cb-document': document.document_id,
    'data-cb-procedure': '',
    children: [
      jsx(ProcedureHeader, { procedure, sectionTitle: document.section_title }),
      jsx(ProcedureHazardCallout, { hazards: procedure.hazards, stopCondition: procedure.stop_condition }),
      jsx(ProcedureSchematic, { schematic: procedure.schematic, sources, blockId: document.document_id }),
      jsx('ol', {
        'data-cb-procedure-steps': String(steps.length),
        style: { listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.2rem', maxWidth: '48rem' },
        children: steps.map((entry) =>
          jsx(
            ProcedureStepCard,
            {
              step: entry.step,
              index: entry.index,
              block: entry.block,
              sources,
              checkLabels,
              onSaveBlock,
              pronunciation,
              checkSlot: attachedIndex === entry.index ? checkSlot : null
            },
            entry.block.id
          )
        )
      }),
      checkId && checkSlot && attachedIndex < 0
        ? jsxs('section', {
            'data-cb-procedure-verification': '',
            style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', maxWidth: '48rem' },
            children: [jsx(DeskLabel, { children: 'Verification checklist' }), checkSlot]
          })
        : attachedIndex >= 0
          ? jsxs('section', {
              'data-cb-procedure-verification': 'attached',
              style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', maxWidth: '48rem' },
              children: [
                jsx(DeskLabel, { children: 'Verification checklist' }),
                jsx('p', {
                  style: { margin: 0, fontSize: '0.75rem', color: 'var(--cb-ink-soft)' },
                  children: 'The checklist is on the step above. It is the section’s one check, not an extra quiz.'
                })
              ]
            })
          : null,
      leftover.length > 0
        ? jsxs('div', {
            'data-cb-procedure-unplaced': String(leftover.length),
            style: { display: 'flex', flexDirection: 'column', gap: '0.25rem', maxWidth: '48rem' },
            children: [
              jsx(DeskLabel, { children: 'Also in this lesson' }),
              ...leftover.map((block) =>
                jsx(TextbookBlock, { block, sources, checkSlot: null, checkLabels, onSaveBlock, pronunciation }, block.id)
              )
            ]
          })
        : null,
      jsx(ProcedureSourceCard, { source: procedure.source, sources })
    ]
  })
}

function lessonTextAttrs(document) {
  // H-18: lang and direction are properties of the text. Every view renders the same document,
  // so every view root carries the same two attributes; absence means the page never recorded a
  // locale and no direction is invented.
  const attrs = {}
  if (document && (document.direction === 'rtl' || document.direction === 'ltr')) {
    attrs.dir = document.direction
  }
  if (document && typeof document.lang === 'string' && document.lang) {
    attrs.lang = document.lang
  }
  return attrs
}

function LessonDocumentView({ document, view, sources, checkSlot, checkLabels, progress, focusBlockId, onOpenBlock, onSaveBlock, pronunciation }) {
  const blocks = (document && document.blocks) || []
  const labels = Array.isArray(checkLabels) ? checkLabels : []
  const [step, setStep] = useState(0)
  const rootRef = useRef(null)
  const focusIndex = focusBlockId ? blocks.findIndex((block) => block.id === focusBlockId) : -1
  // A mission can hand the reader to the same block in another view. The ids are the document's,
  // so the handoff sets Guided's step by id and moves focus to that block rather than guessing an
  // offset; nothing about the block, its check or its sources is re-created by the switch.
  useEffect(() => {
    if (focusIndex < 0) return
    if (view === 'guided' && focusIndex !== step) {
      setStep(focusIndex)
      return
    }
    const root = rootRef.current
    if (!root || typeof root.querySelector !== 'function') return
    const target = root.querySelector(`[data-cb-block="${focusBlockId}"]`)
    if (target && typeof target.focus === 'function') target.focus()
  }, [focusBlockId, focusIndex, view, step])
  if (blocks.length === 0) {
    return jsx(EmptyState, {
      title: 'This section has no teaching content yet',
      description:
        (document && document.view_note) ||
        'Teaching content appears here after a lesson turn, and Coursebook does not write it for you.'
    })
  }
  const checkId = document.check_id
  const attached = checkId ? blocks.findIndex((block) => block.check_id === checkId) : -1
  const unattached = attached < 0 && checkSlot
    ? jsxs('div', {
        className: 'flex flex-col gap-2',
        children: [jsx(sdk.PanelSectionLabel, { children: 'CHECK' }), checkSlot]
      })
    : null

  if (document.procedure && view === 'textbook') {
    return jsx(ProcedureDocument, {
      document,
      sources,
      checkSlot,
      checkLabels: labels,
      onSaveBlock,
      pronunciation
    })
  }

  if (view === 'field_quest' && document.views && document.views.field_quest) {
    return jsx(FieldQuestView, {
      document,
      sources,
      checkSlot,
      checkLabels: labels,
      progress,
      unattached,
      onOpenBlock,
      onSaveBlock,
      pronunciation
    })
  }

  if (view === 'guided' && document.views && document.views.guided) {
    const current = Math.min(step, blocks.length - 1)
    const block = blocks[current]
    return jsxs('div', {
      ref: rootRef,
      className: 'flex flex-col gap-3',
      ...lessonTextAttrs(document),
      'data-cb-lesson-view': 'guided',
      'data-cb-document': document.document_id,
      children: [
        jsx(GuidedBlock, {
          block,
          index: current,
          total: blocks.length,
          sources,
          checkLabels: labels,
          checkSlot: block.check_id && block.check_id === checkId ? checkSlot : null,
          onBack: () => setStep(Math.max(0, current - 1)),
          onNext: () => setStep(Math.min(blocks.length - 1, current + 1)),
          onSaveBlock,
          pronunciation
        }),
        unattached
      ]
    })
  }

  return jsxs('div', {
    ref: rootRef,
    className: 'flex flex-col gap-3',
    ...lessonTextAttrs(document),
    'data-cb-lesson-view': 'textbook',
    'data-cb-document': document.document_id,
    children: [
      jsx('div', {
        className: 'flex flex-col',
        children: blocks.map((block) =>
          jsx(
            TextbookBlock,
            {
              block,
              sources,
              checkLabels: labels,
              checkSlot: attached >= 0 && block.check_id === checkId ? checkSlot : null,
              onSaveBlock,
              pronunciation
            },
            block.id
          )
        )
      }),
      unattached
    ]
  })
}

function SectionPage({ row, objectiveId, page, pageStatus, pageError, onRetryPage, implemented, onBack, onChanged, review, targetBlockId }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const section = page && page.section
  const runtime = page && page.runtime
  const bindingActive = Boolean(runtime && runtime.binding_status === 'active')
  const [saveSeed, setSaveSeed] = useState(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  const [lessonView, setLessonView] = useState('textbook')
  // A mission or a saved moment hands the reader to the same block in Textbook. The target is a
  // block id, so the handoff survives the view switch and lands on the document's own block, not
  // an offset. A target from outside the section (Notebook, Field Desk) arrives the same way.
  const [focusBlockId, setFocusBlockId] = useState(targetBlockId || null)
  // The document is a v8 read projection. A backend that predates it answers with segments only,
  // so the segment list below stays as the fallback rather than becoming dead code.
  const document = page && page.document ? page.document : null
  const sourceIndex = {}
  for (const source of (page && page.sources) || []) {
    if (source && source.source_id) sourceIndex[source.source_id] = source
  }
  // One view is on screen at a time, so a single check node serves the Textbook block, the Guided
  // step and the legacy segment list. It is never rendered twice in one view.
  useEffect(() => {
    setLessonView('textbook')
    setFocusBlockId(targetBlockId || null)
  }, [objectiveId, targetBlockId])
  const check = useOpenCheck({
    enrollmentId: row.enrollment_id,
    objectiveId,
    revision: page ? page.revision : 0,
    enabled: Boolean(page) && supports('check.open') && Boolean(section),
    implemented
  })
  // The check surface prints one label per structured item; the document prose must not print the
  // same line again on the teaching block or the practice block.
  const checkStimulus = check.check && check.check.stimulus ? check.check.stimulus : null
  const checkLabels =
    checkStimulus && Array.isArray(checkStimulus.items)
      ? checkStimulus.items.map((item) => item && item.label).filter(Boolean)
      : []
  const checkNode =
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
          revision: page ? page.revision : 0,
          implemented,
          bindingState: runtime ? runtime.binding_status : 'detached',
          parentLed: Boolean(row && row.recipe === 'parent'),
          onCommitted: () => {
            if (onChanged) onChanged()
          }
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
    setSaveSeed({
      course_title: row.title || null,
      objective_title: section ? section.title : null,
      excerpt: segment.text,
      kind: segment.artifact_id ? 'artifact' : 'lesson_segment',
      artifact_id: segment.artifact_id || null,
      source_ids: segment.source_id ? [segment.source_id] : [],
      source_titles: segment.source_id ? [(sourceIndex[segment.source_id] && sourceIndex[segment.source_id].title) || segment.source_id] : []
    })
  }, [row, section, sourceIndex])

  /**
   * Seed the notebook editor from the document's own block.
   *
   * `block` and `media` are exactly what the backend served: no excerpt is fetched from the chat,
   * no selection API is invented. The block id, its source ids and the artifact id travel with the
   * save so `Open in textbook` can return to this block and `Play/view media` to this artifact.
   */
  const saveBlock = useCallback((block, media) => {
    const sourceIds = (block.source_ids || []).slice(0, 8)
    setSaveSeed({
      course_title: row.title || null,
      objective_title: section ? section.title : null,
      block_id: block.id,
      block_headline: block.headline,
      artifact_id: media ? media.artifact_id || null : null,
      source_ids: sourceIds,
      source_titles: sourceIds.map((id) => (sourceIndex[id] && sourceIndex[id].title) || id),
      excerpt: blockSaveExcerpt(block, checkLabels, media),
      kind: media ? 'artifact' : 'lesson_segment',
      check_id: block.check_id || null
    })
  }, [row, section, checkLabels, sourceIndex])

  /**
   * Hand a mission to another view by block id.
   *
   * The check node is not re-created by this: it is the same `check.get` read and the same
   * `AttemptControls` node, mounted once in whichever view is on screen.
   */
  const openBlock = useCallback((blockId, targetView) => {
    setFocusBlockId(blockId || null)
    setLessonView(targetView || 'textbook')
  }, [])

  /**
   * The practice loop travels as one bundle.
   *
   * It exists only when the backend registers `pronunciation.attempt` and the enrollment row carries
   * a locale: without either, the studio would have to invent a language hint or a score. The
   * studio itself is seated per block, and only a block with an authored narration transcript gets
   * one (see `PronunciationSeat`).
   */
  const pronunciation =
    document && row.locale && supports('pronunciation.attempt')
      ? {
          enrollmentId: row.enrollment_id,
          objectiveId,
          revision: page ? page.revision : 0,
          locale: row.locale,
          implemented,
          onSaved: () => {
            if (onChanged) onChanged()
          }
        }
      : null

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
        document && !(document.views && document.views.guided) && document.view_note
          ? jsx(QuietNote, { children: document.view_note })
          : null,

        runtime && !bindingActive
          ? jsxs('div', {
              className: 'flex flex-wrap items-center justify-between gap-2 border-l border-(--ui-stroke-secondary) pl-3',
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

        document
          ? jsx(
              LessonDocumentView,
              {
                document,
                view: lessonView,
                sources: sourceIndex,
                checkSlot: checkNode,
                checkLabels,
                progress: row.evidence_summary || null,
                focusBlockId,
                onOpenBlock: openBlock,
                onSaveBlock: supports('notebook.save') ? saveBlock : null,
                pronunciation
              },
              objectiveId
            )
          : jsx(sdk.PanelSectionLabel, { children: 'TEACHING SEGMENTS' }),
        document ? null : page.segments && page.segments.length > 0
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
                      segment.kind === 'media'
                        ? jsx(MediaSegment, { segment })
                        : jsx('div', {
                            className: 'max-w-3xl',
                            children: jsx(sdk.MessageTextContent, { text: segment.text })
                          }),
                      segment.source_id
                        ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: `Source ${segment.source_id}` })
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

        document ? null : jsx(sdk.PanelSectionLabel, { children: 'CURRENT CHECK' }),
        document ? null : checkNode,

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
                            jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: verdictLabel(attempt.verdict, attempt.evidence_class) }),
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
          : null
      ]
    })
  }

  // The header, the view switcher and the field rail are the route shell; `body` is the reading
  // column only. The rail replaces the old in-page sources/notebook blocks, so nothing is printed
  // twice: the source cards and saved notes live in the third part of the workspace.
  const railFacts = section
    ? [
        { label: 'State', value: section.state || 'unrecorded' },
        { label: 'Evidence', value: section.evidence_target || 'unrecorded' },
        { label: 'Attempts', value: String((page && page.attempts ? page.attempts.length : 0)) }
      ]
    : []
  const viewOptions = document ? lessonViewOptions(document) : []
  const activeView = viewOptions.some((option) => option.id === lessonView) ? lessonView : 'textbook'
  const switcher = document
    ? jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        'data-cb-view-switcher': viewOptions.length > 1 ? 'available' : 'textbook-only',
        'data-cb-view-options': viewOptions.map((option) => option.id).join(' '),
        children: [
          jsx('span', { className: 'text-xs text-(--ui-text-secondary)', children: 'Lesson view' }),
          viewOptions.length > 1
            ? jsx(sdk.SegmentedControl, {
                onChange: (next) => {
                  setFocusBlockId(null)
                  setLessonView(next)
                },
                options: viewOptions,
                sizing: 'content',
                value: activeView
              })
            : jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: 'Textbook only' })
        ]
      })
    : null
  const shellActions = page
    ? [switcher, runtime ? jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: runtime.session_state }) : null]
    : [jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: onBack, children: 'All sections' })]

  return jsx(WorkspaceShell, {
    eyebrow: 'Coursebook',
    title: section && section.title ? section.title : 'Section',
    subtitle: section
      ? [
          section.state || null,
          section.evidence_target || null,
          section.last_opened_at ? `last opened ${whenLabel(section.last_opened_at)}` : null
        ].filter(Boolean).join(' · ')
      : null,
    meta: page && check.status === 'error' ? [jsx(QuietNote, { children: 'The check could not be opened.' })] : [],
    actions: shellActions,
    rail: page
      ? jsx(FieldRail, {
          next: row.next_step && (row.next_step.label || row.next_step.kind) ? (row.next_step.label || row.next_step.kind) : null,
          facts: railFacts,
          sources: page.sources || [],
          notes: page.notebook_entries || []
        })
      : null,
    children: [
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
                    children: `${verdictLabel(recent.verdict, recent.evidence_class)} · ${whenLabel(recent.committed_at || recent.created_at)}`
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
function TextbookView({ row, page, pageState, review, notebooks, outline, implemented, openSectionId, onOpenSection, onCloseSection, onChanged, targetBlockId }) {
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
      onChanged,
      targetBlockId: targetBlockId || null
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
                                    className: 'text-xs text-(--ui-text-secondary)',
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
function NotebookView({ row, notebooks, implemented, onOpenSection, onChanged, sections }) {
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
  const editTriggerRef = useRef(null)

  useEffect(() => {
    if (!pluginContext) return undefined
    const timer = pluginContext.setTimeout(() => setQuery(searchInput.trim()), 250)
    return timer
  }, [searchInput])

  const entries = notebooks && Array.isArray(notebooks.entries) ? notebooks.entries : []
  const sectionTitles = {}
  ;(sections || []).forEach((entry) => {
    if (entry && entry.objective_id && entry.title) sectionTitles[entry.objective_id] = entry.title
  })
  const [mediaOpen, setMediaOpen] = useState(null)
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
    // The editor's fields unmount here; hand focus back to the control that opened them.
    editTriggerRef.current?.focus({ preventScroll: true })
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
            className: 'flex flex-wrap items-center justify-between gap-2 border-l border-(--ui-stroke-secondary) pl-3',
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
                    jsx('div', {
                      className: 'max-w-3xl',
                      children: jsx(sdk.MessageTextContent, { text: entry.excerpt || entry.note || entry.kind })
                    }),
                    entry.note && entry.excerpt
                      ? jsx('p', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: entry.note })
                      : null,
                    mediaOpen === entry.entry_id
                      ? jsx(MediaSegment, {
                          segment: {
                            artifact_id: readNotebookRef(entry.source_ref).artifact_id,
                            text: entry.excerpt
                          }
                        })
                      : null,
                    jsxs('div', {
                      className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-secondary)',
                      children: [
                        jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: entry.kind }),
                        jsx('span', {
                          'data-cb-note-section': entry.objective_id,
                          children: `Section · ${sectionTitles[entry.objective_id] || entry.objective_id}`
                        }),
                        readNotebookRef(entry.source_ref).source_ids.length > 0
                          ? jsx('span', {
                              children: `Source · ${readNotebookRef(entry.source_ref).source_ids.join(', ')}`
                            })
                          : null,
                        row.title ? jsx('span', { children: `Course · ${row.title}` }) : null
                      ]
                    }),
                    jsxs('div', {
                      className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-secondary)',
                      children: [
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
                          onClick: () => onOpenSection(entry.objective_id, readNotebookRef(entry.source_ref).block_id),
                          children: 'Open in textbook'
                        }),
                        jsx(sdk.Button, {
                          variant: 'text',
                          size: 'sm',
                          onClick: () => onOpenSection(entry.objective_id, readNotebookRef(entry.source_ref).block_id),
                          children: 'Continue from here'
                        }),
                        readNotebookRef(entry.source_ref).artifact_id
                          ? jsx(sdk.Button, {
                              variant: 'text',
                              size: 'sm',
                              'aria-expanded': mediaOpen === entry.entry_id ? 'true' : 'false',
                              onClick: () => setMediaOpen(mediaOpen === entry.entry_id ? null : entry.entry_id),
                              children: 'Play/view media'
                            })
                          : null,
                        supports('notebook.update')
                          ? jsx(sdk.Button, {
                              variant: 'text',
                              size: 'sm',
                              onClick: (event) => {
                                editTriggerRef.current = event.currentTarget
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
                                jsx(sdk.Button, {
                                  variant: 'text',
                                  size: 'sm',
                                  onClick: () => {
                                    setEditing(null)
                                    editTriggerRef.current?.focus({ preventScroll: true })
                                  },
                                  children: 'Cancel'
                                })
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

      jsx(FocusReturningDialog, {
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
                            jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: verdictLabel(attempt.verdict, attempt.evidence_class) }),
                            jsx(EvidenceClassText, { value: attempt.evidence_class }),
                            jsx('span', { className: 'text-xs text-(--ui-text-secondary)', children: whenLabel(attempt.committed_at || attempt.created_at) })
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
                                      `${item.id || 'criterion'}-${index}`
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
                                          course_title: row.title || null,
                                          objective_title: attempt.title || null,
                                          check_id: attempt.check_id
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
                      className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-secondary)',
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
                      jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: `basis: ${item.basis}` })
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
                          jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: verdictLabel(attempt.verdict, attempt.evidence_class) }),
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
                    className: 'flex flex-wrap items-center justify-between gap-2 py-1 text-xs text-(--ui-text-secondary)',
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
              className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-secondary)',
              children: [
                jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: source.source_type }),
                jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: source.support_status }),
                jsx('span', { children: source.fetched_at ? `fetched ${whenLabel(source.fetched_at)}` : 'fetch date unknown' }),
                source.published_at ? jsx('span', { children: `published ${whenLabel(source.published_at)}` }) : null
              ]
            }),
            source.url
              ? jsx('div', {
                  className: 'text-xs text-(--ui-text-secondary)',
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
 * Export — the learner's course packages itself (cb.rpc v11).
 *
 * `course.export.read` is the review, `course.export` is the write, and the two agree about the
 * content hash: the surface echoes the hash it displayed, so the exported archive is the exact
 * page set a person read. The file list, licence, rights statement and no-upload statement all come
 * from the backend; nothing here invents a file, a size or a promise.
 *
 * A pack-backed course has no business here — its bytes belong to `pack.export` — so the backend
 * answers `course_pack_backed` and this view says so instead of offering a second, competing export.
 */
const COURSE_EXPORT_BLOCKED_COPY = {
  plan_not_approved:
    'The plan is not approved yet. Approve the plan before packaging this course: an unapproved plan is not a published design.',
  lessons_not_validated:
    'At least one lesson page has not passed validation, so it cannot be packaged. Regenerate or fix the page first; a page no validator cleared is not content to hand to someone else.',
  no_generated_content:
    'This course has no lesson pages yet. Generate the lessons before packaging it.',
  changes_need_review:
    'The lesson text changed after it was approved. Review the pages again before packaging them.',
  export_not_exportable:
    'The generated lessons do not meet the pack’s teaching minima yet, so the archive would not import. Fix the lesson content first.',
  export_write_failed:
    'The archive could not be written. Nothing was exported and nothing was sent anywhere.',
  course_pack_backed:
    'This course came from a pack. Its file list and licence belong to that pack, so re-export it from the pack surface — this course cannot export its own copy.'
}

/** The exact write call, including the reviewed-content fence. Pure so a test can assert it. */
function courseExportRequest(row, reviewedContentHash) {
  return {
    method: 'course.export',
    payload: {
      enrollment_id: row.enrollment_id,
      expected_content_hash: reviewedContentHash
    },
    options: { idempotencyKey: newOperationId('course-export') }
  }
}

function CourseExportView({ row, implemented }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const key = `course-export-${row.enrollment_id}`
  const query = useRpcQuery(
    'course.export.read',
    { enrollment_id: row.enrollment_id },
    key,
    supports('course.export.read')
  )
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [exported, setExported] = useState(null)
  const [artifact, setArtifact] = useState(null)

  const run = useCallback(async () => {
    if (!query.data || !query.data.content_hash) return
    setBusy(true)
    setError(null)
    try {
      const request = courseExportRequest(row, query.data.content_hash)
      const response = await rpc(request.method, request.payload, request.options)
      if (!response.ok) {
        if (response.error && response.error.code === 'DELETE_SCOPE_STALE') {
          setError({
            message:
              'The lesson text changed since this page was read, so nothing was exported. The review was refreshed; export again only if the new file list is the one you want.'
          })
          query.reload()
          return
        }
        throw new Error(`${response.error ? response.error.code + ': ' : ''}${describeError(response.error)}`)
      }
      if (response.result.content_hash !== query.data.content_hash) {
        throw new Error(
          'The backend exported a different content hash than the one reviewed. Nothing here should be handed on.'
        )
      }
      setExported(response.result)
      const facts = await rpc('artifact.get', {
        artifact_id: response.result.artifacts[0].artifact_id
      })
      if (facts.ok) setArtifact(facts.result)
      query.reload()
    } catch (failure) {
      setError({ message: describeError(failure) })
    } finally {
      setBusy(false)
    }
  }, [query, row])

  if (!supports('course.export.read')) {
    return jsx(QuietNote, {
      children:
        'This backend build does not publish the course export commands, so there is no export action here. Nothing is offered that would produce a file the backend did not write.'
    })
  }
  if (query.status === 'loading' && !query.data) {
    return jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading what an export would contain' }) })
  }
  if (query.status === 'error' && !query.data) {
    return jsx(sdk.ErrorState, {
      title: 'The export review could not be read',
      description: `${query.error && query.error.code ? query.error.code + ': ' : ''}${describeError(query.error)}`,
      children: jsx(sdk.Button, { variant: 'secondary', onClick: query.reload, children: 'Try again' })
    })
  }
  const read = query.data || {}
  const files = read.files || []

  if (!read.ready) {
    return jsxs('div', {
      className: 'flex max-w-3xl flex-col gap-3',
      children: [
        jsx('div', { className: 'text-sm font-semibold', children: 'This course cannot be packaged yet' }),
        jsx('div', {
          className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
          children:
            (read.blocked_reason && COURSE_EXPORT_BLOCKED_COPY[read.blocked_reason]) ||
            read.blocked_message ||
            'The backend gave no reason, so no export is offered.'
        }),
        (read.problems || []).length > 0
          ? jsx('div', {
              className: 'flex flex-col gap-1',
              children: read.problems.map((problem) =>
                jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: `• ${problem}` }, problem)
              )
            })
          : null,
        read.sections
          ? jsx('div', {
              className: 'text-xs text-(--ui-text-secondary)',
              children: `${Number(read.sections.validated)} of ${Number(read.sections.total)} lesson page(s) validated.`
            })
          : null,
        jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: query.reload, children: 'Check again' })
      ]
    })
  }

  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-3',
    children: [
      jsx('div', { className: 'text-sm font-semibold', children: 'Review the export' }),
      jsx('div', {
        className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
        children:
          'Every file below is in the archive. Attempts, notebook notes, evidence, transcripts and provider ' +
          'settings are not part of a pack and are excluded by construction.'
      }),
      jsxs('div', {
        className: 'flex flex-col',
        children: files.map((file) =>
          jsxs(
            'div',
            {
              className:
                'flex flex-wrap items-baseline justify-between gap-2 border-b border-(--ui-stroke-tertiary) py-1.5 last:border-b-0',
              children: [
                jsx('div', { className: 'min-w-0 break-all text-xs', children: file.name }),
                jsxs('div', {
                  className: 'flex shrink-0 items-center gap-2 text-xs text-(--ui-text-secondary)',
                  children: [
                    jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: file.role }),
                    jsx('span', { children: bytesLabel(file.bytes) })
                  ]
                })
              ]
            },
            file.name
          )
        )
      }),
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(PackReviewLine, { label: 'Files', value: String(files.length) }),
          jsx(PackReviewLine, {
            label: 'Content hash',
            value: jsx('code', { className: 'text-xs', children: read.content_hash })
          }),
          jsx(PackReviewLine, {
            label: 'Licence',
            value: `${(read.license && read.license.id) || 'unknown'} · ${(read.license && read.license.redistribution) || 'unknown'}`
          }),
          jsx(PackReviewLine, {
            label: 'Plan',
            value: read.plan ? `version ${read.plan.version} · ${read.plan.state}` : 'not recorded'
          })
        ]
      }),
      jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: read.rights }),
      jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: read.no_upload }),
      jsxs('label', {
        className: 'flex items-start gap-2 text-xs text-(--ui-text-secondary)',
        children: [
          jsx('input', {
            checked: confirmed,
            onChange: (event) => setConfirmed(Boolean(event.target.checked)),
            type: 'checkbox'
          }),
          jsx('span', {
            children: 'I reviewed these files, the licence and the rights statement; package exactly this text.'
          })
        ]
      }),
      jsx(sdk.Button, {
        disabled: busy || !confirmed,
        onClick: run,
        size: 'sm',
        variant: 'default',
        children: busy ? 'Packaging' : 'Export these files'
      }),
      error ? jsx('div', { className: 'text-xs', children: error.message }) : null,
      exported
        ? jsxs('div', {
            className: 'flex flex-col',
            children: [
              jsx(sdk.PanelSectionLabel, { children: 'EXPORTED' }),
              jsx(PackReviewLine, {
                label: 'Content hash',
                value: jsx('code', { className: 'text-xs', children: exported.content_hash })
              }),
              jsx(PackReviewLine, { label: 'Matches the reviewed hash', value: 'yes' }),
              jsx(PackReviewLine, {
                label: 'Pack',
                value: `${exported.pack.pack_id} v${exported.pack.pack_version}`
              }),
              jsx(PackReviewLine, { label: 'Files', value: String((exported.files || []).length) }),
              jsx(PackReviewLine, {
                label: 'Archive bytes',
                value: bytesLabel(exported.artifacts && exported.artifacts[0] ? exported.artifacts[0].bytes : 0)
              }),
              artifact
                ? jsx(sdk.Button, {
                    asChild: true,
                    size: 'sm',
                    variant: 'secondary',
                    children: jsx('a', {
                      download: `${exported.pack.pack_id}-${exported.pack.pack_version}.zip`,
                      href: artifact.download.url,
                      children: 'Download archive'
                    })
                  })
                : null,
              jsx('div', {
                className: 'mt-1 text-xs leading-relaxed text-(--ui-text-secondary)',
                children:
                  'The download link is the host route the backend named; the session is checked there and the ' +
                  'handle expires. The file is byte-identical to the hash above.'
              })
            ]
          })
        : null
    ]
  })
}

/**
 * Course detail — the durable page for one enrollment.
 *
 * Local tabs, not more sidebar destinations. At wide widths the view switcher is a segmented
 * control; below ~47.5rem it collapses into one labelled picker so the strip can never clip.
 */
function CourseDetail({ row, implemented, profile, onBack, onChanged, focusObjectiveId, focusBlockId, focusView }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  // A route in from the Field Desk names the section to open; otherwise the course opens on its
  // overview with the backend's own current objective already selected.
  const [view, setView] = useState(focusView || (focusObjectiveId ? 'textbook' : 'overview'))
  const [objectiveId, setObjectiveId] = useState(
    focusObjectiveId || (row.evidence_summary && row.evidence_summary.current_objective_id) || null
  )
  const [openSectionId, setOpenSectionId] = useState(focusObjectiveId || null)
  // A saved moment carries the block it came from; the section opens on that block, not its top.
  const [targetBlockId, setTargetBlockId] = useState(focusBlockId || null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  // `plan.approve` fences on the enrolment revision, so the page tracks the revision the last
  // mutation returned instead of trusting the row it was opened with.
  const [revision, setRevision] = useState(Number(row.revision || 0))

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

  const openSection = useCallback((nextObjectiveId, blockId) => {
    if (nextObjectiveId) setObjectiveId(nextObjectiveId)
    setOpenSectionId(nextObjectiveId || null)
    // Only a call that names a block aims at one; a plain "Open section" lands at the top.
    setTargetBlockId(blockId || null)
    setView('textbook')
  }, [])

  const closeSection = useCallback(() => {
    setOpenSectionId(null)
    setTargetBlockId(null)
  }, [])

  const selectView = useCallback((nextView) => {
    setView(nextView)
    if (nextView === 'textbook') setOpenSectionId(null)
  }, [])

  const viewLabel = (LEARNING_VIEWS.find((option) => option.id === view) || { label: view }).label

  const startLesson = useCallback(
    async (mode, explicitObjectiveId) => {
      const target = explicitObjectiveId || objectiveId || (row.evidence_summary && row.evidence_summary.current_objective_id)
      if (!target) {
        setNotice('This course has no current objective yet; approve the plan first.')
        return
      }
      setBusy(true)
      setNotice(null)
      const outcome = await beginLessonFor({
        row,
        objectiveId: target,
        mode,
        profile: profile || currentScope().profile
      })
      setBusy(false)
      setNotice(outcome.message)
      if (outcome.ok) refresh()
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
      onChanged: refresh,
      targetBlockId
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
          onChanged: refresh,
          sections: rows
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
    body = jsx(LearnerPlanView, {
      course: { course_id: row.course_id, enrollment_id: row.enrollment_id },
      revision,
      onRevision: setRevision,
      implemented,
      onOpenSection: openSection,
      onStartLesson: (objectiveId) => startLesson('fresh', objectiveId),
      onChanged: refresh
    })
  } else if (view === 'evidence') {
    body = jsx(EvidenceView, { evidence: evidence.data, implemented, onOpenSection: openSection })
  } else if (view === 'export') {
    body = jsx(CourseExportView, { row, implemented })
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
                  jsx('span', { className: 'text-xs text-(--ui-text-secondary)', children: currentTitle })
                ]
              })
            ]
          }),
          jsxs('div', {
            className: 'flex shrink-0 flex-wrap items-center justify-end gap-2',
            children: [
              // The export action lives on the course itself: a course a learner authored from a
              // goal can package itself without visiting Parent Studio or the pack library.
              supports('course.export.read') && view !== 'export'
                ? jsx(sdk.Button, {
                    variant: 'secondary',
                    size: 'sm',
                    onClick: () => selectView('export'),
                    children: 'Export course…'
                  })
                : null,
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
                  // The selected view is part of the name: a combobox whose name is only
                  // "Course view" makes a screen-reader user open it to learn where they are.
                  'aria-label': `Course view: ${viewLabel}`,
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
    enabled: Boolean(objectiveId) && backendSupports('check.open') && Boolean(page.data),
    implemented: backendWire.implemented
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
            className: 'flex flex-col gap-1 border-l border-(--ui-stroke-secondary) pl-3',
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
                parentLed: Boolean(row && row.recipe === 'parent'),
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
        className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-secondary)',
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
          ? jsx('p', { className: 'text-xs text-(--ui-text-secondary)', children: hint })
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
    return jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'Queued. The job runner picks it up on its next tick; nothing is spent until it starts.' })
  }
  if (job.state === 'cancel_requested' || job.state === 'cancelling') {
    return jsx('div', {
      className: 'text-xs text-(--ui-text-secondary)',
      children: 'Cancelling. The current provider call is not aborted; the job stops before its next step.'
    })
  }
  if (job.state === 'running') {
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
  if (job.state === 'cancelled') {
    return jsx('div', {
      className: 'text-xs text-(--ui-text-secondary)',
      children: 'Cancelled before it finished. The brief and any work that had already been saved are kept.'
    })
  }
  const error = job.error || {}
  return jsxs('div', {
    className: 'flex flex-col gap-1 text-xs text-(--ui-text-secondary)',
    children: [
      jsx('div', { children: `Failed${error.code ? ` (${error.code})` : ''}.` }),
      error.message ? jsx('div', { className: 'text-(--ui-text-secondary)', children: error.message }) : null
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

function StudioJobLine({ jobId, onSettled, onRunAgain }) {
  const job = useStudioJob(jobId, onSettled)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  if (!jobId) return null

  const state = job && job.state
  const running = state === 'queued' || state === 'running'
  const retryable = Boolean(
    onRunAgain && job && job.brief && (state === 'cancelled' || state === 'failed' || state === 'interrupted_requires_retry')
  )

  const cancel = async () => {
    setBusy(true)
    setError(null)
    const response = await rpc('jobs.cancel', { job_id: jobId })
    setBusy(false)
    if (!response.ok) setError(response.error)
  }

  // Re-queue the same stage from the brief the job itself stored. The parent re-reads, so the line
  // shows the new job id rather than pretending the cancelled one resumed.
  const runAgain = async () => {
    setBusy(true)
    setError(null)
    const response = await rpc(
      'jobs.create',
      { kind: job.kind || 'plan', brief: job.brief },
      { idempotencyKey: newOperationId('stage-again') }
    )
    setBusy(false)
    if (!response.ok) {
      setError(response.error)
      return
    }
    if (onRunAgain) onRunAgain(response.result.job_id)
  }

  return jsxs('div', {
    className: 'flex flex-col gap-1',
    'data-cb-job-id': jobId,
    'data-cb-job-state': state || 'reading',
    children: [
      jsx(JobStateText, { job }),
      running ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'It runs in the background; leaving this page does not stop it.' }) : null,
      running
        ? jsx(sdk.Button, {
            size: 'sm',
            variant: 'secondary',
            disabled: busy,
            onClick: cancel,
            className: 'self-start',
            children: busy ? 'Cancelling' : 'Cancel generation'
          })
        : null,
      retryable
        ? jsx(sdk.Button, {
            size: 'sm',
            variant: 'secondary',
            disabled: busy,
            onClick: runAgain,
            className: 'self-start',
            children: busy ? 'Starting' : 'Run this stage again'
          })
        : null,
      error
        ? jsx('div', {
            className: 'text-xs text-(--ui-text-secondary)',
            children: `${error.code ? error.code + ': ' : ''}${describeError(error)}`
          })
        : null
    ]
  })
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
      jsx('div', { className: 'pb-1 text-xs text-(--ui-text-secondary)', children: `${rows.length} authored course${rows.length === 1 ? '' : 's'}` }),
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
        className: 'flex flex-col gap-2 border-l border-(--ui-stroke-secondary) pl-3',
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
              jsx('div', { className: 'text-(--ui-text-secondary)', children: 'The brief was not saved and no job was queued.' })
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
        ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'This backend does not register parent.brief.create.' })
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
    className: 'flex flex-col gap-1 border-l border-(--ui-stroke-secondary) pl-3',
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
        className: 'text-xs text-(--ui-text-secondary)',
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
          jsx(StudioJobLine, { jobId: planJobId, onSettled: onJobSettled, onRunAgain: onJobSettled })
        ]
      }),
      latestProposal
        ? jsxs('div', {
            className: 'flex flex-col gap-1 border-l border-(--ui-stroke-tertiary) pl-3',
            children: [
              jsx('div', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: 'A note from your last reflection' }),
              jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: latestProposal.revisit_note }),
              jsx('div', {
                className: 'text-xs text-(--ui-text-secondary)',
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
  supported,
  surface,
  outlineHidden
}) {
  // `surface: 'learner'` is the same outline/plan review for a learner course: identical reads,
  // identical approve and lessons actions, minus the parent-only authoring controls (edit plan,
  // start a new version). It is one component so the two doors can never drift.
  const learner = surface === 'learner'
  // A learner's approved-plan tab shows its own objective state list, so this panel keeps the
  // actions and the job line and drops the duplicated outline.
  const hideOutline = Boolean(outlineHidden)
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

  // A plan version carries its authored document (sections and research) in `gen_plan_documents`,
  // keyed by plan_id. `plan.replan` now carries that document onto a content-preserving new version
  // (keep / retitle / defer / remove), so a replanned plan is authorable again — the version is no
  // longer unauthorable just because it was replanned. Two cases still leave the version without a
  // covering document: a structural `add` through the editor (no authored section exists for a new
  // objective) and a version whose replan could not carry. No wire field declares authorship, so the
  // studio does not guess before the click: it reads the refusal the lessons job itself returns and
  // withholds the action for that plan version instead of offering the same failure twice.
  const [lessonDocumentGap, setLessonDocumentGap] = useState(null)
  const planIdOnScreen = plan && plan.plan_id

  // The editor's displayed order. Local until Save changes sends it as a permutation.
  useEffect(() => setOrder(null), [outline.data])
  const displayObjectives = order
    ? order.map((id) => objectives.find((objective) => objective.objective_id === id)).filter(Boolean)
    : objectives

  // A new plan version (plan.replan) is a new set of objective rows with new ids. The editor is
  // opened right after that replan, before the outline reload lands, so its drafts can be keyed by
  // the previous version's ids — every title input then renders empty. Backfill a draft for any
  // objective that has none while the editor is open, so a title is never shown as blank.
  useEffect(() => {
    if (!editing) return
    setDrafts((previous) => {
      let changed = false
      const next = { ...previous }
      for (const objective of objectives) {
        if (!next[objective.objective_id]) {
          next[objective.objective_id] = { title: objective.title, evidence_target: objective.evidence_target }
          changed = true
        }
      }
      return changed ? next : previous
    })
  }, [editing, objectives])

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
    // `plan.approve` fences on the digest recomputed from the plan rows, and an edit changes it the
    // moment it is saved. The page's `book` query can still hold the pre-edit digest for a render or
    // two, and submitting that is refused `VALIDATION_FAILED: the approved hash does not match the
    // current plan content`. Read the digest directly at approve time instead of trusting the render.
    let hash = planHash
    if (supported('parent.blueprint.read')) {
      const fresh = await rpc('parent.blueprint.read', { course_id: course.course_id })
      const freshHash = fresh && fresh.ok && fresh.result && fresh.result.plan ? fresh.result.plan.plan_hash : null
      if (freshHash) hash = freshHash
    }
    if (!hash) {
      setBusy(false)
      setError('The plan digest is not available yet. Re-read the plan and try again.')
      return
    }
    const response = await rpc(
      'plan.approve',
      { enrollment_id: course.enrollment_id, plan_id: plan.plan_id, plan_hash: hash },
      { expectedRevision: revision, idempotencyKey: newOperationId('plan-approve') }
    )
    setBusy(false)
    if (!response.ok) {
      const nextRevision = staleRevision(response)
      if (nextRevision !== null) onRevision(nextRevision)
      const hashMismatch = /plan content/i.test((response.error && response.error.message) || '')
      if (hashMismatch) onChanged()
      setError(
        `${response.error.code}: ${describeError(response.error)}` +
          (hashMismatch ? ' The plan was re-read; press Approve plan again.' : '') +
          (nextRevision !== null ? ' The course revision was refreshed; press Approve plan again.' : '')
      )
      return
    }
    onRevision(response.result.revision)
    setNotice('Plan approved. The outline and activities are now fixed; the generated pages are a separate approval.')
    onChanged()
  }, [plan, course.enrollment_id, course.course_id, planHash, revision, onRevision, onChanged, supported])

  const generateLessons = useCallback(async () => {
    if (!plan) return
    setBusy(true)
    setError(null)
    // Keyed by the plan version: a double click or a retried click replays the same job instead of
    // enqueueing a second lessons run (and a second spend) for the same approved outline.
    const response = await rpc(
      'jobs.create',
      { kind: 'plan', brief: { stage: 'lessons', plan_id: plan.plan_id, enrollment_id: course.enrollment_id } },
      { idempotencyKey: `cb-lessons-${plan.plan_id}` }
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

  // Clear the gap when the screen moves to another plan version (a replan or a fresh authoring job
  // that completed and reloaded the outline).
  useEffect(() => setLessonDocumentGap(null), [planIdOnScreen])

  const settled = useCallback(
    (job) => {
      if (!job) return
      const isLessons = job.brief && job.brief.stage === 'lessons'
      const message = (job.error && job.error.message) || ''
      if (isLessons && job.state === 'failed' && /no authored document|outline covers objectives/i.test(message)) {
        setLessonDocumentGap(message)
        onJobSettled(job)
        return
      }
      if (job.state === 'completed' || job.state === 'completed_late') {
        if (isLessons) setLessonDocumentGap(null)
        onChanged()
        return
      }
      onJobSettled(job)
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
      title: planJobId ? 'The plan is being written' : 'No plan yet',
      description: planJobId
        ? 'Research and drafting run in the background; this screen fills itself when the plan is written. Nothing is shown from a template, and there is no progress percentage to show.'
        : learner
          ? 'This course has no plan job attached. Start a new course to generate one; nothing is invented to fill the gap.'
          : 'No plan job is attached to this course, so there is nothing to review. Start a new brief.',
      children: planJobId ? jsx(StudioJobLine, { jobId: planJobId, onSettled, onRunAgain: onChanged }) : null
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
              jsx('span', { className: 'text-xs text-(--ui-text-secondary)', children: `plan ${String(planHash || '').slice(0, 19)}…` })
            ]
          }),
          jsxs('div', {
            className: 'flex flex-wrap items-center gap-2',
            children: [
              isDraft && !editing && !learner
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
              !isDraft && !editing && !lessonDocumentGap
                ? jsx(sdk.Button, {
                    size: 'sm',
                    variant: 'default',
                    disabled: busy || !supported('jobs.create'),
                    onClick: generateLessons,
                    children: contentReady ? 'Generate missing lessons' : 'Generate lessons'
                  })
                : null,
              !isDraft && !editing && !learner
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
      lessonDocumentGap
        ? jsx('p', {
            className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
            'data-cb-plan-document': 'missing',
            children:
              `Lessons cannot be generated from this plan version: ${lessonDocumentGap} ` +
              'The authored outline (its sections and research) belongs to the version that was written with the plan, and this version has changes it does not cover, so Generate lessons is withheld rather than offered as a second failure. Start a new plan version to author an outline that covers every objective.'
          })
        : null,
      notice ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: notice }) : null,
      error ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: error }) : null,
      planJobId ? jsx(StudioJobLine, { jobId: planJobId, onSettled: onJobSettled, onRunAgain: onChanged }) : null,
      lessonJobId ? jsx(StudioJobLine, { jobId: lessonJobId, onSettled: settled }) : null,

      !isDraft && contentReady
        ? jsx('div', {
            className: 'text-xs text-(--ui-text-secondary)',
            children:
              'Re-running generation reuses every lesson already authored at this plan version and only authors what is missing. Nothing is paid for twice.'
          })
        : null,

      hideOutline
        ? null
        : jsxs('div', {
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
                              jsx('span', { className: 'shrink-0 text-xs tabular-nums text-(--ui-text-secondary)', children: String(objective.ordinal).padStart(2, '0') }),
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
                        className: 'text-xs text-(--ui-text-secondary)',
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
                ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'No sources recorded for this course.' })
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
                              className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-secondary)',
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
                className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                children: 'A draft plan can be edited freely. An approved plan is changed only by starting a new version, so what you approved stays exact.'
              })
            ]
          })
        ]
      })
    ]
  })
}

/**
 * The learner's plan surface.
 *
 * Parent Studio and a learner course review the same outline through `StudioPlanView`; this
 * wrapper adds what a learner needs around it: the plan job found by enrolment (leaving and
 * reopening reattaches by id, not by memory), the honest time expectation for the chosen scope,
 * and — once the pages exist — a link into the first lesson. It never invents content or a
 * percentage: a failed job keeps its typed reason and the draft stays recoverable.
 */
function LearnerPlanView({
  course,
  revision,
  onRevision,
  implemented,
  onOpenSection,
  onStartLesson,
  onChanged,
  jobHint,
  scopeHint
}) {
  const supports = (method) => (implemented ? implemented.has(method) : backendSupports(method))
  const outline = useRpcQuery(
    'course.outline',
    { enrollment_id: course.enrollment_id },
    `learner-plan-outline-${course.enrollment_id}`,
    supports('course.outline')
  )
  const book = useRpcQuery(
    'parent.blueprint.read',
    { course_id: course.course_id },
    `learner-plan-book-${course.course_id}`,
    supports('parent.blueprint.read')
  )
  // The job is discovered from the enrolment it names, so a reload or a route change reattaches to
  // the same run instead of starting another one.
  const jobs = useRpcQuery(
    'jobs.list',
    { enrollment_id: course.enrollment_id, kind: ['plan'], limit: 20 },
    `learner-plan-jobs-${course.enrollment_id}`,
    supports('jobs.list')
  )
  const [retryJobId, setRetryJobId] = useState(null)

  const plan = outline.data && outline.data.plan
  const objectives = (outline.data && outline.data.objectives) || []
  const jobRows = (jobs.data && jobs.data.jobs) || []
  const planJob = jobRows.find((job) => ((job.brief || {}).stage || 'plan') === 'plan') || null
  const lessonsJob = jobRows.find((job) => (job.brief || {}).stage === 'lessons') || null
  const scope = (planJob && planJob.brief && planJob.brief.scope) || scopeHint || null
  const jobId = retryJobId || jobHint || (planJob && planJob.job_id) || null
  // A plan that is already readable does not need its finished job line repeated on every visit.
  const showJob = Boolean(jobId && (objectives.length === 0 || !planJob || !JOB_TERMINAL_STATES.has(planJob.state)))

  const reloadAll = useCallback(() => {
    outline.reload()
    book.reload()
    jobs.reload()
    if (onChanged) onChanged()
  }, [outline, book, jobs, onChanged])

  if (outline.status === 'error' && !outline.data) {
    return jsx(sdk.ErrorState, {
      title: 'The plan could not be read',
      description: `${outline.error && outline.error.code ? outline.error.code + ': ' : ''}${describeError(outline.error)}`,
      children: jsx(sdk.Button, { variant: 'secondary', onClick: outline.reload, children: 'Try again' })
    })
  }

  const lessonsFailed = Boolean(
    lessonsJob && ['failed', 'cancelled', 'interrupted_requires_retry'].includes(lessonsJob.state)
  )
  const lessonsReady = Boolean(
    lessonsJob &&
      !lessonsFailed &&
      JOB_TERMINAL_STATES.has(lessonsJob.state) &&
      Number((lessonsJob.checkpoint || {}).lessons || 0) > 0
  )
  const approved = Boolean(plan && plan.state === 'approved')

  return jsxs('div', {
    className: 'flex flex-col gap-4',
    'data-cb-learner-plan': (plan && plan.state) || 'none',
    'data-cb-learner-plan-job': jobId || 'none',
    children: [
      jsx('p', { className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)', children: planTimingCopy(scope) }),
      approved && objectives.length > 0
        ? jsxs('div', {
            className: 'flex flex-wrap items-center gap-2',
            children: [
              lessonsReady && onStartLesson
                ? jsx(sdk.Button, {
                    size: 'sm',
                    variant: 'default',
                    onClick: () => onStartLesson(objectives[0].objective_id),
                    children: 'Start the first lesson'
                  })
                : null,
              onOpenSection
                ? jsx(sdk.Button, {
                    size: 'sm',
                    variant: 'secondary',
                    onClick: () => onOpenSection(objectives[0].objective_id),
                    children: 'Open the first section'
                  })
                : null
            ]
          })
        : null,
      approved && !lessonsReady && !lessonsFailed
        ? jsx(QuietNote, {
            children:
              'The outline is approved. Lesson pages are written by the lessons job below; the section list is the approved outline, not generated content.'
          })
        : null,
      approved && objectives.length > 0 && onOpenSection
        ? jsx(PlanView, {
            row: { course_id: course.course_id, enrollment_id: course.enrollment_id, revision },
            review: null,
            notebooks: null,
            outline: outline.data,
            page: null,
            implemented,
            onOpenSection,
            onChanged: reloadAll
          })
        : null,
      jsx(StudioPlanView, {
        course,
        revision,
        onRevision,
        outline,
        book,
        brief: null,
        planJobId: showJob ? jobId : null,
        onJobSettled: reloadAll,
        onChanged: reloadAll,
        supported: supports,
        surface: 'learner',
        outlineHidden: approved
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
        className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-secondary)',
        children: [
          jsx('span', { children: `${files.length} file${files.length === 1 ? '' : 's'} in this tab` }),
          jsx('span', { children: `content hash ${String(data.content_hash || '').slice(0, 19)}…` })
        ]
      }),
      tab === 'sources'
        ? sources.length === 0
          ? jsx('div', { className: 'py-4 text-xs text-(--ui-text-secondary)', children: 'No sources were recorded for this course.' })
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
                        className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-secondary)',
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
                            className: 'flex shrink-0 items-center gap-2 text-xs text-(--ui-text-secondary)',
                            children: [
                              jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: file.role }),
                              jsx('span', { children: bytesLabel(file.bytes) }),
                              file.truncated ? jsx(sdk.Badge, { size: 'xs', variant: 'warn', children: 'clipped' }) : null
                            ]
                          })
                        ]
                      }),
                      jsx('div', {
                        className: 'max-w-3xl',
                        children: jsx(sdk.MessageTextContent, { text: file.text })
                      }),
                      jsxs('div', {
                        className: 'text-xs break-all text-(--ui-text-secondary)',
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
function StudioExportPanel({ course, book, revision, onRevision, supported, onChanged }) {
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
      {
        expectedRevision: typeof revision === 'number' ? revision : 0,
        idempotencyKey: newOperationId('parent-final-approve')
      }
    )
    setApproving(false)
    if (!response.ok) {
      const nextRevision = staleRevision(response)
      if (nextRevision !== null && typeof onRevision === 'function') onRevision(nextRevision)
      setApproveError(
        describeError(response.error) +
          (nextRevision !== null ? ' The course revision was refreshed; press Approve this lesson set again.' : '')
      )
      return
    }
    if (typeof onRevision === 'function') onRevision(Number(response.result.revision) || 0)
    if (typeof onChanged === 'function') onChanged()
  }, [course.enrollment_id, plan.plan_id, planHash, contentHash, revision, onRevision, onChanged])

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
            value: jsx('code', { className: 'text-xs break-all', children: approval.content_hash || '—' })
          }),
          jsx(PackReviewLine, {
            label: 'Current content hash',
            value: jsx('code', { className: 'text-xs break-all', children: (book && book.data && book.data.content_hash) || '—' })
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
                    className: 'flex flex-col gap-0.5 text-(--ui-text-secondary)',
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
                className: 'text-xs text-(--ui-text-secondary)',
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
                className: 'flex flex-col gap-1 text-xs leading-relaxed text-(--ui-text-secondary)',
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
                          jsx('div', { className: 'min-w-0 break-all text-xs text-(--ui-text-secondary)', children: artifact.content_hash })
                        ]
                      }),
                      facts && facts.download
                        ? jsx(sdk.Button, {
                            asChild: true,
                            size: 'sm',
                            variant: 'secondary',
                            children: jsx('a', {
                              download:
                                artifact.kind === 'pdf'
                                  ? 'parent-lesson-pack.pdf'
                                  : artifact.kind === 'pack'
                                    ? 'parent-lesson-pack.zip'
                                    : 'parent-export.json',
                              href: facts.download.url,
                              children:
                                artifact.kind === 'pdf'
                                  ? 'Download PDF'
                                  : artifact.kind === 'pack'
                                    ? 'Download pack archive'
                                    : 'Download export record'
                            })
                          })
                        : null,
                      facts && facts.download
                        ? jsx('div', {
                            className: 'text-xs text-(--ui-text-secondary)',
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
              jsx(PackReviewLine, { label: 'Plan hash', value: jsx('code', { className: 'text-xs break-all', children: saved.plan_hash || '—' }) })
            ]
          })
        : null,
      jsx(sdk.PanelSectionLabel, { children: `REFLECTIONS (${list.length})` }),
      list.length === 0
        ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'No reflections recorded for this course yet.' })
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
                        jsx('span', { className: 'text-(--ui-text-secondary)', children: `parent-reported · ${whenLabel(item.created_at)}` }),
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
    body = jsx(StudioExportPanel, {
      course,
      book,
      revision,
      onRevision,
      supported: supports,
      onChanged: reloadAll
    })
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
            className: 'text-xs text-(--ui-text-secondary)',
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

/**
 * A controlled `ConfirmDialog` that hands focus back to the control that opened it.
 *
 * Every Coursebook dialog is opened from a button, not a DialogTrigger, so Radix has no trigger to
 * restore to and focus lands on `<body>` when the dialog unmounts. The control that opened it is
 * remembered at open time and refocused at close; when the section refresh replaced that node while
 * the dialog was up, the same control is found again by its label inside this plugin's own route
 * root. Only Coursebook's own markup is read — nothing here observes or restyles the app shell.
 *
 * This is the ONLY focus-restoration mechanism in the plugin. A separate `useReturnFocus` hook
 * briefly coexisted here (both ran on NotebookSaveDialog); it restored the same opener from the
 * effect cleanup, one animation frame later. It was removed rather than the dialog wrapper because
 * the wrapper also owns the label fallback for a replaced opener and is used by every dialog in
 * this file, so keeping one mechanism means no dialog can drift.
 */
function FocusReturningDialog({ open, ...props }) {
  const openerRef = useRef(null)
  useEffect(() => {
    if (open) {
      const active = document.activeElement
      if (active && active !== document.body && !(active.closest && active.closest('[role="dialog"]'))) {
        openerRef.current = { element: active, label: (active.innerText || '').trim().slice(0, 80) }
      }
      return
    }
    const opener = openerRef.current
    openerRef.current = null
    if (!opener) return
    let target = opener.element && opener.element.isConnected ? opener.element : null
    if (!target && opener.label) {
      const root = document.querySelector('[data-cb-route]')
      target =
        (root &&
          [...root.querySelectorAll('button')].find(
            (button) => (button.innerText || '').trim().slice(0, 80) === opener.label
          )) ||
        null
    }
    if (target && typeof target.focus === 'function') target.focus({ preventScroll: true })
  }, [open])
  const dialogProps = { open, ...props }
  return jsx(sdk.ConfirmDialog, dialogProps)
}

function CoursebookPage() {
  const { state: health, reload: reloadHealth } = useHealth()
  const implemented = useRuntime(health.status)
  // The scoped Ink & Field Notes layer: every Coursebook surface paints from `--cb-*`, and the
  // layer stops at this root, so Hermes chrome keeps its own theme untouched.
  const cbMode = useCbMode()
  const cbMotion = useCbMotion()
  const [destination, setDestination] = useState(rememberedDestination)
  const [coursesMode, setCoursesMode] = useState('desk')
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
    setCoursesMode('desk')
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
      row: openCourse.row,
      focusObjectiveId: openCourse.objectiveId,
      focusBlockId: openCourse.blockId || null,
      focusView: openCourse.view || null,
      implemented,
      profile: currentScope().profile,
      onBack: () => setOpenCourse(null),
      onChanged: () => reloadHealth()
    })
  } else if (coursesMode === 'list') {
    body = jsx(CoursesView, {
      createOpen: creating,
      implemented,
      onStartCreate: () => setCreating(true),
      onOpen: (row) => setOpenCourse({ row, objectiveId: null }),
      onShowDesk: () => setCoursesMode('desk')
    })
  } else {
    body = jsx(FieldDesk, {
      implemented,
      profile: currentScope().profile,
      onOpen: (row, objectiveId, blockId, view) =>
        setOpenCourse({ row, objectiveId: objectiveId || null, blockId: blockId || null, view: view || null }),
      onShowAll: () => setCoursesMode('list'),
      onStartCreate: () => setCreating(true)
    })
  }

  const statusCopy = backendCopy(health.status)
  const online = useOnline()
  const showDestinationNav = health.status === 'ready' && !creating && !importing

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col px-[clamp(1.25rem,4vw,4rem)]',
    'data-cb-destination': destination,
    'data-cb-route': ROUTE_PATH,
    'data-cb-scope': cbMode,
    'data-cb-motion': cbMotion,
    style: cbScopeStyle(cbMode),
    children: [
      jsxs('header', {
        className: 'flex shrink-0 flex-col gap-2 pt-3',
        children: [
          jsxs('div', {
            className: 'flex flex-wrap items-start justify-between gap-3',
            children: [
              jsxs('div', {
                className: 'min-w-0',
                children: [
                  jsx('div', { className: 'text-sm font-semibold', children: ROUTE_TITLE }),
                  jsx('div', {
                    className: 'mt-0.5 text-xs text-(--ui-text-secondary)',
                    children:
                      destination === 'studio' && !studioSeed
                        ? studioCourse
                          ? 'One authored course: brief, plan, pages, export and reflection.'
                          : 'Parent-led lesson packs: write the brief, review it, then teach it.'
                        : destination === 'library' && !creating
                          ? 'Packs you can teach from, with the provenance the backend recorded.'
                          : openCourse
                            ? 'One objective, its evidence and the next permitted action.'
                            : coursesMode === 'list'
                              ? 'Every course on this profile, with search and the backend’s own next step.'
                              : 'One next move: the section to continue, the path and its sources.'
                  })
                ]
              }),
              jsxs('div', {
                className: 'flex shrink-0 flex-wrap items-center justify-end gap-2',
                children: [
                  online ? null : jsx(sdk.Badge, { variant: 'warn', children: 'Offline' }),
                  statusCopy ? jsx(sdk.Badge, { variant: health.status === 'unavailable' ? 'warn' : 'muted', children: statusCopy }) : null,
                  health.status === 'ready' && online && !creating && !importing && destination === 'courses' && canCreate
                    ? jsx(sdk.Button, { onClick: () => setCreating(true), size: 'sm', variant: 'default', children: 'New course' })
                    : null,
                  health.status === 'ready' && !creating && !importing && destination === 'library' && canImport
                    ? jsx(sdk.Button, { onClick: onImportPlaceholder, size: 'sm', variant: 'default', children: 'Import pack' })
                    : null,
                  health.status === 'ready' && online && !studioSeed && destination === 'studio' && !studioCourse && canAuthor
                    ? jsx(sdk.Button, { onClick: () => setStudioSeed({ initial: null, note: null }), size: 'sm', variant: 'default', children: 'New lesson brief' })
                    : null
                ]
              })
            ]
          }),
          online
            ? null
            : jsx('div', {
                className: 'text-xs text-(--ui-text-secondary)',
                children:
                  'Offline. Lessons, notes and review keep working from what this profile already saved. ' +
                  'Creating a course, writing a brief and grading open answers are paused until the connection returns.'
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
  // The pane is part of the same scoped surface as the route: same token table, same mode.
  const cbMode = useCbMode()
  const cbMotion = useCbMotion()
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
    'data-cb-scope': cbMode,
    'data-cb-motion': cbMotion,
    style: cbScopeStyle(cbMode),
    children: [
      jsx(sdk.PanelSectionLabel, { children: 'COURSEBOOK' }),
      bindNote ? jsx('div', { className: 'pb-2 text-xs text-(--ui-text-secondary)', children: bindNote }) : null,
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
      className: 'text-xs text-(--ui-text-secondary)',
      children: `Contract inventory unavailable. ${describeError(state.error)}`
    })
  }
  return jsx('div', {
    className: 'flex flex-col',
    children: state.contracts.map((entry) =>
      jsx(
        StatusRow,
        {
          label: entry.id,
          value: `v${entry.version}`,
          detail: `${entry.file} · ${String(entry.sha256).slice(7, 19)}…`
        },
        entry.id
      )
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
        className: 'text-xs text-(--ui-text-secondary)',
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

// Named seam for tests/test_desktop_lesson_views.py and tests/test_desktop_field_quest.py. The
// block views, the section page and the quest projection are pure components/functions over a
// server-owned document, so a Node test can render them without a backend, a chat or a window.
export {
  AttemptControls,
  AttemptVerdict,
  BackendUnavailable,
  CB_TOKENS,
  CB_TOKEN_NAMES,
  COURSE_SCOPES,
  EvidenceClassText,
  FieldRail,
  FieldDeskHome,
  FieldNotesStrip,
  FieldQuestView,
  LESSON_VIEWS,
  LEARNING_VIEWS,
  SELF_REPORTED_CONFIRM_COPY,
  SELF_REPORTED_EVIDENCE_COPY,
  LearnerPlanView,
  LessonDocumentView,
  MediaFrame,
  NotebookView,
  PronunciationSeat,
  PronunciationStudio,
  QuestMission,
  SectionPage,
  WorkspaceShell,
  blockSaveExcerpt,
  buildDeskModel,
  cbLayoutFor,
  cbModeFromTheme,
  cbMotionPreference,
  cbScopeStyle,
  checklistAnswer,
  checklistItems,
  deskEstimateLabel,
  lessonViewOptions,
  mainlineObjective,
  notebookSourceRef,
  pronPercent,
  pronunciationAvailabilityCopy,
  questMissions,
  planJobBrief,
  planTimingCopy,
  startLearnerPlan,
  courseCreatePayload,
  questProgressLabel,
  readNotebookRef,
  stripExcerpt,
  courseExportRequest,
  COURSE_EXPORT_BLOCKED_COPY
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
