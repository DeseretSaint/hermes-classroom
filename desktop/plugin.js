/**
 * Coursebook — Desktop half (skeleton).
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
 * Phase boundary: this file is the platform bootstrap — route, sidebar row, pane, palette,
 * keybind, settings page, the scoped `ctx.rest` RPC client, profile/connection scope, and the
 * explicit stored-vs-runtime session-id helpers. Feature views (library, textbook, parent studio)
 * are added by their owning work packages together with the backend commands they call; a button
 * that does nothing is not a skeleton, it is a lie.
 *
 * Session ids are never interchangeable here. `host.state.focusedSessionId` is the live runtime
 * id (diagnostics only); `host.state.focusedStoredSessionId` is the durable id a binding stores
 * and the only id `binding.get` / `host.openSession` may receive. A fresh draft legitimately has
 * no stored id — the pane says so instead of falling back to "most recent".
 */
import * as sdk from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useCallback, useEffect, useState } from 'react'

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

/** Set once in register(); components read the scoped context from here. */
let pluginContext = null

/** The host door, imported once. Everything below calls `host.*` exactly as documented. */
const host = sdk.host

/**
 * What the mounted backend actually speaks, read from `/runtime` at register time.
 *
 * This is the registry, not a second copy of the contract: `contractVersion` travels on every
 * envelope and `implemented` gates any control that would call an unimplemented command. When
 * the frozen contract is amended (v2 adds library.list / lesson.* / artifact.get / jobs.list /
 * notebook.update), this module needs no edit — it re-reads the version and the method list.
 */
let backendWire = { contractVersion: 1, implemented: null, error: null }

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
 * explicitly because `attempt.submit` requires both — nothing is generated behind the caller's
 * back.
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
  if (options.expectedRevision !== undefined) {
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
 * Which profile/connection this pane is acting for.
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
    setState({ status: 'loading', result: null, error: null })
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
      jsx('div', { className: 'shrink-0 text-xs text-(--ui-text-secondary)', children: value })
    ]
  })
}

function BackendUnavailable({ error, reload }) {
  return jsx('div', {
    className: 'flex flex-1 flex-col items-start gap-3 py-8',
    children: [
      jsx(sdk.ErrorState, {
        title: 'Coursebook needs its agent plugin',
        description:
          'The Desktop half is enabled but its Python backend is not answering for this profile. ' +
          'Enable Coursebook under Capabilities → Plugins, then restart the gateway. ' +
          'Desktop and backend are enabled separately.'
      }),
      error && error.code
        ? jsx('div', {
            className: 'text-xs text-(--ui-text-tertiary)',
            children: `${error.code}: ${describeError(error)}`
          })
        : jsx('div', { className: 'text-xs text-(--ui-text-tertiary)', children: describeError(error) }),
      jsxs('div', {
        className: 'flex items-center gap-2',
        children: [
          jsx(sdk.Button, { variant: 'default', onClick: openCapabilities, children: 'Open Capabilities' }),
          jsx(sdk.Button, { variant: 'secondary', onClick: reload, children: 'Check again' })
        ]
      })
    ]
  })
}

function ConnectedBody({ result, reload }) {
  const db = result.db || {}
  const contractLabel = `cb.rpc v${result.contract_version}`
  return jsxs('div', {
    className: 'flex max-w-2xl flex-col gap-4 py-4',
    children: [
      jsxs('div', {
        className: 'flex flex-col gap-1',
        children: [
          jsx('div', { className: 'text-sm font-medium', children: 'Build a course around what you want to do.' }),
          jsx('div', {
            className: 'text-xs text-(--ui-text-tertiary)',
            children:
              'Coursebook is connected to its backend. Course creation, packs and lessons arrive with the ' +
              'learning kernel; this page reports only what is working now.'
          })
        ]
      }),
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(StatusRow, { label: 'Backend', value: contractLabel, detail: `plugin ${result.plugin_version}` }),
          jsx(StatusRow, {
            label: 'Database',
            value: db.ready ? `schema v${db.schema_version}` : 'not migrated',
            detail: db.ready
              ? 'Profile-scoped SQLite is ready.'
              : 'The backend contract is loaded but no course data can be stored yet.'
          }),
          jsx(StatusRow, {
            label: 'Courses',
            value: 'none yet',
            detail: 'No courses are created in this build. Nothing here is sample data.'
          })
        ]
      }),
      jsx('div', {
        className: 'flex items-center gap-2',
        children: jsx(sdk.Button, { variant: 'secondary', onClick: reload, children: 'Check backend' })
      })
    ]
  })
}

function CoursebookPage() {
  const { state, reload } = useHealth()
  let body
  if (state.status === 'loading') {
    body = jsx('div', { className: 'py-10', children: jsx(sdk.Loader, { label: 'Checking the Coursebook backend' }) })
  } else if (state.status === 'unavailable') {
    body = jsx(BackendUnavailable, { error: state.error, reload })
  } else {
    body = jsx(ConnectedBody, { result: state.result, reload })
  }

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col',
    children: [
      jsxs('header', {
        className: 'flex shrink-0 items-start justify-between gap-3 px-4 pt-3',
        children: [
          jsxs('div', {
            className: 'min-w-0',
            children: [
              jsx('div', { className: 'text-sm font-semibold', children: ROUTE_TITLE }),
              jsx('div', {
                className: 'mt-0.5 text-xs text-(--ui-text-tertiary)',
                children: 'A governed learning workspace: one objective, real evidence, honest next steps.'
              })
            ]
          }),
          state.status === 'degraded'
            ? jsx(sdk.Badge, { children: 'database not ready' })
            : state.status === 'unavailable'
              ? jsx(sdk.Badge, { children: 'backend off' })
              : null
        ]
      }),
      jsx('div', { className: 'min-h-0 flex-1 overflow-auto px-4 pb-6', children: body })
    ]
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
    host.navigate(ROUTE_PATH)
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
              'The backend is connected and answering, but this build ships no kernel schema, so no ' +
              'session binding can exist yet. Nothing here is being guessed.',
            action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: openCoursebook, children: 'Open Coursebook' })
          })
        : jsx(sdk.PanelEmpty, {
            icon: 'warning',
            title: 'Cannot read this chat’s binding',
            description: code
              ? `${code}: ${describeError(state.error)}`
              : describeError(state.error),
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
    children: [
      jsx(sdk.PanelSectionLabel, { children: 'COURSEBOOK' }),
      body
    ]
  })
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
    })
  }
}
