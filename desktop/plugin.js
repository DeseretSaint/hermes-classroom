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
  { id: 'library', label: 'Library' }
]

/**
 * Set true by the pack work package when its import/export screens land in this module. The
 * import action is a two-step trust/rights review that does not exist yet, so the button is
 * absent rather than disabled-forever. Named here so the next package has one place to flip.
 */
const IMPORT_FLOW_WIRED = false
/** The create flow lives in this file, so it needs no separate flag. */

/** Set once in register(); components read the scoped context from here. */
let pluginContext = null

/** The host door, imported once. Everything below calls `host.*` exactly as documented. */
const host = sdk.host

/**
 * What the mounted backend actually speaks, read from `/runtime`.
 *
 * This is the registry, not a second copy of the contract: `contractVersion` travels on every
 * envelope and `implemented` gates any control that would call an unimplemented command. When
 * the frozen contract is amended (v2 adds library.list / lesson.* / artifact.get / jobs.list /
 * notebook.update), this module needs no edit — it re-reads the version and the method list.
 */
let backendWire = { contractVersion: 1, implemented: null, error: null }

/** Route-level intents the palette and keybind can hand to an already-mounted page. */
const intentListeners = new Set()
let pendingIntent = null

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
    response = await requireContext().rest('/rpc', {
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
    const runtime = await requireContext().rest('/runtime')
    const version = Number(runtime && runtime.wire_version)
    backendWire = {
      contractVersion: Number.isFinite(version) && version > 0 ? version : 1,
      implemented: Array.isArray(runtime && runtime.implemented_methods)
        ? new Set(runtime.implemented_methods)
        : null,
      error: null
    }
  } catch (error) {
    backendWire = { contractVersion: backendWire.contractVersion, implemented: null, error }
  }
  return backendWire
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
  if (typeof host.profileRoutes === 'function') {
    const routes = host.profileRoutes() || []
    const match = routes.find((route) => route && route.profile === profile)
    if (match && match.connectionId) connectionId = match.connectionId
  }
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
  return pluginContext.rest('/health')
}

async function fetchSchema() {
  if (!pluginContext) throw new Error('Coursebook is not registered')
  return pluginContext.rest('/schema')
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
  host.notify({ kind: 'warning', message: 'Pack import is not wired in this build.' })
}

/** Archive / unarchive is reversible and fenced by revision; deletion needs a previewed scope. */
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

function CourseRow({ row, implemented, onResume, onArchive, onDelete }) {
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
        canResume
          ? jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: () => onResume(row), children: 'Resume lesson' })
          : null,
        jsx(CourseMenu, { row, supports, onArchive, onDelete })
      ]
    })
  })
}

function CoursesView({ implemented, onStartCreate, createOpen }) {
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
  const filteredEmpty = noCourses && data.applied_filter && data.applied_filter !== 'all'

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
              jsx(sdk.EmptyState, {
                title: 'No courses match this filter',
                description: 'Your courses are still here; this filter just excludes them right now.'
              }),
              jsx(sdk.Button, {
                variant: 'secondary',
                onClick: () => {
                  setFilter('all')
                  setSearchInput('')
                },
                children: 'Clear filter'
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
        rows.map((row) =>
          jsx(
            CourseRow,
            {
              row,
              implemented,
              onResume,
              onArchive,
              onDelete
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

function PackFacts({ row, implemented, onResume, onArchive, onDelete, onBack, showBack }) {
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
            : null
        ]
      }),
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
        jsx(sdk.EmptyState, {
          title: 'Installed packs could not be read',
          description: `${error && error.code ? error.code + ': ' : ''}${describeError(error)}`
        }),
        jsx(sdk.Button, { className: 'self-start', onClick: reload, size: 'sm', variant: 'secondary', children: 'Try again' })
      ]
    })
  } else if (rows.length === 0) {
    listBody = jsx(sdk.EmptyState, {
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
                onResume,
                row: detailRow,
                showBack: true
              })
            : jsx('div', {
                className: 'hidden min-[47.5rem]:flex min-w-0 flex-1 items-start',
                children: jsx(sdk.EmptyState, {
                  className: 'w-full',
                  title: 'Choose a pack to see what the backend recorded',
                  description: 'Preview shows the pack’s provenance, enrolment state and evidence summary — nothing inferred.'
                })
              })
        ]
      }),
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

function CoursebookPage() {
  const { state: health, reload: reloadHealth } = useHealth()
  const implemented = useRuntime(health.status)
  const [destination, setDestination] = useState(rememberedDestination)
  const [creating, setCreating] = useState(false)

  const changeDestination = useCallback((next) => {
    rememberedDestination = next
    setCreating(false)
    setDestination(next)
  }, [])

  useRouteIntent(
    useCallback((intent) => {
      if (!intent) return
      if (intent.kind === 'create') {
        rememberedDestination = 'courses'
        setDestination('courses')
        setCreating(true)
      } else if (intent.kind === 'library') {
        rememberedDestination = 'library'
        setDestination('library')
        setCreating(false)
      }
    }, [])
  )

  const canCreate = Boolean(implemented && implemented.has('course.create'))
  const canImport = Boolean(IMPORT_FLOW_WIRED && implemented && implemented.has('pack.import'))

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
  } else if (destination === 'library') {
    body = jsx(LibraryView, { createOpen: creating, implemented })
  } else {
    body = jsx(CoursesView, { createOpen: creating, implemented, onStartCreate: () => setCreating(true) })
  }

  const statusCopy = backendCopy(health.status)
  const showDestinationNav = health.status === 'ready' && !creating

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
                      destination === 'library' && !creating
                        ? 'Packs you can teach from, with the provenance the backend recorded.'
                        : 'A governed learning workspace: one objective, real evidence, honest next steps.'
                  })
                ]
              }),
              jsxs('div', {
                className: 'flex shrink-0 flex-wrap items-center justify-end gap-2',
                children: [
                  statusCopy ? jsx(sdk.Badge, { variant: health.status === 'unavailable' ? 'warn' : 'muted', children: statusCopy }) : null,
                  health.status === 'ready' && !creating && destination === 'courses' && canCreate
                    ? jsx(sdk.Button, { onClick: () => setCreating(true), size: 'sm', variant: 'default', children: 'New course' })
                    : null,
                  health.status === 'ready' && !creating && destination === 'library' && canImport
                    ? jsx(sdk.Button, { onClick: onImportPlaceholder, size: 'sm', variant: 'default', children: 'Import pack' })
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
  const { state } = useSessionBinding()
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
  } else if (!state.binding) {
    body = jsx(sdk.PanelEmpty, {
      icon: 'book',
      title: 'Not a Coursebook lesson',
      description: 'This chat has no lesson binding. A bound chat shows its current objective and check here.',
      action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: openCoursebook, children: 'Open Coursebook' })
    })
  } else {
    const binding = state.binding
    body = jsxs('div', {
      className: 'flex flex-col gap-2',
      children: [
        jsx(StatusRow, { label: 'Enrollment', value: binding.enrollment_id }),
        jsx(StatusRow, { label: 'Binding', value: binding.status, detail: `profile ${binding.profile}` }),
        jsx(StatusRow, {
          label: 'Chat',
          value: `${String(binding.stored_session_id || '').slice(0, 10)}…`,
          detail: binding.matched_column === 'stored_session_id' ? 'resolved by stored id' : undefined
        }),
        jsxs('div', {
          className: 'flex items-center gap-2 pt-1',
          children: [
            jsx(sdk.Button, {
              variant: 'default',
              size: 'sm',
              onClick: resume,
              disabled: binding.status !== 'active' || !binding.stored_session_id,
              children: 'Resume lesson'
            }),
            jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: openCoursebook, children: 'Open Coursebook' })
          ]
        })
      ]
    })
  }

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col px-3 py-2',
    children: [jsx(sdk.PanelSectionLabel, { children: 'COURSEBOOK' }), body]
  })
}

/** `useValue` with a non-reactive fallback for hosts too old to export it. */
const useHostValue = typeof sdk.useValue === 'function' ? sdk.useValue : (atom) => atom.get()

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
  }, [storedId])

  return { storedId, runtimeId, state }
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
