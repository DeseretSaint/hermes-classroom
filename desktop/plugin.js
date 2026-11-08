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
/**
 * Learner-facing names for the contract's recipe enum (H-28).
 *
 * The enum ids are frozen by the contract and checked in `tests/test_desktop_contracts.py`; these
 * strings are the only place a person reads them. "Recipe" never reaches the screen: a learner is
 * asked how they will use the course, and `one_off` says it is a task, not a quiz-shaped mini-course.
 */
const RECIPE_COPY = {
  one_off: {
    title: 'One task I need to do now',
    description: 'A single thing to get right — a repair, a form, a procedure. You practise the task, not a quiz.'
  },
  casual: {
    title: 'A little at a time',
    description: 'Short sessions you pick up when you have ten minutes, with no schedule to keep.'
  },
  committed: {
    title: 'A steady plan',
    description: 'A sequence that builds on itself, with practice you come back to.'
  },
  companion: {
    title: 'Alongside something else',
    description: 'A subject you keep returning to while you study or work on other things.'
  },
  parent: {
    title: 'Preparing for my child',
    description: 'You are preparing material for a child. That happens in Parent Studio, not here.'
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
/**
 * H-145 — Home is the launcher (the selected classroom's Continue plate); Courses is the
 * all-courses catalog. Home is first because it is the only destination that answers "what do I do
 * now?" without a choice.
 */
const DESTINATIONS = [
  { id: 'home', label: 'Home' },
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
/**
 * What `host.profileRoutes()` answered. `unavailable` is a visible state, not an empty list: an
 * empty cache makes `currentScope().connectionId` null, which is harmless on a one-connection
 * install and a route to the wrong backend on a multi-connection one.
 */
let profileRouteState = { status: 'loading', error: null }

async function loadProfileRoutes(attempt = 0) {
  try {
    const routes = await (typeof host.profileRoutes === 'function' ? host.profileRoutes() : [])
    profileRouteCache = Array.isArray(routes) ? routes : []
    profileRouteState = { status: 'ready', error: null }
  } catch (error) {
    if (attempt < 2) {
      setTimeout(() => { loadProfileRoutes(attempt + 1) }, 150 * (attempt + 1))
      return
    }
    profileRouteCache = []
    profileRouteState = {
      status: 'unavailable',
      error: String((error && error.message) || error || 'profile routes could not be read')
    }
  }
}

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

function armPendingBind({ enrollmentId, objectiveId, objectiveTitle, lessonRunId, profile }) {
  if (!enrollmentId || !objectiveId || !lessonRunId) {
    pendingBind = null
    return null
  }
  pendingBind = {
    enrollmentId,
    objectiveId,
    objectiveTitle: objectiveTitle || null,
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
let rememberedDestination = 'home'

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
  return { profile, connectionId, routingUnavailable: profileRouteState.status === 'unavailable' }
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
    return { ok: false, reason: 'no-durable-chat', message: 'This lesson has no chat to return to yet.' }
  }
  if (binding.status !== 'active') {
    return { ok: false, reason: 'binding-not-active', message: 'This lesson is not connected to a chat right now.' }
  }
  if (typeof host.openSession !== 'function') {
    return { ok: false, reason: 'unsupported', message: 'Update Hermes Desktop to resume a bound lesson.' }
  }
  try {
    await host.openSession(binding.stored_session_id, {
      profile: binding.profile || currentScope().profile || undefined
    })
  } catch (error) {
    return {
      ok: false,
      reason: 'open-failed',
      message: 'The saved lesson chat could not be opened from this desktop. The section is still available to read.'
    }
  }
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
 * Open the new chat that an armed run belongs to. Kept behind a named helper because the arming
 * path is deliberately separate from the chat-opening seam: `beginLessonFor` records the exact
 * run, then the surface the learner clicked decides to show the chat. A host without `newChat`
 * keeps the course page and the explicit "Open the lesson chat" action.
 */
function openArmedLessonChat(profile) {
  return startLessonChat(profile)
}

/**
 * Start a lesson chat that is bound BEFORE its first turn.
 *
 * Why this exists: a fresh draft has no stored session id until its first turn, so the binding
 * that makes a chat "the lesson chat" could only land after turn one — and a turn with no binding
 * is a turn where the tutor skill cannot be proven to apply (the skill question is answered from
 * the store's own row, never from recency). Creating the session through the host first gives the
 * chat a stored id while it is still empty: this file binds it, then reveals it. Turn one is then
 * a governed lesson turn.
 *
 * Feature-detected and non-fatal on purpose: an older host that cannot create a session through
 * `host.request` keeps exactly today's path (arm a pending bind, open a draft, bind on the first
 * stored id). The coaching window is one turn, not a broken lesson.
 */
async function startBoundLessonChat({ enrollmentId, objectiveId, lessonRunId, title, profile }) {
  const target = profile || currentScope().profile || null
  if (typeof host.request !== 'function' || typeof host.openSession !== 'function') {
    return { ok: false, reason: 'unsupported' }
  }
  let created
  try {
    created = await host.request('session.create', {
      source: 'desktop',
      cols: 96,
      title: title || 'Coursebook lesson',
      ...(target ? { profile: target } : {}),
      idempotency_key: newOperationId('lesson-chat')
    })
  } catch (error) {
    return { ok: false, reason: 'create-failed', message: describeError(error) }
  }
  const storedSessionId = created && created.stored_session_id
  if (!storedSessionId) return { ok: false, reason: 'no-stored-id' }
  const bound = await rest('/sessions/bind', {
    method: 'POST',
    body: {
      stored_session_id: storedSessionId,
      enrollment_id: enrollmentId,
      objective_id: objectiveId,
      lesson_run_id: lessonRunId,
      profile: target || undefined
    }
  })
  if (!bound || bound.ok === false) {
    // The chat exists but is not this lesson's chat. Say so instead of opening a look-alike.
    return {
      ok: false,
      reason: 'bind-refused',
      message: `${(bound && bound.code) || 'BIND_REFUSED'}: ${(bound && bound.message) || 'this chat could not be bound.'}`
    }
  }
  try {
    await host.openSession(storedSessionId, { profile: target || undefined })
  } catch (error) {
    return { ok: false, reason: 'open-failed', message: describeError(error) }
  }
  revealCoursebookPane()
  return { ok: true, storedSessionId }
}

/**
 * Start or resume one governed lesson run and put the learner in front of it.
 *
 * Shared by the course detail and the Field Desk so both next-step buttons take exactly the same
 * path: `lesson.begin` under an idempotency key, the bound chat when the backend says a resume is
 * available, otherwise an armed pending bind and the section left on screen. It returns a message
 * rather than notifying, so each surface can place it where it belongs. It never calls
 * `host.newChat` on the learner's behalf: that seam swaps the route to `#/` and would leave the
 * learner on a blank draft (H-64).
 */
async function beginLessonFor({ row, objectiveId, objectiveTitle, mode, profile }) {
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
  if (mode === 'resume') {
    if (outcome.resume && outcome.resume.available && outcome.binding) {
      const opened = await resumeBoundSession(outcome.binding)
      return { ok: opened.ok, message: opened.ok ? 'Resumed the bound lesson chat.' : opened.message }
    }
    // A lesson run can outlive its chat binding. Opening a fresh chat here looked like a resume
    // but landed the learner on an empty draft; keep the course page instead and say what is true.
    return {
      ok: false,
      reason: 'no-binding',
      objectiveId: target,
      message:
        'There is no saved lesson chat for this section yet. Read the section below, then start a new lesson when you are ready.'
    }
  }
  // A fresh run is opened as a new chat with an armed binder, not through
  // `session.create`/`host.openSession`: that seam can focus a just-created session before the
  // host has a stored id for it, which leaves the learner on a blank "No durable chat yet"
  // screen. The pending binder names this exact run and is consumed by the chat's first stored id.
  armPendingBind({
    enrollmentId: row.enrollment_id,
    objectiveId: target,
    objectiveTitle: objectiveTitle || (row.next_step && row.next_step.label) || null,
    lessonRunId: outcome.lesson_run_id,
    profile: profile || currentScope().profile
  })
  return {
    ok: true,
    armed: true,
    started: false,
    lessonRunId: outcome.lesson_run_id,
    objectiveId: target,
    message: `The lesson is ready. Your section is open below. The chat becomes this lesson’s chat when you send your first message.`
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
    detail: 'This lesson is no longer connected to its chat, so Submit is off. Open a new lesson run to connect a new chat.'
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

/** Shared page chrome: the route's one `main` landmark, named for the surface it holds. */
function PageBody({ children, label }) {
  return jsx('main', {
    id: 'cb-main-content',
    'data-cb-main': '',
    tabIndex: -1,
    'aria-label': label || 'Coursebook content',
    className: 'min-h-0 flex-1 overflow-auto pb-6',
    children
  })
}

/**
 * The skip path. It is the first focus stop on the route and is clipped until it is focused, so a
 * keyboard or screen-reader user can jump the route header and the destination nav. It lands on the
 * reading column when the surface has one (a section or textbook page), and on the `main` region
 * otherwise — never on the header.
 */
function SkipToContent({ label }) {
  const [revealed, setRevealed] = useState(false)
  const hidden = {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '1px',
    height: '1px',
    padding: 0,
    margin: '-1px',
    overflow: 'hidden',
    clip: 'rect(0 0 0 0)',
    whiteSpace: 'nowrap',
    border: '1px solid transparent',
    fontFamily: CB_SANS,
    fontSize: CB_TYPE.meta,
    lineHeight: 1.4
  }
  const shown = {
    ...hidden,
    width: 'auto',
    height: 'auto',
    margin: 0,
    padding: '0.35rem 0.7rem',
    overflow: 'visible',
    clip: 'auto',
    zIndex: 40,
    color: 'var(--cb-on-lamp)',
    background: 'var(--cb-lamp)',
    border: '1px solid var(--cb-ink)',
    borderRadius: '2px',
    textDecoration: 'none'
  }
  return jsx('a', {
    href: '#cb-main-content',
    'data-cb-skip': '',
    onFocus: () => setRevealed(true),
    onBlur: () => setRevealed(false),
    onClick: (event) => {
      const root = document.querySelector('[data-cb-route]')
      const reading = root ? root.querySelector('[data-cb-reading-column]') : null
      const main = document.getElementById('cb-main-content')
      const target = reading || main
      if (!target) return
      event.preventDefault()
      target.setAttribute('tabindex', '-1')
      if (typeof target.focus === 'function') target.focus({ preventScroll: true })
      if (typeof target.scrollIntoView === 'function') target.scrollIntoView({ block: 'start' })
    },
    style: revealed ? shown : hidden,
    children: label || 'Skip to course content'
  })
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
          'Coursebook is turned on in Desktop, but its backend is not answering for this profile. ' +
          'Enable Coursebook under Capabilities → Plugins, then restart the gateway. ' +
          'Desktop and backend halves are enabled separately.',
        children: jsxs('div', {
          className: 'flex flex-wrap items-center justify-center gap-2',
          children: [
            jsx(CbAction, { variant: 'primary', onClick: openCapabilities, children: 'Open Capabilities' }),
            jsx(CbAction, { variant: 'secondary', onClick: reload, children: 'Check again' })
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
            jsx(CbAction, { variant: 'primary', onClick: reload, children: 'Check again' }),
            jsx(CbAction, { variant: 'secondary', onClick: openCapabilities, children: 'Open Capabilities' })
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

/**
 * The one plain sentence under the welcome (H-28).
 *
 * Replaces the three "governed learning workspace / real evidence / nothing advances on its own"
 * orientation lines. It says the same thing in a learner's words, and it stays true: progress is
 * profile-local and an objective only advances on a check the learner can see.
 */
const FIRST_RUN_COPY = {
  title: 'What do you want to be able to do?',
  promise:
    'Name one goal, review the plan, then learn. Nothing is created until you approve the plan.',
  progress:
    'Your progress stays on this profile. Nothing is marked complete without a check you can see.',
  primary: 'Start with a goal',
  primaryNext: 'Next you choose how big the course is.',
  path: [
    { n: 1, title: 'Name a goal', line: 'Say what you want to be able to do.' },
    { n: 2, title: 'Review the plan', line: 'Check the sections and their sources. No lesson is written yet.' },
    { n: 3, title: 'Learn and adapt', line: 'Lessons follow the plan you approved.' }
  ],
  secondary: 'Use a course I already have',
  secondaryHint:
    'You will see who made it, where it came from and what is checked before anything is added.',
  syllabus: 'Use my college syllabus',
  syllabusHint:
    'Your syllabus sets the scope. Coursebook writes its own lessons alongside it and stores your file on this profile.'
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

/**
 * The honest welcome (H-28, UX-01). One promise, one primary action, one secondary path, one plain
 * progress sentence. No "governed learning workspace", no marketing hero, no fake sample progress.
 *
 * "Use my college syllabus" is gated on the same capability it is served by (H-27 ships the flow as
 * `syllabus.intake.create`), just as the import action is gated on `pack.import`: the button appears
 * only when the backend can honour it, and never as a disabled-forever or faked control.
 */
function FirstRun({ implemented, onCreate, onSyllabus }) {
  const canCreate = Boolean(implemented && implemented.has('course.create')) && typeof onCreate === 'function'
  const canImport = Boolean(IMPORT_FLOW_WIRED && implemented && implemented.has('pack.import'))
  const canSyllabus = typeof onSyllabus === 'function' && Boolean(implemented && implemented.has('syllabus.intake.create'))
  const width = useCbViewportWidth()
  const compact = width > 0 && width < 520
  const hintStyle = { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' }
  // One start plate: what Coursebook is for, one filled action, then the path in three short rows.
  // The numbers carry the sequence, so step one is never marked current until a course exists.
  return jsxs('div', {
    'data-cb-first-run': '',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '1rem',
      width: '100%',
      maxWidth: '42rem',
      margin: '0 auto',
      padding: compact ? '1rem 0.9rem 1.1rem' : '1.4rem 1.5rem 1.5rem',
      background: 'var(--cb-lamp-soft)',
      border: '1px solid var(--cb-rule)',
      borderTop: '1px solid var(--cb-lamp)',
      boxSizing: 'border-box'
    },
    children: [
      jsxs('div', {
        style: { display: 'flex', alignItems: 'flex-start', gap: '0.85rem', flexWrap: 'wrap' },
        children: [
          jsx('h2', {
            'data-cb-first-run-title': '',
            style: {
              margin: 0,
              flex: '1 1 12rem',
              minWidth: 0,
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.heading,
              fontWeight: 600,
              lineHeight: 1.08,
              letterSpacing: '-0.015em',
              color: 'var(--cb-ink)',
              maxWidth: '22ch',
              overflowWrap: 'break-word'
            },
            children: FIRST_RUN_COPY.title
          })
        ]
      }),
      jsx('p', {
        style: {
          margin: 0,
          maxWidth: '54ch',
          fontFamily: CB_SANS,
          fontSize: CB_TYPE.body,
          lineHeight: 1.55,
          color: 'var(--cb-ink)'
        },
        children: FIRST_RUN_COPY.promise
      }),
      canCreate
        ? jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', alignItems: 'flex-start' },
            children: [
              jsx(CbAction, {
                'data-cb-first-run-primary': '',
                variant: 'primary',
                onClick: onCreate,
                children: FIRST_RUN_COPY.primary
              }),
              jsx('p', { style: hintStyle, children: FIRST_RUN_COPY.primaryNext })
            ]
          })
        : null,
      jsx('ol', {
        'data-cb-first-run-path': '',
        'aria-label': 'How a course is made',
        style: { listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column' },
        children: FIRST_RUN_COPY.path.map((step) =>
          jsxs(
            'li',
            {
              'data-cb-first-run-step': String(step.n),
              style: { display: 'flex', alignItems: 'baseline', gap: '0.7rem', padding: '0.5rem 0', borderTop: '1px solid var(--cb-rule)' },
              children: [
                jsx('span', {
                  style: {
                    flex: '0 0 1.3rem',
                    fontFamily: CB_SERIF,
                    fontSize: CB_TYPE.body,
                    fontWeight: 600,
                    fontVariantNumeric: 'tabular-nums',
                    color: 'var(--cb-ink-soft)'
                  },
                  children: String(step.n)
                }),
                jsxs('span', {
                  style: { display: 'flex', flexDirection: 'column', gap: '0.1rem', minWidth: 0 },
                  children: [
                    jsx('span', {
                      style: { fontFamily: CB_SANS, fontSize: CB_TYPE.body, fontWeight: 600, color: 'var(--cb-ink)' },
                      children: step.title
                    }),
                    jsx('span', {
                      style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
                      children: step.line
                    })
                  ]
                })
              ]
            },
            step.n
          )
        )
      }),
      canImport || canSyllabus
        ? jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', borderTop: '1px solid var(--cb-rule)' },
            children: [
              canImport
                ? jsxs('div', {
                    style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', alignItems: 'flex-start', padding: '0.65rem 0' },
                    children: [
                      jsx(CbAction, {
                        variant: 'secondary',
                        onClick: onImportPlaceholder,
                        children: FIRST_RUN_COPY.secondary
                      }),
                      jsx('p', { style: hintStyle, children: FIRST_RUN_COPY.secondaryHint })
                    ]
                  })
                : null,
              canSyllabus
                ? jsxs('div', {
                    style: {
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.2rem',
                      alignItems: 'flex-start',
                      padding: '0.65rem 0',
                      borderTop: '1px solid var(--cb-rule)'
                    },
                    children: [
                      jsx(CbAction, {
                        variant: 'secondary',
                        onClick: onSyllabus,
                        children: FIRST_RUN_COPY.syllabus
                      }),
                      jsx('p', { style: hintStyle, children: FIRST_RUN_COPY.syllabusHint })
                    ]
                  })
                : null
            ]
          })
        : null,
      jsx('p', {
        style: {
          margin: 0,
          paddingTop: '0.6rem',
          borderTop: '1px solid var(--cb-rule)',
          maxWidth: '56ch',
          fontFamily: CB_SANS,
          fontSize: CB_TYPE.meta,
          lineHeight: 1.5,
          color: 'var(--cb-ink-soft)'
        },
        children: FIRST_RUN_COPY.progress
      }),
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
          jsx('h2', { className: 'text-sm font-semibold', children: manifest.title }),
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
      jsx(CbLabel, { children: 'Author and rights' }),
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
      jsx(CbLabel, { children: 'Integrity and size' }),
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
      jsx(CbLabel, { children: 'Trust, kept separate' }),
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
              jsx(CbLabel, { children: 'Content notes' }),
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
              jsx(CbLabel, { children: 'Safety notes' }),
              ...manifest.safety_notes.map((note, index) =>
                jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: note }, `safety-${index}`)
              )
            ]
          })
        : null,
      jsx('p', {
        className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
        'data-cb-breadth': 'pack-plan',
        children: PLAN_BREADTH_DISCLOSURE
      }),
      jsx(CbLabel, { children: `OUTCOMES (${objectives.length})` }),
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
              jsx(CbLabel, { children: `SOURCES AND SUPPORT (${sources.length})` }),
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
      jsx(CbLabel, { children: `FILES (${files.length})` }),
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
            jsx('div', { className: 'text-sm font-medium', children: 'Choose a course pack' }),
            jsx('div', {
              className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
              children:
                'A pack is a zip file someone else made: lessons, sources, and a manifest that lists every file with its hash. ' +
                'Choose the folder that holds the .zip the pack arrived in. Coursebook copies it into a staging area and checks ' +
                'every file before showing it to you — nothing is added until you review it and press Import.'
            })
          ]
        }),
        jsxs('div', {
          className: 'flex flex-wrap items-center gap-2',
          children: [
            jsx(CbAction, {
              disabled: busy || !files,
              onClick: chooseFolder,
              variant: 'primary',
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
        jsx(CbAction, {
          onClick: () => setStep('mode'),
          variant: 'primary',
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
        jsx(CbAction, {
          disabled: busy,
          onClick: () => runImport('fresh'),
          variant: 'primary',
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
        jsx(CbAction, { onClick: onImported, size: 'sm', variant: 'primary', children: 'Back to the library' })
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
      jsx(CbAction, {
        disabled: busy || !confirmed,
        onClick: run,
        variant: 'primary',
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
              jsx(CbLabel, { children: 'Exported' }),
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
                          'The link points at the session the backend named. The handle ' +
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
        ? jsx(CbAction, { disabled: busy, onClick: remove, size: 'sm', variant: 'primary', children: 'Freeze this pack' })
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
          children: jsx(sdk.Codicon, { name: 'kebab-vertical', size: CB_ICON_UI })
        })
      }),
      jsx(sdk.DropdownMenuContent, { align: 'end', children: items })
    ]
  })
}

function CourseRow({ row, group, implemented, onResume, onArchive, onDelete, onOpen }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const next = row.next_step || {}
  const canResume = next.kind === 'resume_lesson' && supports('binding.get')
  const warning = WARNING_COPY[row.warning]
  // H-99: the row is a course object, not a text list item: cover, goal, four-segment path.
  // `group` carries the other records for the same course so nothing is hidden by collapsing.
  return jsx(CourseCover, {
    row,
    group,
    onOpenMember: onOpen,
    detail: jsxs('span', {
      className: 'flex min-w-0 flex-wrap items-center gap-2',
      children: [
        jsx(sdk.Badge, { variant: 'muted', size: 'xs', children: RECIPE_COPY[row.recipe] ? RECIPE_COPY[row.recipe].title : row.recipe }),
        warning ? jsx(WarningBadge, { warning: row.warning }) : null,
        jsx('span', {
          className: 'min-w-0 break-words',
          style: { fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
          children: next.label ? next.label : 'No next step recorded'
        }),
        warning
          ? jsx('span', { className: 'w-full max-w-prose text-xs text-(--ui-text-secondary)', children: warning.detail })
          : null
      ]
    }),
    action: jsxs('div', {
      className: 'flex flex-wrap items-center gap-1',
      children: [
        canResume
          ? jsx(CbAction, { variant: 'secondary', onClick: () => onResume(row), children: 'Resume lesson' })
          : null,
        onOpen
          ? jsx(CbAction, {
              variant: 'tertiary',
              onClick: () => onOpen(row),
              children: 'Open'
            })
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
  start_lesson: 'Start a fresh run',
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

/**
 * The estimate state, normalized for rendering. `error` means the read itself failed: the desk
 * has no answer, so it must not say the author recorded none. `none` means the backend answered
 * successfully and the answer carries no estimate. The two are never collapsed.
 */
function deskEstimateState(estimate) {
  const status = estimate && estimate.status ? estimate.status : 'none'
  if (status === 'loading' || status === 'idle') return 'loading'
  if (status === 'error') return 'error'
  if (status === 'ready' && Number(estimate.minutes) > 0) return 'ready'
  return 'none'
}

/** "Estimated minutes" is either recorded, absent from a real answer, or unreadable. Never derived. */
function deskEstimateLabel(estimate) {
  const state = deskEstimateState(estimate)
  if (state === 'loading') return 'Reading the estimate'
  if (state === 'error') return 'Session length could not be read'
  if (state === 'ready') return `≈ ${Number(estimate.minutes)} min`
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
      estimateState: deskEstimateState(estimate),
      estimateError: estimate && estimate.error ? estimate.error : null,
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
    estimateState: deskEstimateState(estimate),
    estimateError: estimate && estimate.error ? estimate.error : null,
    // `last_opened_at` is this section's newest lesson run; `updated_at` is the enrollment's own
    // write. The section wins when it exists, and the label says which clock was read.
    lastTouched: (current && current.last_opened_at) || row.updated_at || null,
    touchedSource: current && current.last_opened_at ? 'section' : 'course'
  }
}

function DeskLabel({ children, as }) {
  const tag = as || 'div'
  return jsx(tag, {
    style: {
      fontFamily: CB_SANS,
      fontSize: CB_TYPE.caption,
      fontWeight: 600,
      letterSpacing: '0.01em',
      color: 'var(--cb-ink-soft)',
      margin: 0
    },
    children
  })
}

/** Deterministic initial stamp: kept as plain text for hosts that render no SVG. */
function courseStampText(title) {
  return cbCourseMonogram(title)
}

/** The course cover: deterministic monogram as type, with the title adjacent. */
function CourseStamp({ title, large, courseId, identity }) {
  return jsx('div', {
    'data-cb-course-stamp': '',
    title: title || 'Course',
    'aria-hidden': 'true',
    style: { flex: '0 0 auto', display: 'flex', alignItems: 'center' },
    children: jsx('span', {
      style: {
        fontFamily: CB_SERIF,
        fontSize: large ? CB_TYPE.heading : CB_TYPE.meta,
        fontWeight: 600,
        letterSpacing: '0.04em',
        color: 'var(--cb-ink-soft)'
      },
      children: courseStampText(title || 'Course')
    })
  })
}

/* ── The shelf object: cover, goal and a four-segment path (H-99) ────────────────────────── */

const CB_PATH_TONE = {
  done: 'var(--cb-field)',
  due: 'var(--cb-ochre)',
  current: 'var(--cb-accent)',
  quiet: 'var(--cb-rule)',
  empty: 'var(--cb-rule)'
}

/** The four segments under a cover. Colour never carries the state alone: the caption does. */
function CoursePath({ row }) {
  const segments = cbCoursePathSegments(row)
  return jsxs('div', {
    'data-cb-course-path': String(segments.length),
    style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', marginTop: '0.1rem' },
    children: [
      jsx('div', {
        'aria-hidden': 'true',
        style: { display: 'flex', gap: '0.2rem', height: '0.3rem', alignItems: 'stretch' },
        children: segments.map((segment) =>
          jsx(
            'span',
            {
              style: {
                flex: '1 1 0',
                minWidth: 0,
                background: CB_PATH_TONE[segment.state] || CB_PATH_TONE.quiet,
                opacity: segment.state === 'quiet' || segment.state === 'empty' ? 0.45 : 1,
                outline: segment.state === 'current' ? '1px solid var(--cb-accent)' : 'none'
              }
            },
            segment.index
          )
        )
      }),
      jsx('div', {
        'data-cb-course-path-caption': '',
        style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.4, color: 'var(--cb-ink-soft)' },
        children: cbCoursePathCaption(row)
      })
    ]
  })
}

/**
 * The disclosure under a grouped cover. It is the only place the other records for a shared
 * course are named, so grouping never hides a plan or an enrollment: each line is openable.
 */
function ShelfDisclosure({ group, onOpen, label }) {
  if (!group || !group.label) return null
  return jsxs('details', {
    'data-cb-shelf-versions': group.key,
    style: { marginTop: '0.1rem' },
    children: [
      jsx('summary', {
        className: 'cursor-pointer',
        'aria-label': `${label || 'Records'} for ${group.primary.title}`,
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: '0.3rem',
          minHeight: '1.75rem',
          fontFamily: CB_SANS,
          fontSize: CB_TYPE.caption,
          fontWeight: 600,
          color: 'var(--cb-ink-soft)'
        },
        children: [
          jsx(sdk.Codicon, { name: 'chevron-right', size: CB_ICON_UI }),
          jsx('span', { children: group.label })
        ]
      }),
      jsx('ul', {
        style: {
          margin: '0.2rem 0 0',
          padding: 0,
          listStyle: 'none',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.25rem'
        },
        children: group.members.map((member) =>
          jsxs(
            'li',
            {
              style: {
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '0.25rem 0.5rem',
                fontFamily: CB_SANS,
                fontSize: CB_TYPE.caption,
                lineHeight: 1.45,
                color: 'var(--cb-ink-soft)'
              }
            },
            [
              jsxs('span', { style: { minWidth: 0, overflowWrap: 'anywhere' }, children: [
                jsx('span', { children: member.title || 'Untitled' }),
                jsx('span', { children: ` · ${whenLabel(member.updated_at)}` }),
                jsx('span', { children: ` · ${cbShelfFingerprint(member)}` })
              ] }),
              onOpen
                ? jsx(CbAction, {
                    variant: 'tertiary',
                    'aria-label': `Open ${member.title || 'record'} from ${whenLabel(member.updated_at)}`,
                    onClick: () => onOpen(member),
                    children: 'Open'
                  })
                : null
            ],
            member.enrollment_id
          )
        )
      })
    ]
  })
}

/**
 * One course on a shelf: a 16:9 cover field on `paper-raised` carrying the seal and the
 * two-letter monogram, then the title, the goal line and the four-segment path. The cover is
 * deterministic (`cbSealStation(course_id)` and the monogram from the title), so reloading the
 * route paints the same object, and `data-cb-course-cover` carries the content fingerprint.
 */
function CourseCover({ row, identity, detail, action, group, onOpenMember, testId }) {
  return jsxs('article', {
    'data-cb-course-cover': cbShelfFingerprint(row),
    'data-cb-course-id': row.course_id || '',
    'data-cb-all-courses-row': testId || undefined,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.35rem',
      minWidth: 0,
      paddingTop: '0.55rem',
      borderTop: '1px solid var(--cb-rule)'
    },
    children: [
      jsxs('div', {
        'data-cb-cover-field': '',
        style: {
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: '0.5rem',
          aspectRatio: '16 / 9',
          minHeight: '3rem',
          maxHeight: '7.5rem',
          padding: '0.5rem 0.6rem',
          boxSizing: 'border-box',
          background: 'var(--cb-paper-raised)',
          overflow: 'hidden'
        },
        children: [
          jsx('div', {
            'aria-hidden': 'true',
            style: {
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.lead,
              fontWeight: 600,
              letterSpacing: '0.02em',
              lineHeight: 1,
              color: 'var(--cb-ink-soft)'
            },
            children: cbCourseMonogram(row.title)
          })
        ]
      }),
      jsx('h3', {
        style: {
          margin: 0,
          fontFamily: CB_SERIF,
          fontSize: CB_TYPE.lead,
          fontWeight: 600,
          lineHeight: 1.3,
          color: 'var(--cb-ink)',
          overflowWrap: 'anywhere'
        },
        children: row.title || 'Untitled course'
      }),
      jsx('p', {
        'data-cb-course-goal': '',
        style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
        children: cbCourseGoalLine(row)
      }),
      jsx(CoursePath, { row }),
      detail ? jsx('div', { style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.35rem 0.6rem' }, children: detail }) : null,
      group && group.label ? jsx(ShelfDisclosure, { group, onOpen: onOpenMember }) : null,
      action ? jsx('div', { style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' }, children: action }) : null
    ]
  })
}

/**
 * One pack on the Library shelf: a compact row, not a course cover.
 *
 * A pack is not a course. Reusing `CourseCover` here put a 16:9 decorative field, a 40 px
 * Atlas Lamp seal and a title-derived monogram above every pack. Two test packs whose titles
 * began with the same two words therefore showed the same "HL" mark and the same empty cover,
 * which read as a product logo and made the rows impossible to tell apart. The pack's own title,
 * source and state are the identity; no seal or monogram is invented for it.
 *
 * An empty pack keeps the row honest: it names the missing sections and still offers Preview
 * (the manifest is inspectable) without a four-segment path that would imply content.
 */
function PackShelfRow({ row, group, onOpenMember, onPreview, selected }) {
  const summary = (row && row.evidence_summary) || {}
  const total = Math.max(0, Number(summary.total_objectives || 0))
  const empty = total === 0
  return jsxs('article', {
    'data-cb-pack-row': cbShelfFingerprint(row),
    'data-cb-pack-empty': empty ? 'true' : 'false',
    'data-cb-pack-selected': selected ? 'true' : 'false',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.35rem',
      minWidth: 0,
      paddingTop: '0.55rem',
      borderTop: '1px solid var(--cb-rule)'
    },
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-start justify-between gap-2',
        children: [
          jsxs('div', {
            style: { display: 'flex', minWidth: 0, flexDirection: 'column', gap: '0.2rem' },
            children: [
              jsx('h3', {
                style: {
                  margin: 0,
                  fontFamily: CB_SERIF,
                  fontSize: CB_TYPE.lead,
                  fontWeight: 600,
                  lineHeight: 1.3,
                  color: 'var(--cb-ink)',
                  overflowWrap: 'anywhere'
                },
                children: row.title || 'Untitled pack'
              }),
              jsxs('div', {
                className: 'flex flex-wrap items-center gap-2',
                style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
                children: [
                  jsx(sdk.Badge, {
                    variant: 'muted',
                    size: 'xs',
                    children: sourceLabel(row.provenance && row.provenance.source)
                  }),
                  jsx('span', {
                    children: empty ? 'No sections yet' : `${total} objective${total === 1 ? '' : 's'}`
                  })
                ]
              })
            ]
          }),
          onPreview
            ? jsx(CbAction, {
                'aria-label': `Preview ${row.title || 'pack'}`,
                onClick: () => onPreview(row),
                variant: 'tertiary',
                children: 'Preview'
              })
            : null
        ]
      }),
      empty
        ? jsx('p', {
            'data-cb-pack-empty-note': '',
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
            children: 'This pack has no sections yet. Preview it to see the manifest; there is nothing to open.'
          })
        : jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', gap: '0.2rem' },
            children: [
              jsx('p', {
                'data-cb-pack-goal': '',
                style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                children: cbCourseGoalLine(row)
              }),
              jsx(CoursePath, { row })
            ]
          }),
      group && group.label ? jsx(ShelfDisclosure, { group, onOpen: onOpenMember }) : null
    ]
  })
}

/** A real-state progress strip: one segment per objective, painted from its own state. */
function DeskProgress({ objectives }) {
  const list = Array.isArray(objectives) ? objectives.slice(0, 12) : []
  if (list.length === 0) return null
  return jsx('div', {
    'data-cb-desk-progress': '',
    'aria-hidden': 'true',
    style: { display: 'flex', gap: '0.18rem', height: '0.3rem', alignItems: 'stretch' },
    children: list.map((objective) => {
      const tone = DESK_STATE_TONE[objective.state] || 'quiet'
      const started = objective.state !== 'not_started'
      return jsx(
        'span',
        {
          style: {
            flex: '1 1 0',
            minWidth: 0,
            background: deskToneColor(tone),
            opacity: started ? 1 : 0.32
          }
        },
        objective.objective_id
      )
    })
  })
}

/**
 * The desk's facts, in the same voice as course detail's hero line: one line, the value then its
 * caption, separated by a rule. It replaces the three equal stat cards (H-94 V2-5): there is no
 * percentage, no streak and no invented goal, only counts the backend actually recorded.
 */
function DeskFacts({ desk }) {
  const current = desk.current
  const facts = [
    current ? { value: DESK_STATE_WORD[current.state] || 'Not started', label: 'This section' } : null,
    { value: `${desk.settled} of ${desk.total}`, label: 'With evidence' },
    desk.dueCount > 0 ? { value: String(desk.dueCount), label: 'Due now' } : null
  ].filter(Boolean)
  return jsx('div', {
    'data-cb-desk-facts': String(facts.length),
    style: { borderTop: '1px solid var(--cb-rule)', paddingTop: '0.55rem' },
    children: jsx(HeroFacts, { facts })
  })
}

/** One raised frame, not a card in a card: the Continue card is the only surface on the desk. */
function ContinueCard({ desk, busy, onPrimary, onOpenSection, onRetryEstimate }) {
  const current = desk.current
  const title = current ? current.title : desk.nextLabel
  const courseTitle = desk.row && desk.row.title ? desk.row.title : null
  // At a genuinely narrow route the stamp would steal the last usable line length from the title.
  // Keep it on the wide desk, where it reads as a course cover; drop it when the text must lead.
  const viewportWidth = useCbViewportWidth()
  const compact = viewportWidth > 0 && viewportWidth < 620
  return jsxs('section', {
    'data-cb-continue': '',
    'data-cb-continue-compact': compact ? 'true' : 'false',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.65rem',
      padding: compact ? '0.9rem 0.95rem' : '1.1rem 1.2rem 1.15rem',
      background: 'var(--cb-lamp-soft)',
      border: 'none',
      borderTop: '1px solid var(--cb-lamp)',
      maxWidth: '100%',
      boxSizing: 'border-box'
    },
    children: [
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.75rem 1rem' },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', minWidth: 0, flex: '1 1 16rem' },
            children: [
              jsx(DeskLabel, { children: desk.primaryKind === 'resolve_review_due' ? 'Review due' : desk.primaryKind === 'start_lesson' ? 'Start here' : 'Continue' }),
              courseTitle
                ? jsx('div', {
                    'data-cb-desk-course': '',
                    style: {
                      fontFamily: CB_SANS,
                      fontSize: CB_TYPE.caption,
                      fontWeight: 600,
                      letterSpacing: '0.02em',
                      lineHeight: 1.4,
                      color: 'var(--cb-ink-soft)',
                      overflowWrap: 'break-word'
                    },
                    children: courseTitle
                  })
                : null,
              jsx('h2', {
                'data-cb-continue-section': '',
                style: {
                  margin: 0,
                  fontFamily: CB_SERIF,
                  fontSize: compact ? CB_TYPE.heading : CB_TYPE.heading,
                  fontWeight: 600,
                  lineHeight: 1.12,
                  letterSpacing: '-0.015em',
                  color: 'var(--cb-ink)',
                  maxWidth: '20ch',
                  overflowWrap: 'break-word'
                },
                children: title
              }),
              jsxs('div', {
                style: {
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'baseline',
                  gap: '0.2rem 0.85rem',
                  fontSize: CB_TYPE.caption,
                  color: 'var(--cb-ink-soft)'
                },
                children: [
                  desk.sectionLabel
                    ? jsx('span', { 'data-cb-continue-position': '', children: desk.sectionLabel })
                    : null,
                  jsx('span', {
                    'data-cb-continue-minutes': '',
                    'data-cb-continue-minutes-state': desk.estimateState || 'none',
                    title:
                      desk.estimateState === 'error' && desk.estimateError && desk.estimateError.code
                        ? `${desk.estimateError.code}: ${desk.estimateError.message || ''}`.trim()
                        : undefined,
                    style: desk.estimateState === 'error' ? { color: 'var(--cb-ochre)' } : undefined,
                    children: desk.estimateLabel
                  }),
                  desk.estimateState === 'error'
                    ? jsx(CbAction, {
                        variant: 'tertiary',
                        onClick: onRetryEstimate,
                        'aria-label': 'Retry reading the session length',
                        children: 'Retry'
                      })
                    : null,
                  jsx('span', {
                    'data-cb-continue-touched': desk.touchedSource || 'none',
                    children: desk.lastTouched ? `Last touched ${whenLabel(desk.lastTouched)}` : 'Nothing touched yet'
                  })
                ]
              }),
              jsx(DeskProgress, { objectives: desk.objectives }),
              jsx(DeskFacts, { desk })
            ]
          })
        ]
      }),
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', gap: '0.4rem', paddingTop: '0.2rem' },
        children: [
          jsx(CbAction, {
            variant: 'primary',
            disabled: Boolean(busy) || !current,
            onClick: onPrimary,
            children: busy ? 'Opening' : desk.primaryLabel
          }),
          jsx(CbAction, {
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
    style: { display: 'flex', flexDirection: 'column', gap: '0.25rem', maxWidth: '100%' },
    children: [
      jsx(PlateHead, {
        label: 'The route',
        title: desk.row && desk.row.title ? desk.row.title : 'Your path'
      }),
      jsx(EvidenceTally, {
        objectives: desk.objectives,
        caption: objectives.length
          ? `${desk.settled} of ${plural(desk.total, 'section', 'sections')} with evidence${desk.dueCount ? ` · ${desk.dueCount} due` : ''}`
          : 'No evidence recorded yet'
      }),
      jsx('ol', {
        'aria-label': 'Course route',
        style: {
          listStyle: 'none',
          margin: 0,
          padding: '0 0 0 0.75rem',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
          borderLeft: '1px solid var(--cb-rule)'
        },
        children: objectives.map((objective) => {
          const tone = DESK_STATE_TONE[objective.state] || 'quiet'
          const isCurrent = Boolean(desk.current && desk.current.objective_id === objective.objective_id)
          return jsx(
            'li',
            {
              style: {
                borderTop: '1px solid var(--cb-rule)',
                background: isCurrent ? 'var(--cb-accent-soft)' : 'transparent'
              },
              children: jsx(CbAction, {
                variant: 'row',
                'aria-current': isCurrent ? 'step' : undefined,
                onClick: () => onOpenSection(objective.objective_id),
                children: jsxs('span', {
                  'data-cb-path-item': objective.objective_id,
                  'data-cb-path-state': objective.state,
                  'data-cb-path-current': isCurrent ? 'true' : 'false',
                  style: {
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '0.7rem',
                    width: '100%',
                    padding: '0.45rem 0.1rem',
                    textAlign: 'left',
                    color: 'var(--cb-ink)',
                    fontSize: CB_TYPE.meta,
                    borderLeft: isCurrent ? '2px solid var(--cb-accent)' : '2px solid transparent',
                    paddingLeft: '0.55rem'
                  },
                  children: [
                    jsx('span', {
                      style: {
                        flex: '0 0 1.75rem',
                        width: '1.75rem',
                        height: '1.75rem',
                        borderRadius: '50%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        border: `1px solid ${deskToneColor(tone)}`,
                        background: isCurrent ? 'var(--cb-paper-raised)' : 'transparent',
                        color: deskToneColor(tone),
                        fontVariantNumeric: 'tabular-nums',
                        fontSize: CB_TYPE.caption,
                        lineHeight: 1
                      },
                      children: String(objective.ordinal).padStart(2, '0')
                    }),
                    jsx('span', {
                      style: {
                        flex: '1 1 8rem',
                        minWidth: 0,
                        overflowWrap: 'anywhere',
                        whiteSpace: 'normal',
                        lineHeight: 1.35
                      },
                      children: objective.title
                    }),
                    jsx('span', {
                      style: {
                        flex: '0 0 auto',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.3rem',
                        fontSize: CB_TYPE.caption,
                        color: deskToneColor(tone),
                        fontWeight: 600
                      },
                      children: [
                        jsx('span', {
                          'aria-hidden': 'true',
                          style: {
                            width: '0.35rem',
                            height: '0.35rem',
                            borderRadius: '50%',
                            background: deskToneColor(tone)
                          }
                        }),
                        jsx('span', { children: DESK_STATE_WORD[objective.state] || objective.state })
                      ]
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
        ? jsx('div', { style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)', paddingTop: '0.2rem' }, children: `${remaining} more section${remaining === 1 ? '' : 's'} in the path` })
        : null,
      objectives.length === 0
        ? jsx('p', {
            style: { margin: 0, fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
            children: 'This course has no objectives yet, so there is no path to show. Approve its plan to start one.'
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
    style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', maxWidth: '100%' },
    children: [
      jsx(CbAction, {
        variant: 'tertiary',
        className: 'self-start',
        'aria-expanded': open ? 'true' : 'false',
        'aria-controls': 'cb-desk-sources',
        onClick: onToggle,
        children: open ? 'Hide sources' : 'Show sources'
      }),
      jsx('div', {
        style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
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
                      style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
                      children: [
                        jsx('span', {
                          children: `${error && error.code ? error.code + ': ' : ''}${describeError(error)} The sources were not read.`
                        }),
                        jsx(CbAction, { variant: 'tertiary', onClick: onRetry, children: 'Try again' })
                      ]
                    })
                  : items.length === 0
                    ? jsx('p', { style: { margin: 0, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' }, children: 'No sources are recorded for this section yet.' })
                    : jsx('ul', {
                        style: { listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.4rem' },
                        children: items.map((source) =>
                          jsxs(
                            'li',
                            {
                              'data-cb-desk-source': source.source_id || '',
                              style: { borderLeft: '2px solid var(--cb-rule)', paddingLeft: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.05rem' },
                              children: [
                                jsx('span', { style: { fontSize: CB_TYPE.meta, color: 'var(--cb-ink)' }, children: source.title || 'Untitled source' }),
                                jsx('span', { style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' }, children: source.support_status || 'status unrecorded' })
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
  // H-99: the shelf is one object per course. Repeated enrollments of the same course no longer
  // become three identical tiles; the group keeps its count for the full list.
  const groups = groupShelfRows(rows)
  const others = groups.slice(1)
  // The desk stays one glance: three more courses, then the honest count and the full list.
  const shown = others.slice(0, 3)
  const hidden = others.length - shown.length
  return jsxs('section', {
    'data-cb-all-courses': '',
    style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', maxWidth: '100%' },
    children: [
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.25rem 0.75rem' },
        children: [
          jsx(DeskLabel, { as: 'h2', children: `All courses · ${groups.length}` }),
          jsx(CbAction, { variant: 'tertiary', onClick: onShowAll, children: 'Search and manage courses' })
        ]
      }),
      others.length === 0
        ? jsx('p', {
            style: { margin: 0, fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
            children: 'This is the only course on this profile.'
          })
        : jsx('div', {
            style: {
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(13rem, 1fr))',
              gap: '0.55rem'
            },
            children: shown.map((group) =>
              jsx(
                CourseCover,
                {
                  row: group.primary,
                  group,
                  testId: group.primary.enrollment_id,
                  onOpenMember: onOpen,
                  action: jsx(CbAction, {
                    variant: 'tertiary',
                    onClick: () => onOpen(group.primary),
                    children: 'Open'
                  })
                },
                `all-${group.key}`
              )
            )
          }),
      hidden > 0
        ? jsx('div', {
            'data-cb-all-courses-more': String(hidden),
            style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)', paddingTop: '0.1rem' },
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

  const quietText = { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.55, color: 'var(--cb-ink-soft)' }

  return jsxs('section', {
    'data-cb-field-notes': status === 'ready' && recent.length > 0 ? 'ready' : status,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.45rem',
      maxWidth: '100%',
      border: '1px solid var(--cb-rule)',
      background: 'var(--cb-paper-raised)',
      padding: '0.8rem 0.9rem'
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
              jsx(DeskLabel, { as: 'h2', children: 'Field Notes' }),
              entries.length > 0
                ? jsx('span', {
                    style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
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
            style: { ...quietText, fontSize: CB_TYPE.caption },
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
                    style: { ...quietText, maxWidth: CB_MEASURE },
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
                            fontSize: CB_TYPE.meta,
                            lineHeight: 1.55,
                            color: 'var(--cb-ink)',
                            whiteSpace: 'pre-wrap',
                            overflowWrap: 'anywhere'
                          },
                          children: stripExcerpt(entry)
                        }),
                        entry.note && entry.excerpt
                          ? jsx('p', {
                              style: { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                              children: entry.note
                            })
                          : null,
                        jsxs('div', {
                          style: {
                            display: 'flex',
                            flexWrap: 'wrap',
                            alignItems: 'baseline',
                            gap: '0.25rem 0.8rem',
                            fontSize: CB_TYPE.caption,
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
                                    fontSize: CB_TYPE.caption,
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
  onSyllabus,
  onPrimary,
  onOpenSection,
  onRetryEstimate,
  onOpen,
  onShowAll,
  sourcesOpen,
  onToggleSources,
  sourcesStatus,
  sourcesError,
  sources,
  onRetrySources,
  implemented,
  onEmptyChange
}) {
  const width = useCbViewportWidth()
  const wide = cbLayoutFor(width) === 'wide'
  // The welcome is on screen only when the desk really has no course: a load in flight or a failed
  // read is not an empty profile. The route header reads this so its own "New course" button does
  // not duplicate the welcome's primary action (UX-01).
  const emptyFirstRun = !desk.row && libraryStatus !== 'loading' && libraryStatus !== 'error'
  useEffect(() => {
    if (onEmptyChange) onEmptyChange(emptyFirstRun)
  }, [emptyFirstRun, onEmptyChange])

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
            jsx(CbAction, { variant: 'primary', onClick: onRetry, children: 'Try again' }),
            jsx(CbAction, { variant: 'secondary', onClick: openCapabilities, children: 'Open Capabilities' })
          ]
        })
      })
    })
  }
  if (!desk.row) {
    return jsx('div', {
      'data-cb-desk': 'empty',
      children: jsx(FirstRun, { implemented, onCreate, onSyllabus })
    })
  }

  const continueCard = jsx(ContinueCard, { desk, busy, onPrimary, onOpenSection, onRetryEstimate })
  const notesCard = jsx(FieldNotesStrip, {
    notes,
    courseTitle: desk.row && desk.row.title ? desk.row.title : null,
    current: desk.current || null,
    sections: desk.objectives || [],
    stale,
    onOpenSection,
    onShowNotebook,
    onRetry
  })
  const pathCard = jsx(PathPreview, { desk, onOpenSection })
  const sourcesCard = jsx(SourcesDrawer, {
    open: sourcesOpen,
    onToggle: onToggleSources,
    sectionTitle: desk.current ? desk.current.title : null,
    status: sourcesStatus,
    error: sourcesError,
    sources,
    onRetry: onRetrySources
  })
  const coursesCard = jsx(AllCoursesList, { rows: desk.rows, onOpen, onShowAll })
  const mainColumn = jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0, maxWidth: CB_MEASURE },
    children: [continueCard, pathCard, sourcesCard]
  })
  const sideColumn = jsxs('aside', {
    'aria-label': 'Field notes and all courses',
    style: { display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0, maxWidth: CB_MEASURE },
    children: [notesCard, coursesCard]
  })

  return jsxs('div', {
    'data-cb-desk': 'ready',
    'data-cb-desk-layout': wide ? 'wide' : 'stacked',
    style: { display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0 },
    children: [
      stale
        ? jsxs('div', {
            className: 'flex flex-wrap items-center justify-between gap-2 border-b border-(--ui-stroke-tertiary) pb-2',
            children: [
              jsx('div', {
                className: 'text-xs text-(--ui-text-secondary)',
                children: 'Reconnecting. Showing the courses that were last read; the desk is paused.'
              }),
              jsx(CbAction, { variant: 'tertiary', onClick: onRetry, children: 'Retry now' })
            ]
          })
        : null,
      notice ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: notice }) : null,
      wide
        ? jsxs('div', {
            style: {
              display: 'grid',
              gridTemplateColumns: 'minmax(0, 1.2fr) minmax(19rem, 0.8fr)',
              gap: '1rem',
              alignItems: 'start'
            },
            children: [mainColumn, sideColumn]
          })
        : jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0 },
            children: [continueCard, notesCard, pathCard, sourcesCard, coursesCard]
          })
    ]
  })
}

/**
 * The estimate the backend already recorded: a pack manifest's per-objective `estimated_minutes`,
 * or the parent brief's `duration_minutes`. It never computes one from a count of sections.
 *
 * A failed read is its own state (`error`), not `none`: the desk has no answer and must not tell
 * the author they recorded none. `retryToken` re-runs the read for the desk's Retry control.
 */
function useSessionEstimate({ row, current, enabled, retryToken = 0 }) {
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
    // A refusal is not an empty answer: only `parent.brief.get`'s NOT_FOUND is a real answer
    // ("this course has no parent brief"), so it alone collapses to `none`.
    const refusalIsAnAnswer = (method, response) =>
      method === 'parent.brief.get' && Boolean(response.error) && response.error.code === 'NOT_FOUND'
    let read
    if (packId && packVersion && backendSupports('pack.inspect')) {
      read = rpc('pack.inspect', { pack_id: packId, pack_version: packVersion }).then((response) => {
        if (!response.ok) return { failed: true, error: response.error || null }
        const manifest = response.result && response.result.manifest
        const entries = manifest && Array.isArray(manifest.objectives) ? manifest.objectives : []
        const match = entries.find((entry) => Number(entry.ordinal) === Number(ordinal))
        const minutes = match && Number(match.estimated_minutes) > 0 ? Number(match.estimated_minutes) : null
        return minutes ? { minutes, source: 'pack_manifest' } : null
      })
    } else if (backendSupports('parent.brief.get')) {
      read = rpc('parent.brief.get', { course_id: courseId }).then((response) => {
        if (!response.ok) {
          return refusalIsAnAnswer('parent.brief.get', response)
            ? null
            : { failed: true, error: response.error || null }
        }
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
        if (found && found.failed) {
          setState({ status: 'error', minutes: null, source: null, error: found.error || null })
          return
        }
        setState(
          found
            ? { status: 'ready', minutes: found.minutes, source: found.source, error: null }
            : { status: 'none', minutes: null, source: null, error: null }
        )
      })
      .catch((error) => {
        if (cancelled) return
        setState({
          status: 'error',
          minutes: null,
          source: null,
          error: { code: 'HOST_UNAVAILABLE', message: describeError(error) }
        })
      })
    return () => {
      cancelled = true
    }
  }, [enabled, courseId, packId, packVersion, ordinal, key, retryToken])

  return state
}

/**
 * The Field Desk container. One `library.list` read picks the course to continue (the most
 * recently written row), `course.outline` supplies the path, and the section's sources are read
 * only when the drawer opens. A failure in any of those is shown, never papered over.
 */
function FieldDesk({ implemented, onOpen, onShowAll, onStartCreate, onStartSyllabus, profile, onEmptyChange }) {
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
  const [estimateTicket, setEstimateTicket] = useState(0)
  const estimate = useSessionEstimate({
    row,
    current,
    enabled: Boolean(row) && Boolean(current),
    retryToken: estimateTicket
  })
  const onRetryEstimate = useCallback(() => setEstimateTicket((value) => value + 1), [])
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
        objectiveTitle: desk.current.title || (desk.current.section ? desk.current.section.title : null),
        mode: kind === 'resume_lesson' ? 'resume' : 'fresh',
        profile: profile || currentScope().profile
      })
      setBusy(false)
      setNotice(outcome.message)
      if (outcome.ok) library.reload()
      if (outcome.ok && outcome.armed) {
        // The desk is a start surface too: arm the exact run, then open the new chat that carries
        // the pending binder. A host without newChat keeps the section/drawer open instead.
        const opened = openArmedLessonChat(profile || currentScope().profile)
        if (!opened) onOpen(desk.row, desk.current.objective_id)
        return
      }
      if (!outcome.ok && outcome.reason === 'no-binding') onOpen(desk.row, desk.current.objective_id)
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
    onSyllabus: onStartSyllabus,
    onPrimary,
    onOpenSection: (objectiveId, blockId) => onOpen(desk.row, objectiveId, blockId),
    onRetryEstimate,
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
    implemented,
    onEmptyChange
  })
}

/**
 * Search and filter only exist when there is something to search (UX-01). With zero courses on the
 * profile, a search box and four pills would be chrome that cannot do anything, so they are absent
 * on first run and appear with the first course.
 */
function courseToolsVisible(data) {
  if (!data) return true
  return Number(data.total || 0) > 0
}

function CoursesView({ implemented, onStartCreate, onStartSyllabus, createOpen, onOpen, onShowDesk, onEmptyChange }) {
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
        message: response && response.error ? `${response.error.code}: ${describeError(response.error)}` : 'Could not read which chat belongs to this course.'
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

  const allRows = data && Array.isArray(data.items) ? data.items : []
  // H-99: one shelf object per distinct course. The review block and the row list both read the
  // grouped view, so a course cannot appear twice in either place.
  const groups = groupShelfRows(allRows)
  const rows = groups.map((group) => group.primary)
  const groupReviewDue = (group) =>
    group.members.reduce((sum, member) => sum + Number((member.evidence_summary || {}).review_due || 0), 0)
  const noCourses = data && Number(data.total || 0) === 0
  // A search is a filter too: with rows present on the profile, an empty result set caused by the
  // search box must never be presented as first-run. `applied_filter` alone missed that case.
  const filteredEmpty =
    noCourses && (Boolean(query) || Boolean(data.applied_filter && data.applied_filter !== 'all'))

  // The filter chips and search box are chrome for a list that exists; the welcome replaces them
  // on first run. This is also what the route header reads to drop its duplicate New course button.
  const emptyFirstRun = Boolean(data) && noCourses && !filteredEmpty
  useEffect(() => {
    if (onEmptyChange) onEmptyChange(emptyFirstRun)
  }, [emptyFirstRun, onEmptyChange])
  const showTools = courseToolsVisible(data)

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
            jsx(CbAction, { variant: 'primary', onClick: reload, children: 'Try again' }),
            jsx(CbAction, { variant: 'secondary', onClick: openCapabilities, children: 'Open Capabilities' })
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
      : jsx(FirstRun, { implemented, onCreate: onStartCreate, onSyllabus: onStartSyllabus })
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
                jsx(CbAction, { variant: 'tertiary', onClick: reload, children: 'Retry now' })
              ]
            })
          : null,
        actionError ? jsx(ErrorLine, { error: { message: actionError } }) : null,
        groups.some((group) => groupReviewDue(group) > 0)
          ? jsxs('div', {
              className: 'mb-2 flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) pb-2',
              children: [
                jsx(CbLabel, { children: 'Review due' }),
                groups
                  .filter((group) => groupReviewDue(group) > 0)
                  .map((group) =>
                    jsxs(
                      'div',
                      {
                        className: 'flex flex-wrap items-center justify-between gap-2 text-xs',
                        children: [
                          jsx('span', {
                            className: 'min-w-0 break-words text-(--ui-text-secondary)',
                            children: `${group.primary.title} · ${groupReviewDue(group)} due`
                          }),
                          jsx(CbAction, {
                            variant: 'tertiary',
                            onClick: () => onOpen(group.primary),
                            children: 'Review'
                          })
                        ]
                      },
                      `review-${group.key}`
                    )
                  )
              ]
            })
          : null,
        groups.map((group) =>
          jsx(
            CourseRow,
            {
              row: group.primary,
              group,
              implemented,
              onResume,
              onArchive,
              onDelete,
              onOpen
            },
            group.key
          )
        ),
        data.next_cursor
          ? jsx('div', {
              className: 'pt-3 text-xs text-(--ui-text-secondary)',
              children: `${groups.length} courses shown. Narrow the filter to see the rest.`
            })
          : null
      ]
    })
  }

  const toolsDisabled = createOpen
  return jsxs('div', {
    className: 'flex flex-col',
    children: [
      onShowDesk
        ? jsx(CbAction, {
            className: 'mb-2 self-start',
            variant: 'tertiary',
            onClick: onShowDesk,
            children: 'Back to the Field Desk'
          })
        : null,
      jsx(PlateHead, {
        title: 'All courses',
        caption: data
          ? `${Number(data.total || 0)} ${Number(data.total || 0) === 1 ? 'course' : 'courses'} on this profile`
          : 'Reading the courses on this profile'
      }),
      jsxs('div', {
        className: 'mb-2 flex flex-wrap items-center justify-between gap-2',
        children: [
          showTools
            ? jsx(sdk.SearchField, {
                'aria-label': 'Search courses',
                containerClassName: 'max-w-sm min-w-0 flex-1',
                onChange: setSearchInput,
                placeholder: 'Search courses',
                value: searchInput
              })
            : null,
          showTools
            ? jsx(sdk.SegmentedControl, {
                onChange: setFilter,
                options: FILTERS,
                sizing: 'content',
                value: filter,
                disabled: toolsDisabled
              })
            : null
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

/** `enrollment_status` is a contract enum; a learner reads a sentence, not the raw value (H-28). */
const ENROLLMENT_STATUS_COPY = {
  active: 'Active',
  archived: 'Archived',
  completed: 'Completed'
}

function enrollmentStatusLabel(value) {
  return ENROLLMENT_STATUS_COPY[value] || value || 'Unknown'
}

function PackFacts({ row, implemented, onResume, onArchive, onDelete, onExportPack, onDeletePack, onBack, showBack }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const next = row.next_step || {}
  const warning = WARNING_COPY[row.warning]
  return jsxs('div', {
    className: 'flex min-w-0 flex-1 flex-col gap-3',
    children: [
      showBack
        ? jsx(CbAction, { className: 'self-start', onClick: onBack, variant: 'tertiary', children: 'All packs' })
        : null,
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx('h2', { className: 'text-sm font-semibold', children: row.title }),
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
      jsx(CbLabel, { children: 'What the record shows' }),
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(StatusRow, { label: 'Next step', value: next.label || '—' }),
          jsx(StatusRow, {
            label: 'Enrolment',
            value: enrollmentStatusLabel(row.enrollment_status),
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
            ? jsx(CbAction, { onClick: () => onResume(row), variant: 'secondary', children: 'Resume lesson' })
            : null,
          supports('enrollment.update')
            ? jsx(CbAction, {
                onClick: () => onArchive(row, row.enrollment_status === 'archived' ? 'unarchive' : 'archive'),
                variant: 'tertiary',
                children: row.enrollment_status === 'archived' ? 'Unarchive' : 'Archive'
              })
            : null,
          supports('enrollment.delete')
            ? jsx(CbAction, { onClick: () => onDelete(row), variant: 'tertiary', children: 'Delete enrollment…' })
            : null,
          row.provenance && row.provenance.pack_id && supports('pack.export')
            ? jsx(CbAction, { onClick: () => onExportPack(row), variant: 'tertiary', children: 'Export pack…' })
            : null,
          row.provenance && row.provenance.pack_id && supports('pack.delete') && row.warning !== 'pack_frozen'
            ? jsx(CbAction, { onClick: () => onDeletePack(row), variant: 'tertiary', children: 'Remove pack…' })
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

/**
 * How a pack is explained before anything is added (UX-06).
 *
 * The absence of a marketplace and of a verified badge is true but it is not a welcome. It lives in
 * an opened disclosure, under what is checked and what is not, so the trust labels keep their
 * meaning and nobody reads a pack as endorsed.
 */
const LIBRARY_COPY = {
  lead: 'Courses made by other people. You will see who made it, where it came from and what has been checked before you add one.',
  whatWeCheck:
    'What we check — that every file matches the hashes in the pack’s manifest, that its structure and teaching minima pass the automated checks, and whether a named reviewer and a model assessment are recorded. Those are separate labels on every pack and they are never merged into a score.',
  whatWeDoNotCheck:
    'What we do not check — whether the teaching is good for you, whether the author is trustworthy, and how this pack compares with any other. There is no marketplace ranking and no verified badge.',
  emptyTitle: 'No packs on this profile yet',
  emptyBody:
    'A pack is a zip file someone else made: lessons, sources and a manifest that lists every file. Bundled packs ship with Coursebook; a pack from someone else is added from the Import flow, where you review it first.'
}

function LibraryView({ implemented, createOpen, onStartSyllabus, onStartImport }) {
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
      host.notify({ kind: 'warning', message: 'Could not read which chat belongs to this lesson.' })
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
  const filteredRows = allRows.filter((row) => {
    const source = (row.provenance && row.provenance.source) || 'authored'
    if (view === 'bundled') return source === 'bundled'
    if (view === 'local') return source === 'local' || source === 'community'
    return true
  })
  // H-99: one shelf object per course/pack. Fourteen enrollments of the same pack are one row
  // with an `N enrollments` disclosure, not fourteen identical text cards.
  const groups = groupShelfRows(filteredRows)
  const rows = filteredRows

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
        jsx(CbAction, { className: 'self-start', onClick: reload, variant: 'tertiary', children: 'Try again' })
      ]
    })
  } else if (rows.length === 0) {
    listBody = jsxs('div', {
      className: 'flex flex-col gap-3',
      children: [
        jsx(EmptyState, {
          title: view === 'bundled' ? 'No bundled pack on this profile' : view === 'local' ? 'No pack from someone else on this profile' : LIBRARY_COPY.emptyTitle,
          description: LIBRARY_COPY.emptyBody
        }),
        jsx('p', {
          style: { margin: 0, maxWidth: CB_MEASURE, fontSize: CB_TYPE.body, lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
          children: LIBRARY_COPY.lead
        })
      ]
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
        groups.map((group) => {
          const row = group.primary
          return jsx(
            PackShelfRow,
            {
              row,
              group,
              selected: row.enrollment_id === selected,
              onOpenMember: (member) => setSelected(member.enrollment_id),
              onPreview: (member) => setSelected(member.enrollment_id)
            },
            group.key
          )
        })
      ]
    })
  }

  return jsxs('div', {
    className: 'flex flex-col',
    style: { maxWidth: CB_MEASURE },
    children: [
      jsx(PlateHead, {
        label: 'Library',
        title: 'Packs on this profile',
        caption: jsx('span', { children: LIBRARY_COPY.lead })
      }),
      // H-99: the two import paths live in the route header — one primary `Import pack` and one
      // secondary `Use my college syllabus`. They are no longer repeated here under a second set
      // of labels; one surface, one primary per object (see the H-94 rule).
      jsxs('div', {
        className: 'mb-2 flex flex-col gap-2',
        children: [
          jsxs('div', {
            className: 'flex flex-wrap items-center justify-between gap-2',
            children: [
              jsx('div', {
                className: 'max-w-prose leading-relaxed text-(--ui-text-secondary)',
                style: { maxWidth: CB_MEASURE, fontSize: CB_TYPE.body },
                children: stale ? 'Reconnecting. Showing the last packs that were read.' : ''
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
          jsxs('details', {
            'data-cb-pack-trust': '',
            className: 'max-w-prose leading-relaxed text-(--ui-text-secondary)',
            style: { maxWidth: CB_MEASURE, fontSize: CB_TYPE.body },
            children: [
              jsx('summary', {
                'data-cb-affordance': 'disclosure',
                className: 'flex cursor-pointer items-center gap-1 text-xs font-medium',
                style: { listStyle: 'none', minHeight: '1.75rem' },
                children: [
                  jsx(sdk.Codicon, { name: 'chevron-right', size: CB_ICON_UI }),
                  jsx('span', { children: 'What we check / what we do not check' })
                ]
              }),
              jsx('p', { className: 'mt-1', style: { fontSize: CB_TYPE.body, lineHeight: 1.55 }, children: LIBRARY_COPY.whatWeCheck }),
              jsx('p', { className: 'mt-1', style: { fontSize: CB_TYPE.body, lineHeight: 1.55 }, children: LIBRARY_COPY.whatWeDoNotCheck })
            ]
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
                  title: 'Choose a pack to see what we know about it',
                  description: 'Preview shows who made the pack, where it came from, the progress you have and what has been checked — nothing inferred.'
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

/**
 * How much course a brief asks for. Contract enum: `single` | `short` | `full`.
 *
 * H-28 (UX-02/UX-09) makes scope the first question and gives each answer one sentence saying what
 * the learner receives. The ids stay exactly the contract's; only the words a person reads change.
 */
const COURSE_SCOPES = [
  {
    id: 'single',
    label: 'A single lesson',
    consequence: 'One lesson with one check — best when you have a task in front of you today.'
  },
  {
    id: 'short',
    label: 'A short course (a few sessions)',
    consequence: 'A few sessions that build on each other, each with its own check.'
  },
  {
    id: 'full',
    label: 'A full course (weeks or months)',
    consequence: 'A longer course split into units; you review the plan before any lesson is written.'
  }
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
 * A neutral goal gallery (H-100). The default form is a general harness, not a single-topic demo:
 * one language, one practical skill, one academic concept and one everyday skill, so a new learner
 * sees four different shapes of course in one glance.
 *
 * These are examples, never defaults. They appear as buttons and a greyed placeholder only; nothing
 * reaches the goal or title field until the learner presses one or types their own words.
 */
const GOAL_EXAMPLES = [
  { domain: 'Language', text: 'Hold a six-minute conversation in Spanish' },
  { domain: 'Skill', text: 'Wire a lamp safely' },
  { domain: 'Concept', text: 'Understand the first month of a statistics class' },
  { domain: 'Everyday', text: 'Read a nutrition label for added sugar' }
]
const GOAL_PLACEHOLDER = 'e.g. Hold a six-minute conversation in Spanish'
const TITLE_PLACEHOLDER = 'e.g. Six-minute Spanish conversation'

/**
 * The examples, labelled as examples and inert until chosen. Pressing one fills the goal field the
 * learner can still edit; it never submits the form or starts a job.
 */
function GoalGallery({ examples, onChoose }) {
  const rows = examples || GOAL_EXAMPLES
  return jsxs('div', {
    'data-cb-goal-examples': '',
    className: 'flex flex-col gap-1.5',
    children: [
      jsx('div', {
        className: 'text-xs text-(--ui-text-secondary)',
        id: 'cb-goal-examples-label',
        children: 'Examples — press one to start from it, or write your own:'
      }),
      jsx('div', {
        'aria-labelledby': 'cb-goal-examples-label',
        className: 'flex flex-wrap gap-1.5',
        role: 'group',
        children: rows.map((example) =>
          jsxs(
            sdk.Button,
            {
              'aria-label': `${example.text} — ${example.domain} example`,
              className: 'max-w-full text-left',
              onClick: () => onChoose && onChoose(example.text),
              size: 'sm',
              variant: 'outline',
              children: [
                jsx('span', { className: 'whitespace-normal text-(--ui-text-secondary)', children: `${example.domain}: ` }),
                jsx('span', { className: 'whitespace-normal', children: example.text })
              ]
            },
            example.text
          )
        )
      })
    ]
  })
}

/** The create result speaks before the receipt does (UX-03). */
const CREATE_RESULT_COPY = {
  lead: 'Your plan is being researched; this may take several minutes and you can leave this page.',
  body: 'When it arrives it opens here. Approve the plan to start the first lesson; no lesson is written before that.',
  details: 'Details and job state'
}

/** Dials are chosen as enum ids; the review panel shows the label the learner actually picked. */
function dialLabel(dial, value) {
  const options = (DIALS[dial] && DIALS[dial].options) || []
  const found = options.find((option) => option.id === value)
  return found ? found.label : value
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

/**
 * The scope a learner picks proposes how the course is used, until they choose for themselves: one
 * lesson is a task (`one_off`), a short course is casual, a full course is a steady plan. The recipe
 * stays a real contract field; this only saves the learner from decoding an enum.
 */
const SCOPE_DEFAULT_RECIPE = { single: 'one_off', short: 'casual', full: 'committed' }

/** The three steps, in the words a learner uses, each with the next thing that will happen. */
const CREATE_STEP_SPINE = Object.freeze([
  { n: 1, name: 'Size', next: 'Next: name the goal and the course.' },
  { n: 2, name: 'Goal', next: 'Next: review what will be created.' },
  { n: 3, name: 'Review', next: 'Create the course, then review the draft plan.' }
])

/** A compact staged create flow; every step is editable before the one mutation. */
function CreateCourseFlow({ onCancel, onCreated, seed }) {
  // H-103: a rejected plan can hand its goal and choices back here. The seed is a starting point,
  // never a silent submission: the learner still reviews and presses Create. Opening from the plan
  // rejection lands on the Goal step, because size and recipe were already answered last time.
  const start = seed || {}
  const [step, setStep] = useState(seed ? 2 : 1)
  const [goal, setGoal] = useState(start.goal || '')
  const [title, setTitle] = useState(start.title || '')
  const [recipe, setRecipe] = useState(start.recipe || 'casual')
  // No scope is preselected: the first screen asks for intent, so "Continue" is only enabled once
  // the learner has said whether this is one lesson, a short course or a full course (UX-09).
  const [scope, setScope] = useState(start.scope || '')
  const [recipeTouched, setRecipeTouched] = useState(Boolean(seed))
  const [level, setLevel] = useState(start.level || '')
  const [subjectDomain, setSubjectDomain] = useState(start.subjectDomain || '')
  const [locale, setLocale] = useState(start.locale || '')
  const [dials, setDials] = useState(
    start.dials || { pace: 'light', depth: 'survey', assessment: 'self_check', autonomy: 'guided' }
  )
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  // The course/enrolment can already exist when the plan job fails. Those ids stay on screen so the
  // same key can retry the same job; the draft is never lost to a redraw.
  const [recoverable, setRecoverable] = useState(null)
  const [revision, setRevision] = useState(0)
  const [error, setError] = useState(null)
  const keyRef = useRef(null)

  const goalInvalid = step >= 1 && goal.trim().length === 0
  const canAdvance = step === 1 ? Boolean(scope) : goal.trim().length > 0 && title.trim().length > 0

  const chooseScope = useCallback(
    (id) => {
      setScope(id)
      if (!recipeTouched) setRecipe(SCOPE_DEFAULT_RECIPE[id] || 'casual')
    },
    [recipeTouched]
  )
  const chooseRecipe = useCallback((id) => {
    setRecipeTouched(true)
    setRecipe(id)
  }, [])

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
        jsx('h2', { className: 'text-sm font-semibold', children: CREATE_RESULT_COPY.lead }),
        jsx('p', {
          className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
          children: CREATE_RESULT_COPY.body
        }),
        jsxs('details', {
          'data-cb-create-receipt': '',
          className: 'text-xs text-(--ui-text-secondary)',
          children: [
            jsx('summary', { className: 'cursor-pointer', children: CREATE_RESULT_COPY.details }),
            jsxs('div', {
              className: 'mt-1 flex flex-col',
              children: [
                jsx(StatusRow, { label: 'Course', value: result.courseId }),
                jsx(StatusRow, { label: 'Plan', value: `${result.planId} (draft)` }),
                jsx(StatusRow, { label: 'Enrolment', value: result.enrollmentId }),
                jsx(StatusRow, { label: 'Plan job', value: `${result.jobId} · ${result.jobState}` })
              ]
            })
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
            jsx(sdk.Button, { onClick: onCancel, variant: 'secondary', children: 'Open in Courses' }),
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
              variant: 'text',
              children: 'Create another'
            })
          ]
        })
      ]
    })
  }

  const stepTitle = step === 1 ? 'What do you want to make?' : step === 2 ? 'What should it cover?' : 'Review and create'

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
              jsx('div', {
                'data-cb-create-spine': '',
                className: 'flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-(--ui-text-secondary)',
                children: CREATE_STEP_SPINE.map((item) =>
                  jsxs(
                    'span',
                    {
                      'data-cb-create-step': String(item.n),
                      'aria-current': item.n === step ? 'step' : undefined,
                      style:
                        item.n === step
                          ? {
                              display: 'inline-flex',
                              alignItems: 'baseline',
                              gap: '0.3rem',
                              fontWeight: 600,
                              color: 'var(--ui-text-primary)',
                              borderBottom: '2px solid var(--cb-lamp)',
                              paddingBottom: '0.1rem'
                            }
                          : { display: 'inline-flex', alignItems: 'baseline', gap: '0.3rem' },
                      children: [
                        jsx('span', { style: { fontVariantNumeric: 'tabular-nums' }, children: String(item.n) }),
                        jsx('span', { children: item.name })
                      ]
                    },
                    item.n
                  )
                )
              }),
              jsx('div', { className: 'mt-1 text-xs text-(--ui-text-secondary)', children: `Step ${step} of 3` }),
              jsx('h2', { className: 'mt-1 text-lg font-semibold', children: stepTitle }),
              jsx('p', {
                'data-cb-create-next': '',
                className: 'mt-0.5 max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
                children: CREATE_STEP_SPINE[step - 1].next
              })
            ]
          }),
          jsx(sdk.Button, { onClick: onCancel, size: 'sm', variant: 'text', children: 'Cancel' })
        ]
      }),
      step === 1
        ? jsxs('div', {
            className: 'flex flex-col gap-3',
            children: [
              jsx('p', {
                className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
                children: 'Pick how much course you want. Nothing is created yet, and you can go back at any point.'
              }),
              jsx('div', {
                role: 'listbox',
                'aria-label': 'How much course you want',
                className: 'flex flex-col gap-1.5',
                children: COURSE_SCOPES.map((option) => {
                  const selected = scope === option.id
                  // H-64: the whole card is the hit target and carries the selected state in words
                  // as well as in `aria-selected`. The small "Choose" button left most of the card
                  // dead to a click and made the state hard to see.
                  return jsx(
                    'button',
                    {
                      type: 'button',
                      role: 'option',
                      'aria-selected': selected,
                      'data-cb-scope-option': option.id,
                      onClick: () => chooseScope(option.id),
                      className: `flex w-full items-start justify-between gap-3 rounded-[2.5px] border px-3 py-2.5 text-left transition-colors ${
                        selected
                          ? 'border-(--cb-accent) bg-(--cb-accent-soft)'
                          : 'border-(--cb-rule) hover:border-(--cb-accent)'
                      }`,
                      children: [
                        jsxs('span', {
                          className: 'flex min-w-0 flex-col gap-0.5',
                          children: [
                            jsx('span', { className: 'text-xs font-medium', children: option.label }),
                            jsx('span', {
                              className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                              children: option.consequence
                            })
                          ]
                        }),
                        jsx('span', {
                          className: selected
                            ? 'shrink-0 text-xs font-medium'
                            : 'shrink-0 text-xs text-(--ui-text-secondary)',
                          children: selected ? 'Selected' : 'Choose'
                        })
                      ]
                    },
                    option.id
                  )
                })
              }),
              jsx('div', {
                'aria-live': 'polite',
                className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                id: 'cb-scope-time',
                children: scope
                  ? planTimingCopy(scope)
                  : 'Choose one option above to continue. Nothing is generated until you review the plan on the last step.'
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
                  jsx('label', { className: 'text-xs font-medium text-(--ui-text-secondary)', htmlFor: 'cb-goal', children: 'What do you want to be able to do?' }),
                  jsx(sdk.Textarea, {
                    'aria-describedby': 'cb-goal-help',
                    'aria-invalid': goalInvalid ? true : undefined,
                    id: 'cb-goal',
                    onChange: (event) => setGoal(event.target.value),
                    placeholder: GOAL_PLACEHOLDER,
                    rows: 4,
                    value: goal
                  }),
                  jsx('div', {
                    className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                    id: 'cb-goal-help',
                    children:
                      goal.trim().length === 0
                        ? 'Say it as the situation you want to handle. The examples below are starting points, not a course yet.'
                        : `${goal.trim().length} characters. Keep editing, or start from a different example.`
                  }),
                  jsx(GoalGallery, { onChoose: setGoal })
                ]
              }),
              jsxs('div', {
                className: 'flex flex-col gap-1.5',
                children: [
                  jsx('label', { className: 'text-xs font-medium text-(--ui-text-secondary)', htmlFor: 'cb-title', children: 'Name this course (required)' }),
                  jsx(sdk.Input, {
                    id: 'cb-title',
                    onChange: (event) => setTitle(event.target.value),
                    placeholder: TITLE_PLACEHOLDER,
                    value: title
                  }),
                  jsx('div', {
                    className: 'text-xs text-(--ui-text-secondary)',
                    children: 'This is the name you will see in your course list.'
                  })
                ]
              }),
              jsxs('div', {
                className: 'flex flex-col',
                children: [
                  jsx('div', { className: 'mb-1 text-xs font-medium text-(--ui-text-secondary)', children: 'What kind of course is this?' }),
                  RECIPES.filter((id) => id !== 'parent').map((id) =>
                    jsx(sdk.ListRow, {
                      action: jsx(sdk.Button, {
                        'aria-pressed': recipe === id,
                        onClick: () => chooseRecipe(id),
                        size: 'sm',
                        variant: recipe === id ? 'secondary' : 'outline',
                        children: recipe === id ? 'Selected' : 'Choose'
                      }),
                      description: RECIPE_COPY[id].description,
                      title: RECIPE_COPY[id].title
                    }, id)
                  ),
                  jsx('div', {
                    className: 'mt-1 text-xs leading-relaxed text-(--ui-text-secondary)',
                    children: 'Preparing lessons for a child is a different path: Parent Studio, not a learner course.'
                  })
                ]
              }),
              jsxs('details', {
                'data-cb-tune': '',
                className: 'border-t border-(--ui-stroke-tertiary) pt-3 text-xs text-(--ui-text-secondary)',
                children: [
                  jsx('summary', { className: 'cursor-pointer text-xs font-medium', children: 'Help me tune it (optional)' }),
                  jsxs('div', {
                    className: 'mt-2 flex flex-col gap-3',
                    children: [
                      jsxs('div', {
                        className: 'flex flex-col gap-1.5',
                        children: [
                          jsx('label', { className: 'text-xs text-(--ui-text-secondary)', htmlFor: 'cb-level', children: 'Where you are starting from' }),
                          jsx(sdk.Input, {
                            id: 'cb-level',
                            maxLength: 35,
                            onChange: (event) => setLevel(event.target.value),
                            placeholder: 'e.g. complete beginner, or rusty',
                            value: level
                          })
                        ]
                      }),
                      jsxs('div', {
                        className: 'flex flex-col gap-1.5',
                        children: [
                          jsx('label', { className: 'text-xs text-(--ui-text-secondary)', htmlFor: 'cb-subject', children: 'Subject, in your own words' }),
                          jsx(sdk.Input, {
                            id: 'cb-subject',
                            maxLength: 60,
                            onChange: (event) => setSubjectDomain(event.target.value),
                            placeholder: 'e.g. Spanish, statistics, electrical safety',
                            value: subjectDomain
                          })
                        ]
                      }),
                      jsxs('div', {
                        className: 'flex flex-col gap-1.5',
                        children: [
                          jsx('label', { className: 'text-xs text-(--ui-text-secondary)', htmlFor: 'cb-locale', children: 'Language or locale (language courses only)' }),
                          jsx(sdk.Input, {
                            id: 'cb-locale',
                            maxLength: 35,
                            onChange: (event) => setLocale(event.target.value),
                            placeholder: 'e.g. es-ES for Spanish, ja-JP for Japanese',
                            value: locale
                          }),
                          jsx('div', {
                            className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                            children: 'This only sets language and formatting conventions. It never describes the subject.'
                          })
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
                      jsx('div', {
                        className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                        children: 'These shape the plan only. Nothing here becomes a grade.'
                      })
                    ]
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
                  jsx(StatusRow, {
                    label: 'What you get',
                    value: (COURSE_SCOPES.find((option) => option.id === scope) || {}).label || 'Not chosen'
                  }),
                  jsx(StatusRow, { label: 'Goal', value: jsx('span', { className: 'max-w-[36ch] break-words', children: goal.trim() }) }),
                  jsx(StatusRow, { label: 'Name', value: title.trim() }),
                  jsx(StatusRow, { label: 'How you will use it', value: RECIPE_COPY[recipe].title }),
                  jsx(StatusRow, { label: 'Pace', value: dialLabel('pace', dials.pace) }),
                  jsx(StatusRow, { label: 'Depth', value: dialLabel('depth', dials.depth) }),
                  jsx(StatusRow, { label: 'Checks', value: dialLabel('assessment', dials.assessment) }),
                  jsx(StatusRow, { label: 'Guidance', value: dialLabel('autonomy', dials.autonomy) }),
                  level.trim() ? jsx(StatusRow, { label: 'Starting point', value: level.trim() }) : null,
                  subjectDomain.trim() ? jsx(StatusRow, { label: 'Subject', value: subjectDomain.trim() }) : null,
                  locale.trim() ? jsx(StatusRow, { label: 'Language / locale', value: locale.trim() }) : null
                ]
              }),
              jsx('div', {
                'data-cb-create-confirm': '',
                className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
                children:
                  'Create course writes the course and one draft plan. The plan then opens here for you to ' +
                  'approve, and no lesson is written until you do.'
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
            ? jsx(CbAction, {
                'aria-describedby': step === 1 && !canAdvance ? 'cb-scope-time' : undefined,
                disabled: step === 1 ? !canAdvance : false,
                onClick: () => setStep(step + 1),
                variant: 'primary',
                children: 'Continue'
              })
            : jsx(CbAction, {
                disabled: submitting,
                onClick: submit,
                variant: 'primary',
                children: submitting ? 'Creating course' : recoverable ? 'Retry the plan job' : 'Create course'
              })
        ]
      })
    ]
  })
}
// ══ H-27 — the student syllabus path: intake, parse review, anchors and alignment ══
//
// `docs/STUDENT-MODE.md` is the frozen design (H-25). This half renders exactly what the
// `syllabus.*` commands answer and nothing else:
//
//   intake     the host door reads bytes; the RPC carries bytes or pasted text and never a path;
//              when this Desktop build has no byte-reading door the screen says so and offers the
//              paste path, which the design makes first-class;
//   parse      every scalar is an item with a state and anchors. `unknown` renders as
//              "Not in your file" — a table cell is never filled from world knowledge;
//   alignment  one row per syllabus item with its state, one-line reason and the verbatim anchor;
//              conflict and stale block approval, and the learner's review is the gate;
//   course     the existing `course.create` → `enrollment.create` → plan job path, with the
//              syllabus fields the contract added. There is no second job engine and no percentage
//              invented for a job the backend reports by state only.
//
// The external class is the authority; Coursebook is a companion. That sentence is copy, not a
// badge, and `tests/test_desktop_syllabus_ui.py` refuses the marketing claims the design bans.

const SYLLABUS_LIMITS = Object.freeze({
  file_name: 255,
  text_bytes: 4 * 1024 * 1024,
  binary_bytes: 8 * 1024 * 1024,
  text_chars: 200000,
  pdf_pages: 60,
  docx_paragraphs: 2000,
  base64_chars: 11184812
})

/** The closed type list (§2.2). Anything else is refused; the UI does not offer it. */
const SYLLABUS_ACCEPT = Object.freeze([
  { ext: 'md', label: 'Markdown (.md)', format: 'markdown', mime: 'text/markdown', text: true },
  { ext: 'markdown', label: 'Markdown (.markdown)', format: 'markdown', mime: 'text/markdown', text: true },
  { ext: 'txt', label: 'Plain text (.txt)', format: 'text', mime: 'text/plain', text: true },
  { ext: 'pdf', label: 'PDF (.pdf)', format: 'pdf', mime: 'application/pdf', text: false },
  { ext: 'docx', label: 'Word document (.docx)', format: 'docx', mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', text: false }
])

const SYLLABUS_MIME_HINTS = Object.freeze([
  'text/markdown',
  'text/plain',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/octet-stream'
])

/**
 * The surface's copy, in one place so a test can read it without scraping JSX.
 *
 * Design §3.2 forbids "complete", "official" and "verified with your institution" as claims about
 * the parse; §4.6 forbids "official week 4 lesson", "your professor's lesson", "required by your
 * course", "counts toward your grade", "enrolled" and "accredited". "Not official course material"
 * is the required calm disclaimer and is written as a negation, never a promise.
 */
const SYLLABUS_COPY = Object.freeze({
  action: 'Use my college syllabus',
  actionDetail: 'You already have the syllabus. Coursebook builds a companion course around it.',
  entryTitle: 'Have a college syllabus?',
  entryBody:
    'Start a companion course from your own class. Your syllabus sets the scope; Coursebook authors its own lessons alongside it.',
  authority:
    'Your syllabus is the authority for what the class covers. Coursebook is a companion that supports it — it is not your class, your registrar, or a grade.',
  notOfficial: 'Not official course material. Coursebook writes its own lessons; your instructor’s document stays the authority.',
  parseSentence: 'Parsed from your file. Check each item against the page.',
  unknownValue: 'Not in your file',
  unknownWeight: 'Weight not in your file',
  unknownDue: 'Due date not in your file',
  ambiguousValue: 'Two readings in your file',
  acceptTypes: 'Markdown, plain text, PDF or Word (.docx). Up to 8 MB; 200,000 characters of text.',
  noFileDoor:
    'This Hermes Desktop build has no file door, so it cannot open a syllabus file here. Paste the text below — it is stored the same way and gets the same anchors.',
  noBackend:
    'This Coursebook backend does not have the syllabus import yet. Nothing here pretends to read your file until it does.',
  parseRunning: 'Reading your file. Extraction is local and runs in stages, so there is no percentage to show.',
  parseNeedsReview:
    'Some items could not be tied to a quote in your file. Check the ones marked below, or upload a cleaner copy.',
  storage: 'Your file stays on this profile. The parse and the alignment are sent to the model provider you have configured, and only after you acknowledge that.',
  alignmentGate: 'Review the mapping before a course is built. Conflict or stale items block approval.',
  researchMinutes: 'Research and authoring may take several minutes. The plan appears when the backend finishes it.',
  staleLead: 'Your syllabus changed. The earlier mapping was made against the old revision, so it is marked stale.',
  staleAction: 'Check the new revision, then review the mapping again. Your approved plan and lessons are kept as they were.',
  startsCompanion: 'Create companion course',
  coversLine: (covered, total) => `This course covers ${covered} of ${total} syllabus weeks.`
})

const ALIGNMENT_STATE_COPY = Object.freeze({
  aligned: { label: 'Aligned', tone: 'ok', line: 'Coursebook covers what this item asks.' },
  partial: { label: 'Partly covered', tone: 'warn', line: 'This is covered, but less than the syllabus asks.' },
  unmatched: { label: 'Not covered', tone: 'warn', line: 'Nothing in this course plan maps to this item yet.' },
  conflict: { label: 'Conflicts', tone: 'bad', line: 'The course plan contradicts this item.' },
  unknown: { label: 'Not checked', tone: 'muted', line: 'This item has not been evaluated yet.' },
  stale: { label: 'Out of date', tone: 'bad', line: 'The syllabus or the plan changed after this was mapped.' }
})

const SYLLABUS_REASON_COPY = Object.freeze({
  week_ordinal: 'Matched on the week number in your syllabus.',
  title_tokens: 'Matched on the wording of the topic.',
  reading_match: 'Matched on the reading named in your syllabus.',
  assessment_match: 'Matched on the assessment name.',
  model: 'Suggested by the model; treat it as a hypothesis, not proof.',
  anchor_mismatch: 'The quote could not be found in your file, so this stays unknown.',
  no_target: 'No row in the course plan matched this item.',
  weak_title_tokens: 'The plan covers part of this item, not all of it.',
  scheduled_after_deadline: 'The plan reaches this topic after the week your syllabus gives it.',
  value_unknown: 'Your file does not state this item, so nothing was mapped to it.',
  week_mismatch: 'The plan places this topic in a different week.',
  deadline_passed: 'The plan schedules work after the date in your syllabus.',
  scope_exceeded: 'The plan claims more than this item asks for.',
  ignored_assessment: 'The plan claims coverage while ignoring this assessment.',
  revision_changed: 'The syllabus revision changed after this mapping was made.',
  plan_superseded: 'The plan was replaced after this mapping was made.'
})

/** Format from the extension, never from a declared MIME (§2.1: magic bytes decide at the backend). */
function syllabusFormatFor(name) {
  const value = String(name || '')
  const dot = value.lastIndexOf('.')
  if (dot < 0 || dot === value.length - 1) return null
  const ext = value.slice(dot + 1).toLowerCase()
  const entry = SYLLABUS_ACCEPT.find((candidate) => candidate.ext === ext)
  return entry ? entry.format : null
}

function syllabusAcceptEntry(name) {
  const value = String(name || '')
  const dot = value.lastIndexOf('.')
  const ext = dot >= 0 ? value.slice(dot + 1).toLowerCase() : ''
  return SYLLABUS_ACCEPT.find((candidate) => candidate.ext === ext) || null
}

function base64FromUtf8(text) {
  const encoder = new TextEncoder()
  const bytes = encoder.encode(String(text))
  let binary = ''
  const step = 0x8000
  for (let index = 0; index < bytes.length; index += step) {
    binary += String.fromCharCode.apply(null, bytes.subarray(index, index + step))
  }
  return btoa(binary)
}

function utf8Bytes(text) {
  return new TextEncoder().encode(String(text)).length
}

/**
 * The `syllabus.intake.create` payload, or a typed refusal.
 *
 * Exactly one of `content_base64` / `pasted_text` (§2.1). Bounds are checked here, before a job
 * exists, so an oversized file is refused with the measured size instead of being uploaded to be
 * refused later. Nothing here is a sample: a caller that passes nothing gets a refusal.
 */
function syllabusIntakePayload(input = {}) {
  const fail = (code, message) => ({ ok: false, error: { code, message } })
  const pasted = typeof input.pastedText === 'string' ? input.pastedText : null
  const text = typeof input.text === 'string' ? input.text : null
  const dataUrl = typeof input.dataUrl === 'string' ? input.dataUrl : null
  const supplied = [pasted !== null, text !== null, dataUrl !== null].filter(Boolean).length
  if (supplied !== 1) {
    return fail('VALIDATION_FAILED', 'Send one file or one pasted syllabus, not several at once.')
  }

  const supersedes = input.supersedesSyllabusId ? String(input.supersedesSyllabusId) : null

  if (pasted !== null) {
    const chars = pasted.length
    if (chars === 0) return fail('VALIDATION_FAILED', 'The pasted syllabus is empty.')
    if (chars > SYLLABUS_LIMITS.text_chars) {
      return fail('SYLLABUS_REJECTED', `That text is ${chars.toLocaleString()} characters; the limit is ${SYLLABUS_LIMITS.text_chars.toLocaleString()}.`)
    }
    const payload = { pasted_text: pasted }
    if (supersedes) payload.supersedes_syllabus_id = supersedes
    return { ok: true, payload }
  }

  const fileName = String(input.fileName || '').trim()
  if (!fileName) return fail('VALIDATION_FAILED', 'The file has no name to show beside it.')
  if (fileName.length > SYLLABUS_LIMITS.file_name) {
    return fail('SYLLABUS_REJECTED', 'That file name is longer than the 255 characters the contract accepts.')
  }
  const entry = syllabusAcceptEntry(fileName)
  if (!entry) {
    return fail('SYLLABUS_REJECTED', 'Coursebook reads Markdown, plain text, PDF and Word (.docx) only. Nothing else is accepted.')
  }

  if (text !== null) {
    if (!entry.text) return fail('SYLLABUS_REJECTED', 'A PDF or Word file has to be read as bytes, not as text.')
    const chars = text.length
    const bytes = utf8Bytes(text)
    if (chars === 0) return fail('VALIDATION_FAILED', 'That file is empty.')
    if (chars > SYLLABUS_LIMITS.text_chars) {
      return fail('SYLLABUS_REJECTED', `That file is ${chars.toLocaleString()} characters; the limit is ${SYLLABUS_LIMITS.text_chars.toLocaleString()}.`)
    }
    if (bytes > SYLLABUS_LIMITS.text_bytes) {
      return fail('SYLLABUS_REJECTED', `That file is ${bytesLabel(bytes)}; the text limit is ${bytesLabel(SYLLABUS_LIMITS.text_bytes)}.`)
    }
    if (text.indexOf('\u0000') >= 0) return fail('SYLLABUS_REJECTED', 'That file is not plain UTF-8 text.')
    const payload = { content_base64: base64FromUtf8(text), file_name: fileName, mime_hint: entry.mime }
    if (supersedes) payload.supersedes_syllabus_id = supersedes
    return { ok: true, payload }
  }

  const match = /^data:([^;,]*)(?:;[^,]*)?;base64,(.*)$/s.exec(dataUrl)
  if (!match) return fail('VALIDATION_FAILED', 'The host returned a file in a form Coursebook cannot read. Paste the text instead.')
  const base64 = match[2] || ''
  if (base64.length > SYLLABUS_LIMITS.base64_chars) {
    return fail('SYLLABUS_REJECTED', `That file is larger than the 8 MB limit for PDF and Word.`)
  }
  const bytes = Math.floor((base64.length * 3) / 4)
  if (bytes > SYLLABUS_LIMITS.binary_bytes) {
    return fail('SYLLABUS_REJECTED', `That file is ${bytesLabel(bytes)}; the limit is ${bytesLabel(SYLLABUS_LIMITS.binary_bytes)}.`)
  }
  if (entry.text) return fail('SYLLABUS_REJECTED', 'A text document has to be read as text, not as bytes.')
  const declared = String(match[1] || '')
  const hint = SYLLABUS_MIME_HINTS.indexOf(declared) >= 0 ? declared : entry.mime
  const payload = { content_base64: base64, file_name: fileName, mime_hint: hint }
  if (supersedes) payload.supersedes_syllabus_id = supersedes
  return { ok: true, payload }
}

/** One anchor as a short human label: a page, a line range, or a named section. */
function syllabusAnchorLabel(anchor) {
  if (!anchor) return 'your file'
  const page = anchor.page
  if (page !== undefined && page !== null && String(page).length) return `p. ${page}`
  const start = anchor.line_start
  const end = anchor.line_end
  if (start !== undefined && start !== null && String(start).length) {
    if (end !== undefined && end !== null && String(end).length && end !== start) return `lines ${start}–${end}`
    return `line ${start}`
  }
  if (anchor.section) return String(anchor.section)
  if (anchor.label) return String(anchor.label)
  return 'your file'
}

/**
 * One parsed scalar as the review screen shows it.
 *
 * `unknown` never renders a value: the cell says the file does not state it. `ambiguous` shows
 * that the file supports two readings and lists them; it does not pick one. A state this module
 * does not know is treated as unknown, because guessing is the one thing this surface must not do.
 */
function syllabusItemView(item) {
  const state = item && typeof item.state === 'string' ? item.state : 'unknown'
  const anchors = (item && Array.isArray(item.anchors) ? item.anchors : []).filter(Boolean)
  const anchorLabels = anchors.map(syllabusAnchorLabel)
  if (state === 'extracted' && item.value !== null && item.value !== undefined && item.value !== '') {
    return {
      state: 'extracted',
      unknown: false,
      text: String(item.value),
      anchors,
      anchorLabels,
      derivation: item.derivation || 'explicit'
    }
  }
  if (state === 'ambiguous') {
    return {
      state: 'ambiguous',
      unknown: true,
      text: SYLLABUS_COPY.ambiguousValue,
      candidates: Array.isArray(item.candidates) ? item.candidates : [],
      anchors,
      anchorLabels,
      derivation: item.derivation || 'ambiguous'
    }
  }
  return {
    state: 'unknown',
    unknown: true,
    text: SYLLABUS_COPY.unknownValue,
    reason: item && item.reason ? String(item.reason) : null,
    anchors,
    anchorLabels,
    derivation: 'unknown'
  }
}

/** Weight and due date, each stated or explicitly unknown. No conversion, no arithmetic. */
function syllabusAssessmentRows(assessments) {
  return (Array.isArray(assessments) ? assessments : []).map((assessment) => {
    const rawTitle = assessment && assessment.title
    const title = syllabusItemView(
      rawTitle && typeof rawTitle === 'object'
        ? rawTitle
        : rawTitle
          ? { value: rawTitle, state: 'extracted', anchors: assessment.anchors }
          : { state: 'unknown' }
    )
    const weight = syllabusItemView((assessment && assessment.weight) || { state: 'unknown' })
    const unit = (assessment && assessment.weight_unit) || 'unknown'
    let weightText = weight.text
    if (!weight.unknown) {
      if (unit === 'percent') weightText = `${weight.text}%`
      else if (unit === 'points') weightText = `${weight.text} points`
    } else {
      weightText = SYLLABUS_COPY.unknownWeight
    }
    const due = syllabusItemView((assessment && assessment.due) || { state: 'unknown' })
    let dueText = due.text
    if (due.unknown) dueText = SYLLABUS_COPY.unknownDue
    else if (due.derivation === 'computed_from_term_start') dueText = `${due.text} (counted from your term start)`
    return {
      id: (assessment && assessment.id) || null,
      title: title.text,
      titleUnknown: title.unknown,
      kind: (assessment && assessment.kind) || 'unknown',
      due: dueText,
      dueUnknown: due.unknown,
      weight: weightText,
      weightUnknown: weight.unknown,
      weekOrdinal: assessment && assessment.week_ordinal !== undefined ? assessment.week_ordinal : null,
      anchors: (assessment && assessment.anchors) || [],
      anchorLabels: ((assessment && assessment.anchors) || []).map(syllabusAnchorLabel)
    }
  })
}

/**
 * The scope the parser proposes, with its reason. A syllabus with no term length proposes
 * nothing — the learner chooses, and the screen says why (§5).
 */
function syllabusScopeProposal(parsed) {
  const document = parsed && parsed.document ? parsed.document : parsed || {}
  const weeks = Array.isArray(document.weeks) ? document.weeks.length : 0
  const assessments = Array.isArray(document.assessments) ? document.assessments.length : 0
  if (weeks === 0) {
    return { proposal: null, reason: 'Your file does not list weeks, so Coursebook cannot propose a length. Choose one.', weeks, assessments }
  }
  if (weeks === 1) {
    return { proposal: 'single', reason: 'Your file covers one week, so one lesson is enough — you can choose a short course instead.', weeks, assessments }
  }
  if (weeks <= 7) {
    return { proposal: 'short', reason: `Your file lists ${weeks} weeks, so a short course fits.`, weeks, assessments }
  }
  return { proposal: 'full', reason: `Your file lists ${weeks} weeks and ${assessments} assessment${assessments === 1 ? '' : 's'}, so this is a long course; authoring runs unit by unit.`, weeks, assessments }
}

/**
 * One parsed item kind in the learner's words. The backend's `syllabus.get` serves a flat item
 * list; the review screen groups it, and the "what is missing" line never prints a raw kind.
 */
const SYLLABUS_KIND_COPY = Object.freeze({
  course_code: 'course code',
  course_title: 'course title',
  institution: 'institution',
  instructor: 'instructor',
  meeting_pattern: 'when the class meets',
  term_label: 'term name',
  term_start: 'term start',
  term_end: 'term end',
  week: 'week',
  reading: 'reading',
  assessment: 'assessment',
  learning_outcome: 'learning outcome',
  policy: 'study policy'
})

/**
 * `syllabus.get` → the review document.
 *
 * The wire carries a flat item list (`kind`, `title`, `value`, `state`, `anchors`, `week_ordinal`);
 * this groups it into the course facts, weeks, readings, assessments, outcomes and policies the
 * review renders. It composes nothing: an item the backend marks unknown stays unknown, a weight the
 * item list does not carry stays unknown, and a week's topic is only read off a title that the parse
 * wrote. Fixture documents (already in this shape) pass through unchanged.
 */
function syllabusParseView(view) {
  const source = view || {}
  if (source.document) return source
  const items = Array.isArray(source.items) ? source.items : []
  const blocks = Array.isArray(source.blocks) ? source.blocks : []
  const syllabus = source.syllabus || {}
  const run = source.parse_run || null
  const validation = (run && run.validation) || {}
  const item = (kind) => {
    const found = items.find((entry) => entry && entry.kind === kind)
    return found
      ? {
          value: found.value,
          state: found.state,
          anchors: Array.isArray(found.anchors) ? found.anchors : [],
          derivation: found.derivation || 'unknown',
          candidates: found.candidates,
          item_id: found.item_id
        }
      : { state: 'unknown', anchors: [], derivation: 'unknown' }
  }
  const weekItems = items.filter((entry) => entry && entry.kind === 'week')
  const weeks = weekItems.map((entry) => {
    const title = String(entry.title || '')
    const split = title.indexOf(':')
    const label = (split >= 0 ? title.slice(0, split) : title).trim()
    const topic = split >= 0 ? title.slice(split + 1).trim() : ''
    return {
      ordinal: { value: entry.value, state: entry.state, anchors: entry.anchors || [], derivation: entry.derivation || 'unknown' },
      weekOrdinal: entry.week_ordinal === undefined ? null : entry.week_ordinal,
      label: label ? { value: label, state: 'extracted', anchors: entry.anchors || [] } : { state: 'unknown', anchors: [] },
      topic: topic ? { value: topic, state: 'extracted', anchors: entry.anchors || [] } : { state: 'unknown', anchors: [] },
      anchors: Array.isArray(entry.anchors) ? entry.anchors : [],
      readings: items.filter((candidate) => candidate.kind === 'reading' && candidate.week_ordinal === entry.week_ordinal),
      assessments: []
    }
  })
  // An assessment with no due date is stored twice: the title row and a `"<title> (due)"` row that
  // carries the unknown. The companion row is folded back into its title; it is never a second
  // assessment, and it never invents a date.
  const assessments = []
  for (const entry of items.filter((candidate) => candidate && candidate.kind === 'assessment')) {
    const title = String(entry.title || '')
    const due = /^(.*) \(due\)$/.exec(title)
    if (due) {
      const parent = assessments.find(
        (row) => row.baseTitle === due[1].trim() && row.week_ordinal === entry.week_ordinal
      )
      if (parent) {
        parent.due = {
          value: entry.value,
          state: entry.state,
          anchors: Array.isArray(entry.anchors) ? entry.anchors : [],
          derivation: entry.derivation || 'unknown'
        }
        continue
      }
    }
    const row = {
      id: entry.item_id || null,
      baseTitle: title,
      title: {
        value: entry.value,
        state: entry.state,
        anchors: Array.isArray(entry.anchors) ? entry.anchors : [],
        derivation: entry.derivation || 'unknown'
      },
      kind: 'assessment',
      due: { state: 'unknown', anchors: [], derivation: 'unknown' },
      weight: { state: 'unknown', anchors: [], derivation: 'unknown' },
      weight_unit: 'unknown',
      week_ordinal: entry.week_ordinal === undefined ? null : entry.week_ordinal,
      anchors: Array.isArray(entry.anchors) ? entry.anchors : []
    }
    assessments.push(row)
    const week = weeks.find((candidate) => candidate.weekOrdinal === entry.week_ordinal)
    if (week) week.assessments.push(row)
  }
  const listOf = (kind) =>
    items
      .filter((entry) => entry && entry.kind === kind)
      .map((entry) => ({
        value: entry.value,
        state: entry.state,
        anchors: Array.isArray(entry.anchors) ? entry.anchors : [],
        derivation: entry.derivation || 'unknown'
      }))
  const unknowns = []
  for (const entry of items) {
    if (!entry || entry.state !== 'unknown') continue
    const label = SYLLABUS_KIND_COPY[entry.kind] || 'item'
    const title = entry.title && !/ \(due\)$/.test(String(entry.title)) ? ` (${entry.title})` : ''
    unknowns.push(`${label}${title}`)
  }
  const warnings = []
  const mismatches = Number(validation.anchor_mismatches || 0)
  if (mismatches > 0) {
    warnings.push(
      `${mismatches} item${mismatches === 1 ? '' : 's'} could not be tied to a quote in your file. They are shown as not stated rather than guessed.`
    )
  }
  return {
    syllabus_id: syllabus.syllabus_id || null,
    revision: syllabus.revision === undefined ? null : syllabus.revision,
    content_sha256: syllabus.content_sha256 || null,
    parse_state: run ? (run.state === 'needs_review' ? 'needs_review' : 'parsed') : null,
    parse_run: run,
    warnings,
    blocks,
    coverage: source.coverage || {},
    unknowns: [...new Set(unknowns)],
    document: {
      schema: 'syllabus.parse.v1',
      course: { code: item('course_code'), title: item('course_title') },
      institution: item('institution'),
      instructor: item('instructor'),
      meeting_pattern: item('meeting_pattern'),
      term: { label: item('term_label'), start_date: item('term_start'), end_date: item('term_end') },
      weeks,
      assessments,
      learning_outcomes: listOf('learning_outcome'),
      policies: listOf('policy'),
      unknowns: [...new Set(unknowns)],
      coverage: source.coverage || {}
    }
  }
}

/** The course's own metadata, each field stated by the file or absent. Nothing is composed. */
function syllabusCourseFields(parsed) {
  const document = parsed && parsed.document ? parsed.document : parsed || {}
  const course = document.course || {}
  const code = syllabusItemView(course.code || { state: 'unknown' })
  const title = syllabusItemView(course.title || { state: 'unknown' })
  return {
    code: code.unknown ? null : code.text,
    title: title.unknown ? null : title.text,
    codeView: code,
    titleView: title,
    institution: syllabusItemView(document.institution ? document.institution : { state: 'unknown' })
  }
}

/**
 * `course.create` for a companion course (§6.2). The syllabus id and revision travel together or
 * not at all; `recipe` is always `companion` and `pack_id` is never sent, so the backend keeps
 * `courses.pack_id` NULL.
 */
function syllabusCoursePayload({ parsed, scope, goal, learnerLabel }) {
  const fields = syllabusCourseFields(parsed)
  const title = fields.title || fields.code || String(learnerLabel || '').trim() || 'Companion course'
  const payload = {
    title,
    recipe: 'companion',
    goal: String(goal || '').trim() || (fields.title ? `Support the class on ${fields.title}.` : 'Support the class described in my syllabus.'),
    dials: {},
    scope: scope || 'short'
  }
  if (parsed && parsed.syllabus_id) payload.syllabus_id = parsed.syllabus_id
  if (parsed && parsed.revision !== undefined) payload.syllabus_revision = parsed.revision
  return payload
}

/** The plan job brief: the existing brief plus the syllabus fields the contract added. */
function syllabusPlanBrief({ courseId, enrollmentId, goal, syllabusId, syllabusRevision, alignmentRevision, scope }) {
  const brief = { stage: 'plan', course_id: courseId, enrollment_id: enrollmentId, goal, recipe: 'companion', dials: {} }
  if (scope) brief.scope = scope
  if (syllabusId) brief.syllabus_id = syllabusId
  if (syllabusRevision !== undefined && syllabusRevision !== null) brief.syllabus_revision = syllabusRevision
  if (alignmentRevision !== undefined && alignmentRevision !== null) brief.alignment_revision = alignmentRevision
  return brief
}

/** `syllabus.align` between the draft plan and the parsed syllabus. */
function syllabusAlignPayload({ syllabusId, revision, courseId, planId }) {
  return { syllabus_id: syllabusId, revision: Number(revision) || 0, course_id: courseId, plan_id: planId }
}

/**
 * The alignment as the review screen shows it.
 *
 * One row per syllabus item. `aligned` and `partial` do not block; `conflict`, `stale`, and an
 * extracted item still awaiting evaluation (`unknown`) do. An item whose *value* is unknown never
 * blocks, because nothing was mapped, so nothing was invented (§4.2).
 */
function syllabusAlignmentView(alignment) {
  const source = alignment || {}
  const items = Array.isArray(source.items) ? source.items : []
  const rows = items.map((item) => {
    const state = typeof item.state === 'string' ? item.state : 'unknown'
    const copy = ALIGNMENT_STATE_COPY[state] || ALIGNMENT_STATE_COPY.unknown
    const valueState = item.value_state || item.valueState || (item.value === undefined || item.value === null ? 'unknown' : 'extracted')
    const anchors = Array.isArray(item.anchors) ? item.anchors : []
    const target = item.target || null
    const evidence = item.evidence && typeof item.evidence === 'object' ? item.evidence : {}
    const reasonCode = item.reason_code || item.reasonCode || null
    const reason =
      item.reason ||
      (reasonCode && SYLLABUS_REASON_COPY[reasonCode]) ||
      evidence.explanation ||
      copy.line
    const blocks = state === 'conflict' || state === 'stale' || (state === 'unknown' && valueState !== 'unknown')
    const actions = []
    if (state === 'partial') actions.push({ action: 'accept_partial', label: 'Accept what it covers' })
    if (state === 'unmatched') actions.push({ action: 'accept_unmatched', label: 'Accept not covered' })
    if (state === 'conflict') {
      actions.push({ action: 'accept_divergence', label: 'Accept this divergence' })
      actions.push({ action: 'request_replan', label: 'Replan to match my syllabus' })
    }
    return {
      itemId: item.item_id || item.itemId || null,
      kind: item.kind || 'item',
      title: item.title || item.value || (item.kind ? String(item.kind) : 'Syllabus item'),
      state,
      stateLabel: copy.label,
      tone: copy.tone,
      line: copy.line,
      reason,
      reasonCode,
      valueState,
      anchors,
      anchorLabels: anchors.map(syllabusAnchorLabel),
      target,
      targetLabel: target ? target.title || target.label || target.target_id || null : null,
      reviewState: item.review_state || 'pending',
      blocks,
      actions
    }
  })
  const counts = { aligned: 0, partial: 0, unmatched: 0, conflict: 0, unknown: 0, stale: 0 }
  if (source.counts && typeof source.counts === 'object') {
    for (const key of Object.keys(counts)) counts[key] = Number(source.counts[key] || 0)
  } else {
    rows.forEach((row) => {
      counts[row.state] = (counts[row.state] || 0) + 1
    })
  }
  const alignmentRevision = Number(source.alignment_revision) || 0
  const reviewedRevision = Number(source.reviewed_revision) || 0
  const stale = Boolean(source.stale) || rows.some((row) => row.state === 'stale')
  const blocking = rows.filter((row) => row.blocks)
  const awaitingReview = rows.filter((row) => row.state !== 'aligned' && row.state !== 'unknown' && row.reviewState === 'pending')
  return {
    rows,
    counts,
    stale,
    alignmentRevision,
    reviewedRevision,
    reviewComplete: alignmentRevision > 0 && reviewedRevision === alignmentRevision,
    blocking,
    awaitingReview,
    approveReady: !stale && blocking.length === 0 && alignmentRevision > 0 && reviewedRevision === alignmentRevision,
    approveBlockedReason: stale
      ? SYLLABUS_COPY.staleLead
      : blocking.length
        ? `${blocking.length} item${blocking.length === 1 ? '' : 's'} must be resolved before the plan can be approved.`
        : reviewedRevision !== alignmentRevision
          ? 'Review each item, then approve the mapping.'
          : null
  }
}

/** `syllabus.alignment.review`: the decisions, fenced to the revision the learner actually saw. */
function syllabusReviewPayload({ syllabusId, revision, courseId, alignmentRevision, decisions }) {
  const accepted = ['accept_partial', 'accept_unmatched', 'accept_divergence', 'request_replan']
  const rows = (Array.isArray(decisions) ? decisions : [])
    .filter((decision) => decision && decision.item_id && accepted.indexOf(decision.action) >= 0)
    .map((decision) => ({ item_id: decision.item_id, action: decision.action }))
  return {
    syllabus_id: syllabusId,
    revision: Number(revision) || 0,
    course_id: courseId,
    alignment_revision: Number(alignmentRevision) || 0,
    decisions: rows
  }
}

/** The revision notice. A new revision marks the old mapping stale; it never regenerates a plan. */
function syllabusStaleNotice({ revision, counts, planRevision }) {
  const pending = counts && typeof counts === 'object' ? Number(counts.conflict || 0) + Number(counts.stale || 0) : 0
  const lines = [SYLLABUS_COPY.staleLead]
  if (pending > 0) lines.push(`${pending} mapping${pending === 1 ? '' : 's'} need another look.`)
  if (planRevision !== undefined && planRevision !== null) {
    lines.push(`Your approved plan is still the one aligned to syllabus revision ${planRevision}; it stays readable.`)
  }
  lines.push(SYLLABUS_COPY.staleAction)
  return { revision: Number(revision) || 0, pending, lines, action: 'Check the new revision' }
}

/**
 * One companion course: `course.create` → `enrollment.create` → one plan job.
 *
 * The same shape as `startLearnerPlan`, with the syllabus binding and no second engine. A failed
 * plan job keeps the ids that already exist, and the same key retries the same job.
 */
async function startCompanionCourse({ call, key, parsed, scope, goal, learnerLabel }) {
  const course = await call('course.create', syllabusCoursePayload({ parsed, scope, goal, learnerLabel }), {
    idempotencyKey: key,
    expectedRevision: null
  })
  if (!course || !course.ok) return { ok: false, stage: 'course.create', error: (course && course.error) || null }
  const courseId = course.result.course_id
  const planId = course.result.plan_id || null

  const enrollment = await call(
    'enrollment.create',
    { course_id: courseId, learner_label: learnerLabel || course.result.title || 'Companion course' },
    { idempotencyKey: `${key}-enroll`, expectedRevision: null }
  )
  if (!enrollment || !enrollment.ok) {
    return { ok: false, stage: 'enrollment.create', error: (enrollment && enrollment.error) || null, courseId, planId }
  }
  const enrollmentId = enrollment.result.enrollment_id

  const job = await call(
    'jobs.create',
    {
      kind: 'plan',
      brief: syllabusPlanBrief({
        courseId,
        enrollmentId,
        goal,
        scope,
        syllabusId: parsed && parsed.syllabus_id,
        syllabusRevision: parsed && parsed.revision
      })
    },
    { idempotencyKey: `${key}-plan` }
  )
  if (!job || !job.ok) {
    return { ok: false, stage: 'jobs.create', error: (job && job.error) || null, courseId, planId, enrollmentId }
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

/** `syllabus.align` once a draft plan exists. Idempotent per (syllabus, revision, plan). */
async function queueSyllabusAlignment({ call, syllabusId, revision, courseId, planId }) {
  const response = await call(
    'syllabus.align',
    syllabusAlignPayload({ syllabusId, revision, courseId, planId }),
    { idempotencyKey: `cb-syllabus-align-${syllabusId}-${revision}-${planId}` }
  )
  if (!response || !response.ok) return { ok: false, error: (response && response.error) || null }
  return { ok: true, jobId: response.result.job_id, alignmentRevision: response.result.alignment_revision, state: response.result.state }
}

// ── surfaces ────────────────────────────────────────────────────────────────────────────────

/** A value and its anchors. An unknown is a word, not an empty cell. */
function SyllabusValue({ item, label, onAnchor }) {
  const view = syllabusItemView(item)
  return jsxs('div', {
    className: 'flex min-w-0 flex-col gap-1 py-1.5',
    'data-cb-syllabus-field': label,
    'data-cb-syllabus-state': view.state,
    children: [
      jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: label }),
      jsxs('div', {
        className: 'flex flex-wrap items-baseline gap-2',
        children: [
          jsx('div', {
            className: view.unknown ? 'text-sm italic text-(--ui-text-secondary)' : 'text-sm',
            children: view.text
          }),
          ...view.anchorLabels.map((anchorLabel, index) =>
            jsx(
              sdk.Button,
              {
                size: 'sm',
                variant: 'text',
                'aria-label': `${label} — show the source at ${anchorLabel}`,
                onClick: () => onAnchor && onAnchor({ anchors: [view.anchors[index]], label }),
                children: anchorLabel
              },
              `${label}-anchor-${index}`
            )
          )
        ]
      })
    ]
  })
}

function SyllabusAnchorPanel({ open, anchors, blocks, label, onClose }) {
  if (!open) return null
  const index = new Map((Array.isArray(blocks) ? blocks : []).map((block) => [block.block_id, block]))
  return jsxs('div', {
    className: 'mt-2 flex flex-col gap-2 border-l-2 border-(--ui-stroke-secondary) pl-3',
    'data-cb-syllabus-anchor': label || 'source',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between gap-2',
        children: [
          jsx('div', { className: 'text-xs font-semibold', children: 'Source in your file' }),
          jsx(sdk.Button, { size: 'sm', variant: 'ghost', onClick: onClose, children: 'Close source' })
        ]
      }),
      ...(Array.isArray(anchors) ? anchors : []).map((anchor, position) => {
        const block = anchor && anchor.block_id ? index.get(anchor.block_id) : null
        const text = (anchor && anchor.quote) || (block && block.text) || null
        return jsxs(
          'div',
          {
            className: 'flex flex-col gap-0.5',
            children: [
              jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: syllabusAnchorLabel(anchor) }),
              jsx('div', {
                className: 'whitespace-pre-wrap break-words text-sm',
                children: text || 'That quote is no longer in this copy of your file.'
              })
            ]
          },
          `anchor-${position}`
        )
      }),
      jsx('div', {
        className: 'text-xs text-(--ui-text-secondary)',
        children: 'This is the text the item was read from. If it does not match, the item is wrong.'
      })
    ]
  })
}

function SyllabusWeekRow({ week, onAnchor }) {
  // A parse item (`{value,state,anchors}`) and a hand-written fixture (a plain ordinal or string)
  // are both honourd; neither is turned into a value the file did not state.
  const asItem = (value, anchors) =>
    value && typeof value === 'object' && !Array.isArray(value)
      ? value
      : value === undefined || value === null || value === ''
        ? { state: 'unknown', anchors: anchors || [] }
        : { value, state: 'extracted', anchors: anchors || [], derivation: 'explicit' }
  const ordinal = syllabusItemView(asItem(week && week.ordinal, week && week.anchors))
  const label = syllabusItemView(asItem(week && week.label, week && week.anchors))
  // `topic` is an item in the parse document and a plain string in a hand-written fixture: both
  // shapes are honoured, and neither is turned into a value the file did not state.
  const topic = syllabusItemView(asItem(week && week.topic, week && week.anchors))
  const readings = (week && Array.isArray(week.readings) ? week.readings : []).map((entry) =>
    syllabusItemView(asItem(entry, week && week.anchors))
  )
  return jsxs('div', {
    className: 'flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
    'data-cb-syllabus-week': ordinal.unknown ? label.text : ordinal.text,
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-baseline gap-2',
        children: [
          jsx('div', { className: 'text-sm font-medium', children: ordinal.unknown ? label.text : `Week ${ordinal.text}` }),
          label.unknown ? null : jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: label.text }),
          ...topic.anchorLabels.map((anchorLabel, index) =>
            jsx(sdk.Button, { size: 'sm', variant: 'text', onClick: () => onAnchor && onAnchor({ anchors: [topic.anchors[index]], label: 'the week' }), children: anchorLabel }, `w-${index}`)
          )
        ]
      }),
      jsx('div', { className: topic.unknown ? 'text-sm italic text-(--ui-text-secondary)' : 'text-sm', children: topic.text }),
      readings.length
        ? jsx('div', {
            className: 'text-xs text-(--ui-text-secondary)',
            children: `Reading: ${readings.map((entry) => entry.text).join('; ')}`
          })
        : null
    ]
  })
}

/**
 * The parse review: course facts, outcomes, weeks, assessments, then what the file does not
 * state. The coverage line is measured by the backend; the sentence is the design's own.
 */
function SyllabusParseReview({ parsed, blocks, onContinue, onBack, onReparse, busy, continueLabel }) {
  const [anchor, setAnchor] = useState(null)
  const document = parsed && parsed.document ? parsed.document : parsed || {}
  const fields = syllabusCourseFields(document)
  const outcomes = (Array.isArray(document.learning_outcomes) ? document.learning_outcomes : []).map(syllabusItemView)
  const weeks = Array.isArray(document.weeks) ? document.weeks : []
  const assessments = syllabusAssessmentRows(document.assessments)
  const policies = (Array.isArray(document.policies) ? document.policies : []).map(syllabusItemView)
  const unknowns = Array.isArray(document.unknowns) ? document.unknowns : []
  const coverage = document.coverage || {}
  const needsReview = (parsed && parsed.parse_state) === 'needs_review'
  const warnings = Array.isArray(parsed && parsed.warnings) ? parsed.warnings : []

  return jsxs('div', {
    className: 'flex flex-col gap-4',
    'data-cb-syllabus': 'parse-review',
    children: [
      jsxs('div', { className: 'flex flex-col gap-1', children: [
        jsx('div', { className: 'text-sm font-semibold', children: 'What Coursebook read from your syllabus' }),
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.parseSentence }),
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.notOfficial })
      ] }),
      needsReview
        ? jsxs('div', {
            className: 'flex flex-col gap-1 border-l-2 border-(--ui-stroke-secondary) pl-3',
            'data-cb-syllabus': 'parse-warning',
            children: [
              jsx('div', { className: 'text-sm font-medium', children: 'Check these items before you continue' }),
              jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.parseNeedsReview })
            ]
          })
        : null,
      ...warnings.slice(0, 6).map((warning, index) =>
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: String(warning) }, `warning-${index}`)
      ),
      jsxs('div', {
        className: 'grid grid-cols-1 gap-x-8 gap-y-1 min-[47.5rem]:grid-cols-2',
        children: [
          jsx(SyllabusValue, { item: document.course && document.course.code, label: 'Course code', onAnchor: setAnchor }),
          jsx(SyllabusValue, { item: document.course && document.course.title, label: 'Course title', onAnchor: setAnchor }),
          jsx(SyllabusValue, { item: document.institution, label: 'Institution', onAnchor: setAnchor }),
          jsx(SyllabusValue, { item: document.instructor, label: 'Instructor', onAnchor: setAnchor }),
          jsx(SyllabusValue, { item: document.meeting_pattern, label: 'When it meets', onAnchor: setAnchor }),
          jsx(SyllabusValue, { item: document.term && document.term.start_date, label: 'Term starts', onAnchor: setAnchor }),
          jsx(SyllabusValue, { item: document.term && document.term.end_date, label: 'Term ends', onAnchor: setAnchor })
        ]
      }),
      anchor ? jsx(SyllabusAnchorPanel, { open: true, anchors: anchor.anchors, blocks, label: anchor.label, onClose: () => setAnchor(null) }) : null,
      jsx(CbLabel, { children: 'Learning outcomes in your file' }),
      outcomes.length
        ? jsxs('div', { className: 'flex flex-col', children: outcomes.map((outcome, index) =>
            jsxs('div', { className: 'flex flex-col gap-0.5 border-b border-(--ui-stroke-tertiary) py-1.5 last:border-b-0', children: [
              jsx('div', { className: outcome.unknown ? 'text-sm italic text-(--ui-text-secondary)' : 'text-sm', children: outcome.text }),
              jsxs('div', { className: 'flex flex-wrap gap-2', children: outcome.anchorLabels.map((label, position) =>
                jsx(sdk.Button, { size: 'sm', variant: 'text', onClick: () => setAnchor({ anchors: [outcome.anchors[position]], label: 'an outcome' }), children: label }, `o-${index}-${position}`)) })
            ] }, `outcome-${index}`)) })
        : jsx(sdk.PanelEmpty, { children: 'Your file does not list learning outcomes.' }),
      jsx(CbLabel, { children: 'Weeks' }),
      weeks.length
        ? jsx('div', { className: 'flex flex-col', children: weeks.map((week, index) => jsx(SyllabusWeekRow, { week, onAnchor: setAnchor }, `week-${index}`)) })
        : jsx(sdk.PanelEmpty, { children: 'Your file does not list weeks.' }),
      jsx(CbLabel, { children: 'Assessments and weights' }),
      assessments.length
        ? jsx('div', {
            className: 'flex flex-col',
            children: assessments.map((row, index) =>
              jsxs('div', {
                className: 'flex flex-col gap-0.5 border-b border-(--ui-stroke-tertiary) py-1.5 last:border-b-0',
                'data-cb-syllabus-assessment': row.title,
                children: [
                  jsxs('div', { className: 'flex flex-wrap items-baseline gap-2', children: [
                    jsx('div', { className: row.titleUnknown ? 'text-sm italic text-(--ui-text-secondary)' : 'text-sm font-medium', children: row.title }),
                    jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: row.due }),
                    jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: row.weight })
                  ] }),
                  jsxs('div', { className: 'flex flex-wrap gap-2', children: row.anchorLabels.map((label, position) =>
                    jsx(sdk.Button, { size: 'sm', variant: 'text', onClick: () => setAnchor({ anchors: [row.anchors[position]], label: 'an assessment' }), children: label }, `a-${index}-${position}`)) })
                ]
              }, `assessment-${index}`)
            )
          })
        : jsx(sdk.PanelEmpty, { children: 'Your file does not list assessments.' }),
      jsx(CbLabel, { children: 'Policies your file states' }),
      policies.length
        ? jsx('div', { className: 'flex flex-col', children: policies.map((policy, index) =>
            jsx('div', { className: 'max-w-prose border-b border-(--ui-stroke-tertiary) py-1.5 text-sm last:border-b-0', children: policy.text }, `policy-${index}`)) })
        : jsx(sdk.PanelEmpty, { children: 'Your file does not state study policies Coursebook can quote.' }),
      jsx(CbLabel, { children: 'What your file does not state' }),
      unknowns.length
        ? jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: unknowns.join(' · ') })
        : jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: 'Nothing was left out by this parse.' }),
      jsx('div', {
        className: 'text-xs text-(--ui-text-secondary)',
        'data-cb-syllabus-coverage': `${coverage.pages || 0}/${coverage.items_total || 0}/${coverage.items_extracted || 0}`,
        children: coverage.pages
          ? `Read from ${coverage.pages} page${coverage.pages === 1 ? '' : 's'}: ${coverage.items_extracted || 0} of ${coverage.items_total || 0} items had a quote in your file.`
          : 'The backend did not report coverage for this parse.'
      }),
      jsxs('div', { className: 'flex flex-wrap items-center gap-2 border-t border-(--ui-stroke-tertiary) pt-3', children: [
        jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: onBack, children: 'Back' }),
        onReparse ? jsx(sdk.Button, { size: 'sm', variant: 'ghost', onClick: onReparse, disabled: Boolean(busy), children: 'Read it again' }) : null,
        jsx(CbAction, {
          variant: 'primary',
          disabled: Boolean(busy) || needsReview,
          onClick: onContinue,
          children: continueLabel || 'Confirm these details'
        })
      ] })
    ]
  })
}

/** The authority sentence, the counts, then one row per item with its reason and source. */
function SyllabusAlignmentReview({ alignment, onDecision, onApprove, onRealign, busy }) {
  const [anchor, setAnchor] = useState(null)
  const view = syllabusAlignmentView(alignment)
  const countsLine = ['aligned', 'partial', 'unmatched', 'conflict', 'unknown', 'stale']
    .filter((state) => Number(view.counts[state] || 0) > 0)
    .map((state) => `${view.counts[state]} ${(ALIGNMENT_STATE_COPY[state] || ALIGNMENT_STATE_COPY.unknown).label.toLowerCase()}`)
    .join(' · ')
  return jsxs('div', {
    className: 'flex flex-col gap-3',
    'data-cb-syllabus': 'alignment',
    'data-cb-syllabus-approve': view.approveReady ? 'ready' : 'blocked',
    children: [
      jsxs('div', { className: 'flex flex-col gap-1', children: [
        jsx('div', { className: 'text-sm font-semibold', children: 'How the course maps to your syllabus' }),
        jsx('div', { className: 'max-w-prose text-sm', 'data-cb-syllabus': 'authority', children: SYLLABUS_COPY.authority }),
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.alignmentGate })
      ] }),
      view.stale
        ? jsxs('div', {
            className: 'flex flex-col gap-1 border-l-2 border-(--ui-stroke-secondary) pl-3',
            'data-cb-syllabus': 'stale',
            children: [
              jsx('div', { className: 'text-sm font-medium', children: 'This mapping is out of date' }),
              jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.staleAction }),
              onRealign ? jsx(sdk.Button, { className: 'self-start', size: 'sm', variant: 'secondary', onClick: onRealign, disabled: Boolean(busy), children: 'Check the new revision' }) : null
            ]
          })
        : null,
      jsx('div', { className: 'text-xs text-(--ui-text-secondary)', 'data-cb-syllabus-counts': countsLine, children: countsLine || 'The backend reported no items to align.' }),
      view.rows.length
        ? jsx('div', { className: 'flex flex-col', children: view.rows.map((row, index) =>
            jsxs('div', {
              className: 'flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
              'data-cb-align-row': row.state,
              'data-cb-align-item': row.itemId || `row-${index}`,
              children: [
                jsxs('div', { className: 'flex flex-wrap items-baseline gap-2', children: [
                  jsx('div', { className: 'text-sm font-medium', children: row.title }),
                  jsx(sdk.Badge, { variant: row.tone === 'bad' ? 'warn' : row.tone === 'ok' ? 'muted' : 'outline', size: 'xs', children: row.stateLabel }),
                  row.targetLabel ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: `→ ${row.targetLabel}` }) : null
                ] }),
                jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: row.reason }),
                jsxs('div', { className: 'flex flex-wrap items-center gap-2', children: [
                  row.anchorLabels.map((label, position) =>
                    jsx(sdk.Button, {
                      size: 'sm',
                      variant: 'text',
                      onClick: () => setAnchor({ anchors: [row.anchors[position]], label: row.title }),
                      children: label
                    }, `anchor-${position}`)),
                  row.actions.map((entry) =>
                    jsx(sdk.Button, {
                      size: 'sm',
                      variant: 'secondary',
                      disabled: Boolean(busy),
                      onClick: () => onDecision && onDecision({ item_id: row.itemId, action: entry.action }),
                      children: entry.label
                    }, entry.action))
                ] })
              ]
            }, row.itemId || `row-${index}`)) })
        : jsx(sdk.PanelEmpty, { children: 'Nothing has been mapped yet. Run the alignment against a draft plan first.' }),
      anchor ? jsx(SyllabusAnchorPanel, { open: true, anchors: anchor.anchors, blocks: alignment && alignment.blocks, label: anchor.label, onClose: () => setAnchor(null) }) : null,
      jsxs('div', { className: 'flex flex-wrap items-center gap-2 border-t border-(--ui-stroke-tertiary) pt-3', children: [
        jsx(CbAction, {
          variant: 'primary',
          disabled: Boolean(busy) || !view.approveReady,
          onClick: onApprove,
          children: 'Approve this mapping'
        }),
        view.approveBlockedReason
          ? jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', 'data-cb-syllabus': 'approve-reason', children: view.approveBlockedReason })
          : jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'Approved. The plan can be approved on the Plan tab.' })
      ] })
    ]
  })
}

/**
 * The plan-tab gate, as one value both the panel and a test can read.
 *
 * `plan.approve` on a companion course is refused by the backend until the bound syllabus revision
 * has been reviewed and no mapping row is stale. The UI predicts exactly that so the button is
 * disabled with a reason instead of failing after a click; the backend remains the authority.
 */
function syllabusPlanGate({ binding, planState, rowsReady }) {
  if (!binding) return { required: false, ready: true, reason: null, stale: false }
  const stale = Boolean(binding.stale)
  const reviewed =
    binding.reviewed_revision !== null &&
    binding.reviewed_revision !== undefined &&
    Number(binding.reviewed_revision) === Number(binding.revision)
  const ready = Boolean(reviewed) && !stale
  const reason = stale
    ? 'Your syllabus changed. This course stays as it was until the new revision is mapped and reviewed; approval is blocked.'
    : !rowsReady
      ? 'Map the draft plan to your syllabus before approving it.'
      : !reviewed
        ? 'Review the mapping on this tab before approving the plan.'
        : null
  return { required: true, ready, reason, stale }
}

/**
 * The alignment gate on a companion course's plan tab.
 *
 * It reads the binding from `course.get`, the parsed document from `syllabus.get` and the mapping
 * from `syllabus.alignment.get`. Mapping is an explicit click once a draft plan exists (the plan is
 * the thing being mapped), the learner's decisions go through `syllabus.alignment.review`, and the
 * component reports to its parent whether `plan.approve` may be pressed. It never regenerates a
 * plan, never re-aligns after a revision change on its own, and never hides a stale mapping.
 */
function SyllabusAlignmentPanel({ course, planId, planState, reloadSignal, onGateChange, onChanged, onNewSyllabus }) {
  const supports = (method) => (typeof backendSupports === 'function' ? backendSupports(method) : false)
  const signal = Number(reloadSignal || 0)
  const bindingQuery = useRpcQuery(
    'course.get',
    { course_id: course.course_id },
    `cb-syl-binding-${course.course_id}-${signal}`,
    supports('course.get') && supports('syllabus.alignment.get')
  )
  const binding =
    bindingQuery.data && bindingQuery.data.course && bindingQuery.data.course.syllabus
      ? bindingQuery.data.course.syllabus
      : null
  const syllabusId = binding ? binding.syllabus_id : null
  const syllabusRevision = binding ? binding.revision : null
  const documentQuery = useRpcQuery(
    'syllabus.get',
    { syllabus_id: syllabusId, revision: syllabusRevision, include_blocks: true },
    `cb-syl-doc-${syllabusId}-${syllabusRevision}-${signal}`,
    Boolean(syllabusId) && supports('syllabus.get')
  )
  const alignmentQuery = useRpcQuery(
    'syllabus.alignment.get',
    { syllabus_id: syllabusId, revision: syllabusRevision, course_id: course.course_id },
    `cb-syl-align-${syllabusId}-${syllabusRevision}-${course.course_id}-${signal}`,
    Boolean(syllabusId) && supports('syllabus.alignment.get')
  )
  const [decisions, setDecisions] = useState({})
  const [busy, setBusy] = useState(false)
  const [aligning, setAligning] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const alignment = alignmentQuery.data || null
  const view = alignment ? syllabusAlignmentView(alignment) : null
  const blocks = (documentQuery.data && documentQuery.data.blocks) || (alignment && alignment.blocks) || []
  const needsDecision = view
    ? view.rows.filter(
        (row) =>
          row.reviewState === 'pending' &&
          ['partial', 'unmatched', 'conflict'].includes(row.state) &&
          row.valueState !== 'unknown'
      )
    : []
  const stale = Boolean((binding && binding.stale) || (view && view.stale))
  const rowsReady = Boolean(view && view.rows.length > 0)
  const gate = syllabusPlanGate({ binding, planState, rowsReady })
  const gateReady = gate.ready
  const gateReason = gate.reason

  useEffect(() => {
    if (onGateChange) {
      onGateChange({ required: Boolean(binding), ready: gateReady, reason: gateReason, stale })
    }
  }, [binding, gateReady, gateReason, stale, onGateChange])

  // Mapping runs as the existing import job; the screen polls the alignment read instead of
  // inventing a percentage for a job that reports state only.
  useEffect(() => {
    if (!aligning) return undefined
    let attempts = 0
    const handle = setInterval(() => {
      attempts += 1
      alignmentQuery.reload()
      if (attempts >= 40) setAligning(false)
    }, 1500)
    return () => clearInterval(handle)
  }, [aligning, alignmentQuery.reload])

  useEffect(() => {
    if (view && view.rows.length > 0 && aligning) setAligning(false)
  }, [view, aligning])

  const mapPlan = useCallback(async () => {
    if (!planId || !syllabusId) return
    setBusy(true)
    setError(null)
    setNotice(null)
    const outcome = await queueSyllabusAlignment({
      call: rpc,
      syllabusId,
      revision: syllabusRevision,
      courseId: course.course_id,
      planId
    })
    setBusy(false)
    if (!outcome.ok) {
      setError(outcome.error || { code: 'INTERNAL_ERROR', message: 'The mapping job could not be started.' })
      return
    }
    setAligning(true)
    setNotice('Mapping the plan to your syllabus. This runs on this device; the rows appear when it finishes.')
    alignmentQuery.reload()
  }, [planId, syllabusId, syllabusRevision, course.course_id, alignmentQuery.reload])

  const review = useCallback(async () => {
    if (!view || !syllabusId) return
    const payload = syllabusReviewPayload({
      syllabusId,
      revision: syllabusRevision,
      courseId: course.course_id,
      alignmentRevision: view.alignmentRevision,
      decisions: needsDecision.map((row) => ({ item_id: row.itemId, action: decisions[row.itemId] })).filter((row) => row.action)
    })
    if (payload.decisions.length === 0) {
      setError({ code: 'SYLLABUS_UNREVIEWED', message: 'Every item already needs no decision. The backend records a review only from an accepted item, so approval cannot be recorded for this mapping.' })
      return
    }
    setBusy(true)
    setError(null)
    const response = await rpc('syllabus.alignment.review', payload, { idempotencyKey: newOperationId('syllabus-review') })
    setBusy(false)
    if (!response.ok) {
      const nextRevision = staleRevision(response)
      if (nextRevision !== null) alignmentQuery.reload()
      setError(response.error || { code: 'INTERNAL_ERROR', message: 'The review was not recorded.' })
      return
    }
    const result = response.result || {}
    if (result.plan_replan_required) {
      setNotice('The plan needs to change to match your syllabus. Start a new plan version, then map it again. Your current plan is unchanged.')
    } else if (result.reviewed_revision !== null && result.reviewed_revision !== undefined) {
      setNotice('Mapping approved. The plan can now be approved on this tab.')
    } else {
      setNotice('Some items still need a decision before the mapping is approved.')
    }
    bindingQuery.reload()
    alignmentQuery.reload()
    if (onChanged) onChanged()
  }, [view, syllabusId, syllabusRevision, course.course_id, needsDecision, decisions, alignmentQuery, bindingQuery, onChanged])

  const decide = useCallback((itemId, action) => {
    setDecisions((previous) => ({ ...previous, [itemId]: action }))
  }, [])

  if (bindingQuery.status === 'error' && !bindingQuery.data) {
    return jsx(sdk.ErrorState, {
      title: 'The syllabus binding could not be read',
      description: `${bindingQuery.error && bindingQuery.error.code ? bindingQuery.error.code + ': ' : ''}${describeError(bindingQuery.error)}`,
      children: jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: bindingQuery.reload, children: 'Try again' })
    })
  }
  if (!binding) return null
  if (!planId) {
    return jsx('div', {
      className: 'max-w-prose text-xs text-(--ui-text-secondary)',
      'data-cb-align-panel': 'waiting',
      children: 'Your syllabus is attached to this course. The matching appears once the draft plan is written; nothing is matched against a template.'
    })
  }

  return jsxs('div', {
    className: 'flex flex-col gap-3 border-t border-(--ui-stroke-tertiary) pt-3',
    'data-cb-align-panel': gateReady ? 'ready' : 'blocked',
    children: [
      stale
        ? jsxs('div', {
            className: 'flex flex-col gap-1 border-l-2 border-(--ui-stroke-secondary) pl-3',
            'data-cb-align-stale': 'true',
            children: [
              jsx('div', { className: 'text-sm font-medium', children: 'Your syllabus has a new revision' }),
              jsx('div', {
                className: 'max-w-prose text-xs text-(--ui-text-secondary)',
                children:
                  syllabusStaleNotice({ revision: syllabusRevision, counts: (alignment && alignment.counts) || {}, planRevision: syllabusRevision }).lines.join(' ')
              }),
              onNewSyllabus
                ? jsx(sdk.Button, {
                    className: 'self-start',
                    size: 'sm',
                    variant: 'secondary',
                    onClick: () => onNewSyllabus({ syllabusId, revision: syllabusRevision, courseId: course.course_id, enrollmentId: course.enrollment_id }),
                    children: 'Upload the new syllabus'
                  })
                : null
            ]
          })
        : null,
      !rowsReady && !aligning
        ? jsxs('div', { className: 'flex flex-col gap-2', children: [
            jsx('div', { className: 'text-sm font-semibold', children: 'Map this plan to your syllabus' }),
            jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.alignmentGate }),
            jsx(CbAction, {
              className: 'self-start',
              variant: 'primary',
              disabled: busy || stale,
              onClick: mapPlan,
              children: 'Map the plan to my syllabus'
            })
          ] })
        : null,
      aligning && !rowsReady
        ? jsxs('div', { className: 'flex flex-col gap-2', children: [
            jsx(sdk.Loader, { label: 'Mapping the plan to your syllabus' }),
            jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: 'The mapping runs on this device and is built from validated items only. There is no percentage to show.' })
          ] })
        : null,
      rowsReady
        ? jsx(SyllabusAlignmentReview, {
            alignment: { ...alignment, blocks },
            busy,
            onDecision: (decision) => decide(decision.item_id, decision.action),
            onApprove: review,
            onRealign: stale ? null : mapPlan
          })
        : null,
      needsDecision.length
        ? jsx('div', {
            className: 'max-w-prose text-xs text-(--ui-text-secondary)',
            children: `${needsDecision.filter((row) => decisions[row.itemId]).length} of ${needsDecision.length} items have a decision. Every partly covered, uncovered or conflicting item needs one before the mapping is approved.`
          })
        : null,
      notice ? jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: notice }) : null,
      error
        ? jsx(sdk.ErrorState, {
            title: error.code || 'The mapping could not be recorded',
            description: error.message || describeError(error)
          })
        : null
    ]
  })
}

/**
 * Intake. The file door is feature-detected: a build without a byte-reading door gets the honest
 * sentence and the paste box, never a picker that cannot deliver. Every refusal is the backend's
 * typed code with a readable sentence, and cancellation stops before the next call.
 */
function SyllabusIntakeFlow({ onCancel, onCreated, onParsed, supersedes, revisionOnly }) {
  const supersedesId = supersedes && supersedes.syllabusId ? supersedes.syllabusId : null
  const [step, setStep] = useState('choose')
  const [pasted, setPasted] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [syllabus, setSyllabus] = useState(null)
  const [parseJob, setParseJob] = useState(null)
  const [parsed, setParsed] = useState(null)
  const [cancelled, setCancelled] = useState(false)
  const [ack, setAck] = useState(false)
  const [door, setDoor] = useState('unknown')
  const cancelledRef = useRef(false)

  useEffect(() => {
    const files = pluginContext && pluginContext.files
    const canRead =
      files &&
      typeof files.readText === 'function' &&
      typeof files.readDataUrl === 'function' &&
      typeof files.requestFolder === 'function'
    setDoor(canRead ? 'available' : 'absent')
  }, [])

  const refuse = useCallback((failure) => {
    const code = failure && failure.code ? failure.code : 'HOST_UNAVAILABLE'
    const message = failure && failure.message ? failure.message : describeError(failure)
    setError({ code, message })
  }, [])

  const submitPasted = useCallback(async () => {
    if (busy || cancelledRef.current) return
    const built = syllabusIntakePayload({ pastedText: pasted, supersedesSyllabusId: supersedesId })
    if (!built.ok) {
      refuse(built.error)
      return
    }
    setBusy(true)
    setError(null)
    setStep('reading')
    try {
      const created = await rpc('syllabus.intake.create', built.payload, {
        idempotencyKey: `cb-syllabus-intake-${newOperationId('intake')}`,
        expectedRevision: null
      })
      if (cancelledRef.current) return
      if (!created.ok) {
        refuse(created.error)
        setStep('choose')
        return
      }
      setSyllabus(created.result)
      const job = await rpc('syllabus.parse', {
        syllabus_id: created.result.syllabus_id,
        revision: created.result.revision,
        egress_acknowledged: true
      }, { idempotencyKey: `cb-syllabus-parse-${created.result.syllabus_id}-${created.result.revision}-${created.result.content_sha256}` })
      if (cancelledRef.current) return
      if (!job.ok) {
        refuse(job.error)
        setStep('choose')
        return
      }
      setParseJob(job.result)
      onParsed && onParsed(created.result)
      setStep('parsing')
    } catch (failure) {
      refuse({ code: 'HOST_UNAVAILABLE', message: describeError(failure) })
      setStep('choose')
    } finally {
      setBusy(false)
    }
  }, [busy, pasted, refuse, onParsed, supersedesId])

  const openFile = useCallback(async () => {
    const files = pluginContext && pluginContext.files
    if (!files || typeof files.requestFolder !== 'function') {
      setDoor('absent')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const picked = await files.requestFolder()
      if (cancelledRef.current) return
      if (!picked || !picked.ok || !picked.folder) {
        if (picked && picked.message) refuse({ code: 'HOST_UNAVAILABLE', message: picked.message })
        return
      }
      const listing = await files.list(picked.folder.id)
      if (!listing || !listing.ok) {
        refuse({ code: 'HOST_UNAVAILABLE', message: (listing && listing.message) || 'That folder could not be read.' })
        return
      }
      const entry = (listing.entries || []).find((candidate) => !candidate.isDirectory && syllabusAcceptEntry(candidate.name))
      if (!entry) {
        refuse({ code: 'SYLLABUS_REJECTED', message: 'No Markdown, text, PDF or Word file was in that folder.' })
        return
      }
      const acceptable = syllabusAcceptEntry(entry.name)
      const read = acceptable.text
        ? await files.readText(picked.folder.id, entry.path)
        : await files.readDataUrl(picked.folder.id, entry.path)
      if (cancelledRef.current) return
      if (!read || !read.ok) {
        refuse({ code: (read && read.code) || 'HOST_UNAVAILABLE', message: (read && read.message) || 'The host could not read that file.' })
        return
      }
      const built = syllabusIntakePayload(
        acceptable.text
          ? { fileName: entry.name, text: read.text, supersedesSyllabusId: supersedesId }
          : { fileName: entry.name, dataUrl: read.dataUrl, supersedesSyllabusId: supersedesId }
      )
      if (!built.ok) {
        refuse(built.error)
        return
      }
      await sendIntake(built.payload)
    } catch (failure) {
      refuse({ code: 'HOST_UNAVAILABLE', message: describeError(failure) })
    } finally {
      setBusy(false)
    }
  }, [supersedesId])

  const sendIntake = useCallback(async (payload) => {
    const created = await rpc('syllabus.intake.create', payload, {
      idempotencyKey: `cb-syllabus-intake-${newOperationId('intake')}`,
      expectedRevision: null
    })
    if (!created.ok) {
      refuse(created.error)
      return
    }
    setSyllabus(created.result)
    const job = await rpc('syllabus.parse', {
      syllabus_id: created.result.syllabus_id,
      revision: created.result.revision,
      egress_acknowledged: true
    }, { idempotencyKey: `cb-syllabus-parse-${created.result.syllabus_id}-${created.result.revision}-${created.result.content_sha256}` })
    if (!job.ok) {
      refuse(job.error)
      return
    }
    setParseJob(job.result)
    onParsed && onParsed(created.result)
    setStep('parsing')
  }, [refuse, onParsed])

  // Cancelling before the backend has minted a parse job is honest only if it says why: nothing
  // further is sent from this screen, and there is no job id here to stop. Once a job exists the
  // parse stage owns the cancel so its answer is rendered instead of assumed.
  const cancelBeforeJob = useCallback(() => {
    cancelledRef.current = true
    setCancelled(true)
  }, [])

  if (step === 'parsing' || step === 'parsed') {
    return jsx(SyllabusParseStage, {
      syllabus,
      jobId: parseJob && parseJob.job_id,
      parsed,
      revisionOnly,
      onParsed: setParsed,
      onStep: setStep,
      onCancel: onCancel,
      onCreated,
      door: door,
      busy,
      error,
      refuse
    })
  }

  return jsxs('div', {
    className: 'flex flex-col gap-3',
    'data-cb-syllabus': 'intake',
    children: [
      jsxs('div', { className: 'flex flex-col gap-1', children: [
        jsx('div', { className: 'text-sm font-semibold', children: SYLLABUS_COPY.action }),
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.entryBody }),
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.acceptTypes })
      ] }),
      door === 'absent'
        ? jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', 'data-cb-syllabus': 'no-file-door', children: SYLLABUS_COPY.noFileDoor })
        : null,
      jsxs('div', { className: 'flex flex-wrap items-center gap-2', children: [
        door === 'available'
          ? jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: openFile, disabled: busy, children: 'Choose a syllabus file' })
          : null,
        jsx(sdk.Button, { size: 'sm', variant: 'ghost', onClick: cancelBeforeJob, children: 'Cancel' })
      ] }),
      jsxs('div', { className: 'flex flex-col gap-1', children: [
        jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'Or paste the syllabus text' }),
        jsx(sdk.Textarea, {
          'aria-label': 'Paste your syllabus text',
          value: pasted,
          rows: 8,
          onChange: (event) => setPasted(event && event.target ? event.target.value : '')
        }),
        jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: `${pasted.length.toLocaleString()} of ${SYLLABUS_LIMITS.text_chars.toLocaleString()} characters` })
      ] }),
      jsxs('div', { className: 'flex items-start gap-2', children: [
        jsx(sdk.Checkbox, {
          id: 'cb-syllabus-egress',
          'aria-label': 'Acknowledge that the extracted text goes to my configured model provider',
          checked: ack,
          onCheckedChange: setAck
        }),
        jsx('div', {
          className: 'max-w-prose text-xs text-(--ui-text-secondary)',
          'data-cb-syllabus': 'egress',
          children: SYLLABUS_COPY.storage
        })
      ] }),
      jsx(CbAction, {
        className: 'self-start',
        variant: 'primary',
        disabled: busy || !ack || pasted.trim().length === 0,
        onClick: submitPasted,
        children: busy ? 'Reading your syllabus' : 'Use this text'
      }),
      error
        ? jsx(sdk.ErrorState, { title: error.code, description: error.message })
        : null,
      cancelled
        ? jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'cancelled-before-job', children: [
          jsx('div', {
            className: 'max-w-prose text-xs text-(--ui-text-secondary)',
            children: 'Cancelled. Nothing further was sent — no parse job had been recorded here, so there was nothing to stop.'
          }),
          jsx(sdk.Button, { className: 'self-start', size: 'sm', variant: 'secondary', onClick: onCancel, children: 'Close' })
        ] })
        : null
    ]
  })
}

/** Parse stage: poll the stored document, then hand the review screen its real items. */
function SyllabusParseStage({ syllabus, jobId, parsed, revisionOnly, onParsed, onStep, onCancel, onCreated, busy, error, refuse }) {
  const [document, setDocument] = useState(null)
  const [state, setState] = useState(parsed && parsed.parse_state ? 'parsed' : 'parsing')
  const [step, setStep] = useState('review')
  const [scope, setScope] = useState('short')
  const [submitting, setSubmitting] = useState(false)
  const [failure, setFailure] = useState(null)
  // The backend's answer to a cancel, rendered instead of assumed. `asking` is the unanswered
  // moment; nothing claims the job stopped until this holds the backend's own state.
  const [cancelOutcome, setCancelOutcome] = useState(null)
  const cancelRef = useRef(false)
  const keyRef = useRef(null)

  useEffect(() => {
    if (!syllabus || document || cancelOutcome) return undefined
    let stopped = false
    let attempts = 0
    let dispose = null
    const stop = () => {
      stopped = true
      if (dispose) {
        dispose()
        dispose = null
      }
    }
    const tick = async () => {
      if (stopped || cancelRef.current) return
      attempts += 1
      const response = await rpc('syllabus.get', {
        syllabus_id: syllabus.syllabus_id,
        revision: syllabus.revision,
        include_blocks: true
      })
      if (stopped) return
      if (!response.ok) {
        setFailure(response.error)
        stop()
        return
      }
      const result = response.result || {}
      // `syllabus.get` carries no top-level state: the parse run is the state, and the stored
      // document is only readable once that run exists.
      const view = syllabusParseView(result)
      if (view.parse_state) {
        setDocument(view)
        setState('parsed')
        onParsed && onParsed(view)
        stop()
        return
      }
      if (result.syllabus && result.syllabus.state === 'failed') {
        setFailure({ code: 'SYLLABUS_REJECTED', message: 'Your file could not be read. Check it is the syllabus itself and try again.' })
        setState('failed')
        stop()
        return
      }
      if (jobId) {
        const job = await rpc('jobs.get', { job_id: jobId })
        if (stopped) return
        const jobView = job && job.ok ? job.result.job : null
        if (jobView && ['failed', 'cancelled', 'interrupted_requires_retry'].includes(jobView.state)) {
          const message = (jobView.error && jobView.error.message) || 'The parse did not finish. Check the file is the syllabus itself and try again.'
          setFailure({ code: (jobView.error && jobView.error.code) || 'SYLLABUS_REJECTED', message })
          setState('failed')
          stop()
          return
        }
      }
      if (attempts >= 150) {
        setState('slow')
        stop()
      }
    }
    // `ctx.setInterval` returns a disposer and is cleared when the plugin unloads, so a poller
    // cannot outlive the surface that started it.
    if (pluginContext && typeof pluginContext.setInterval === 'function') {
      dispose = pluginContext.setInterval(tick, 2000)
    } else {
      const handle = setInterval(tick, 2000)
      dispose = () => clearInterval(handle)
    }
    return stop
  }, [syllabus, jobId, document, onParsed, cancelOutcome])

  // Stopping the watch is not stopping the job. `cancelRef` halts the poll immediately, then the
  // `jobs.cancel` answer decides which of the three outcomes is shown: accepted (`queued` became
  // `cancelled`), requested but still finishing (`running` became `cancel_requested`), or refused.
  const requestCancel = useCallback(async () => {
    cancelRef.current = true
    setCancelOutcome({ status: 'asking' })
    if (!jobId) {
      setCancelOutcome({ status: 'no-job' })
      return
    }
    const response = await rpc('jobs.cancel', { job_id: jobId }, { idempotencyKey: `cb-syllabus-parse-cancel-${jobId}` })
    if (!response || response.ok !== true) {
      const refusal = (response && response.error) || {
        code: 'INTERNAL_ERROR',
        message: 'The backend did not answer the cancel, so this screen cannot say the parse stopped.'
      }
      setCancelOutcome({ status: 'failed', error: refusal })
      return
    }
    const target = response.result && response.result.state
    if (target === 'cancelled') setCancelOutcome({ status: 'accepted' })
    else setCancelOutcome({ status: 'requested', state: target || null })
  }, [jobId])

  if (cancelOutcome) {
    const close = jsx(sdk.Button, { className: 'self-start', size: 'sm', variant: 'secondary', onClick: onCancel, children: 'Back to Library' })
    if (cancelOutcome.status === 'asking') {
      return jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'cancel-asking', children: [
        jsx(sdk.Loader, { label: 'Asking the backend to stop the parse' })
      ] })
    }
    if (cancelOutcome.status === 'accepted') {
      return jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'cancel-accepted', children: [
        jsx('div', { className: 'max-w-prose text-sm', children: 'Cancelled. Nothing further was sent.' }),
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: 'The backend accepted the stop, so no course will be created from this parse.' }),
        close
      ] })
    }
    if (cancelOutcome.status === 'requested') {
      return jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'cancel-requested', children: [
        jsx('div', {
          className: 'max-w-prose text-sm',
          children: 'Asked the backend to stop; it will not start new work. The course will not be created until you review it.'
        }),
        close
      ] })
    }
    if (cancelOutcome.status === 'no-job') {
      return jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'cancelled-before-job', children: [
        jsx('div', {
          className: 'max-w-prose text-sm',
          children: 'Cancelled. Nothing further was sent — no parse job had been recorded here, so there was nothing to stop.'
        }),
        close
      ] })
    }
    const refusal = cancelOutcome.error || {}
    return jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'cancel-failed', children: [
      jsx(sdk.ErrorState, {
        title: refusal.code || 'CANCEL_REFUSED',
        description: `${refusal.message || 'The backend refused the cancel.'} The parse may still be running, and a course could be created from it. Retry the cancel, or review the course when it appears.`
      }),
      jsxs('div', { className: 'flex flex-wrap gap-2', children: [
        jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: requestCancel, children: 'Retry cancel' }),
        close
      ] })
    ] })
  }

  const target = document || (parsed && parsed.document ? parsed : null)

  if (state === 'parsing') {
    return jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'parsing', children: [
      jsx(sdk.Loader, { label: 'Reading your syllabus' }),
      jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.parseRunning }),
      jsx(sdk.Button, { className: 'self-start', size: 'sm', variant: 'ghost', onClick: requestCancel, children: 'Stop watching this parse' })
    ] })
  }
  if (state === 'failed' || failure) {
    return jsxs('div', { className: 'flex flex-col gap-2', children: [
      jsx(sdk.ErrorState, { title: failure ? failure.code : 'SYLLABUS_REJECTED', description: failure ? failure.message : 'The parse did not finish.' }),
      jsx(sdk.Button, { className: 'self-start', size: 'sm', variant: 'secondary', onClick: onCancel, children: 'Back' })
    ] })
  }
  if (state === 'slow') {
    return jsxs('div', { className: 'flex flex-col gap-2', children: [
      jsx('div', { className: 'max-w-prose text-sm', children: 'The parse is taking longer than usual. It keeps running on this device; you can come back to it from Library.' }),
      jsx(sdk.Button, { className: 'self-start', size: 'sm', variant: 'secondary', onClick: onCancel, children: 'Back to Library' })
    ] })
  }
  if (!target) {
    return jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'parse-unreadable', children: [
      jsx(sdk.ErrorState, {
        title: 'The parsed details could not be read',
        description: 'The parse finished but its stored items did not load. Nothing is shown from a template; try reading the file again.'
      }),
      jsx(sdk.Button, { className: 'self-start', size: 'sm', variant: 'secondary', onClick: onCancel, children: 'Back' })
    ] })
  }

  if (step === 'scope') {
    const proposal = syllabusScopeProposal(target)
    const choices = [
      { id: 'single', label: 'One lesson' },
      { id: 'short', label: 'A short course' },
      { id: 'full', label: 'The whole term' }
    ]
    return jsxs('div', { className: 'flex flex-col gap-3', 'data-cb-syllabus': 'scope', children: [
      jsx('div', { className: 'text-sm font-semibold', children: 'How much of the class should this course support?' }),
      jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: proposal.proposal ? proposal.reason : proposal.reason }),
      jsx(sdk.SegmentedControl, { onChange: setScope, options: choices, sizing: 'content', value: scope }),
      jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.researchMinutes }),
      failure ? jsx(sdk.ErrorState, { title: failure.code, description: failure.message }) : null,
      jsxs('div', { className: 'flex flex-wrap gap-2 border-t border-(--ui-stroke-tertiary) pt-3', children: [
        jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: () => setStep('review'), disabled: submitting, children: 'Back to the details' }),
        jsx(CbAction, {
          variant: 'primary',
          disabled: submitting,
          onClick: async () => {
            if (!keyRef.current) keyRef.current = `cb-companion-${newOperationId('companion')}`
            setSubmitting(true)
            const outcome = await startCompanionCourse({
              call: rpc,
              key: keyRef.current,
              parsed: target,
              scope,
              goal: '',
              learnerLabel: (syllabusCourseFields(target).title || 'Companion course')
            })
            setSubmitting(false)
            if (!outcome.ok) {
              setFailure(outcome.error || { code: 'INTERNAL_ERROR', message: 'The course could not be created.' })
              return
            }
            onCreated && onCreated(outcome)
          },
          children: submitting ? 'Creating the course' : SYLLABUS_COPY.startsCompanion
        })
      ] })
    ] })
  }

  return jsx(SyllabusParseReview, {
    parsed: target,
    blocks: (target && target.blocks) || [],
    busy: Boolean(busy),
    continueLabel: revisionOnly ? 'Check the new revision' : null,
    onBack: onCancel,
    onContinue: () => {
      if (revisionOnly) {
        // A new revision is not a new course: the parse is recorded, the mapping is now stale, and
        // the screen returns to the course so the learner can see that before anything else.
        onCreated && onCreated({ revision: target.revision, syllabusId: target.syllabus_id })
        return
      }
      const proposal = syllabusScopeProposal(target)
      setScope(proposal.proposal || 'short')
      setStep('scope')
    }
  })
}

/** The entry point, shared by Library and the first-run card. Two import paths, said plainly. */
function SyllabusEntry({ onStartSyllabus, onStartImport, compact }) {
  return jsxs('div', {
    className: compact ? 'mb-2 flex flex-wrap items-center gap-2' : 'mb-4 flex flex-col gap-2 border-b border-(--ui-stroke-tertiary) pb-3',
    'data-cb-syllabus': 'entry',
    children: [
      compact
        ? null
        : jsxs('div', { className: 'flex flex-col gap-1', children: [
            jsx('div', { className: 'text-sm font-medium', children: SYLLABUS_COPY.entryTitle }),
            jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.entryBody })
          ] }),
      onStartSyllabus
        ? jsx(sdk.Button, { size: 'sm', variant: compact ? 'secondary' : 'default', onClick: onStartSyllabus, children: SYLLABUS_COPY.action })
        : null,
      onStartImport
        ? jsx(sdk.Button, { size: 'sm', variant: 'ghost', onClick: onStartImport, children: 'Import a pack' })
        : null
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
  // The backend's `cold` class means *independent*: no hint and no shown answer. The learner reads
  // what that means for them, never the evidence vocabulary (H-29, UX-05).
  cold: 'First try, no hints',
  hinted: 'Hinted',
  answer_shown: 'Answer shown',
  self_reported: 'Reported by you — not independently verified.',
  parent_reported: 'Reported by the parent — not graded by Coursebook.',
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
  self_reported: SELF_REPORTED_EVIDENCE_COPY,
  // One line, because the phrase "First try, no hints" raises the obvious question: why does it
  // matter? It matters because it is the only thing that counts as independent evidence.
  cold: 'Independent evidence is worth more: it shows what you can do without help.'
}

/**
 * The learner-facing words for the rubric's evidence target.
 *
 * `discrimination` is a construct id, not a label a person should have to decode. The badge shows
 * the plain phrase; the raw id travels in the index's opened details panel so an audit can still
 * name the exact construct (UX-04, UX-05).
 */
const EVIDENCE_TARGET_LEARNER_COPY = {
  recall: 'Remember it',
  comprehension: 'Explain it',
  production: 'Say or write it',
  discrimination: 'Tell the difference',
  procedure: 'Do the steps',
  transfer: 'Use it somewhere new'
}

function learnerEvidenceTarget(value) {
  if (!value) return ''
  const known = EVIDENCE_TARGET_LEARNER_COPY[value]
  if (known) return known
  // An unknown enum is still never printed raw: snake_case becomes sentence case.
  return String(value)
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

/**
 * The four states the index uses. Every row carries BOTH an icon and a word, so the state is
 * legible without colour. `next` is not a stored state: it is projected from the backend's own
 * next step, and it wins over the stored state only while that section is still open.
 */
const SECTION_STATE_SEMANTIC = {
  not_started: { key: 'not_started', label: 'Not started', icon: 'circle-outline' },
  introduced: { key: 'started', label: 'Started', icon: 'circle-filled' },
  independent_evidence: { key: 'complete', label: 'Complete', icon: 'pass' },
  delayed_evidence: { key: 'complete', label: 'Complete', icon: 'pass' },
  review_due: { key: 'review', label: 'Review due', icon: 'history' },
  needs_review: { key: 'review', label: 'Review needed', icon: 'history' },
  overridden: { key: 'moved_on', label: 'Moved on without a grade', icon: 'dash' }
}

function sectionStateSemantic(state, isNext) {
  const settled = state === 'independent_evidence' || state === 'delayed_evidence'
  if (isNext && !settled) return { key: 'next', label: 'Next', icon: 'chevron-right' }
  return SECTION_STATE_SEMANTIC[state] || SECTION_STATE_SEMANTIC.not_started
}

/**
 * "3 of 4 objectives have independent evidence" — a count the backend already records.
 *
 * There is no percentage, no streak and no mastery word: `independent` is the objective's own
 * stored state, and a course with nothing recorded says so instead of showing a zero that looks
 * like a grade.
 */
function progressStatement(independent, total) {
  const done = Math.max(0, Number(independent) || 0)
  const all = Math.max(0, Number(total) || 0)
  if (all === 0) return 'No objectives recorded yet'
  const noun = all === 1 ? 'objective' : 'objectives'
  return `${done} of ${all} ${noun} ${all === 1 ? 'has' : 'have'} independent evidence`
}

/** The counts the index and overview print, read only from the outline the backend returned. */
function objectiveProgress(objectives, totalFallback) {
  const list = Array.isArray(objectives) ? objectives.filter(Boolean) : []
  const total = list.length > 0 ? list.length : Math.max(0, Number(totalFallback) || 0)
  const independent = list.filter((entry) => entry.independent).length
  const due = list.filter((entry) => entry.state === 'review_due' || entry.state === 'needs_review').length
  return { total, independent, due, statement: progressStatement(independent, total) }
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
 * One concrete thing the learner showed, read from the graded criteria.
 *
 * This replaces the old "objective complete" line. It is deliberately not a compliment
 * generator: it repeats only what the backend marked `met` with an observation, and a pass with no
 * observation says exactly that instead of inventing a takeaway.
 */
function verdictTakeaway(result, criteria) {
  if (!result || result.verdict !== 'pass') return null
  if (result.evidence_class === 'self_reported') return null
  const shown = (criteria || [])
    .filter((item) => item && item.met && item.observed)
    .map((item) => String(item.observed).trim())
    .filter(Boolean)
  if (shown.length === 0) return 'You answered with no hints, and the backend recorded this check as a pass.'
  return `What you showed: ${shown.slice(0, 2).join('; ')}.`
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

/**
 * What a learner reads when the question could not be loaded.
 *
 * It names the failure when the backend did (a refusal code, a transport message) and never claims
 * the question is above. The check itself stays open, so this is a read failure and not a lost
 * attempt: the only action offered is one Retry.
 */
function stimulusUnavailableDescription(error) {
  const detail = error ? `${error.code || 'STIMULUS_UNAVAILABLE'}${error.message ? `: ${error.message}` : ''}` : null
  return detail
    ? `The check opened, but its question did not load (${detail}). Submitting here would be blind, so the answer form stays closed. Retry the read; the check itself is still open.`
    : 'The check opened, but the backend returned no question. Submitting here would be blind, so the answer form stays closed. Retry the read; the check itself is still open.'
}

// Frozen learner-facing breadth copy (`docs/ASSESSMENT-BREADTH.md` §7). One static disclosure for
// every plan and every check: this build grades written answers, choices and checklists only. The
// strings are not keyed to a topic — a keyword classifier over the learner's goal would announce a
// construct-specific limit the harness cannot actually detect.
const PLAN_BREADTH_DISCLOSURE =
  'What Coursebook can check — Written answers, choices, and checklists. This build cannot collect or grade a program, a recording, a photo, or a built object. Checks marked "practice only" never advance a section.'
const CHECK_SURFACE_DISCLOSURE =
  'Your answer is text, a choice, or a checklist. Nothing you type is executed.'
const OPEN_LANE_NOT_GRADED_COPY =
  'Saved, not graded. This build has no grading model for open answers, so no verdict was produced. Your answer is saved, no progress was changed, and Retry grading does not consume an attempt.'
// The backend writes this into `attempts.grading_provenance_json.failure` when it fails closed
// because `grading.grade_open` had no aux grader. That record is the only honest signal that a
// `needs_retry` came from the unconfigured open lane rather than a closed-lane grader fault.
const OPEN_LANE_UNCONFIGURED_PATTERN = /open-response aux grader is not configured/i

const VERDICT_COPY = {
  pass: 'Passed',
  partial: 'Partly there',
  not_yet: 'Not yet',
  // The system's state, not the learner's outcome: this says what happened to the answer, and the
  // saved/not-graded line right under it says nothing was lost (H-29, UX-05/UX-10).
  needs_retry: 'We could not grade this answer'
}

const NEXT_ACTION_COPY = {
  // A pass is evidence for one objective, never mastery of the course. The takeaway (what the
  // learner actually showed) is rendered from the graded criteria above this line.
  complete_objective:
    'Next: open the section after this one and keep going. This check is independent evidence for one objective, not mastery of the whole course.',
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
  detached_chat: 'This lesson is no longer connected to its chat, so Submit is off. Open a new lesson run to connect a new chat.',
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

/** True only when the backend's own attempt record says the open lane had no grader. */
function openLaneWasUnconfigured(provenance) {
  if (!provenance || typeof provenance !== 'object') return false
  const failure = provenance.failure
  return typeof failure === 'string' && OPEN_LANE_UNCONFIGURED_PATTERN.test(failure)
}

function Hairline() {
  return jsx('div', { className: 'h-px w-full bg-(--ui-stroke-tertiary)' })
}

function QuietNote({ children }) {
  return jsx('p', {
    className: 'leading-relaxed text-(--ui-text-secondary)',
    style: { maxWidth: CB_MEASURE, fontSize: CB_TYPE.caption },
    children
  })
}

/**
 * A lesson-start notice is text, or text plus one real next action.
 *
 * H-64: the old fresh-run path reported what it had done nowhere and navigated away; every
 * lesson-start outcome now renders here, and when a run is armed the action opens the chat it is
 * armed to. A notice is never a dead label with no way forward.
 */
function NoticeLine({ notice, busy }) {
  if (!notice) return null
  const text = typeof notice === 'string' ? notice : notice.text
  const action = typeof notice === 'string' ? null : notice.action
  return jsxs('div', {
    role: 'status',
    'data-cb-lesson-notice': '',
    className: 'flex flex-wrap items-center justify-between gap-2 text-xs leading-relaxed text-(--ui-text-secondary)',
    style: {
      padding: '0.6rem 0.75rem',
      borderLeft: '2px solid var(--cb-accent)',
      background: 'var(--cb-accent-soft)'
    },
    children: [
      jsx('span', { className: 'max-w-prose min-w-0', children: text }),
      action
        ? jsx(sdk.Button, {
            size: 'sm',
            variant: 'secondary',
            disabled: busy,
            onClick: action.run,
            children: action.label
          })
        : null
    ]
  })
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
  // `stimulusStatus` is a state of its own, not a property inferred from `check.stimulus`: a failed
  // or empty `check.get` and a build without that command are different facts, and neither one is
  // "the question is here". `loading` holds the form back rather than offering a blind textarea.
  //   idle → unsupported (no check.get) | loading → ready | unavailable
  const [state, setState] = useState({
    status: 'idle',
    check: null,
    error: null,
    stimulusStatus: 'idle',
    stimulusError: null
  })
  const [ticket, setTicket] = useState(0)
  // `check.open` returns identity only; the learner-facing stimulus (prompt, choices, items) is a
  // separate read. A build that does not implement `check.get` keeps today's answer-only surface
  // (the question lives in the teaching chat) rather than guessing a question.
  const canReadStimulus = Boolean(implemented && implemented.has('check.get'))

  useEffect(() => {
    if (!enabled || !enrollmentId || !objectiveId) {
      setState({ status: 'idle', check: null, error: null, stimulusStatus: 'idle', stimulusError: null })
      return undefined
    }
    let cancelled = false
    setState((previous) => ({
      status: 'loading',
      check: previous.check,
      error: null,
      stimulusStatus: canReadStimulus ? 'loading' : 'unsupported',
      stimulusError: null
    }))
    const settleStimulus = (checkId, update) =>
      setState((previous) =>
        previous.check && previous.check.check_id === checkId ? { ...previous, ...update } : previous
      )
    rpc(
      'check.open',
      { enrollment_id: enrollmentId, objective_id: objectiveId },
      { expectedRevision: Number(revision) || 0 }
    )
      .then((response) => {
        if (cancelled) return
        if (!response || !response.ok) {
          setState({
            status: 'error',
            check: null,
            error: (response && response.error) || null,
            stimulusStatus: 'idle',
            stimulusError: null
          })
          return
        }
        const opened = response.result
        setState({
          status: 'ready',
          check: opened,
          error: null,
          stimulusStatus: canReadStimulus ? 'loading' : 'unsupported',
          stimulusError: null
        })
        if (!canReadStimulus || !opened || !opened.check_id) return
        // A rejection, a refused envelope and an `ok` answer with no stimulus are all "we cannot
        // show this question". Each keeps the opened check on screen and names the failure; none
        // of them may leave the answer form looking as if the prompt were above it.
        rpc('check.get', { enrollment_id: enrollmentId, check_id: opened.check_id })
          .then((detail) => {
            if (cancelled) return
            if (!detail || !detail.ok) {
              settleStimulus(opened.check_id, {
                stimulusStatus: 'unavailable',
                stimulusError: (detail && detail.error) || null
              })
              return
            }
            const stimulus = detail.result && detail.result.stimulus ? detail.result.stimulus : null
            if (!stimulus) {
              settleStimulus(opened.check_id, { stimulusStatus: 'unavailable', stimulusError: null })
              return
            }
            settleStimulus(opened.check_id, { stimulusStatus: 'ready', stimulusError: null })
            setState((previous) =>
              previous.check && previous.check.check_id === opened.check_id
                ? { ...previous, check: { ...previous.check, stimulus } }
                : previous
            )
          })
          .catch((error) => {
            if (cancelled) return
            settleStimulus(opened.check_id, {
              stimulusStatus: 'unavailable',
              stimulusError: { code: 'HOST_UNAVAILABLE', message: describeError(error) }
            })
          })
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            status: 'error',
            check: null,
            error: { code: 'HOST_UNAVAILABLE', message: describeError(error) },
            stimulusStatus: 'idle',
            stimulusError: null
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
  const takeaway = verdictTakeaway(result, criteria)
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

      takeaway
        ? jsx('div', {
            className: 'max-w-prose text-sm leading-relaxed',
            'data-cb-takeaway': '',
            children: takeaway
          })
        : null,

      confirmed.length > 0
        ? jsxs('div', {
            className: 'flex flex-col gap-1',
            'data-cb-check-criteria': String(confirmed.length),
            children: [
              jsx(CbLabel, { children: 'Steps you confirmed' }),
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
                      jsx(sdk.Codicon, { name: item.met ? 'pass' : 'circle-slash', size: CB_ICON_UI }),
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
                ? jsx(CbAction, {
                    variant: 'primary',
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
 * The parent-observation lane (cb.rpc v14, `observation.record`).
 *
 * `docs/CHECKLIST-CONFIRMATION.md` §6 draws the boundary: a parent-recipe objective is observed by
 * the adult, never ticked or answered by the child, so the observation is the only recording path
 * for that objective. The write is one layer-1 evidence row — no attempt, no check state, no
 * verdict, no objective transition — and the response `revision` is the enrollment revision echoed
 * unchanged, so nothing here may be rendered as a pass, a grade or a completed objective.
 *
 * The note bound is the contract's own (`maxLength: 1000`). The schema refuses 1001 rather than
 * truncating, so the control bounds the field and the call refuses before the wire, never slicing
 * a parent's words.
 */
const OBSERVATION_NOTE_MAX = 1000
const PARENT_OBSERVATION_CLASS = 'parent_reported'

/** The exact `observation.record` payload. An absent note travels as `null`, never `''`. */
function parentObservationPayload({ enrollmentId, objectiveId, note }) {
  const trimmed = String(note === undefined || note === null ? '' : note).trim()
  return {
    enrollment_id: enrollmentId,
    objective_id: objectiveId,
    evidence_class: PARENT_OBSERVATION_CLASS,
    note: trimmed ? trimmed : null
  }
}

/**
 * The envelope key for one submission.
 *
 * `idempotency_key` lives at the envelope root and is required, so a double click cannot mint two
 * evidence rows. The caller mints one key per distinct payload and reuses it on retry; a new key on
 * a retry of the same payload would record a second observation.
 */
function parentObservationKey({ enrollmentId, objectiveId, nonce }) {
  return `cb-observation-${enrollmentId}-${objectiveId}-${nonce}`
}

/** What identifies one submission: the same ids and the same note are the same write. */
function observationSignature({ enrollmentId, objectiveId, note }) {
  const trimmed = String(note === undefined || note === null ? '' : note).trim()
  return `${enrollmentId}|${objectiveId}|${trimmed}`
}

/**
 * The submission on screen, and its key.
 *
 * An unchanged payload keeps the key it already sent, so a retry of a failed or duplicated call
 * replays the stored observation instead of recording a second one. A changed note is a different
 * observation and gets its own key. Pure, with the nonce injected, so the rule is asserted directly.
 */
function nextObservationSubmission(previous, { enrollmentId, objectiveId, note, nonce }) {
  const signature = observationSignature({ enrollmentId, objectiveId, note })
  if (previous && previous.signature === signature) return previous
  return {
    signature,
    key: parentObservationKey({ enrollmentId, objectiveId, nonce: nonce || newOperationId('observation') })
  }
}

/**
 * One parent observation, over an injected transport so a test can prove the envelope.
 *
 * `call` is the rpc transport (`rpc` in the app). No `expected_revision` is sent: v14 declares no
 * fence for this method and the append moves no aggregate.
 */
async function recordParentObservation({ call, key, enrollmentId, objectiveId, note }) {
  const payload = parentObservationPayload({ enrollmentId, objectiveId, note })
  if (payload.note !== null && payload.note.length > OBSERVATION_NOTE_MAX) {
    return {
      ok: false,
      stage: 'note_too_long',
      error: {
        code: 'VALIDATION_FAILED',
        message: `A note is at most ${OBSERVATION_NOTE_MAX} characters. Nothing was recorded.`
      }
    }
  }
  return call('observation.record', payload, { idempotencyKey: key, expectedRevision: null })
}

/** The recorded state. Reuses `EvidenceClassText`, so no second badge language is invented. */
function ParentObservationRecorded({ result, nodeRef }) {
  const evidenceId = result && result.evidence_id
  return jsxs('div', {
    className: 'flex flex-col gap-1',
    role: 'status',
    tabIndex: -1,
    ref: nodeRef,
    'data-cb-parent-observation-recorded': evidenceId || 'recorded',
    children: [
      jsx(EvidenceClassText, { value: (result && result.evidence_class) || PARENT_OBSERVATION_CLASS }),
      jsx('p', {
        className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
        children:
          'Recorded. This is a parent report: it is not independent evidence, it is not a pass or a grade, and it does not complete this objective.'
      }),
      evidenceId
        ? jsx('p', { className: 'text-xs text-(--ui-text-secondary)', children: `Observation ${evidenceId}` })
        : null
    ]
  })
}

/**
 * Record what the parent saw. Keyboard-first: a labelled textarea, a labelled button, the error
 * inline and the control left enabled, and the recorded state announced (`role="status"`, focus
 * moved to it) instead of silently swapping the form.
 *
 * The submission ref holds the key of the payload on screen. Retrying an unchanged note re-sends
 * the SAME key (the backend replays the stored evidence); editing the note is a different payload
 * and mints a new key; a success clears it so the next observation is a new write.
 */
function ParentObservation({ enrollmentId, objectiveId, onRecorded }) {
  const [note, setNote] = useState('')
  const [phase, setPhase] = useState('editing')
  const [recorded, setRecorded] = useState(null)
  const [error, setError] = useState(null)
  const submissionRef = useRef(null)
  const statusRef = useRef(null)
  const trimmed = note.trim()
  const overLimit = trimmed.length > OBSERVATION_NOTE_MAX

  useEffect(() => {
    if (phase === 'recorded') statusRef.current?.focus({ preventScroll: true })
  }, [phase])

  const submission = useCallback(
    () =>
      nextObservationSubmission(submissionRef.current, {
        enrollmentId,
        objectiveId,
        note: trimmed
      }),
    [enrollmentId, objectiveId, trimmed]
  )

  const submit = useCallback(async () => {
    if (!enrollmentId || !objectiveId) return
    if (trimmed.length > OBSERVATION_NOTE_MAX) {
      setError({
        code: 'VALIDATION_FAILED',
        message: `A note is at most ${OBSERVATION_NOTE_MAX} characters. Nothing was recorded.`
      })
      return
    }
    const current = submission()
    submissionRef.current = current
    setPhase('saving')
    setError(null)
    const response = await recordParentObservation({
      call: rpc,
      key: current.key,
      enrollmentId,
      objectiveId,
      note: trimmed
    })
    if (!response || !response.ok) {
      // The control stays exactly as it was: the note is still in the field and Retry re-sends the
      // same key, so an offline call is recoverable rather than a lost observation.
      setError((response && response.error) || { code: 'INTERNAL_ERROR', message: 'No contract envelope was returned.' })
      setPhase('failed')
      return
    }
    setRecorded(response.result || null)
    setPhase('recorded')
    submissionRef.current = null
    if (onRecorded) onRecorded(response.result, response)
  }, [enrollmentId, objectiveId, trimmed, submission, onRecorded])

  const recordAgain = () => {
    setRecorded(null)
    setError(null)
    setNote('')
    setPhase('editing')
  }

  return jsxs('div', {
    className: 'flex flex-col gap-2',
    'data-cb-parent-observation': objectiveId || 'objective',
    children: [
      jsx(CbLabel, { children: 'Parent observation' }),
      jsx('p', {
        className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
        children:
          'Record what you saw your child do. It is stored as a parent report — not independent evidence — and it does not grade, pass or complete the objective.'
      }),
      recorded
        ? jsxs('div', {
            className: 'flex flex-col gap-2',
            children: [
              jsx(ParentObservationRecorded, { result: recorded, nodeRef: statusRef }),
              jsx('div', {
                className: 'flex flex-wrap items-center gap-2',
                children: jsx(sdk.Button, {
                  variant: 'secondary',
                  size: 'sm',
                  onClick: recordAgain,
                  children: 'Record another observation'
                })
              })
            ]
          })
        : jsxs('div', {
            className: 'flex flex-col gap-2',
            children: [
              jsx('label', {
                className: 'text-xs font-medium text-(--ui-text-secondary)',
                htmlFor: 'cb-observation-note',
                children: 'What did you observe? (optional note)'
              }),
              jsx(sdk.Textarea, {
                id: 'cb-observation-note',
                'aria-describedby': 'cb-observation-help',
                'aria-invalid': overLimit ? 'true' : undefined,
                disabled: phase === 'saving',
                maxLength: OBSERVATION_NOTE_MAX,
                onChange: (event) => setNote(event.target.value),
                placeholder: 'For example: set the table and lit the candle without being asked.',
                rows: 3,
                value: note
              }),
              jsx('p', {
                id: 'cb-observation-help',
                className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                children: `Optional, up to ${OBSERVATION_NOTE_MAX} characters. ${trimmed.length}/${OBSERVATION_NOTE_MAX}`
              }),
              error ? jsx(ErrorLine, { error }) : null,
              jsx('div', {
                className: 'flex flex-wrap items-center gap-2',
                children: jsx(CbAction, {
                  variant: 'primary',
                  disabled: phase === 'saving' || overLimit,
                  onClick: submit,
                  children: phase === 'saving' ? 'Recording…' : error ? 'Try again' : 'Record observation'
                })
              })
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
  parentLed = false,
  stimulusStatus = null,
  stimulusError = null,
  onRetryStimulus = null
}) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const [text, setText] = useState('')
  const [ticked, setTicked] = useState([])
  const [phase, setPhase] = useState('awaiting_input')
  const [result, setResult] = useState(null)
  const [resultCheck, setResultCheck] = useState(null)
  const [error, setError] = useState(null)
  const [overrideOpen, setOverrideOpen] = useState(false)
  const [openLaneUnconfigured, setOpenLaneUnconfigured] = useState(false)
  const nonceRef = useRef(null)
  const answerRef = useRef(null)
  const resultRef = useRef(null)
  const detached = Boolean(bindingState && bindingState !== 'active')

  // What this card is asking for. A `verification` stimulus with declared items is a checklist and
  // is answered with the item ids; every other stimulus keeps the written-answer path.
  const stimulus = check ? check.stimulus || null : null
  // The form is only offered for a question the learner can actually see. `stimulusStatus` comes
  // from `useOpenCheck`; a direct render that does not pass it keeps the pre-existing behaviour
  // (a served stimulus is ready; otherwise the build speaks about the teaching chat).
  const stimulusState = stimulusStatus || (stimulus ? 'ready' : 'unsupported')
  const promptPresent = Boolean(stimulus && stimulus.prompt)
  const stimulusLoading = stimulusState === 'loading'
  const stimulusUnavailable = stimulusState === 'unavailable'
  const stimulusReady = stimulusState === 'ready'
  const mayAnswer = stimulusReady || stimulusState === 'unsupported'
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
    setOpenLaneUnconfigured(false)
    nonceRef.current = null
  }, [check && check.check_id, result])
  const displayCheck = resultCheck || check

  // §7.3 copy is keyed to the lane, not to the topic. `attempt.submit` returns the verdict but not
  // the reference kind, so read the attempt's own grading provenance once: only when the backend
  // recorded that the open-response grader was unconfigured does the "Saved, not graded" copy
  // replace the generic retry copy. If that read is unavailable or silent, nothing changes.
  const resolveNeedsRetryLane = useCallback(
    async (attemptId) => {
      if (!attemptId || !(implemented && implemented.has('quiz.history'))) return
      try {
        const response = await rpc('quiz.history', { enrollment_id: enrollmentId, objective_id: objectiveId })
        if (!response.ok) return
        const rows = (response.result && response.result.attempts) || []
        const row = rows.find((item) => item.attempt_id === attemptId)
        if (row && openLaneWasUnconfigured(row.grading_provenance)) setOpenLaneUnconfigured(true)
      } catch (err) {
        // A read-only lane probe must never replace the verdict the learner just received.
      }
    },
    [enrollmentId, objectiveId, implemented]
  )

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
    setOpenLaneUnconfigured(false)
    setPhase(graded.verdict === 'needs_retry' ? 'needs_retry' : 'graded')
    if (graded.verdict === 'needs_retry') void resolveNeedsRetryLane(graded.attempt_id)
    if (onCommitted) onCommitted(graded)
  }, [check, text, ticked, checklist, enrollmentId, revision, onCommitted, resolveNeedsRetryLane])

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
    setOpenLaneUnconfigured(false)
    setPhase(response.result.verdict === 'needs_retry' ? 'needs_retry' : 'graded')
    if (response.result.verdict === 'needs_retry') void resolveNeedsRetryLane(response.result.attempt_id)
    if (onCommitted) onCommitted(response.result)
  }, [check, text, ticked, checklist, enrollmentId, revision, onCommitted, resolveNeedsRetryLane])

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
              jsx(ProseText, { className: 'max-w-prose', text: stimulus.prompt }),
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
                      jsx('li', { children: choice }, `choice-${index}`)
                    )
                  })
                : null,
              checklist.length > 0
                ? jsxs('div', {
                    className: 'flex flex-col gap-1',
                    'data-cb-check-items': String(checklist.length),
                    'data-cb-check-items-mode': 'selection',
                    children: [
                      jsx(CbLabel, { children: 'Checklist' }),
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
                        jsx(CbLabel, { children: 'Checklist' }),
                        // One label per item, printed here and nowhere else in the lesson.
                        jsx('ul', {
                          className: 'flex flex-col gap-1',
                          'aria-label': 'Checklist',
                          children: readOnlyItems.map((item) =>
                            jsx('li', {
                              className: 'text-sm leading-snug',
                              'data-cb-check-item': item.id,
                              children: item.label
                            }, item.id)
                          )
                        })
                      ]
                    })
                  : null
            ]
          })
        : null,

      showForm && stimulusLoading
        ? jsxs('div', {
            className: 'flex items-center gap-2 text-xs text-(--ui-text-secondary)',
            'data-cb-check-stimulus-state': 'loading',
            children: [
              jsx(sdk.Loader, { label: 'Loading the question' }),
              jsx('span', { children: 'The answer form stays closed until the question is here.' })
            ]
          })
        : null,

      showForm && stimulusUnavailable
        ? jsxs('div', {
            className: 'flex flex-col gap-2',
            'data-cb-check-stimulus-state': 'unavailable',
            children: [
              jsx(sdk.ErrorState, {
                title: 'The question could not be loaded',
                description: stimulusUnavailableDescription(stimulusError)
              }),
              onRetryStimulus
                ? jsx(sdk.Button, {
                    className: 'self-start',
                    size: 'sm',
                    variant: 'secondary',
                    disabled: locked,
                    onClick: onRetryStimulus,
                    children: 'Retry'
                  })
                : null
            ]
          })
        : null,

      showForm && mayAnswer
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
                    style: { maxWidth: CB_MEASURE },
                    children: stimulusReady && promptPresent
                      ? 'The question and any choices are shown above; this field records what you answered.'
                      : 'The question and any choices are in the teaching chat. This field records your answer and the backend grades it once.'
                  }),
              detached
                ? jsx(QuietNote, {
                    children: 'This lesson is no longer connected to its chat, so Submit is off. Open a new lesson run to connect a new chat.'
                  })
                : null,
              jsxs('div', {
                className: 'flex flex-wrap items-center gap-2',
                children: [
                  jsx(CbAction, {
                    variant: 'primary',
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
              openLaneUnconfigured
                ? jsx('p', {
                    className: 'max-w-prose text-sm leading-relaxed',
                    'data-cb-breadth': 'open-lane',
                    children: OPEN_LANE_NOT_GRADED_COPY
                  })
                : jsx('div', {
                    className: 'text-sm font-medium',
                    children: 'We could not grade this answer'
                  }),
              openLaneUnconfigured
                ? null
                : jsx(QuietNote, {
                    children:
                      'Your answer is saved, not graded. No progress was changed, and Retry grading does not create a second attempt.'
                  }),
              error ? jsx(ErrorLine, { error }) : null,
              jsxs('div', {
                className: 'flex flex-wrap items-center gap-2',
                children: [
                  jsx(CbAction, { variant: 'primary', size: 'sm', onClick: retryGrading, children: 'Retry grading' }),
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

      jsx('p', {
        className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
        style: { maxWidth: CB_MEASURE },
        'data-cb-breadth': 'check',
        children: CHECK_SURFACE_DISCLOSURE
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
        independent: objective.independent,
        unit: objective.unit,
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
    const pageSection = page && page.section && page.section.objective_id === current ? page.section : null
    // The current objective only *names* a row the outline already carries; it must not overwrite
    // that row's title with a placeholder or drop the unit it belongs to.
    if (!seen.has(current)) {
      add({
        objective_id: current,
        title: (pageSection && pageSection.title) || 'Current section',
        ordinal: pageSection ? pageSection.ordinal : 0,
        state: pageSection ? pageSection.state : undefined,
        evidence_target: pageSection ? pageSection.evidence_target : undefined
      })
    } else if (pageSection) {
      add({
        objective_id: current,
        title: pageSection.title,
        ordinal: pageSection.ordinal,
        state: pageSection.state,
        evidence_target: pageSection.evidence_target
      })
    }
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
 * ── Atlas Lamp: the scoped Coursebook token layer ───────────────────────────────────────────
 *
 * The Desktop SDK has no per-route theme seam: `THEMES_AREA` registers an app-wide theme, and a
 * runtime plugin may import only `@hermes/plugin-sdk`, `react` and `react/jsx-runtime`, so a
 * second stylesheet cannot be shipped as a module. The smallest honest seam is therefore a scoped
 * route shell: the token table below is applied as CSS custom properties on the Coursebook route
 * and pane roots only, and every Coursebook surface paints from `var(--cb-*)`. Hermes chrome is
 * untouched, and the host's own `--ui-*` tokens still supply anything outside this layer.
 *
 * The table is one embedded JSON literal so `tests/test_desktop_tokens.py` can read the shipped
 * module, compare it byte-for-byte with `contracts/cb.tokens.v2.json`, and compute WCAG contrast
 * on the values that actually ship. `CB_TOKENS_JSON` is the ONLY colour literal in this file: the
 * test refuses any hex outside it.
 *
 * Colour has three jobs and never four (docs/COURSEBOOK-VISUAL-IDENTITY-V2.md §2.3): identity
 * (`lamp`, `plum`), mode (`accent` Textbook, `field` Guided, `ochre` Field Quest) and state
 * (evidence/due/attention/not started). `lamp` is a fill and never text on `paper`; `coral` is
 * attention only and never a mode hue.
 */
const CB_TOKENS_JSON =
  '{"light":{"paper":"#f7f1e4","paper-raised":"#fffcf3","ink":"#1a1713","ink-soft":"#5c5347","rule":"#d7cbb4","accent":"#2c4a8c","accent-soft":"#e2e8f7","field":"#2f6047","ochre":"#7b4b0a","coral":"#9c2e1c","lamp":"#e8a93a","lamp-soft":"#fbebcb","on-lamp":"#1a1713","plum":"#6a3e74","plum-soft":"#f0e6f3"},"dark":{"paper":"#131210","paper-raised":"#1d1b16","ink":"#f5efe1","ink-soft":"#b9ae9a","rule":"#3d382d","accent":"#a8c0f2","accent-soft":"#222a3b","field":"#9fc69a","ochre":"#e0b25c","coral":"#ea9480","lamp":"#efc06b","lamp-soft":"#33290f","on-lamp":"#131210","plum":"#cda0d8","plum-soft":"#2e2434"}}'

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
  'coral',
  'lamp',
  'lamp-soft',
  'on-lamp',
  'plum',
  'plum-soft'
])

/**
 * Six type steps, and only six. Every font size Coursebook authors for its own text is one of
 * these; the host's own chrome (badges, buttons, tab strips) keeps its own sizes and is outside
 * this claim. Body is `1rem`, so a 16px root paints 16px body copy; a 200% root scales the lot.
 * Display is a clamp inside the 2.25-2.5rem band, so no hero ever exceeds the step.
 */
const CB_TYPE_SCALE_JSON =
  '{"caption":"0.75rem","meta":"0.875rem","body":"1rem","lead":"1.125rem","heading":"1.5rem","display":"clamp(2.25rem, 1.9rem + 0.7vw, 2.5rem)"}'

const CB_TYPE = JSON.parse(CB_TYPE_SCALE_JSON)
const CB_TYPE_STEPS = Object.freeze(['caption', 'meta', 'body', 'lead', 'heading', 'display'])

/** One plural rule for every count the learner reads: `plural(1,'section','sections')`. */
function plural(count, one, many) {
  return `${count} ${Number(count) === 1 ? one : many}`
}

/** The host cannot ship a font file, so the voices are OS-resident stacks only. */
const CB_SERIF = 'ui-serif, Georgia, "Iowan Old Style", "Palatino Linotype", "Noto Serif", serif'
const CB_SANS = 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif'

/** Codicon only, two sizes: 16px beside UI text, 20px on a plate mark. Never a per-row icon. */
const CB_ICON_UI = '1rem'
const CB_ICON_PLATE = '1.25rem'

/** Four named ranges, measured from the route, never from a media query. */
const CB_WIDE_BREAKPOINT = 1050
const CB_MID_BREAKPOINT = 900
const CB_NARROW_BREAKPOINT = 460
/** A comfortable reading measure (62-72 characters) for the lesson column. */
const CB_MEASURE = '66ch'
const CB_RAIL_WIDTH = '20rem'

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
  for (const step of CB_TYPE_STEPS) style[`--cb-text-${step}`] = CB_TYPE[step]
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
  // The host atom reports the whole application window. Coursebook can sit in a much narrower
  // route pane (for example beside the chat rail), and choosing the wide shell from the window
  // width squeezes the Continue card into a word-per-line column. Measure the route itself when a
  // DOM exists; keep the host read as the SSR/older-host fallback.
  const [containerWidth, setContainerWidth] = useState(0)
  useEffect(() => {
    if (typeof document === 'undefined' || typeof window === 'undefined') return undefined
    let node = null
    let observer = null
    const read = () => {
      if (!node || !node.isConnected) return
      const rect = node.getBoundingClientRect()
      if (rect.width > 0) setContainerWidth(Math.round(rect.width))
    }
    const attach = () => {
      node = document.querySelector('[data-cb-route]')
      if (!node) return false
      read()
      if (typeof ResizeObserver === 'function') {
        observer = new ResizeObserver(read)
        observer.observe(node)
      }
      window.addEventListener('resize', read)
      return true
    }
    if (!attach()) {
      const retry = window.setTimeout(attach, 0)
      return () => window.clearTimeout(retry)
    }
    return () => {
      if (observer) observer.disconnect()
      window.removeEventListener('resize', read)
    }
  }, [])

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
    if (rect && typeof rect.width === 'number') return containerWidth || rect.width
  }
  return containerWidth || read()
}

/** Pure so the layout decision is testable without a window: the route decides, not the app. */
function cbLayoutFor(width) {
  if (typeof width !== 'number' || !Number.isFinite(width) || width <= 0) return 'phone'
  if (width >= CB_WIDE_BREAKPOINT) return 'wide'
  if (width >= CB_MID_BREAKPOINT) return 'mid'
  if (width >= CB_NARROW_BREAKPOINT) return 'narrow'
  return 'phone'
}

/** The rail sits beside the reading column only at `wide`; every other range stacks it after. */
function cbIsWide(layout) {
  return layout === 'wide'
}

/* ── Atlas Lamp primitives ─────────────────────────────────────────────────────────────────
 * The recurring motifs of the identity, built from tokens only: the course seal, the plate head,
 * the route spine, the evidence tally and the hero field. No primitive names a colour directly,
 * so the scoped layer is still the only place a palette value exists.
 */

/** Deterministic character sum, so one course keeps one seal station across sessions. */
function cbSealStation(courseId) {
  const text = String(courseId || '')
  let sum = 0
  for (let index = 0; index < text.length; index += 1) sum += text.charCodeAt(index)
  return sum % 4
}

/* ── The shelf: one object per course, deterministic cover ─────────────────────────────────
 * H-99. Library, All Courses and Parent Studio all read the same `library.list` rows, and the
 * store can legitimately hold many enrollments (or many plans) that describe the same course.
 * Everything below is pure: no sdk, no jsx, no DOM. `tests/test_desktop_course_shelf.py`
 * imports these functions through Node and executes them, so grouping and cover determinism
 * are proven by running the shipped code rather than by matching source strings.
 */

/** FNV-1a over UTF-16 code units: stable across reloads, engines and row order. */
function cbStableHash(text) {
  const value = String(text == null ? '' : text)
  let hash = 0x811c9dc5
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return hash >>> 0
}

/** The two-letter mark on a cover. Deterministic from the title; never random, never a colour. */
function cbCourseMonogram(title) {
  const words = String(title || 'Coursebook')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
  if (words.length === 0) return 'CB'
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return `${words[0][0]}${words[1][0]}`.toUpperCase()
}

/**
 * The content the shelf can actually see on one `library.list` row. The per-plan hash lives in
 * `course.outline`, which the shelf does not call for every row; this projection is the honest
 * substitute and its fingerprint is shown to the reader, so two rows that share a cover can be
 * told apart without opening either.
 */
function cbShelfContent(row) {
  const provenance = (row && row.provenance) || {}
  const summary = (row && row.evidence_summary) || {}
  return {
    title: String((row && row.title) || '').trim().replace(/\s+/g, ' ').toLowerCase(),
    recipe: String((row && row.recipe) || ''),
    locale: String((row && row.locale) || ''),
    objectives: Math.max(0, Number(summary.total_objectives || 0)),
    packId: String(provenance.pack_id || ''),
    packVersion: String(provenance.pack_version || ''),
    source: String(provenance.source || '')
  }
}

/** The full content fingerprint: the closest thing to a plan hash a shelf row carries. */
function cbShelfFingerprint(row) {
  const content = cbShelfContent(row)
  const text = [
    content.title,
    content.recipe,
    content.locale,
    content.objectives,
    content.packId,
    content.packVersion,
    content.source
  ].join('|')
  return cbStableHash(text).toString(16).padStart(8, '0')
}

/**
 * The grouping key. A pack-backed course is one object per pack (docs/COURSEBOOK-VISUAL-
 * IDENTITY-V2 §5.3: "when several enrollments share one pack, show one row per pack"). An
 * authored course groups by its normalised title and recipe, so fourteen copies of the same
 * named plan become one row plus a disclosure — the records are listed there, never deleted.
 */
function cbShelfGroupKey(row) {
  const content = cbShelfContent(row)
  if (content.packId) return `pack:${content.packId}`
  const text = [content.title, content.recipe, content.locale].join('|')
  return `plan:${cbStableHash(text).toString(16)}`
}

/** Active first, then most recently touched, then highest revision, then the id — no ties. */
function cbShelfMemberOrder(left, right) {
  const activeLeft = left && left.enrollment_status === 'active' ? 0 : 1
  const activeRight = right && right.enrollment_status === 'active' ? 0 : 1
  if (activeLeft !== activeRight) return activeLeft - activeRight
  const touchedLeft = String((left && left.updated_at) || '')
  const touchedRight = String((right && right.updated_at) || '')
  if (touchedLeft !== touchedRight) return touchedLeft < touchedRight ? 1 : -1
  const revisionLeft = Number((left && left.revision) || 0)
  const revisionRight = Number((right && right.revision) || 0)
  if (revisionLeft !== revisionRight) return revisionRight - revisionLeft
  return String((left && left.enrollment_id) || '').localeCompare(String((right && right.enrollment_id) || ''))
}

/**
 * Group rows into shelf objects. The reader gets the primary enrollment of each object plus a
 * count; `members` keeps every record so the disclosure can list them and nothing is hidden.
 */
function groupShelfRows(rows) {
  const list = Array.isArray(rows) ? rows : []
  const buckets = new Map()
  for (const row of list) {
    if (!row || !row.enrollment_id) continue
    const key = cbShelfGroupKey(row)
    if (!buckets.has(key)) buckets.set(key, { key, members: [] })
    buckets.get(key).members.push(row)
  }
  const groups = []
  for (const bucket of buckets.values()) {
    const members = bucket.members.slice().sort(cbShelfMemberOrder)
    const versions = new Set(members.map(cbShelfFingerprint))
    const courses = new Set(members.map((member) => member.course_id || member.enrollment_id))
    let label = ''
    if (members.length > 1) {
      const packBacked = Boolean(cbShelfContent(members[0]).packId)
      if (packBacked) label = `${members.length} enrollments`
      else if (versions.size > 1) label = `${members.length} plans · ${versions.size} versions`
      else label = `${members.length} copies of this plan`
    }
    groups.push({
      key: bucket.key,
      primary: members[0],
      members,
      count: members.length,
      versions: versions.size,
      courses: courses.size,
      label
    })
  }
  groups.sort((left, right) => cbShelfMemberOrder(left.primary, right.primary) || String(left.key).localeCompare(String(right.key)))
  return groups
}

const CB_COURSE_PATH_PARTS = 4

/**
 * The four-segment path on a cover. Segments are fractions of the objective list, so the
 * current segment is the quarter the evidence has reached: `done` behind it, `current` (or
 * `due` when a review is waiting) at it, `quiet` ahead. With no objectives recorded there is
 * nothing to fill, and the path says so instead of drawing invented progress.
 */
function cbCoursePathSegments(row) {
  const summary = (row && row.evidence_summary) || {}
  const total = Math.max(0, Number(summary.total_objectives || 0))
  const independent = Math.max(0, Math.min(total, Number(summary.independent || 0)))
  const due = Math.max(0, Number(summary.review_due || 0))
  const segments = []
  if (total === 0) {
    for (let index = 0; index < CB_COURSE_PATH_PARTS; index += 1) {
      segments.push({ index, state: 'empty' })
    }
    return segments
  }
  const quarter = Math.ceil(total / CB_COURSE_PATH_PARTS)
  const reached = independent >= total ? CB_COURSE_PATH_PARTS : Math.floor(independent / quarter)
  for (let index = 0; index < CB_COURSE_PATH_PARTS; index += 1) {
    let state = 'quiet'
    if (index < reached) state = 'done'
    else if (index === reached) state = due > 0 ? 'due' : 'current'
    segments.push({ index, state })
  }
  return segments
}

/** The exact counts under the path. Never a percentage, never a score. */
function cbCoursePathCaption(row) {
  const summary = (row && row.evidence_summary) || {}
  const total = Math.max(0, Number(summary.total_objectives || 0))
  if (total === 0) return 'No sections yet'
  const independent = Math.max(0, Math.min(total, Number(summary.independent || 0)))
  const due = Math.max(0, Number(summary.review_due || 0))
  const parts = [`${independent} of ${total} with evidence`]
  if (due > 0) parts.push(`${due} due`)
  return parts.join(' · ')
}

/**
 * The one line under the title. The shelf row carries no plan goal, so this is the goal the
 * backend stored when it has one, the course's own subtitle, and otherwise the recorded next
 * step. It never invents a goal to make a card look fuller.
 */
function cbCourseGoalLine(row) {
  const goal = row && typeof row.goal === 'string' ? row.goal.trim() : ''
  if (goal) return goal
  const subtitle = row && typeof row.subtitle === 'string' ? row.subtitle.trim() : ''
  if (subtitle) return subtitle
  const label = row && row.next_step && typeof row.next_step.label === 'string' ? row.next_step.label.trim() : ''
  if (label) return label
  return 'No next step recorded'
}

/**
 * H-145 — the course seal was retired from every surface it appeared on. The owner asked twice
 * what it meant; a mark that needs an explanation is not identity. `cbSealStation` stays exported
 * because the visual-identity probes address it, but nothing in the route renders an SVG seal.
 */

/** Segment kinds are internal enums; the learner sees a plain word. */
const CB_SEGMENT_WORD = {
  teaching: 'Teaching',
  practice: 'Practice',
  example: 'Worked example',
  recap: 'Recap',
  orientation: 'Getting started',
  check_prompt: 'Check',
  media: 'Media',
  audio: 'Audio',
  visual: 'Image'
}

function cbSegmentWord(kind) {
  if (!kind) return ''
  const known = CB_SEGMENT_WORD[kind]
  if (known) return known
  const text = String(kind).replaceAll('_', ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** A section label in sentence case: no eyebrow, no all-caps, 0.75rem floor. */
function CbLabel({ children }) {
  return jsx('div', {
    style: {
      fontFamily: CB_SANS,
      fontSize: CB_TYPE.caption,
      fontWeight: 600,
      letterSpacing: '0.01em',
      color: 'var(--cb-ink-soft)'
    },
    children
  })
}

/** One plate head: a display title, an optional label and one honest caption. */
function PlateHead({ id, label, title, caption, actions, level }) {
  const heading = level === 3 ? 'h3' : 'h2'
  return jsxs('div', {
    'data-cb-plate-head': '',
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      alignItems: 'flex-end',
      justifyContent: 'space-between',
      gap: '0.5rem 1rem',
      paddingBottom: '0.5rem',
      borderBottom: '1px solid var(--cb-rule)'
    },
    children: [
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', minWidth: 0 },
        children: [
          label
            ? jsx('div', {
                style: {
                  fontFamily: CB_SANS,
                  fontSize: CB_TYPE.caption,
                  fontWeight: 600,
                  letterSpacing: '0.01em',
                  color: 'var(--cb-ink-soft)'
                },
                children: label
              })
            : null,
          jsx(heading, {
            id,
            style: {
              margin: 0,
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.heading,
              fontWeight: 600,
              lineHeight: 1.2,
              letterSpacing: '-0.01em',
              color: 'var(--cb-ink)',
              maxWidth: '34ch'
            },
            children: title
          }),
          caption
            ? jsx('p', {
                style: { margin: 0, maxWidth: CB_MEASURE, fontFamily: CB_SANS, fontSize: CB_TYPE.body, lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
                children: caption
              })
            : null
        ]
      }),
      actions ? jsx('div', { style: { display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }, children: actions }) : null
    ]
  })
}

/** Five states, five shapes: the spine is never the only carrier of the state word. */
function cbSpineTone(state) {
  if (state === 'independent_evidence' || state === 'delayed_evidence') return 'done'
  if (state === 'review_due' || state === 'overridden') return 'due'
  if (state === 'needs_review') return 'attention'
  if (state === 'introduced') return 'active'
  return 'quiet'
}

function cbSpineNodeStyle(tone, isCurrent, phone) {
  const size = phone ? '1.5rem' : '1.75rem'
  const base = {
    flex: `0 0 ${size}`,
    width: size,
    height: size,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: CB_SANS,
    fontVariantNumeric: 'tabular-nums',
    fontSize: CB_TYPE.caption,
    fontWeight: 600,
    lineHeight: 1,
    boxSizing: 'border-box'
  }
  if (tone === 'done') return { ...base, background: 'var(--cb-field)', color: 'var(--cb-paper)', border: 'none' }
  if (tone === 'due') return { ...base, background: 'var(--cb-paper)', color: 'var(--cb-ochre)', border: '2px solid var(--cb-ochre)' }
  if (tone === 'attention') return { ...base, background: 'var(--cb-paper)', color: 'var(--cb-coral)', border: '2px solid var(--cb-coral)' }
  if (tone === 'active') return { ...base, background: 'var(--cb-accent-soft)', color: 'var(--cb-accent)', border: '2px solid var(--cb-accent)' }
  return { ...base, background: 'var(--cb-paper)', color: 'var(--cb-ink-soft)', border: '1.5px solid var(--cb-rule)' }
}

/** The route: a surveyed spine with numbered nodes and a state word beside every node. */
function RouteSpine({ objectives, currentId, onSelect, phone, ariaLabel }) {
  const rows = objectives || []
  const nodeSize = phone ? '1.5rem' : '1.75rem'
  const left = phone ? '0.6875rem' : '0.8125rem'
  return jsx('ol', {
    'aria-label': ariaLabel || 'Course route',
    style: {
      listStyle: 'none',
      margin: 0,
      padding: 0,
      display: 'flex',
      flexDirection: 'column',
      position: 'relative'
    },
    children: rows.map((objective) => {
      const tone = cbSpineTone(objective.state)
      const isCurrent = Boolean(currentId && objective.objective_id === currentId)
      const word = DESK_STATE_WORD[objective.state] || 'Not started'
      return jsx(
        'li',
        {
          style: { position: 'relative', display: 'flex', flexDirection: 'column' },
          children: jsx(sdk.Button, {
            variant: 'text',
            className: 'w-full justify-start',
            'aria-current': isCurrent ? 'step' : undefined,
            onClick: onSelect ? () => onSelect(objective.objective_id) : undefined,
            children: jsxs('span', {
              'data-cb-path-item': objective.objective_id,
              'data-cb-path-state': objective.state,
              'data-cb-path-current': isCurrent ? 'true' : 'false',
              style: {
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.75rem',
                width: '100%',
                padding: isCurrent ? '0.55rem 0.4rem 0.55rem 0.1rem' : '0.45rem 0.1rem',
                margin: isCurrent ? '0 -0.4rem 0 -0.4rem' : 0,
                boxSizing: 'border-box',
                textAlign: 'left',
                color: 'var(--cb-ink)',
                fontFamily: CB_SANS,
                fontSize: CB_TYPE.meta,
                borderTop: '1px solid var(--cb-rule)',
                background: isCurrent ? 'var(--cb-accent-soft)' : 'transparent',
                borderLeft: isCurrent ? '2px solid var(--cb-accent)' : '2px solid transparent'
              },
              children: [
                jsx('span', {
                  'aria-hidden': 'true',
                  style: {
                    position: 'absolute',
                    left: left,
                    top: 0,
                    bottom: 0,
                    width: '1px',
                    background: 'var(--cb-rule)'
                  }
                }, 'line'),
                jsx('span', {
                  style: cbSpineNodeStyle(tone, isCurrent, phone),
                  children: String(objective.ordinal).padStart(2, '0')
                }),
                jsx('span', {
                  style: {
                    flex: '1 1 8rem',
                    minWidth: 0,
                    overflowWrap: 'anywhere',
                    whiteSpace: 'normal',
                    fontFamily: CB_SERIF,
                    fontSize: CB_TYPE.body,
                    fontWeight: 600,
                    lineHeight: 1.3
                  },
                  children: objective.title
                }),
                jsx('span', {
                  style: {
                    flex: '0 0 auto',
                    display: 'inline-flex',
                    alignItems: 'center',
                    fontFamily: CB_SANS,
                    fontSize: CB_TYPE.caption,
                    fontWeight: 600,
                    color: deskToneColor(tone),
                    border: `1px solid ${deskToneColor(tone)}`,
                    borderRadius: '999px',
                    padding: '0.1rem 0.5rem',
                    whiteSpace: 'nowrap'
                  },
                  children: word
                })
              ]
            })
          })
        },
        objective.objective_id
      )
    })
  })
}

/** The honest record: one tick per objective, never a bar, a ring or a percentage. */
function EvidenceTally({ objectives, caption, phone }) {
  const rows = (objectives || []).slice(0, 12)
  return jsxs('div', {
    'data-cb-tally': '',
    style: { display: 'flex', flexDirection: 'column', gap: '0.35rem' },
    children: [
      rows.length
        ? jsx('div', {
            'aria-hidden': 'true',
            style: { display: 'flex', flexWrap: 'wrap', gap: '4px' },
            children: rows.map((objective, index) => {
              const tone = cbSpineTone(objective.state)
              const paint =
                tone === 'done'
                  ? 'var(--cb-field)'
                  : tone === 'due'
                    ? 'var(--cb-ochre)'
                    : tone === 'attention'
                      ? 'var(--cb-coral)'
                      : tone === 'active'
                        ? 'var(--cb-accent)'
                        : 'var(--cb-rule)'
              return jsx('span', {
                style: { width: phone ? '18px' : '22px', height: '6px', borderRadius: 0, background: paint }
              }, `${objective.objective_id}-${index}`)
            })
          })
        : null,
      jsx('p', {
        'data-cb-tally-caption': '',
        style: { margin: 0, maxWidth: CB_MEASURE, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
        children: caption
      })
    ]
  })
}

/** The lit page: one flat field of light behind the thing that matters now. */
function HeroField({ identity, children, phone }) {
  const parent = identity === 'plum'
  return jsx('section', {
    'data-cb-hero': parent ? 'plum' : 'lamp',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.65rem',
      padding: phone ? '0.9rem 0.95rem' : '1.1rem 1.2rem 1.15rem',
      background: parent ? 'var(--cb-plum-soft)' : 'var(--cb-lamp-soft)',
      borderTop: `1px solid ${parent ? 'var(--cb-plum)' : 'var(--cb-lamp)'}`,
      maxWidth: '100%',
      boxSizing: 'border-box'
    },
    children
  })
}

/** The blank plate: a dashed rectangle and a seal ghost, never an illustration. */
function BlankPlate({ title, caption, action, tertiary }) {
  return jsxs('div', {
    'data-cb-blank-plate': '',
    style: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.85rem', padding: '1.5rem 1rem', textAlign: 'center' },
    children: [
      jsx('div', {
        'aria-hidden': 'true',
        style: {
          width: '100%',
          maxWidth: '240px',
          height: '120px',
          border: '1px dashed var(--cb-rule)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        },
        children: jsx('svg', {
          viewBox: '0 0 96 96',
          width: 40,
          height: 40,
          'aria-hidden': 'true',
          children: [
            jsx('rect', { x: 4, y: 4, width: 88, height: 88, fill: 'none', stroke: 'var(--cb-rule)', strokeWidth: 1.6 }, 'f'),
            jsx('path', { d: 'M4 92 A64 64 0 0 1 68 28', fill: 'none', stroke: 'var(--cb-rule)', strokeWidth: 7 }, 'a')
          ]
        })
      }),
      jsx('h3', {
        style: { margin: 0, fontFamily: CB_SERIF, fontSize: CB_TYPE.heading, fontWeight: 600, lineHeight: 1.15, color: 'var(--cb-ink)', maxWidth: '28ch' },
        children: title
      }),
      caption
        ? jsx('p', { style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)', maxWidth: '48ch' }, children: caption })
        : null,
      action || null,
      tertiary || null
    ]
  })
}

/** A mode hue is a 3px dot plus the mode word, never a coloured block. */
function ModeDot({ mode }) {
  const paint = mode === 'guided' ? 'var(--cb-field)' : mode === 'field_quest' ? 'var(--cb-ochre)' : 'var(--cb-accent)'
  return jsx('span', {
    'aria-hidden': 'true',
    style: { display: 'inline-block', width: '3px', height: '3px', minWidth: '3px', borderRadius: '50%', background: paint, verticalAlign: 'middle' }
  })
}

/** Which hue a surface owns: Textbook `accent`, Guided `field`, Field Quest `ochre`. */
function cbModeFor(view) {
  if (view === 'guided') return 'guided'
  if (view === 'field_quest') return 'field_quest'
  return 'textbook'
}

/**
 * Coursebook's one action primitive (H-151). `sdk.Button` supplies behaviour, focus and disabled
 * semantics; this table supplies the Coursebook control language so a route never inherits the
 * host's settings-page button (the default fill is the host accent, which is not a Coursebook
 * colour). Four variants and no fifth: `primary` is the single lamp field a screen is allowed,
 * `secondary` is a peer action beside it, `tertiary` is a text action inside prose or a meta line,
 * and `row` is a full-width list-row action that keeps its own 44px target.
 *
 * Targets: primary and secondary are 44px, row is 44px, tertiary is 24px. Type: body on the two
 * filled variants and the row, meta on the text action, so a route never gains a seventh size.
 */
const CB_ACTION_VARIANTS = Object.freeze(['primary', 'secondary', 'tertiary', 'row'])

const CB_ACTION_STYLES = {
  primary: {
    variant: 'default',
    minHeight: '44px',
    fontSize: CB_TYPE.body,
    className: undefined,
    style: {
      background: 'var(--cb-lamp)',
      color: 'var(--cb-on-lamp)',
      border: '1px solid var(--cb-on-lamp)',
      borderRadius: '2px',
      fontFamily: CB_SANS,
      fontWeight: 600
    }
  },
  secondary: {
    variant: 'secondary',
    minHeight: '44px',
    fontSize: CB_TYPE.body,
    className: undefined,
    style: {
      background: 'var(--cb-paper)',
      color: 'var(--cb-ink)',
      border: '1px solid var(--cb-ink)',
      borderRadius: '2px',
      fontFamily: CB_SANS,
      fontWeight: 600
    }
  },
  tertiary: {
    variant: 'text',
    minHeight: '24px',
    fontSize: CB_TYPE.meta,
    className: undefined,
    style: {
      background: 'transparent',
      color: 'var(--cb-ink)',
      border: 'none',
      borderRadius: 0,
      padding: '0.15rem 0',
      fontFamily: CB_SANS,
      fontWeight: 600
    }
  },
  row: {
    variant: 'text',
    minHeight: '44px',
    fontSize: CB_TYPE.body,
    className: 'w-full justify-start',
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'flex-start',
      textAlign: 'left',
      background: 'transparent',
      color: 'var(--cb-ink)',
      border: 'none',
      borderRadius: 0,
      padding: '0.35rem 0',
      fontFamily: CB_SANS,
      fontWeight: 500
    }
  }
}

/**
 * One wrapper around `sdk.Button`, so every migrated call site speaks the same control language.
 * The host `size` prop is accepted and dropped: the Coursebook variant owns the target and the
 * type step, so a caller cannot accidentally shrink a primary below 44px. A disabled primary
 * keeps the fill honest: it drops to paper and soft ink rather than pretending it is still live.
 */
function CbAction({ variant, className, style, disabled, children, ...rest }) {
  // The Coursebook variant owns the target and the type step; a caller's host `size` cannot
  // shrink a primary below 44px.
  delete rest.size
  const kind = Object.prototype.hasOwnProperty.call(CB_ACTION_STYLES, variant) ? variant : 'secondary'
  const spec = CB_ACTION_STYLES[kind]
  const palette = disabled && kind === 'primary'
    ? { background: 'var(--cb-paper)', color: 'var(--cb-ink-soft)', border: '1px solid var(--cb-rule)' }
    : null
  return jsx(sdk.Button, {
    ...rest,
    'data-cb-action': kind,
    disabled: Boolean(disabled),
    variant: spec.variant,
    className: [spec.className, className].filter(Boolean).join(' ') || undefined,
    style: {
      ...spec.style,
      ...(style || {}),
      ...(palette || {}),
      minHeight: spec.minHeight,
      fontSize: spec.fontSize
    },
    children
  })
}

/**
 * The state word with its hue. The pill is always text; colour is the second channel, never the
 * only one (docs/COURSEBOOK-VISUAL-IDENTITY-V2.md §2.3, §6.3).
 */
function CbStatePill({ state, label, phone }) {
  const tone = cbSpineTone(state)
  const word = label || DESK_STATE_WORD[state] || 'Not started'
  return jsx('span', {
    'data-cb-state-pill': state || 'not_started',
    'data-cb-state-tone': tone,
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      fontFamily: CB_SANS,
      fontSize: CB_TYPE.caption,
      fontWeight: 600,
      lineHeight: 1.3,
      color: deskToneColor(tone),
      border: `1px solid ${deskToneColor(tone)}`,
      borderRadius: '999px',
      padding: '0.15rem 0.55rem',
      whiteSpace: 'nowrap'
    },
    children: word
  })
}

/**
 * The recorded facts of a course, as one calm line rather than a metric block: the number and its
 * caption sit in reading order, separated by a rule. Only facts the backend read produced appear.
 */
function HeroFacts({ facts, phone }) {
  const rows = (facts || []).filter(Boolean)
  if (rows.length === 0) return null
  return jsx('div', {
    'data-cb-hero-facts': String(rows.length),
    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: phone ? '0.25rem 0.6rem' : '0.25rem 0.9rem', minWidth: 0 },
    children: rows.map((fact, index) =>
      jsxs('span', {
        'data-cb-hero-fact': fact.label,
        style: { display: 'inline-flex', alignItems: 'baseline', gap: '0.3rem', minWidth: 0 },
        children: [
          index > 0
            ? jsx('span', { 'aria-hidden': 'true', style: { color: 'var(--cb-ink-soft)' }, children: '·' })
            : null,
          jsx('span', {
            style: {
              fontFamily: CB_SANS,
              fontVariantNumeric: 'tabular-nums',
              fontSize: CB_TYPE.body,
              fontWeight: 600,
              lineHeight: 1.4,
              color: 'var(--cb-ink)',
              overflowWrap: 'anywhere'
            },
            children: fact.value
          }),
          jsx('span', {
            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
            children: fact.label
          })
        ]
      }, fact.label)
    )
  })
}

/**
 * Tier-one navigation for a course: a plain tab row with the mode dot on the reading surfaces and
 * a 2px underline on the current one. It never hides a surface behind a select.
 */
function LearningTabs({ options, value, onChange, phone, ariaLabel }) {
  return jsx('nav', {
    'aria-label': ariaLabel || 'Course surfaces',
    'data-cb-learning-tabs': value,
    role: 'tablist',
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      alignItems: 'stretch',
      gap: phone ? '0.15rem 0.5rem' : '0.15rem 1.1rem',
      borderBottom: '1px solid var(--cb-rule)',
      minWidth: 0
    },
    children: (options || []).map((option) => {
      const current = option.id === value
      const mode = option.mode ? cbModeFor(option.id) : null
      return jsx(
        sdk.Button,
        {
          variant: 'text',
          role: 'tab',
          'aria-selected': current ? 'true' : 'false',
          'data-cb-tab': option.id,
          className: '!h-auto !px-0 !py-0',
          onClick: () => onChange(option.id),
          children: jsx('span', {
            style: {
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: phone ? '0.7rem 0' : '0.45rem 0 0.4rem',
              borderBottom: current ? '2px solid var(--cb-accent)' : '2px solid transparent',
              fontFamily: CB_SANS,
              fontSize: CB_TYPE.meta,
              fontWeight: current ? 600 : 400,
              color: current ? 'var(--cb-ink)' : 'var(--cb-ink-soft)',
              whiteSpace: 'nowrap'
            },
            children: [mode ? jsx(ModeDot, { mode }) : null, option.label]
          })
        },
        option.id
      )
    })
  })
}

/**
 * The check / notice panel: `lamp-soft` with a 2px `lamp` top edge for a pending state, or a 1px
 * `coral` left edge for a retry. It is a field, not a card, and it never carries a red fill.
 */
function CheckPanelFrame({ kind, label, children }) {
  const retry = kind === 'retry'
  const pending = kind === 'pending'
  return jsxs('section', {
    'data-cb-check-panel': kind || 'check',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
      padding: retry ? '0.75rem 0.9rem 0.8rem 1rem' : '0.9rem 1rem 0.95rem',
      background: retry ? 'var(--cb-paper)' : pending ? 'var(--cb-lamp-soft)' : 'var(--cb-paper-raised)',
      borderTop: pending ? '1px solid var(--cb-lamp)' : 'none',
      borderLeft: retry ? '1px solid var(--cb-coral)' : 'none',
      maxWidth: CB_MEASURE,
      boxSizing: 'border-box'
    },
    children: [
      label
        ? jsx('div', {
            style: {
              fontFamily: CB_SANS,
              fontSize: CB_TYPE.caption,
              fontWeight: 600,
              lineHeight: 1.3,
              color: retry ? 'var(--cb-coral)' : 'var(--cb-ochre)'
            },
            children: label
          })
        : null,
      children
    ]
  })
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
          fontSize: CB_TYPE.caption,
          fontWeight: 600,
          letterSpacing: '0.01em',
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
    'aria-label': 'Section details',
    style: { display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: CB_TYPE.meta, lineHeight: 1.5 },
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
                  jsx('span', { style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' }, children: source.support_status || 'status unrecorded' })
                ]
              }, source.source_id || source.title)
            ) })
          : jsx('div', { style: { color: 'var(--cb-ink-soft)' }, children: 'No sources are recorded for this course yet.' })
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
  const wide = cbIsWide(layout)
  return jsxs('div', {
    'data-cb-workspace-shell': wide ? 'wide' : 'stacked',
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
              jsx('h2', {
                'data-cb-workspace-title': '',
                style: {
                  margin: 0,
                  fontFamily: CB_SERIF,
                  fontSize: CB_TYPE.heading,
                  fontWeight: 600,
                  lineHeight: 1.15,
                  letterSpacing: '-0.015em',
                  color: 'var(--cb-ink)'
                },
                children: title
              }),
              subtitle
                ? jsx('div', { style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' }, children: subtitle })
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
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem', fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
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
            style: { fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink)' },
            children: caption
          })
        : null,
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem', fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
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
            style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
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
            ? jsx('div', { style: { padding: '0.35rem 0', fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' }, children: 'Loading media' })
            : jsx('div', {
                style: { padding: '0.25rem 0', fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
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
            fontSize: CB_TYPE.meta
          },
          children: [
            jsx('span', { children: word.expected || '—' }),
            word.match
              ? null
              : jsx('span', {
                  style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                  children: word.heard ? `heard “${word.heard}”` : 'not heard'
                }),
            word.match && pronPercent(word.confidence)
              ? jsx('span', {
                  'data-cb-word-confidence': pronPercent(word.confidence),
                  style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
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
            message: 'Coursebook answered with data it could not read.'
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
        'Assessed by a model — a practice measurement, not a graded score.',
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
            style: { margin: 0, fontSize: CB_TYPE.meta, fontWeight: 600 },
            children: 'Pronunciation practice'
          }),
          jsx('span', {
            'data-cb-pronunciation-target': target,
            lang: locale,
            style: { fontSize: CB_TYPE.body },
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
            style: { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
            children:
              preview.state === 'loading'
                ? 'Loading the reference recording.'
                : 'No reference recording is attached to this block; the transcript above is the model.'
          }),

      jsx('p', {
        'data-cb-pronunciation-disclosure': availability.tone,
        'aria-live': 'polite',
        style: { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
        children: availability.text
      }),

      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' },
        children: [
          phase === 'recording'
            ? jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: stop, children: 'Stop' })
            : jsx(CbAction, {
                variant: 'primary',
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
                style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                children: `Recording — ${seconds} s of 30 s. Stop when you are done.`
              })
            : null,
          phase === 'comparing'
            ? jsx('span', {
                role: 'status',
                style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
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
              jsx('span', { style: { fontSize: CB_TYPE.meta, fontWeight: 600 }, children: `${error.code}: ${describeError(error)}` }),
              jsx('span', { style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' }, children: 'No evidence was recorded.' })
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
                    children: 'Practice measurement'
                  }),
                  jsx('span', {
                    'data-cb-pronunciation-verdict': assessment.verdict,
                    style: { fontSize: CB_TYPE.meta, fontWeight: 600 },
                    children: PRONUNCIATION_VERDICT_COPY[assessment.verdict] || assessment.verdict
                  }),
                  pronPercent(assessment.confidence)
                    ? jsx('span', {
                        'data-cb-pronunciation-confidence': pronPercent(assessment.confidence),
                        style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                        children: `Recogniser confidence ${pronPercent(assessment.confidence)}`
                      })
                    : null,
                  totalCount > 0
                    ? jsx('span', {
                        'data-cb-pronunciation-matched': `${matchedCount}/${totalCount}`,
                        style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                        children: `${matchedCount} of ${totalCount} ${pronUnitLabel(assessment.unit)} matched`
                      })
                    : null
                ]
              }),
              jsx('p', {
                style: { margin: 0, fontSize: CB_TYPE.meta, lineHeight: 1.5 },
                children: `Heard: ${assessment.transcript || 'nothing'}`
              }),
              jsx(PronunciationWords, { words: assessment.words, unit: assessment.unit }),
              jsx('p', {
                'data-cb-pronunciation-provenance': assessment.provider,
                style: { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
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
                        style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
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
              jsx('span', { style: { fontSize: CB_TYPE.meta, fontWeight: 600 }, children: 'Practice only, not graded' }),
              jsx('span', {
                style: { fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
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
 * Why a view cannot render for this document, in the learner's words.
 *
 * An older stored page has no `views` object at all; that is the same fact as `guided: false`,
 * not a reason to hide the choice. The switcher names all three views and explains the missing
 * ones instead of silently dropping them (H-96 / H-80 F3).
 */
const LESSON_VIEW_UNAVAILABLE_REASON = {
  guided: 'This lesson has no guided version.',
  field_quest: 'This lesson has no Field Quest version.'
}

/**
 * The views *this document* can render.
 *
 * Textbook is the floor. Guided needs authored `short` prose on every block. Field Quest needs the
 * same and exactly one attachable check, because its checkpoints are the document's existing
 * checks and nothing else. This returns only the enabled options (the legacy marker value);
 * `lessonViewChoices` returns all three with an availability flag and a reason.
 */
function lessonViewOptions(document) {
  const views = (document && document.views) || {}
  return LESSON_VIEWS.filter((view) => (view.id === 'textbook' ? true : Boolean(views[view.id])))
}

/** All three named views, each marked available or carrying the plain-words reason it is not. */
function lessonViewChoices(document) {
  const views = (document && document.views) || {}
  return LESSON_VIEWS.map((view) => {
    const available = view.id === 'textbook' ? true : Boolean(views[view.id])
    return {
      ...view,
      available,
      reason: available ? null : LESSON_VIEW_UNAVAILABLE_REASON[view.id] || `This lesson has no ${view.label} version.`
    }
  })
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
    'data-cb-block-sources': String(ids.length),
    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.3rem' },
    children: ids.map((id) =>
      jsx(
        'span',
        {
          'data-cb-source-chip': id,
          style: {
            display: 'inline-flex',
            maxWidth: '100%',
            minWidth: 0,
            alignItems: 'center',
            border: '1px solid var(--cb-rule)',
            borderRadius: '2px',
            padding: '0.1rem 0.45rem',
            fontFamily: CB_SANS,
            fontSize: CB_TYPE.caption,
            fontWeight: 600,
            lineHeight: 1.3,
            color: 'var(--cb-ink-soft)',
            whiteSpace: 'normal',
            overflowWrap: 'anywhere'
          },
          children: (index && index[id] && index[id].title) || `Source ${id}`
        },
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
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: '0.35rem',
        maxWidth: '48rem',
        padding: '0.55rem 0.7rem',
        border: '1px solid var(--cb-rule)',
        background: 'var(--cb-paper-raised)',
        borderRadius: 0,
        boxSizing: 'border-box'
      },
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

/**
 * Authored lesson prose is content underneath the page's one `h1`. A markdown document may carry
 * its own `#` title, so an `h1` inside a reading body is given ARIA heading level 2: the page keeps
 * exactly one `h1`, the prose keeps its own heading, and no level is skipped. The text, its order
 * and the host's markdown renderer are untouched — only the announced level changes.
 */
function useProseHeadingTier() {
  const ref = useRef(null)
  useEffect(() => {
    const root = ref.current
    if (!root) return undefined
    const apply = () => {
      for (const heading of root.querySelectorAll('h1')) {
        if (heading.getAttribute('role') === 'heading' && heading.getAttribute('aria-level') === '2') continue
        heading.setAttribute('role', 'heading')
        heading.setAttribute('aria-level', '2')
      }
    }
    apply()
    if (typeof MutationObserver !== 'function') return undefined
    const observer = new MutationObserver(apply)
    observer.observe(root, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [])
  return ref
}

/** The host's markdown renderer inside a reading body, with the one-`h1` prose tier applied. */
function ProseText({ text, ...wrapper }) {
  const ref = useProseHeadingTier()
  return jsx('div', { ...wrapper, ref, children: jsx(sdk.MessageTextContent, { text }) })
}

/** The excerpt a save will carry: the block's own prose, never a re-summarised one. */
function blockSaveExcerpt(block, checkLabels, media) {
  if (media) return media.text_equivalent || media.purpose || block.headline || ''
  return withoutCheckLabels(block.deep, checkLabels) || block.short || block.headline || ''
}

/**
 * The reading voice of one block: serif, 66ch, 1.65. The first block of a section is its lede and
 * carries a 2px `accent` reading edge; every later block is the same column without the edge, so
 * long prose stays scannable without a second font or a card per paragraph.
 */
function BlockBody({ block, sources, checkSlot, checkLabels, onSaveBlock, pronunciation, lede }) {
  const body = withoutCheckLabels(block.deep, checkLabels)
  return jsxs('div', {
    className: 'flex flex-col gap-2',
    children: [
      body
        ? jsx(ProseText, {
            'data-cb-reading-body': lede ? 'lede' : 'body',
            style: {
              maxWidth: CB_MEASURE,
              fontFamily: CB_SERIF,
              fontSize: lede ? CB_TYPE.lead : CB_TYPE.body,
              lineHeight: lede ? 1.5 : 1.65,
              color: 'var(--cb-ink)',
              borderLeft: lede ? '1px solid var(--cb-accent)' : 'none',
              paddingLeft: lede ? '0.9rem' : 0
            },
            text: body
          })
        : null,
      (block.media || []).map((media, index) =>
        jsx(BlockMedia, { media, blockId: block.id, ordinal: index }, `${block.id}-media-${index}`)
      ),
      jsx(PronunciationSeat, { block, pronunciation }),
      jsx(BlockSourceChips, { ids: block.source_ids, index: sources }),
      jsx(BlockSaveActions, { block, checkLabels, onSaveBlock }),
      checkSlot
        ? jsx(CheckPanelFrame, {
            kind: 'check',
            label: 'Checkpoint',
            children: jsx('div', {
              className: 'flex flex-col gap-2',
              'data-cb-block-check': block.id,
              children: [
                checkSlot,
                jsx('p', {
                  style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
                  children: 'This is the section’s one check. It is the same in Textbook, Guided and Field Quest, and it is not a grade.'
                })
              ]
            })
          })
        : null
    ]
  })
}

/** Textbook: every block in authored order, the full `deep` prose, inline figures. */
function TextbookBlock({ block, sources, checkSlot, checkLabels, onSaveBlock, pronunciation, lede }) {
  return jsxs('article', {
    className: 'flex flex-col gap-2',
    'data-cb-block': block.id,
    'data-cb-role': block.role,
    'data-cb-block-lede': lede ? 'true' : 'false',
    tabIndex: -1,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
      maxWidth: CB_MEASURE,
      padding: lede ? '0 0 1.35rem' : '1.35rem 0',
      borderTop: lede ? 'none' : '1px solid var(--cb-rule)'
    },
    children: [
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.25rem 0.6rem' },
        children: [
          jsx('h3', {
            style: {
              margin: 0,
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.heading,
              fontWeight: 600,
              lineHeight: 1.25,
              letterSpacing: '-0.01em',
              color: 'var(--cb-ink)',
              maxWidth: '34ch',
              overflowWrap: 'anywhere'
            },
            children: block.headline
          }),
          jsx('span', {
            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, fontWeight: 600, lineHeight: 1.3, color: 'var(--cb-ink-soft)' },
            children: BLOCK_ROLE_COPY[block.role] || block.role
          })
        ]
      }),
      BlockBody({ block, sources, checkSlot, checkLabels, onSaveBlock, pronunciation, lede })
    ]
  })
}

/** Guided: one step at a time, the authored `short` prose, the step's place, and the action. */
function GuidedBlock({ block, index, total, sources, checkSlot, checkLabels, onBack, onNext, onSaveBlock, pronunciation }) {
  const last = index >= total - 1
  const body = withoutCheckLabels(block.short || block.deep, checkLabels)
  const phone = cbLayoutFor(useCbViewportWidth()) === 'phone'
  return jsxs('section', {
    className: 'flex flex-col gap-3',
    'aria-labelledby': `cb-guided-headline-${block.id}`,
    'data-cb-block': block.id,
    'data-cb-role': block.role,
    'data-cb-step-count': `${index + 1}/${total}`,
    tabIndex: -1,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.75rem',
      maxWidth: CB_MEASURE,
      paddingLeft: phone ? 0 : '2.75rem',
      position: 'relative'
    },
    children: [
      // The step margin: a 28px node and a 1px connector in the Guided hue. At narrow widths the
      // step number moves into the heading line instead of shrinking the reading column.
      phone
        ? null
        : jsxs('span', {
            'aria-hidden': 'true',
            style: { position: 'absolute', left: 0, top: '0.15rem', display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%' },
            children: [
              jsx('span', {
                'data-cb-guided-node': String(index + 1),
                style: {
                  width: '1.75rem',
                  height: '1.75rem',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'var(--cb-accent-soft)',
                  border: '2px solid var(--cb-field)',
                  color: 'var(--cb-field)',
                  fontFamily: CB_SANS,
                  fontVariantNumeric: 'tabular-nums',
                  fontSize: CB_TYPE.caption,
                  fontWeight: 600
                },
                children: String(index + 1).padStart(2, '0')
              }),
              jsx('span', { style: { flex: '1 1 auto', width: '1px', background: 'var(--cb-rule)', marginTop: '0.25rem' } })
            ]
          }),
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.3rem 0.75rem' },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.25rem 0.6rem', minWidth: 0 },
            children: [
              jsx('h3', {
                id: `cb-guided-headline-${block.id}`,
                style: {
                  margin: 0,
                  minWidth: 0,
                  fontFamily: CB_SERIF,
                  fontSize: CB_TYPE.heading,
                  fontWeight: 600,
                  lineHeight: 1.2,
                  letterSpacing: '-0.01em',
                  color: 'var(--cb-ink)',
                  overflowWrap: 'anywhere'
                },
                children: block.headline
              }),
              jsx('span', {
                style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, fontWeight: 600, lineHeight: 1.3, color: 'var(--cb-field)' },
                children: BLOCK_ROLE_COPY[block.role] || block.role
              })
            ]
          }),
          jsx('span', {
            style: {
              fontFamily: CB_SANS,
              fontVariantNumeric: 'tabular-nums',
              fontSize: CB_TYPE.caption,
              color: 'var(--cb-ink-soft)'
            },
            'aria-live': 'polite',
            'data-cb-step': `${index + 1}/${total}`,
            children: `Step ${index + 1} of ${total}`
          })
        ]
      }),
      body
        ? jsx(ProseText, {
            style: {
              maxWidth: CB_MEASURE,
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.lead,
              lineHeight: 1.6,
              color: 'var(--cb-ink)'
            },
            text: body
          })
        : null,
      (block.media || []).map((media, ordinal) =>
        jsx(BlockMedia, { media, blockId: block.id, ordinal }, `${block.id}-media-${ordinal}`)
      ),
      jsx(PronunciationSeat, { block, pronunciation }),
      jsx(BlockSourceChips, { ids: block.source_ids, index: sources }),
      jsx(BlockSaveActions, { block, checkLabels, onSaveBlock }),
      checkSlot
        ? jsx(CheckPanelFrame, {
            kind: 'check',
            label: 'Checkpoint',
            children: jsx('div', { className: 'flex flex-col gap-2', 'data-cb-block-check': block.id, children: checkSlot })
          })
        : null,
      jsxs('div', {
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '0.5rem',
          paddingTop: '0.65rem',
          borderTop: '1px solid var(--cb-rule)'
        },
        children: [
          jsx(sdk.Button, {
            variant: 'secondary',
            size: 'sm',
            disabled: index === 0,
            onClick: onBack,
            children: 'Back'
          }),
          jsx(CbAction, {
            variant: 'primary',
            disabled: last,
            onClick: onNext,
            children: 'Continue'
          }),
          last
            ? jsx('span', {
                style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
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

/**
 * One mission on the quest spine: a numbered node, the role word, a serif title, one line of what
 * the learner does, and one tertiary way into the same block in Textbook. A checkpoint keeps the
 * same node but gains the `lamp-soft` check field. Nothing is locked, nothing is scored, and the
 * clickable affordance is the whole brief — not a grey bar under every mission
 * (docs/COURSEBOOK-VISUAL-IDENTITY-V2.md §4.7, §5.9).
 */
function QuestMission({ mission, sources, checkSlot, checkLabels, onReadInTextbook, onSaveBlock, pronunciation }) {
  const block = mission.block
  const body = withoutCheckLabels(block.short || block.deep, checkLabels)
  const checkpoint = mission.checkpoint
  const stateWord = checkpoint ? 'Checkpoint' : 'Mission'
  const tone = checkpoint ? 'var(--cb-ochre)' : 'var(--cb-ink-soft)'
  const headingId = `cb-mission-headline-${block.id}`
  // The mission's heading and prose are the brief. Clicking anywhere outside an actual control
  // hands the same block to Textbook, so a learner who taps the brief is not left wondering
  // whether the card is decorative. Nested controls keep their own behaviour.
  const openMission = (event) => {
    const target = event && event.target
    if (
      target &&
      typeof target.closest === 'function' &&
      target.closest('button, a, input, textarea, select, [role="button"], [role="checkbox"], [role="radio"]')
    ) {
      return
    }
    if (onReadInTextbook) onReadInTextbook(block.id)
  }
  const openMissionOnKey = (event) => {
    if (event.target !== event.currentTarget) return
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      if (onReadInTextbook) onReadInTextbook(block.id)
    }
  }
  return jsxs('li', {
    'data-cb-mission': block.id,
    'data-cb-mission-index': String(mission.index + 1),
    'data-cb-mission-role': block.role,
    'data-cb-mission-checkpoint': checkpoint ? 'true' : 'false',
    'data-cb-mission-check': checkpoint && block.check_id ? block.check_id : '',
    tabIndex: 0,
    role: 'link',
    'aria-label': `Open mission ${mission.index + 1}, ${block.headline}, in Textbook`,
    title: 'Open this mission in Textbook',
    onClick: openMission,
    onKeyDown: openMissionOnKey,
    style: {
      position: 'relative',
      display: 'flex',
      flexDirection: 'column',
      listStyle: 'none',
      padding: checkpoint ? '0.85rem 0.95rem 0.95rem 2.9rem' : '0.75rem 0.5rem 0.8rem 2.9rem',
      background: checkpoint ? 'var(--cb-lamp-soft)' : 'transparent',
      borderTop: checkpoint ? '1px solid var(--cb-lamp)' : 'none',
      maxWidth: '46rem',
      boxSizing: 'border-box',
      cursor: 'pointer'
    },
    children: [
      // The spine: a node per mission and a hairline that runs through the whole list.
      jsxs('span', {
        'aria-hidden': 'true',
        style: { position: 'absolute', left: '0.75rem', top: 0, bottom: 0, display: 'flex', flexDirection: 'column', alignItems: 'center' },
        children: [
          jsx('span', {
            'data-cb-mission-node': String(mission.index + 1),
            style: {
              width: '1.75rem',
              height: '1.75rem',
              flex: '0 0 1.75rem',
              marginTop: checkpoint ? '0.05rem' : '0.1rem',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: checkpoint ? 'var(--cb-ochre)' : 'var(--cb-paper)',
              color: checkpoint ? 'var(--cb-paper)' : 'var(--cb-ink-soft)',
              border: checkpoint ? 'none' : '1.5px solid var(--cb-rule)',
              fontFamily: CB_SANS,
              fontVariantNumeric: 'tabular-nums',
              fontSize: CB_TYPE.caption,
              fontWeight: 600
            },
            children: String(mission.index + 1).padStart(2, '0')
          }),
          jsx('span', { style: { flex: '1 1 auto', width: '1px', background: 'var(--cb-rule)', marginTop: '0.2rem' } })
        ]
      }),
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.2rem 0.75rem' },
        children: [
          jsx('h3', {
            id: headingId,
            style: {
              margin: 0,
              minWidth: 0,
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.heading,
              fontWeight: 600,
              lineHeight: 1.25,
              color: 'var(--cb-ink)',
              overflowWrap: 'anywhere'
            },
            children: block.headline
          }),
          jsxs('span', {
            'data-cb-mission-state': checkpoint ? 'checkpoint' : 'mission',
            style: {
              flex: '0 0 auto',
              fontFamily: CB_SANS,
              fontSize: CB_TYPE.caption,
              fontWeight: 600,
              lineHeight: 1.3,
              color: tone
            },
            children: [stateWord, ' · ', BLOCK_ROLE_COPY[block.role] || block.role]
          })
        ]
      }),
      body
        ? jsx(ProseText, {
            style: {
              maxWidth: CB_MEASURE,
              paddingTop: '0.3rem',
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.body,
              lineHeight: 1.6,
              color: 'var(--cb-ink)'
            },
            text: body
          })
        : null,
      (block.media || []).map((media, ordinal) =>
        jsx(BlockMedia, { media, blockId: block.id, ordinal }, `${block.id}-media-${ordinal}`)
      ),
      jsx(BlockSourceChips, { ids: block.source_ids, index: sources }),
      jsx(BlockSaveActions, { block, checkLabels, onSaveBlock, className: 'flex flex-wrap items-center gap-1 self-start' }),
      jsx(PronunciationSeat, { block, pronunciation }),
      checkpoint
        ? jsxs('div', {
            'data-cb-mission-gate': block.check_id || 'unattached',
            style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', paddingTop: '0.35rem' },
            children: [
              jsx('p', {
                style: { margin: 0, maxWidth: CB_MEASURE, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                children: 'This is the section’s existing check — the same one Textbook and Guided use. Finishing it is not required to read anything here.'
              }),
              checkSlot
                ? jsx('div', { style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' }, children: checkSlot })
                : jsx('div', {
                    style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
                    children: 'No check could be attached to this checkpoint, so the mission stays readable and ungated.'
                  })
            ]
          })
        : null,
      // One tertiary link at the foot of the brief, not a full-width bar under every mission.
      jsx('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', paddingTop: '0.35rem' },
        children: jsx(sdk.Button, {
          variant: 'text',
          size: 'sm',
          className: 'self-start',
          'data-cb-mission-read': block.id,
          'aria-label': `Read mission ${mission.index + 1}, ${block.headline}, in Textbook`,
          onClick: () => onReadInTextbook(block.id),
          children: 'Read in Textbook'
        })
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
  const phone = cbLayoutFor(useCbViewportWidth()) === 'phone'
  const progressLabel = questProgressLabel(progress)
  const checkpoints = missions.filter((mission) => mission.checkpoint).length
  const display = `${missions.length} ${missions.length === 1 ? 'mission' : 'missions'}, ${checkpoints} ${checkpoints === 1 ? 'checkpoint' : 'checkpoints'}`
  const due = progress && typeof progress === 'object' ? Number(progress.review_due) || 0 : 0
  const independent = progress && typeof progress === 'object' ? Number(progress.independent) || 0 : 0
  const hasRecord = progress && typeof progress === 'object' && Number(progress.total_objectives) > 0
  return jsxs('div', {
    ...lessonTextAttrs(document),
    'data-cb-lesson-view': 'field_quest',
    'data-cb-document': document.document_id,
    'data-cb-motion': motion,
    'data-cb-quest-progress': progressLabel,
    'data-cb-quest-missions': String(missions.length),
    'data-cb-quest-checkpoints': String(checkpoints),
    style: { display: 'flex', flexDirection: 'column', gap: '0.9rem' },
    children: [
      jsxs('header', {
        'data-cb-quest-head': '',
        style: { display: 'flex', flexDirection: 'column', gap: '0.45rem', maxWidth: '46rem' },
        children: [
          jsx('h2', {
            style: {
              margin: 0,
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.heading,
              fontWeight: 600,
              lineHeight: 1.1,
              letterSpacing: '-0.015em',
              color: 'var(--cb-ink)',
              maxWidth: '24ch'
            },
            children: display.charAt(0).toUpperCase() + display.slice(1)
          }),
          jsx('p', {
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)', maxWidth: '52ch' },
            children: 'Missions are the reading path. The checkpoint is shared with the other lesson views.'
          }),
          jsx(HeroFacts, {
            phone,
            facts: [
              { value: String(missions.length), label: 'Missions' },
              { value: String(checkpoints), label: 'Checkpoints' },
              hasRecord ? { value: String(due), label: 'Due for review' } : null
            ].filter(Boolean)
          }),
          jsxs('details', {
            'data-cb-quest-note': '',
            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: [
              jsx('summary', { style: { cursor: 'pointer' }, children: 'What these counts mean' }),
              jsx('p', {
                style: { margin: '0.3rem 0 0', lineHeight: 1.5, maxWidth: '52ch' },
                children: hasRecord
                  ? `Counts describe evidence already recorded — ${independent} independent, ${due} due. They are not a score, nothing here is locked, and the checkpoint is the section’s existing check.`
                  : 'Counts describe evidence already recorded. They are not a score, nothing here is locked, and the checkpoint is the section’s own check.'
              })
            ]
          })
        ]
      }),
      jsx('ol', {
        'data-cb-quest-path': '',
        style: { listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 0 },
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
  schematic: 'Drawing made from the steps below.',
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
        'data-cb-procedure-tools': String(tools.length),
        style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', minWidth: '12rem', flex: '1 1 12rem' },
        children: [
          jsx(DeskLabel, { children: 'Tools' }),
          jsx('ul', {
            style: { margin: 0, paddingLeft: '1.1rem', fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink)' },
            children: tools.map((item, index) => jsx('li', { children: item }, `${sectionTitle}-tool-${index}`))
          })
        ]
      }, 'tools')
    )
  }
  if (parts.length > 0) {
    columns.push(
      jsxs('div', {
        'data-cb-procedure-parts': String(parts.length),
        style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', minWidth: '12rem', flex: '1 1 12rem' },
        children: [
          jsx(DeskLabel, { children: 'Parts' }),
          jsx('ul', {
            style: { margin: 0, paddingLeft: '1.1rem', fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink)' },
            children: parts.map((item, index) => jsx('li', { children: item }, `${sectionTitle}-part-${index}`))
          })
        ]
      }, 'parts')
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
            style: { margin: 0, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
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
      borderLeft: '1px solid var(--cb-coral)',
      background: 'var(--cb-paper-raised)',
      maxWidth: '48rem'
    },
    children: [
      jsx('div', {
        style: {
          fontSize: CB_TYPE.caption,
          fontWeight: 700,
          letterSpacing: '0.01em',
          color: 'var(--cb-coral)'
        },
        children: 'Do not continue'
      }),
      list.length > 0
        ? jsx('ul', {
            style: { margin: 0, paddingLeft: '1.1rem', fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink)' },
            children: list.map((item, index) => jsx('li', { children: item }, `hazard-${index}`))
          })
        : null,
      jsxs('p', {
        'data-cb-procedure-stop': '',
        style: { margin: 0, fontSize: CB_TYPE.meta, lineHeight: 1.6, color: 'var(--cb-ink)' },
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
        style: { margin: 0, fontSize: CB_TYPE.body, fontWeight: 600, color: 'var(--cb-ink)' },
        children: schematic.title
      }),
      jsx('div', {
        style: { fontSize: CB_TYPE.caption, letterSpacing: '0.01em', color: 'var(--cb-ink-soft)' },
        children: 'Drawing from the steps below'
      }),
      jsx('table', {
        'data-cb-procedure-rows': String(rows.length),
        style: { borderCollapse: 'collapse', width: '100%', fontSize: CB_TYPE.meta, color: 'var(--cb-ink)' },
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
        style: { margin: 0, fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
        children: schematic.text_equivalent
      }),
      schematic.source_id
        ? jsx('p', {
            'data-cb-procedure-schematic-source': schematic.source_id,
            style: { margin: 0, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: `Facts from ${(source && source.title) || schematic.source_id}`
          })
        : null,
      schematic.artifact_id
        ? jsx(BlockMedia, {
            media: {
              artifact_id: schematic.artifact_id,
              role: 'schematic',
              label: 'Drawing made from these steps.',
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
          jsx('span', { style: { fontSize: CB_TYPE.meta, fontWeight: 600, color: 'var(--cb-ink)' }, children: (meta && meta.title) || source.source_id }),
          jsx(sdk.Badge, { size: 'xs', variant: source.permission === 'licensed' ? 'muted' : 'outline', children: permission })
        ]
      }),
      meta && meta.url
        ? jsx('a', {
            href: meta.url,
            rel: 'noreferrer noopener',
            target: '_blank',
            style: { fontSize: CB_TYPE.meta, color: 'var(--cb-accent)', overflowWrap: 'anywhere' },
            children: meta.url
          })
        : null,
      jsx('p', {
        style: { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
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
        'data-cb-procedure-media': item.role || 'media',
        style: { display: 'flex', flexDirection: 'column', gap: '0.25rem' },
        children: [
          note
            ? jsx('p', {
                'data-cb-procedure-media-note': item.role || '',
                style: { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: item.role === 'illustration' ? 'var(--cb-ochre)' : 'var(--cb-ink-soft)' },
                children: note
              })
            : null,
          jsx(BlockMedia, { media: item, blockId: block.id, ordinal })
        ]
      },
      `${block.id}-procedure-media-${ordinal}`
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
          fontSize: CB_TYPE.meta,
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
                style: { margin: 0, fontSize: CB_TYPE.body, fontWeight: 600, lineHeight: 1.35, color: 'var(--cb-ink)' },
                children: block.headline
              })
            ]
          }),
          body
            ? jsx(ProseText, { style: { maxWidth: '44rem' }, text: body })
            : null,
          step.check
            ? jsxs('p', {
                'data-cb-procedure-step-check': block.id,
                style: { margin: 0, fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
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
                  style: { margin: 0, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
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
        children: [jsx(CbLabel, { children: 'Check' }), checkSlot]
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
        children: blocks.map((block, index) =>
          jsx(
            TextbookBlock,
            {
              block,
              lede: index === 0,
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

function SectionPage({ row, objectiveId, page, pageStatus, pageError, onRetryPage, implemented, onBack, onChanged, review, targetBlockId, embedded }) {
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
  // A parent-recipe objective is observed by the adult: its check is a parent observation
  // (`coursebook/generation.py` rejects anything else for that recipe) and the confirmation lane is
  // disabled for it (`coursebook/grading.py`, docs/CHECKLIST-CONFIRMATION.md §6), so the observation
  // is the only recording path for this surface. A learner surface never gets this node.
  const parentLed = Boolean(row && row.recipe === 'parent')
  const observationNode = parentLed
    ? supports('observation.record')
      ? jsx(ParentObservation, {
          enrollmentId: row.enrollment_id,
          objectiveId,
          onRecorded: () => {
            if (onChanged) onChanged()
          }
        })
      : jsxs('div', {
          className: 'flex flex-col gap-2',
          children: [
            jsx(CbLabel, { children: 'Parent observation' }),
            jsx(QuietNote, {
              children:
                'This Desktop build cannot record a parent observation: the backend does not implement observation.record (cb.rpc v14). The section stays readable; nothing can be recorded here yet.'
            })
          ]
        })
    : null

  // When a live check is mounted it is the learner's action on this surface; the chat-run action
  // steps back to secondary so the screen still has exactly one primary (H-151).
  const checkOwnsPrimary = Boolean(!parentLed && check && check.check)
  const checkNode =
    check.status === 'error'
      ? jsx(QuietNote, {
          children: check.error
            ? `${check.error.code}: ${describeError(check.error)}`
            : 'The current check could not be opened.'
        })
      : check.status === 'loading' && !check.check
        ? jsx(sdk.Loader, { label: 'Opening the current check' })
        : jsx(AttemptControls, {
          enrollmentId: row.enrollment_id,
          objectiveId,
          check: check.check,
          revision: page ? page.revision : 0,
          implemented,
          bindingState: runtime ? runtime.binding_status : 'detached',
          parentLed,
          stimulusStatus: check.stimulusStatus,
          stimulusError: check.stimulusError,
          onRetryStimulus: check.reload,
          onCommitted: () => {
            if (onChanged) onChanged()
          }
        })
  // The practice slot: the observation for a parent-led lesson, the graded check everywhere else.
  // It is mounted once by the page body below, not inside a document block: a parent observation is
  // not a check, so it must not inherit the block's `CHECK` heading, and it must still be reachable
  // on a section whose document has no blocks yet.

  const begin = useCallback(
    async (mode) => {
      setBusy(true)
      setNotice(null)
      // One shared path with the course detail: a fresh run arms the exact run, then this surface
      // opens the new chat that carries that binder. It never leaves the learner on a blank chat
      // with no indication of which run it belongs to.
      const outcome = await beginLessonFor({
        row,
        objectiveId,
        objectiveTitle: section ? section.title : null,
        mode,
        profile: row.profile || currentScope().profile
      })
      setBusy(false)
      if (outcome.ok && outcome.armed) {
        // A fresh run is only useful once the learner can type into it. The run is armed first;
        // opening the new chat then lets CoursebookPane name that exact run (never a recency
        // guess). If the host cannot open a chat, the explicit action remains on this page.
        const opened = openArmedLessonChat(row.profile || currentScope().profile)
        setNotice(
          opened
            ? { text: 'A new lesson chat is open. Send the first message to connect it to this lesson.' }
            : {
                text: outcome.message,
                action: {
                  label: 'Open the lesson chat',
                  run: () => startLessonChat(row.profile || currentScope().profile)
                }
              }
        )
        if (onChanged) onChanged()
        return
      }
      if (!outcome.ok && outcome.reason === 'no-binding') {
        // Resume is impossible without a saved chat. Do not leave the learner with a sentence and
        // no way forward: the same arm path the fresh button uses is the honest next action.
        setNotice({
          text: outcome.message,
          action: { label: 'Start a fresh run', run: () => begin('fresh') }
        })
        return
      }
      setNotice(outcome.message)
      if (outcome.ok && onChanged) onChanged()
    },
    [row, objectiveId, section, onChanged]
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
        ? jsx('section', {
            'data-cb-section-error': '',
            style: {
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
              maxWidth: CB_MEASURE,
              padding: '0.8rem 0.9rem 0.85rem 1rem',
              borderLeft: '1px solid var(--cb-coral)'
            },
            children: [
              jsx('h3', {
                style: { margin: 0, fontFamily: CB_SERIF, fontSize: CB_TYPE.heading, fontWeight: 600, lineHeight: 1.2, color: 'var(--cb-ink)' },
                children: 'This section could not be read'
              }),
              jsx('p', {
                style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink)' },
                children: 'Nothing was lost. The page is still saved on this profile; the read just did not finish.'
              }),
              pageError && pageError.code
                ? jsxs('details', {
                    style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                    children: [
                      jsx('summary', { style: { cursor: 'pointer' }, children: 'Technical detail' }),
                      jsx('p', { style: { margin: '0.25rem 0 0' }, children: `${pageError.code}: ${describeError(pageError)}` })
                    ]
                  })
                : null,
              jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', gap: '0.5rem', paddingTop: '0.2rem' },
                children: [
                  jsx(CbAction, { variant: 'primary', onClick: onRetryPage, children: 'Try again' }),
                  jsx(CbAction, { variant: 'secondary', onClick: openCapabilities, children: 'Open Capabilities' })
                ]
              })
            ]
          })
        : jsx('div', {
            style: { padding: '2rem 0', display: 'flex', justifyContent: 'center' },
            children: jsx(sdk.Loader, { label: 'Reading this section' })
          })
  } else {
    body = jsxs('div', {
      className: 'flex flex-col gap-4',
      children: [
        document && !(document.views && document.views.guided) && document.view_note
          ? jsx(QuietNote, { children: document.view_note })
          : null,

        !bindingActive
          ? jsx('div', {
              // A section may have no runtime read at all (the no-chat case): page.runtime is null,
              // and only `bindingActive` is guaranteed. Never dereference `runtime` unguarded here.
              'data-cb-detached': (runtime && runtime.binding_status) || 'detached',
              style: {
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '0.5rem',
                padding: '0.7rem 0.9rem',
                background: 'var(--cb-lamp-soft)',
                borderTop: '1px solid var(--cb-lamp)'
              },
              children: [
                jsx('span', {
                  style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink)' },
                  children: 'This section has no lesson chat yet. Start one and send the first message to begin.'
                })
              ]
            })
          : null,

        // One live action per screen. With no chat open the primary arms a run and opens its
        // chat; with a chat open it resumes that chat. There is no second button for the same run.
        jsxs('div', {
          'data-cb-section-actions': bindingActive ? 'resume' : 'start',
          style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.6rem' },
          children: [
            jsx(CbAction, {
              'data-cb-section-primary': '',
              variant: embedded || checkOwnsPrimary ? 'secondary' : 'primary',
              disabled: busy,
              onClick: () => begin(bindingActive ? 'resume' : 'fresh'),
              children: busy ? 'Opening the lesson' : bindingActive ? 'Continue in the lesson chat' : 'Start a fresh run'
            })
          ]
        }),
        jsx(NoticeLine, { notice, busy }),

        document
          ? jsx(
              LessonDocumentView,
              {
                document,
                view: lessonView,
                sources: sourceIndex,
                checkSlot: parentLed ? null : checkNode,
                checkLabels,
                progress: row.evidence_summary || null,
                focusBlockId,
                onOpenBlock: openBlock,
                onSaveBlock: supports('notebook.save') ? saveBlock : null,
                pronunciation
              },
              objectiveId
            )
          : jsx(CbLabel, { children: 'Teaching segments' }),
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
                          jsx('span', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: cbSegmentWord(segment.kind) }),
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
                        : jsx(ProseText, { className: 'max-w-3xl', text: segment.text }),
                      segment.source_id
                        ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: `Source ${segment.source_id}` })
                        : null
                    ]
                  },
                  segment.segment_id
                )
              )
            })
          : jsx(BlankPlate, {
              title: 'No teaching yet',
              caption:
                'A teaching turn in the lesson chat writes the first segment here. Coursebook does not write it for you.'
            }),

        // A parent-recipe page records an observation; it never mounts the graded check node.
        parentLed ? observationNode : null,

        document || parentLed ? null : jsx(CbLabel, { children: 'Current check' }),
        document || parentLed ? null : checkNode,

        // Repeated identical attempt rows are collapsed into one summary plus a disclosure: the
        // count is recorded, the detail is available, and the reading column stays quiet.
        page.attempts && page.attempts.length > 0
          ? jsxs('details', {
              'data-cb-attempts': String(page.attempts.length),
              style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', maxWidth: CB_MEASURE },
              children: [
                jsx('summary', {
                  style: { cursor: 'pointer', fontFamily: CB_SANS, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
                  children: `${page.attempts.length} ${page.attempts.length === 1 ? 'attempt' : 'attempts'} recorded on this section · last ${whenLabel(page.attempts[0].committed_at || page.attempts[0].created_at)}`
                }),
                jsx('div', {
                  style: { display: 'flex', flexDirection: 'column', paddingTop: '0.3rem' },
                  children: page.attempts.map((attempt) =>
                    jsxs(
                      'div',
                      {
                        className: 'flex flex-wrap items-center justify-between gap-2 text-xs',
                        style: { borderTop: '1px solid var(--cb-rule)', padding: '0.4rem 0' },
                        children: [
                          jsx('span', { style: { color: 'var(--cb-ink-soft)' }, children: whenLabel(attempt.committed_at || attempt.created_at) }),
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
                })
              ]
            })
          : null,

        page.notebook_entries && page.notebook_entries.length > 0
          ? jsxs('div', {
              className: 'flex flex-col gap-1',
              children: [
                jsx(CbLabel, { children: 'Saved from this section' }),
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
        { label: 'State', value: DESK_STATE_WORD[section.state] || 'Not started' },
        { label: 'Evidence', value: learnerEvidenceTarget(section.evidence_target) || 'Not recorded' },
        { label: 'Attempts', value: String((page && page.attempts ? page.attempts.length : 0)) }
      ]
    : []
  const viewOptions = document ? lessonViewOptions(document) : []
  const viewChoices = document ? lessonViewChoices(document) : []
  const unavailableViews = viewChoices.filter((choice) => !choice.available)
  const activeView = viewOptions.some((option) => option.id === lessonView) ? lessonView : 'textbook'
  const activeMode = cbModeFor(activeView)
  // One switcher, always in the header, at every pane width. The three names never disappear: a
  // view this document cannot render stays as a disabled choice with its reason in plain words,
  // and no breakpoint swaps the row for a hidden rail or a below-fold combobox (H-96 / H-80 F3).
  const switcher = document
    ? jsxs('div', {
        role: 'group',
        'aria-label': 'Lesson view',
        className: 'flex flex-wrap items-center gap-2',
        style: { minWidth: 0 },
        'data-cb-view-switcher': viewOptions.length > 1 ? 'available' : 'textbook-only',
        'data-cb-view-options': viewOptions.map((option) => option.id).join(' '),
        'data-cb-view-unavailable': unavailableViews.map((choice) => choice.id).join(' '),
        children: [
          jsxs('span', {
            style: { display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: [jsx(ModeDot, { mode: activeMode }), 'Lesson view']
          }, 'label'),
          jsx('div', {
            'data-cb-view-choice-row': '',
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.25rem', minWidth: 0 },
            children: viewChoices.map((choice) =>
              jsx(
                sdk.Button,
                {
                  size: 'xs',
                  variant: choice.id === activeView ? 'secondary' : 'ghost',
                  disabled: !choice.available,
                  title: choice.reason || undefined,
                  'aria-pressed': choice.available ? choice.id === activeView : undefined,
                  'aria-describedby': choice.available ? undefined : `cb-view-reason-${choice.id}`,
                  'data-cb-view-choice': choice.id,
                  'data-cb-view-choice-state': choice.available ? 'available' : 'unavailable',
                  onClick: () => {
                    if (!choice.available) return
                    setFocusBlockId(null)
                    setLessonView(choice.id)
                  },
                  children: choice.label
                },
                choice.id
              )
            )
          }, 'choices'),
          unavailableViews.length > 0
            ? jsx('span', {
                'data-cb-view-reasons': '',
                style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.35, color: 'var(--cb-ink-soft)', minWidth: 0, overflowWrap: 'anywhere' },
                children: unavailableViews.map((choice, index) =>
                  jsx(
                    'span',
                    {
                      id: `cb-view-reason-${choice.id}`,
                      'data-cb-view-reason': choice.id,
                      children: `${index === 0 ? '' : ' '}${choice.reason}`
                    },
                    choice.id
                  )
                )
              }, 'reasons')
            : null
        ]
      })
    : null
  const shellActions = page ? [switcher] : []

  // The breadcrumb is the course the section belongs to, and the section's place in it: one calm
  // line above the reading column, never a second navigation bar.
  const ordinal = section && section.ordinal ? String(section.ordinal) : null
  const total = row.evidence_summary && row.evidence_summary.total_objectives ? String(row.evidence_summary.total_objectives) : null
  const place = ordinal && total ? `Section ${ordinal} of ${total}` : ordinal ? `Section ${ordinal}` : null
  const metaLine = section
    ? [
        jsx(sdk.Button, {
          variant: 'text',
          size: 'sm',
          'data-cb-breadcrumb': 'sections',
          className: 'self-start',
          onClick: onBack,
          children: [jsx(sdk.Codicon, { name: 'chevron-left', size: CB_ICON_UI }), row.title || 'All sections']
        }, 'back'),
        jsx('span', {
          style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
          children: [place, activeView === 'textbook' ? 'Textbook' : activeView === 'guided' ? 'Guided' : 'Field Quest'].filter(Boolean).join(' · ')
        }, 'place'),
        jsx(CbStatePill, { state: section.state }, 'state'),
        section.evidence_target
          ? jsx('span', {
              style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
              children: learnerEvidenceTarget(section.evidence_target) || 'Evidence target not recorded'
            }, 'evidence')
          : null,
        section.last_opened_at
          ? jsx('span', {
              style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
              children: `Last opened ${whenLabel(section.last_opened_at)}`
            }, 'opened')
          : null
      ]
    : [jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: onBack, children: 'All sections' }, 'back')]

  return jsx(WorkspaceShell, {
    eyebrow: null,
    title: section && section.title ? section.title : 'Section',
    subtitle: null,
    meta: metaLine,
    actions: shellActions,
    rail: page
      ? jsx(FieldRail, {
          next: row.next_step && (row.next_step.label || row.next_step.kind) ? (row.next_step.label || row.next_step.kind) : null,
          facts: railFacts,
          sources: page.sources || [],
          notes: page.notebook_entries || [],
        })
      : null,
    children: [
      body,
      page && document
        ? jsx('div', {
            'data-cb-section-footer': '',
            style: {
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: '0.5rem',
              paddingTop: '0.9rem',
              borderTop: '1px solid var(--cb-rule)',
              maxWidth: CB_MEASURE
            },
            children: jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: onBack, children: 'Back to the section index' })
          })
        : null,
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
/** Overview: the course summary, one next move, the route, then recent evidence and reference. */
function OverviewView({ row, page, review, quizzes, outline, implemented, onOpenSection, onResume }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const next = row.next_step || {}
  const section = page && page.section
  const due = review && Array.isArray(review.items) ? review.items.filter((item) => item.overdue) : []
  const recent = quizzes && Array.isArray(quizzes.attempts) ? quizzes.attempts.slice(0, 3) : []
  const warning = row.warning ? WARNING_COPY_LEARNING[row.warning] : null
  const objectives = outline && Array.isArray(outline.objectives) ? outline.objectives.filter(Boolean) : []
  const summary = row.evidence_summary || {}
  const progress = objectives.length
    ? objectiveProgress(objectives)
    : {
        total: Number(summary.total_objectives) || 0,
        independent: Number(summary.independent) || 0,
        due: Number(summary.review_due) || 0
      }
  const nextEntry = mainlineObjective(row, objectives)
  const nextTitle = section ? section.title : nextEntry ? nextEntry.title : next.label || null
  const nextSemantic = nextEntry ? sectionStateSemantic(nextEntry.state, true) : null
  const currentId = section ? section.objective_id : nextEntry ? nextEntry.objective_id : null
  const phone = cbLayoutFor(useCbViewportWidth()) === 'phone'

  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-5',
    children: [
      warning ? jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: warning }) : null,

      jsx(CourseIdentity, {
        title: row.title || 'This course',
        progress: progress.statement || progressStatement(progress.independent, progress.total),
        nextTitle,
        nextSemantic,
        compact: true
      }),

      // One next move, in the same row language as the course index: the row itself is the action
      // and the primary button is the only filled control on the screen.
      jsxs('section', {
        'data-cb-overview-next': currentId || 'none',
        style: { display: 'flex', flexDirection: 'column', gap: '0.6rem', maxWidth: '46rem' },
        children: [
          jsxs('div', {
            style: {
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.9rem',
              padding: '0.9rem 0.9rem 0.9rem 1rem',
              background: 'var(--cb-lamp-soft)',
              borderTop: '1px solid var(--cb-lamp)',
              boxSizing: 'border-box'
            },
            children: [
              jsx('span', {
                'aria-hidden': 'true',
                style: {
                  flex: '0 0 2.5rem',
                  fontFamily: CB_SANS,
                  fontVariantNumeric: 'tabular-nums',
                  fontSize: CB_TYPE.meta,
                  fontWeight: 600,
                  lineHeight: 1.6,
                  color: 'var(--cb-ink-soft)'
                },
                children: section && section.ordinal ? String(section.ordinal).padStart(2, '0') : '—'
              }),
              jsxs('div', {
                style: { display: 'flex', flexDirection: 'column', gap: '0.25rem', minWidth: 0, flex: '1 1 auto' },
                children: [
                  jsx('div', {
                    style: {
                      fontFamily: CB_SERIF,
                      fontSize: CB_TYPE.heading,
                      fontWeight: 600,
                      lineHeight: 1.25,
                      color: 'var(--cb-ink)',
                      overflowWrap: 'anywhere'
                    },
                    children: nextTitle || 'No objective recorded yet'
                  }),
                  section
                    ? jsxs('div', { style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' } , children: [
                        jsx(CbStatePill, { state: section.state }),
                        section.evidence_target
                          ? jsx('span', {
                              style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
                              children: learnerEvidenceTarget(section.evidence_target)
                            })
                          : null
                      ] })
                    : null,
                  jsx('div', {
                    style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                    children: next.label ? `Next: ${next.label}` : 'The backend did not return a next step for this course.'
                  })
                ]
              })
            ]
          }),
          jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.6rem' },
            children: [
              jsx(CbAction, {
                variant: 'primary',
                disabled: !section,
                onClick: () => onResume(section ? section.objective_id : null),
                children: next.kind === 'resume_lesson' ? 'Resume the lesson' : 'Start a fresh run'
              }),
              jsx(CbAction, {
                variant: 'tertiary',
                disabled: !section,
                onClick: () => onOpenSection(section ? section.objective_id : null),
                children: 'Read this section'
              })
            ]
          })
        ]
      }),

      objectives.length > 0
        ? jsxs('section', {
            'data-cb-overview-route': '',
            style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
            children: [
              jsx(PlateHead, {
                title: `${objectives.length} ${objectives.length === 1 ? 'section' : 'sections'}`,
                caption: progress.statement || progressStatement(progress.independent, progress.total)
              }),
              jsx(RouteSpine, {
                objectives,
                currentId,
                phone,
                onSelect: (objectiveId) => onOpenSection(objectiveId),
                ariaLabel: 'Course sections'
              })
            ]
          })
        : null,

      jsxs('section', {
        'data-cb-overview-evidence': '',
        style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' },
        children: [
          jsx(PlateHead, {
            title: 'Recent evidence',
            caption: due.length > 0 ? `${due.length} ${due.length === 1 ? 'section is' : 'sections are'} due for review.` : null
          }),
          recent.length > 0
            ? jsx('div', {
                style: { display: 'flex', flexDirection: 'column' },
                children: recent.map((attempt, index) =>
                  jsxs('div', {
                    'data-cb-evidence-row': attempt.attempt_id || String(index),
                    style: {
                      display: 'flex',
                      flexWrap: 'wrap',
                      alignItems: 'baseline',
                      justifyContent: 'space-between',
                      gap: '0.2rem 0.75rem',
                      padding: '0.45rem 0',
                      borderTop: index === 0 ? '1px solid var(--cb-rule)' : '1px solid var(--cb-rule)',
                      fontFamily: CB_SANS,
                      fontSize: CB_TYPE.caption,
                      lineHeight: 1.45
                    },
                    children: [
                      jsx('span', {
                        style: { color: 'var(--cb-ink-soft)' },
                        children: `${verdictLabel(attempt.verdict, attempt.evidence_class)} · ${whenLabel(attempt.committed_at || attempt.created_at)}`
                      }),
                      jsx(EvidenceClassText, { value: attempt.evidence_class })
                    ]
                  }, attempt.attempt_id || index)
                )
              })
            : jsx('p', {
                style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                children: 'No attempt has been recorded on this course yet.'
              }),
          due.length > 0
            ? jsx(sdk.Button, {
                variant: 'text',
                size: 'sm',
                className: 'self-start',
                onClick: () => onOpenSection(due[0].objective_id),
                children: `Start with the oldest: ${due[0].title || 'the first section due'}`
              })
            : null
        ]
      }),

      // Reference material, not the headline: it opens on purpose, after the learner has already
      // read where they are and what is next.
      jsxs('details', {
        'data-cb-overview-details': '',
        className: 'flex flex-col',
        children: [
          jsx('summary', {
            className: 'cursor-pointer text-xs font-medium text-(--ui-text-secondary)',
            children: 'Course details'
          }),
          jsxs('div', {
            className: 'flex flex-col pt-1',
            children: [
              jsx(StatusRow, {
                label: 'How you will use it',
                value: (RECIPE_COPY[row.recipe] || {}).title || 'Not recorded'
              }),
              jsx(StatusRow, {
                label: 'Enrolment',
                value: enrollmentStatusLabel(row.enrollment_status),
                detail: `revision ${row.revision}`
              }),
              jsx(StatusRow, {
                label: 'Evidence',
                value: `${Number(summary.independent || 0)} independent`,
                detail: `${Number(summary.total_objectives || 0)} objectives · ${Number(summary.review_due || 0)} due`
              }),
              jsx(StatusRow, {
                label: 'Where it came from',
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
    ]
  })
}

/**
 * A deterministic field-note mark, seeded from the course title.
 *
 * This is composition, not a second theme: every stroke is a `--cb-*` token, there is no gradient,
 * no image asset and no randomness, so the same course paints the same mark on every render. It is
 * decorative (`aria-hidden`), and the course title beside it carries the identity in text.
 */
function fieldNoteSeed(text) {
  let hash = 2166136261
  const value = String(text || '')
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619) >>> 0
  }
  return hash
}

function FieldNoteMark({ title, compact }) {
  const seed = fieldNoteSeed(title)
  // Ruled-note strokes, not a bar chart: every line is horizontal and the variation is indentation
  // and length, so the mark cannot be misread as a progress meter.
  const lines = Array.from({ length: 5 }, (_, index) => {
    const width = 34 + (((seed >>> (index * 5)) & 0xff) % 58)
    const indent = ((seed >>> (index * 5 + 3)) & 0x1) * 8
    return { width, indent, y: 5 + index * 6, accent: index === 2 }
  })
  return jsx('svg', {
    'aria-hidden': 'true',
    focusable: 'false',
    width: compact ? '76' : '108',
    height: compact ? '24' : '32',
    viewBox: '0 0 108 32',
    'data-cb-field-note': '',
    style: { flex: '0 0 auto' },
    children: lines.map((line, index) =>
      jsx(
        'line',
        {
          x1: line.indent,
          y1: line.y,
          x2: line.indent + line.width,
          y2: line.y,
          stroke: line.accent ? 'var(--cb-accent)' : 'var(--cb-rule)',
          strokeWidth: line.accent ? 1.8 : 1,
          strokeLinecap: 'round'
        },
        index
      )
    )
  })
}

/** The token that tints a state's icon; the word beside it is what actually names the state. */
function sectionToneColor(key) {
  if (key === 'complete') return 'var(--cb-field)'
  if (key === 'review') return 'var(--cb-ochre)'
  if (key === 'next') return 'var(--cb-accent)'
  return 'var(--cb-ink-soft)'
}

/**
 * The course line: the title, the recorded progress sentence and the next move, in that order.
 * It is a summary strip, not a hero — the course hero belongs to Course Detail — so it carries no
 * lamp field, no seal and no action. Every value is one the backend recorded; there is no percent,
 * ring or streak (docs/COURSEBOOK-VISUAL-IDENTITY-V2.md §3, §4.4).
 */
function CourseIdentity({ title, subtitle, progress, nextTitle, nextSemantic, compact }) {
  return jsxs('section', {
    'data-cb-identity': compact ? 'summary' : 'course',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.3rem',
      padding: compact ? '0.15rem 0 0.55rem' : '0.2rem 0 0.7rem',
      borderBottom: '1px solid var(--cb-rule)',
      maxWidth: '46rem'
    },
    children: [
      jsx('h2', {
        style: {
          margin: 0,
          fontFamily: CB_SERIF,
          fontSize: compact ? CB_TYPE.heading : CB_TYPE.heading,
          fontWeight: 600,
          lineHeight: 1.15,
          letterSpacing: '-0.01em',
          color: 'var(--cb-ink)',
          maxWidth: '34ch',
          overflowWrap: 'anywhere'
        },
        children: title
      }),
      jsx('div', {
        'data-cb-progress-statement': '',
        style: {
          fontFamily: CB_SANS,
          fontVariantNumeric: 'tabular-nums',
          fontSize: CB_TYPE.meta,
          lineHeight: 1.5,
          color: 'var(--cb-ink-soft)'
        },
        children: progress
      }),
      nextTitle
        ? jsxs('div', {
            'data-cb-next-statement': '',
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.35rem', fontFamily: CB_SANS, fontSize: CB_TYPE.meta },
            children: [
              jsx('span', { style: { fontWeight: 600, color: 'var(--cb-accent)' }, children: 'Next ·' }),
              jsx('span', { style: { color: 'var(--cb-ink)', overflowWrap: 'anywhere' }, children: nextTitle }),
              nextSemantic
                ? jsx('span', { style: { color: sectionToneColor(nextSemantic.key) }, children: ` ${nextSemantic.label}` })
                : null
            ]
          })
        : null,
      subtitle
        ? jsx('div', { style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' }, children: subtitle })
        : null
    ]
  })
}

/**
 * One section row in the course index: a 40px number gutter, a serif title, one honest subline
 * and the state word at the end. The row itself is the action — no chevron-only affordance, no
 * repeated "Open section" label, no card border. State is a word plus its hue, never colour alone
 * (docs/COURSEBOOK-VISUAL-IDENTITY-V2.md §4.6).
 */
function SectionRow({ entry, semantic, isNext, onOpen }) {
  const [hover, setHover] = useState(false)
  const target = learnerEvidenceTarget(entry.evidence_target)
  const subline = target || (isNext && entry.last_opened_at ? `Last opened ${whenLabel(entry.last_opened_at)}` : null)
  return jsx(sdk.Button, {
    variant: 'text',
    className: 'w-full justify-start',
    'aria-current': isNext ? 'step' : undefined,
    'data-cb-section-row': entry.objective_id,
    'data-cb-section-state': semantic.key,
    onClick: () => onOpen(entry.objective_id),
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    onFocus: () => setHover(true),
    onBlur: () => setHover(false),
    children: jsxs('span', {
      style: {
        display: 'flex',
        alignItems: 'flex-start',
        gap: '0.9rem',
        width: '100%',
        padding: '0.8rem 0.35rem 0.8rem 0.6rem',
        boxSizing: 'border-box',
        textAlign: 'left',
        borderTop: '1px solid var(--cb-rule)',
        borderLeft: isNext ? '2px solid var(--cb-accent)' : '2px solid transparent',
        background: isNext ? 'var(--cb-accent-soft)' : hover ? 'var(--cb-accent-soft)' : 'transparent'
      },
      children: [
        jsx('span', {
          'aria-hidden': 'true',
          style: {
            flex: '0 0 2.5rem',
            fontFamily: CB_SANS,
            fontVariantNumeric: 'tabular-nums',
            fontSize: CB_TYPE.meta,
            fontWeight: 600,
            lineHeight: 1.6,
            color: isNext ? 'var(--cb-accent)' : 'var(--cb-ink-soft)'
          },
          children: String(entry.ordinal || 0).padStart(2, '0')
        }),
        jsxs('span', {
          style: { display: 'flex', flexDirection: 'column', gap: '0.15rem', minWidth: 0, flex: '1 1 auto' },
          children: [
            jsx('span', {
              style: {
                overflowWrap: 'anywhere',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                fontFamily: CB_SERIF,
                fontSize: CB_TYPE.lead,
                fontWeight: 600,
                lineHeight: 1.3,
                color: 'var(--cb-ink)'
              },
              children: entry.title
            }),
            subline
              ? jsx('span', { style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' }, children: subline })
              : null
          ]
        }),
        jsx('span', {
          'data-cb-section-pill': semantic.key,
          style: { flex: '0 0 auto', alignSelf: 'center' },
          children: jsx(CbStatePill, { state: entry.state })
        })
      ]
    })
  })
}

/** A unit heading with its own progress line, shown only when the plan really has more than one. */
function UnitHeading({ unit, entries }) {
  const progress = objectiveProgress(entries)
  const blocked =
    unit.prerequisite_state === 'unmet' && Array.isArray(unit.prereq_unit_ordinals) && unit.prereq_unit_ordinals.length > 0
  return jsxs('div', {
    'data-cb-unit': String(unit.ordinal),
    style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', paddingTop: '0.55rem' },
    children: [
      jsxs('div', {
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: '0.2rem 0.75rem',
          borderBottom: '1px solid var(--cb-rule)',
          paddingBottom: '0.3rem'
        },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.45rem', minWidth: 0 },
            children: [
              jsx('span', {
                style: {
                  fontSize: CB_TYPE.caption,
                  fontWeight: 600,
                  letterSpacing: '0.01em',
                  color: 'var(--cb-ink-soft)'
                },
                children: `Unit ${unit.ordinal}`
              }),
              jsx('span', {
                style: { fontSize: CB_TYPE.meta, fontWeight: 600, color: 'var(--cb-ink)', overflowWrap: 'anywhere' },
                children: unit.title
              })
            ]
          }),
          jsx('span', {
            'data-cb-unit-progress': '',
            style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: progress.statement
          })
        ]
      }),
      blocked
        ? jsx('div', {
            style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: `This unit starts after Unit ${unit.prereq_unit_ordinals.join(', ')}. You can still open it.`
          })
        : null
    ]
  })
}

/**
 * The index's one details affordance: the legend and the rubric's own construct names.
 *
 * A learner never has to decode "discrimination" in the list — the row says "Tell the difference".
 * The raw id is still auditable here, inside a panel the learner opens on purpose.
 */
function TextbookIndexDetails({ rows }) {
  const targets = Array.from(new Set(rows.map((entry) => entry.evidence_target).filter(Boolean)))
  const legend = [
    { semantic: { key: 'complete', label: 'Complete', icon: 'pass' }, meaning: 'this objective has independent evidence.' },
    { semantic: { key: 'next', label: 'Next', icon: 'chevron-right' }, meaning: 'the section the course points to now.' },
    { semantic: { key: 'review', label: 'Review due', icon: 'history' }, meaning: 'evidence is scheduled to come back.' },
    { semantic: { key: 'not_started', label: 'Not started', icon: 'circle-outline' }, meaning: 'no attempt recorded yet.' }
  ]
  return jsxs('details', {
    'data-cb-index-details': '',
    style: { maxWidth: '46rem', paddingTop: '0.2rem' },
    children: [
      jsx('summary', {
        style: { cursor: 'pointer', fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
        children: 'What the states and check types mean'
      }),
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: '0.5rem', paddingTop: '0.4rem' },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', gap: '0.2rem' },
            children: legend.map((entry) =>
              jsxs(
                'div',
                {
                  style: { display: 'flex', alignItems: 'baseline', gap: '0.4rem', fontSize: CB_TYPE.caption },
                  children: [
                    jsx('span', { style: { color: sectionToneColor(entry.semantic.key) }, children: entry.semantic.label }),
                    jsx('span', { style: { color: 'var(--cb-ink-soft)' }, children: `— ${entry.meaning}` })
                  ]
                },
                entry.semantic.key
              )
            )
          }),
          targets.length > 0
            ? jsxs('div', {
                'data-cb-check-types': '',
                style: { display: 'flex', flexDirection: 'column', gap: '0.15rem', fontSize: CB_TYPE.caption },
                children: [
                  jsx('div', {
                    style: { fontWeight: 600, color: 'var(--cb-ink-soft)' },
                    children: 'Check types in this course'
                  }),
                  ...targets.map((target) =>
                    jsx(
                      'div',
                      {
                        style: { color: 'var(--cb-ink-soft)' },
                        children: `${learnerEvidenceTarget(target)} — the backend calls this “${target}”.`
                      },
                      target
                    )
                  )
                ]
              })
            : null
        ]
      })
    ]
  })
}

/** Textbook — a scannable section list, not one endless thread. */
function TextbookView({ row, page, pageState, review, notebooks, outline, implemented, openSectionId, onOpenSection, onCloseSection, onChanged, targetBlockId }) {
  const rows = sectionRows({ row, review, notebooks, outline, page })
  const hasOutline = Boolean(outline && Array.isArray(outline.objectives))
  const objectives = hasOutline ? outline.objectives.filter(Boolean) : []
  const summary = row.evidence_summary || {}
  const progress = objectives.length
    ? objectiveProgress(objectives)
    : {
        total: Number(summary.total_objectives) || 0,
        independent: Number(summary.independent) || 0,
        due: Number(summary.review_due) || 0
      }
  const nextEntry = mainlineObjective(row, objectives) || rows.find((entry) => !entry.independent) || null
  const nextSemantic = nextEntry ? sectionStateSemantic(nextEntry.state, true) : null
  const nextTitle = nextEntry ? nextEntry.title : null

  // A plan with more than one unit groups its sections. One implicit unit (a legacy or pack plan)
  // stays a flat list: the backend's single unit is not a heading the learner should have to read.
  const units =
    outline && outline.plan && Array.isArray(outline.plan.units)
      ? outline.plan.units.filter((unit) => unit && Array.isArray(unit.objectives))
      : []
  const rowIndex = new Map(rows.map((entry) => [entry.objective_id, entry]))
  const grouped = units.length > 1
  const groups = grouped
    ? units.map((unit) => ({
        unit,
        entries: unit.objectives
          .map((objective) => rowIndex.get(objective && objective.objective_id) || objective)
          .filter((entry) => entry && entry.objective_id)
      }))
    : []
  const groupedIds = new Set(groups.flatMap((group) => group.entries.map((entry) => entry.objective_id)))
  const extras = grouped ? rows.filter((entry) => !groupedIds.has(entry.objective_id)) : []

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
      targetBlockId: targetBlockId || null,
      // Inside Course Detail the page hero owns the primary; the embedded section does not repeat it.
      embedded: true
    })
  }

  const rowFor = (entry) => {
    const isNext = Boolean(nextEntry && nextEntry.objective_id === entry.objective_id)
    return jsx(
      SectionRow,
      {
        entry,
        semantic: sectionStateSemantic(entry.state, isNext),
        isNext,
        onOpen: onOpenSection
      },
      entry.objective_id
    )
  }

  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-4',
    children: [
      jsx(CourseIdentity, {
        title: row.title || 'This course',
        progress: progress.statement || progressStatement(progress.independent, progress.total),
        nextTitle,
        nextSemantic,
        compact: true
      }),
      // The reading plate: what is here, how much of it carries evidence, and the one line that
      // explains the measure. The old identity paragraph becomes this caption.
      jsxs('section', {
        'data-cb-reading-plate': '',
        style: { display: 'flex', flexDirection: 'column', gap: '0.55rem' },
        children: [
          jsx(PlateHead, {
            title: `${rows.length} ${rows.length === 1 ? 'section' : 'sections'}`,
            caption: progress.due > 0
              ? `${progress.due} ${progress.due === 1 ? 'section is' : 'sections are'} due for review.`
              : null
          }),
          objectives.length > 0
            ? jsx(EvidenceTally, {
                objectives,
                caption: progress.statement || progressStatement(progress.independent, progress.total)
              })
            : null,
          jsx('p', {
            'data-cb-reading-caption': '',
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
            children: '66 characters per line. Evidence is named, never estimated.'
          })
        ]
      }),
      hasOutline
        ? null
        : jsx(QuietNote, {
            children:
              'This build can name the current section and every section with scheduled evidence. The complete ' +
              'section list needs course.outline; rows light up here automatically once that command is registered.'
          }),
      rows.length === 0
        ? jsx(EmptyState, {
            title: 'No sections yet',
            description: 'A section appears once the course has an approved plan with objectives. Approve the plan first.'
          })
        : grouped
          ? jsxs('div', {
              className: 'flex flex-col',
              children: [
                ...groups.map((group) =>
                  jsxs(
                    'div',
                    {
                      className: 'flex flex-col',
                      children: [
                        jsx(UnitHeading, { unit: group.unit, entries: group.entries }, `unit-${group.unit.ordinal}`),
                        ...group.entries.map(rowFor)
                      ]
                    },
                    `group-${group.unit.ordinal}`
                  )
                ),
                extras.length > 0
                  ? jsxs('div', {
                      className: 'flex flex-col',
                      children: [
                        jsx('div', {
                          style: {
                            fontSize: CB_TYPE.caption,
                            color: 'var(--cb-ink-soft)',
                            paddingTop: '0.55rem',
                            borderBottom: '1px solid var(--cb-rule)',
                            paddingBottom: '0.3rem'
                          },
                          children: 'Also recorded on this course'
                        }),
                        ...extras.map(rowFor)
                      ]
                    })
                  : null
              ]
            })
          : jsx('div', { className: 'flex flex-col', children: rows.map(rowFor) }),
      jsx(TextbookIndexDetails, { rows }),
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
                      children: jsx(ProseText, { text: entry.excerpt || entry.note || entry.kind })
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
                                jsx(CbAction, { variant: 'primary', size: 'sm', onClick: saveEdit, children: 'Save changes' }),
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
              { id: 'needs_retry', label: 'Could not be graded' }
            ],
            sizing: 'content',
            value: verdict
          }),
          jsx(sdk.SegmentedControl, {
            onChange: setKlass,
            options: [
              { id: 'all', label: 'All assistance' },
              { id: 'cold', label: 'First try' },
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
                                    jsx(CbLabel, { children: 'Dispute history' }),
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
                        entry.evidence_target ? jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: learnerEvidenceTarget(entry.evidence_target) }) : null,
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
          'This build cannot edit evidence criteria, attempt counts or settings yet. Nothing is filled in to hide that.'
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
          jsx(CbLabel, { children: 'L3 · current recommendation' }),
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
          jsx(CbLabel, { children: 'L2 · objective evidence' }),
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
          jsx(CbLabel, { children: 'L1 · attempts and events' }),
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
                  jsx(CbLabel, { children: 'Disputes' }),
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
      description: 'No sources are recorded for this course. Nothing here is presented as cited.'
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
      jsx(PlateHead, {
        title: 'Export course…',
        caption: 'Review the files, the licence and the rights statement before anything is packaged.'
      }),
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
      jsx(CbAction, {
        disabled: busy || !confirmed,
        onClick: run,
        variant: 'primary',
        children: busy ? 'Packaging' : 'Export these files'
      }),
      error ? jsx('div', { className: 'text-xs', children: error.message }) : null,
      exported
        ? jsxs('div', {
            className: 'flex flex-col',
            children: [
              jsx(CbLabel, { children: 'Exported' }),
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
function CourseDetail({ row, implemented, profile, onBack, onChanged, focusObjectiveId, focusBlockId, focusView, reloadSignal, onChangeGoal, onNewSyllabus }) {
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
        objectiveTitle: page.data && page.data.section ? page.data.section.title : null,
        mode,
        profile: profile || currentScope().profile
      })
      setBusy(false)
      if (outcome.ok && outcome.armed) {
        refresh()
        // Arm first, then open the chat that the pending binder names. The old ordering opened a
        // session before a durable id existed and left the learner on a blank chat.
        const opened = openArmedLessonChat(profile || currentScope().profile)
        openSection(target)
        setNotice(
          opened
            ? { text: 'A new lesson chat is open. Send the first message to connect it to this lesson.' }
            : {
                text: outcome.message,
                action: {
                  label: 'Open the lesson chat',
                  run: () => startLessonChat(profile || currentScope().profile)
                }
              }
        )
        return
      }
      if (!outcome.ok && outcome.reason === 'no-binding') {
        setNotice({
          text: outcome.message,
          action: {
            label: 'Start a fresh run',
            run: () => startLesson('fresh', target)
          }
        })
        openSection(target)
        return
      }
      setNotice(outcome.message)
      if (outcome.ok) refresh()
      else if (outcome.reason === 'no-binding') openSection(target)
    },
    [objectiveId, row, page.data, profile, refresh, openSection]
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
      outline: outline.data,
      implemented,
      onOpenSection: openSection,
      onResume: (objectiveId) =>
        startLesson(
          row.next_step && row.next_step.kind === 'resume_lesson' ? 'resume' : 'fresh',
          objectiveId || null
        )
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
      course: { course_id: row.course_id, enrollment_id: row.enrollment_id, title: row.title },
      revision,
      onRevision: setRevision,
      implemented,
      onOpenSection: openSection,
      onStartLesson: (objectiveId) => startLesson('fresh', objectiveId),
      onChanged: refresh,
      reloadSignal,
      onChangeGoal,
      onNewSyllabus
    })
  } else if (view === 'evidence') {
    body = jsx(EvidenceView, { evidence: evidence.data, implemented, onOpenSection: openSection })
  } else if (view === 'export') {
    body = jsx(CourseExportView, { row, implemented })
  } else {
    body = jsx(SourcesView, { page: page.data })
  }

  const nextKind = (row.next_step && row.next_step.kind) || 'start_lesson'
  const topCanResume = Boolean(
    page.data && page.data.runtime && page.data.runtime.binding_status === 'active'
  )
  const objectives = outline.data && Array.isArray(outline.data.objectives) ? outline.data.objectives.filter(Boolean) : []
  const summary = row.evidence_summary || {}
  const courseProgress = objectives.length
    ? objectiveProgress(objectives)
    : {
        total: Number(summary.total_objectives) || 0,
        independent: Number(summary.independent) || 0,
        due: Number(summary.review_due) || 0
      }
  const section = page.data && page.data.section ? page.data.section : null
  const sectionTotal = objectives.length || Number(courseProgress.total) || 0
  const sectionOrdinal = section && section.ordinal ? Number(section.ordinal) : null
  const dueCount = review.data && typeof review.data.total_overdue === 'number' ? Number(review.data.total_overdue) : null
  const heroFacts = [
    sectionTotal
      ? {
          value: sectionOrdinal ? `Section ${sectionOrdinal} of ${sectionTotal}` : `${sectionTotal} ${sectionTotal === 1 ? 'section' : 'sections'}`,
          label: (section && section.title) || 'In this course'
        }
      : null,
    courseProgress.total
      ? { value: `${courseProgress.independent} of ${courseProgress.total}`, label: 'With independent evidence' }
      : null,
    dueCount !== null && dueCount > 0 ? { value: String(dueCount), label: 'Due for review' } : null
  ].filter(Boolean)
  const parentIdentity = row.recipe === 'parent' ? 'plum' : 'lamp'
  const tierOne = [
    { id: 'overview', label: 'Overview' },
    { id: 'textbook', label: 'Textbook', mode: true },
    { id: 'notebook', label: 'Notebook' },
    { id: 'quizzes', label: 'Quizzes' },
    { id: 'evidence', label: 'Evidence' }
  ]
  const tierTwo = [
    { id: 'plan', label: 'Plan' },
    { id: 'sources', label: 'Sources' },
    supports('course.export.read') ? { id: 'export', label: 'Export' } : null
  ].filter(Boolean)
  const tierTwoActive = tierTwo.some((option) => option.id === view)
  const layout = cbLayoutFor(useCbViewportWidth())
  const phone = layout === 'phone'
  const compactHero = layout !== 'wide'

  return jsxs('div', {
    'data-cb-course-detail': view,
    className: 'flex flex-col gap-4',
    children: [
      jsx(sdk.Button, {
        className: 'self-start',
        variant: 'text',
        size: 'sm',
        'data-cb-course-back': '',
        onClick: onBack,
        children: 'All courses'
      }),

      // The compact hero: one lamp field, one seal, three recorded facts, one primary action.
      jsx(HeroField, {
        identity: parentIdentity,
        phone,
        children: jsxs('div', {
          style: {
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'flex-start',
            gap: phone ? '0.75rem' : '1.75rem'
          },
          children: [
            jsxs('div', {
              style: { display: 'flex', flexDirection: 'column', gap: '0.45rem', minWidth: 0, flex: compactHero ? '1 1 100%' : '1 1 16rem' },
              children: [
                jsx('h2', {
                  'data-cb-course-title': '',
                  style: {
                    margin: 0,
                    fontFamily: CB_SERIF,
                    fontSize: CB_TYPE.heading,
                    fontWeight: 600,
                    lineHeight: 1.12,
                    letterSpacing: '-0.015em',
                    color: 'var(--cb-ink)',
                    maxWidth: '20ch',
                    overflowWrap: 'anywhere'
                  },
                  children: row.title || 'This course'
                }),
                jsxs('div', {
                  style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.45rem' },
                  children: [
                    jsx(CbStatePill, { state: section ? section.state : row.enrollment_status === 'active' ? 'introduced' : 'not_started' }),
                    row.recipe
                      ? jsx('span', {
                          style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
                          children: (RECIPE_COPY[row.recipe] || {}).title || row.recipe
                        })
                      : null,
                    row.warning ? jsx(WarningBadge, { warning: row.warning }) : null
                  ]
                }),
                jsx(HeroFacts, { facts: heroFacts, phone })
              ]
            }),
            jsxs('div', {
              'data-cb-hero-actions': '',
              style: {
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'stretch',
                gap: '0.45rem',
                flex: compactHero ? '1 1 100%' : '0 0 13rem',
                minWidth: 0
              },
              children: [
                view === 'overview' || openSectionId ? null : jsx(CbAction, {
                  variant: 'primary',
                  disabled: busy,
                  onClick: () => startLesson(nextKind === 'resume_lesson' && topCanResume ? 'resume' : 'fresh'),
                  children: busy ? 'Opening' : topCanResume ? 'Resume the lesson' : 'Start a fresh run'
                }),
                jsx(CbAction, {
                  variant: 'secondary',
                  onClick: () => {
                    setView('textbook')
                    setOpenSectionId(null)
                  },
                  children: 'Open the textbook'
                }),
                jsxs('details', {
                  'data-cb-why-next': '',
                  style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                  children: [
                    jsx('summary', { style: { cursor: 'pointer' }, children: 'Why this is next' }),
                    jsx('p', { style: { margin: '0.35rem 0 0', lineHeight: 1.5 }, children: currentTitle })
                  ]
                })
              ]
            })
          ]
        })
      }),

      jsx(NoticeLine, { notice, busy }),

      // Two tiers, every surface one click away. The reading modes carry their dot; the reference
      // tier is a plain text row so it never competes with the reading path.
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: '0.15rem' },
        children: [
          jsx(LearningTabs, { options: tierOne, value: view, onChange: selectView, phone, ariaLabel: 'Course surfaces' }),
          jsx('div', {
            'data-cb-tier-two': view,
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.15rem 0.9rem' },
            children: tierTwo.map((option) =>
              jsx(
                sdk.Button,
                {
                  variant: 'text',
                  size: 'sm',
                  'data-cb-tab': option.id,
                  'aria-current': option.id === view ? 'page' : undefined,
                  onClick: () => selectView(option.id),
                  children: option.label
                },
                option.id
              )
            )
          })
        ]
      }),

      tierTwoActive
        ? jsx('div', {
            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: `You are reading ${viewLabel.toLowerCase()}, outside the course route. Overview, Textbook, Notebook, Quizzes and Evidence stay one click away above.`
          })
        : null,
      review.data && review.data.total_overdue > 0 && view !== 'overview'
        ? jsx(CheckPanelFrame, {
            kind: 'check',
            label: 'Review due',
            children: jsxs('div', {
              style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' },
              children: [
                jsx('span', {
                  style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink)' },
                  children: `${review.data.total_overdue} ${review.data.total_overdue === 1 ? 'section is' : 'sections are'} due for review.`
                }),
                jsx(sdk.Button, {
                  variant: 'text',
                  size: 'sm',
                  onClick: () => selectView('overview'),
                  children: 'See what is due'
                })
              ]
            })
          })
        : null,
      body
    ]
  })
}

/**
 * A teaching turn that reached the chat but not the lesson page.
 *
 * `binding.get` answers `snapshot_failures = {recorded, last_at}` for the bound lesson run: the
 * count of teaching turns whose durable `lesson_segments` row could not be written after one
 * retry. This is an integrity notice, not a blocking error — the chat still holds the turn, so
 * there is no dialog, no disabled control and no retry (a retry writes a *new* turn, not the lost
 * one). The three states are kept distinct: a positive count names the loss, an explicit zero is
 * silent, and `null` is "unknown", never a zero.
 */
function SnapshotLossNotice({ failures }) {
  const recorded = failures && typeof failures === 'object' ? failures.recorded : undefined
  if (recorded === 0) return null
  const count = Number(recorded)
  if (Number.isFinite(count) && count > 0) {
    const lastAt = failures && failures.last_at
    return jsxs('div', {
      className: 'flex flex-col gap-1 border-l-2 border-(--ui-stroke-secondary) pl-3',
      role: 'status',
      'data-cb-snapshot-loss': 'recorded',
      'data-cb-snapshot-count': String(count),
      children: [
        jsx('div', {
          className: 'text-xs leading-relaxed',
          children: `${count} teaching ${count === 1 ? 'turn' : 'turns'} could not be saved to this lesson. The chat has them; this page does not.`
        }),
        lastAt
          ? jsx('div', {
              className: 'text-xs text-(--ui-text-secondary)',
              children: `Last recorded ${whenLabel(lastAt)}.`
            })
          : null
      ]
    })
  }
  return jsx('div', {
    className: 'border-l-2 border-(--ui-stroke-secondary) pl-3 text-xs leading-relaxed text-(--ui-text-secondary)',
    role: 'status',
    'data-cb-snapshot-loss': 'unknown',
    children: 'Coursebook could not check whether any teaching turn was lost.'
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
      objectiveTitle: section ? section.title : null,
      lessonRunId: outcome.lesson_run_id,
      profile
    })
    const started = startLessonChat(profile)
    setNotice(
      started
        ? 'A new lesson run is ready. Its chat connects when you send your first message.'
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
        'This chat is connected to a course the library did not return. Nothing is guessed: reopen Coursebook to check it.',
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

      jsx(SnapshotLossNotice, { failures: binding.snapshot_failures }),

      bindingStatus !== 'active'
        ? jsxs('div', {
            className: 'flex flex-col gap-1 border-l border-(--ui-stroke-secondary) pl-3',
            children: [
              jsx('div', {
                className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                children:
                  'This chat is not part of a lesson yet. Open Coursebook and start a lesson; the first message in its new chat connects it.'
              }),
              jsx(sdk.Button, {
                variant: 'secondary',
                size: 'sm',
                disabled: busy,
                onClick: () => host.navigate(ROUTE_PATH),
                children: 'Open Coursebook'
              })
            ]
          })
        : null,

      notice ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: notice }) : null,

      jsx(CbLabel, { children: 'Current check' }),
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
                stimulusStatus: check.stimulusStatus,
                stimulusError: check.stimulusError,
                onRetryStimulus: check.reload,
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
  if (binding.status !== 'active') return 'This lesson is not connected to its chat right now. Open it from the course page first.'
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
  // `discrimination` is the rubric's name for telling two things apart; the parent reads the plain
  // phrase and the enum id still travels unchanged (H-28, UX-04 vocabulary).
  { id: 'discrimination', label: 'Tell the difference' },
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

function StudioJobLine({ jobId, job: providedJob, onSettled, onRunAgain }) {
  // A caller that already reads the job (plan review needs it for the rejection model) passes it
  // in; the line then shares that read instead of polling the same id a second time.
  const polledJob = useStudioJob(providedJob ? null : jobId, onSettled)
  const job = providedJob || polledJob
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
  // shows the new job id rather than pretending the cancelled one resumed. The key is derived from
  // the job being retried, so a double click replays one job instead of queueing a second spend.
  const runAgain = async () => {
    setBusy(true)
    setError(null)
    const response = await rpc(
      'jobs.create',
      { kind: job.kind || 'plan', brief: job.brief },
      { idempotencyKey: `cb-stage-again-${jobId}` }
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

/** The studio list: lesson plans the parent prepared. Imported packs stay in Library. */
function StudioList({ implemented, onCreate, onOpen, reloadSignal }) {
  const supported = Boolean(implemented && implemented.has('library.list'))
  const query = useRpcQuery(
    'library.list',
    { filter: 'all', recipe: 'parent', limit: 50, sort: 'recent' },
    `studio-list-${reloadSignal}`,
    supported
  )
  const rows = query.data && Array.isArray(query.data.items) ? query.data.items : []
  // H-99: fourteen copies of the same prepared brief are one shelf object with an `N plans`
  // disclosure, not fourteen identical text rows. The records stay reachable inside it.
  const groups = groupShelfRows(rows)

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
      title: 'No lesson plans yet',
      description:
        'A lesson plan starts from a short brief: the child’s age and reading level, where you will teach, what you have, ' +
        'what to leave out, and what you want them to be able to do. Coursebook drafts a plan for you to review before any ' +
        'lesson page is written.',
      children: jsx(CbAction, { onClick: onCreate, variant: 'primary', children: 'New lesson plan' })
    })
  }

  return jsx(StudioLanding, { rows, onCreate, onOpen })
}

/**
 * The Parent Studio landing plate: the one place a parent starts a new plan. The route header
 * carries no create action, so this in-page primary is the only `variant=default` control on the
 * surface (H-94 V2-4; H-91 P2-4 removed the duplicate header button).
 */
function StudioLanding({ rows, onCreate, onOpen }) {
  const groups = groupShelfRows(rows)
  return jsxs('div', {
    'data-cb-studio-landing': '',
    style: {
      display: 'flex',
      flexDirection: 'column',
      maxWidth: CB_MEASURE,
      gap: '0.75rem',
      padding: '1rem 1rem 1.1rem',
      background: 'var(--cb-plum-soft)',
      borderTop: '1px solid var(--cb-plum)',
      boxSizing: 'border-box'
    },
    children: [
      jsx(PlateHead, {
        label: 'Parent Studio',
        title: 'Plans for your child',
        caption: 'Each brief you write is kept as its own plan, so you can compare versions without losing the first.',
        actions: jsx(CbAction, { onClick: onCreate, variant: 'primary', children: 'New lesson plan' })
      }),
      ...groups.map((group) =>
        jsx(
          CourseCover,
          {
            row: group.primary,
            group,
            identity: 'plum',
            onOpenMember: onOpen,
            detail: jsx('span', {
              className: 'flex flex-wrap items-center gap-2',
              children: [
                jsx('span', { children: 'Lesson plan for a child' }),
                jsx('span', { children: `updated ${whenLabel(group.primary.updated_at)}` })
              ]
            }),
            action: jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: () => onOpen(group.primary), children: 'Open plan' })
          },
          group.key
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

      jsx(CbLabel, { children: 'What and who' }),
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

      jsx(CbLabel, { children: 'Where, how long, with what' }),
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

      jsx(CbLabel, { children: 'Exclusions and supervision' }),
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

      jsx(CbLabel, { children: 'Before you paste: provider and egress' }),
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
              jsx(CbLabel, { children: 'Before submitting' }),
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
          jsx(CbAction, {
            variant: 'primary',
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
      jsx(CbLabel, { children: 'The brief' }),
      jsxs('div', {
        className: 'flex flex-col',
        children: rows.map((row) => jsx(PackReviewLine, { label: row.label, value: row.value }, row.label))
      }),
      jsx(CbLabel, { children: 'Plan job' }),
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
          jsx(CbAction, { variant: 'primary', onClick: () => onDuplicate(brief, null), children: 'Duplicate brief' }),
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
 * H-103: a rejected plan is explained, not printed.
 *
 * The backend records the validator's reasons, but a reason is written for a machine: an item id,
 * a contract criterion, a sentence about ordinals. Plan review owes the learner one literal
 * explanation, the unit or check that failed, and one action that can actually be taken. The raw
 * record stays available behind a disclosure; the visible copy never contains a bare `reject`,
 * `model_assessed` or a contract enum.
 */
const PLAN_CHECK_LABELS = Object.freeze({
  alignment: 'whether each objective matches the goal',
  sources: 'whether each claim has a source that was actually read',
  structure: 'whether the units, objectives and checks fit together',
  schedule: 'whether the schedule and time estimates add up',
  policy: 'whether the plan follows the recipe and its limits'
})

/** Map an internal check to a sentence a learner can use. Unknown wording is never a bare token. */
function planCheckLabel(text) {
  const value = String(text || '').toLowerCase()
  if (/source|ledger|citation|provenance|grounded|unsourced|support/.test(value)) return PLAN_CHECK_LABELS.sources
  if (/ordinal|unit|section|prerequisite|contiguous|check plan|coverage|scope|recipe|schedule|parent|structure/.test(value)) return PLAN_CHECK_LABELS.structure
  if (/hour|week|time|duration|estimate|confidence|benchmark/.test(value)) return PLAN_CHECK_LABELS.schedule
  if (/policy|dial|autonomy|assessment|delivery|budget|ceiling/.test(value)) return PLAN_CHECK_LABELS.policy
  return PLAN_CHECK_LABELS.alignment
}

/** Replace snake_case contract tokens with words, so a disclosure cannot leak a bare enum. */
function plainPlanReason(text) {
  return String(text || '')
    .replace(/[A-Za-z]+(?:_[A-Za-z]+)+/g, (token) => token.replace(/_/g, ' '))
    .replace(/\s+/g, ' ')
    .trim()
}

function splitPlanReason(reason) {
  const text = plainPlanReason(reason)
  const match = /^([^:]{1,48}):\s*(.+)$/.exec(text)
  if (match) return { place: match[1].trim(), why: match[2].trim() }
  return { place: null, why: text }
}

const PLAN_RUN_TERMINAL_FAILURE = new Set(['failed', 'cancelled', 'interrupted_requires_retry'])

const VALIDATION_OUTCOME_COPY = {
  rejected: 'The validator did not pass this draft.',
  model_assessed: 'The author model checked its own work; no independent check was recorded.',
  independently_validated: 'A different model checked this draft and passed it.',
  not_validated: 'No validator record was written for this draft.'
}

const VALIDATION_INDEPENDENCE_COPY = {
  independent: 'The writing model and the checking model were different.',
  same_model: 'The same model wrote and checked the plan.',
  unidentified: 'The checking model could not be identified.'
}

const RESEARCH_STATUS_COPY = {
  available: 'Research fetched its sources.',
  degraded: 'Research returned only part of its sources.',
  unavailable: 'Research was unavailable, so no source could be checked.'
}

/**
 * H-105: the validator record, said plainly.
 *
 * `model_assessed` is a limitation, not a badge. The one line only names *who* checked; the words
 * "independently validated" are reserved for a record whose `independence` is `independent` — both
 * model identities were reported by the provider and the model names differ. A same-model or
 * unidentified pass, and a pass with research unavailable, can never be presented as independent.
 * The rule and its consequences are the same as `docs/GENERATION.md` §1 and the status table in
 * `docs/HARNESS-STATUS.md`; the technical provenance stays behind the disclosure.
 *
 * The record travels on the plan job's checkpoint (`checkpoint.validation`), bound to the plan id
 * that job wrote. A carried plan version (`plan.replan`) has no validation record of its own, so
 * this model says no check is recorded for this version rather than borrowing the previous one's.
 */
const PLAN_VALIDATION_LINES = Object.freeze({
  independent: 'Checked by a second model',
  same_model: 'Checked by the same model',
  unidentified: 'Checked by a model that could not be identified',
  unrecorded: 'No validator record is stored for this version'
})

/** Read the recorded independence, or derive it exactly as the backend does. Never upgrade. */
function planValidationIndependence(validation) {
  const declared = validation && validation.independence
  if (declared === 'independent' || declared === 'same_model' || declared === 'unidentified') {
    return declared
  }
  const generator = (validation && validation.generator) || {}
  const validator = (validation && validation.validator) || {}
  if (!generator.model || !validator.model) return 'unidentified'
  return String(generator.model) === String(validator.model) ? 'same_model' : 'independent'
}

/** `provider/model` only from what the runtime reported; a missing half is not invented. */
function planValidationModelName(identity) {
  const model = identity && identity.model ? String(identity.model) : ''
  const provider = identity && identity.provider ? String(identity.provider) : ''
  if (model && provider) return `${provider}/${model}`
  return model || null
}

/**
 * The plan-review provenance model.
 *
 * `null` means the screen is still reading the job that owns the record: a line is not shown until
 * the record is, so a pending read can never look like "no check". A record whose `plan_id` names
 * another version is discarded, because a carried plan is a copy, not a re-validation.
 */
function planValidationView({ job, jobHint, plan, reading }) {
  const planId = plan && plan.plan_id ? String(plan.plan_id) : null
  const sources = [job, jobHint].filter(Boolean)
  let checkpoint = null
  let mismatched = false
  for (const source of sources) {
    const candidate = source.checkpoint || {}
    if (!candidate.validation) continue
    if (planId && candidate.plan_id && String(candidate.plan_id) !== planId) {
      mismatched = true
      continue
    }
    checkpoint = candidate
    break
  }
  if (!checkpoint) {
    // While the owning job is still being read, stay silent rather than claim "no record".
    if (reading && !mismatched) return null
    return {
      state: 'unrecorded',
      line: PLAN_VALIDATION_LINES.unrecorded,
      validatorModel: null,
      generatorModel: null,
      factsUnverified: false,
      warning: null,
      note: null,
      detail: [
        'No validation record is bound to this exact plan version, so nothing here claims a second model.',
        mismatched
          ? 'The plan job read here checked an earlier plan version; a carried version is a copy, not a re-check.'
          : null
      ].filter(Boolean)
    }
  }
  const validation = checkpoint.validation
  const independence = planValidationIndependence(validation)
  const outcome = String(validation.outcome || checkpoint.validation_verdict || '')
  const generatorModel = planValidationModelName(validation.generator)
  const validatorModel = planValidationModelName(validation.validator)
  const factsUnverified = Boolean(validation.facts_unverified)
  const detail = []
  if (VALIDATION_OUTCOME_COPY[outcome]) detail.push(VALIDATION_OUTCOME_COPY[outcome])
  else if (outcome === 'pass') detail.push('The validator passed this draft.')
  if (generatorModel) detail.push(`Writing model: ${generatorModel}.`)
  detail.push(
    validatorModel
      ? `Checking model: ${validatorModel}.`
      : 'The runtime did not report the checking model.'
  )
  if (factsUnverified) detail.push('The sources were not checked, so a pass is not factual verification.')
  if (validation.warning) detail.push(String(validation.warning))
  return {
    // `state` carries the rejection for the screen; the line itself only ever names who checked.
    state: outcome === 'rejected' ? 'rejected' : independence,
    independence,
    outcome,
    line: PLAN_VALIDATION_LINES[independence],
    validatorModel,
    generatorModel,
    factsUnverified,
    warning: validation.warning || null,
    note: factsUnverified
      ? 'The facts were not checked against sources, so this is not factual verification.'
      : null,
    detail
  }
}

/**
 * One plain line plus a disclosure. Never a badge, never an "independently validated" claim for a
 * same-model pass; the model/provider names appear only when the runtime reported them.
 */
function PlanValidationLine({ job, jobHint, plan, reading, learner }) {
  const model = planValidationView({ job, jobHint, plan, reading })
  if (!model) return null
  return jsxs('div', {
    'data-cb-plan-validation': model.state,
    className: 'flex max-w-prose flex-col gap-1 text-xs leading-relaxed text-(--ui-text-secondary)',
    children: [
      jsx('div', {
        'data-cb-plan-validation-line': model.independence || model.state,
        style: { color: 'var(--cb-ink)', fontWeight: 600 },
        children: model.line
      }),
      model.validatorModel
        ? jsx('div', {
            'data-cb-plan-validation-model': model.validatorModel,
            children: `Checking model: ${model.validatorModel}`
          })
        : null,
      model.note
        ? jsx('div', { 'data-cb-plan-validation-facts': 'unverified', children: model.note })
        : null,
      jsxs('details', {
        'data-cb-plan-validation-detail': '',
        children: [
          jsx('summary', { className: 'cursor-pointer', children: 'Technical detail' }),
          jsx('div', {
            className: 'mt-1 flex flex-col gap-1',
            children: [
              ...model.detail.map((line, index) =>
                jsx('div', { children: line }, `validation-detail-${index}`)
              ),
              learner
                ? null
                : jsx('div', {
                    'data-cb-plan-validation-source': 'docs/GENERATION.md',
                    children:
                      'Provenance rule: docs/GENERATION.md §1 (validator independence) and ' +
                      'docs/HARNESS-STATUS.md.'
                  })
            ]
          })
        ]
      })
    ]
  })
}

/**
 * The rejection review model. `null` means there is nothing to repair: the job is still running,
 * it finished with a usable draft, or it failed in a way a fresh job cannot repeat.
 */
function planRejectView({ job, plan, objectiveCount, surface, goal, title }) {
  if (!job || !job.state) return null
  const checkpoint = job.checkpoint || {}
  const validation = checkpoint.validation || {}
  const reasons = Array.isArray(checkpoint.rejection_reasons) ? checkpoint.rejection_reasons : []
  const failedRun = PLAN_RUN_TERMINAL_FAILURE.has(job.state)
  const validatorRejected =
    checkpoint.validation_verdict === 'reject' ||
    validation.outcome === 'rejected' ||
    (checkpoint.generation_state === 'needs_review' && checkpoint.validation_verdict === 'reject')
  if (!failedRun && !validatorRejected) return null

  const learner = surface === 'learner'
  const goalText = String(goal || (job.brief && job.brief.goal) || '').trim()
  const titleText = String(title || '').trim()
  const spoken = goalText ? `“${goalText}”` : titleText ? `“${titleText}”` : 'this course'

  if (failedRun) {
    const cancelled = job.state === 'cancelled'
    const interrupted = job.state === 'interrupted_requires_retry'
    const errorCode = String((job.error && job.error.code) || '')
    const provider = /provider|timeout|llm|research|media|unavailable|deadline/i.test(errorCode)
    const draftKept = Boolean(plan)
    return {
      kind: cancelled ? 'cancelled' : interrupted ? 'interrupted' : provider ? 'provider' : 'failed',
      title: cancelled
        ? 'You stopped this run'
        : interrupted
          ? 'The run lost its worker'
          : provider
            ? 'The planning service did not answer'
            : 'Planning stopped before a plan was written',
      body: cancelled
        ? draftKept
          ? `You stopped this run for ${spoken}. A draft plan had already been written, so it stays here, unapproved; nothing was deleted.`
          : `No plan was written for ${spoken}. Your goal and every choice you made are saved on this job, so running it again repeats the same brief rather than starting over.`
        : draftKept
          ? `The run stopped before it finished, but a draft plan for ${spoken} had already been written. It stays here, unapproved; running the brief again does not create a second course.`
          : `No plan was written for ${spoken}. The brief is saved on the job; running it again sends the same brief and does not create a second course.`,
      where: cancelled ? 'The run, before the plan was approved' : 'The plan job, before the plan was approved',
      detail: [
        errorCode ? `Run error: ${plainPlanReason(errorCode)}` : 'No plan record was written for this run.',
        job.state === 'interrupted_requires_retry'
          ? 'The worker lease expired; the job is safe to start again.'
          : draftKept
            ? 'A draft plan exists and is readable; it is not approved.'
            : 'Nothing was approved, and no lesson pages exist.'
      ],
      action: { id: 'try_again', label: 'Try again' },
      draftKept
    }
  }

  const parsed = reasons.map(splitPlanReason)
  const joined = reasons.join(' ')
  const emptyPlan =
    Number(objectiveCount || 0) === 0 ||
    /no objectives|objective list|empty plan|at least one objective|nothing to teach/i.test(joined)
  const unsourced = /source|ledger|citation|provenance|grounded|unsourced|support/i.test(joined)
  const first = parsed[0] || { place: null, why: '' }
  const kind = emptyPlan ? 'empty' : unsourced ? 'unsourced' : 'structural'
  const count = reasons.length

  const models = {
    empty: {
      title: 'The plan came back with nothing to teach',
      body: `The draft for ${spoken} arrived without any objectives, so there is nothing to approve. The course, its brief and this draft are still saved; nothing was deleted.`,
      where: 'The whole plan: no objective was written',
      action: learner
        ? { id: 'change_goal', label: 'Change the goal' }
        : { id: 'try_again', label: 'Try again' }
    },
    unsourced: {
      title: 'The plan could not show where its facts came from',
      body: `${count === 1 ? 'One part' : `${count} parts`} of the draft could not be tied to a source the research pass actually read. The draft is saved, so nothing is lost; running the same brief gives research another pass, and no lesson is written until this check clears.`,
      where: first.place ? `${first.place}: ${planCheckLabel(first.why)}` : planCheckLabel(first.why),
      action: { id: 'try_again', label: 'Try again' }
    },
    structural: {
      title: 'The outline does not fit together yet',
      body: `The plan was written but failed an outline check${first.why ? `: ${first.why}` : ''}. The draft is saved, so you can repair the outline instead of starting over.`,
      where: first.place ? `${first.place}: ${planCheckLabel(first.why)}` : planCheckLabel(first.why),
      action: learner
        ? { id: 'try_again', label: 'Try again' }
        : { id: 'edit_plan', label: 'Edit the plan' }
    }
  }
  const copy = models[kind]

  const detail = []
  if (reasons.length > 0) detail.push(`Checks that did not clear: ${reasons.map(plainPlanReason).join(' · ')}`)
  if (validation.outcome) detail.push(VALIDATION_OUTCOME_COPY[validation.outcome] || 'The validator did not pass this draft.')
  if (validation.independence) detail.push(VALIDATION_INDEPENDENCE_COPY[validation.independence] || VALIDATION_INDEPENDENCE_COPY.unidentified)
  if (validation.research_status) detail.push(RESEARCH_STATUS_COPY[validation.research_status] || `Research status: ${plainPlanReason(validation.research_status)}`)
  if (detail.length === 0) detail.push('The plan job recorded no detailed reason for this refusal.')

  return {
    kind,
    title: copy.title,
    body: copy.body,
    where: copy.where,
    detail,
    action: copy.action,
    draftKept: Boolean(plan),
    reasons: reasons.map(plainPlanReason)
  }
}

/**
 * One panel, one action. The panel is a status region, not a dialog: the draft stays on screen
 * underneath it and nothing is auto-navigated.
 */
function PlanRejectPanel({ model, busy, error, onAction }) {
  if (!model) return null
  return jsxs('div', {
    role: 'status',
    'data-cb-plan-reject': model.kind,
    'data-cb-plan-reject-action': model.action.id,
    className: 'flex max-w-prose flex-col gap-2 text-xs leading-relaxed text-(--ui-text-secondary)',
    style: {
      padding: '0.6rem 0.75rem',
      borderLeft: '2px solid var(--cb-accent)',
      background: 'var(--cb-accent-soft)'
    },
    children: [
      jsx('div', {
        style: { fontSize: CB_TYPE.meta, fontWeight: 600, color: 'var(--cb-ink)' },
        children: model.title
      }),
      jsx('p', { className: 'max-w-prose', children: model.body }),
      jsx('div', { 'data-cb-plan-reject-where': '', children: `Where: ${model.where}` }),
      jsx('div', {
        'data-cb-plan-reject-draft': model.draftKept ? 'kept' : 'none',
        children: model.draftKept
          ? 'Your draft is still here. It is not approved, and no lesson will be written from it.'
          : 'No draft was written, so there is nothing to lose by running the brief again.'
      }),
      jsx('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: jsx(CbAction, {
          variant: 'primary',
          disabled: busy,
          onClick: onAction,
          children: busy ? 'Starting' : model.action.label
        })
      }),
      error ? jsx('div', { children: error }) : null,
      jsxs('details', {
        'data-cb-plan-reject-details': '',
        children: [
          jsx('summary', { className: 'cursor-pointer', children: 'Technical detail' }),
          jsx('div', {
            className: 'mt-1 flex flex-col gap-1',
            children: model.detail.map((line, index) => jsx('div', { children: line }, `detail-${index}`))
          })
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
  planJobHint,
  onChangeGoal,
  onJobSettled,
  onChanged,
  supported,
  surface,
  outlineHidden,
  syllabusGate
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
  // H-103: the plan job is read here, once, so the review can explain a rejection. The old job
  // line polled this same id separately; StudioJobStatus now shares this read instead of minting a
  // second poller.
  const [retryPlanJobId, setRetryPlanJobId] = useState(null)
  const retryPlanKey = useRef(null)
  const activePlanJobId = retryPlanJobId || planJobId
  const planRun = useStudioJob(activePlanJobId, onJobSettled)
  const [rejectBusy, setRejectBusy] = useState(false)
  const [rejectError, setRejectError] = useState(null)
  // Editing changes the draft the refusal was about. Once an edit is saved the panel steps away:
  // approval is then a deliberate human decision on a different outline, not a silent retry.
  const [rejectionHandled, setRejectionHandled] = useState(false)
  const rejection = planRejectView({
    job: planRun,
    plan,
    objectiveCount: objectives.length,
    surface,
    goal:
      (planRun && planRun.brief && planRun.brief.goal) ||
      (brief && brief.brief && brief.brief.goal) ||
      (plan && plan.goal) ||
      null,
    title: (course && course.title) || (brief && brief.brief && brief.brief.title) || null
  })
  const shownRejection = rejectionHandled ? null : rejection

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
    setRejectionHandled(true)
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

  // H-103: the one repair action on a rejected plan.
  //
  // `edit_plan` opens the existing editor on this draft. `change_goal` hands the same choices back
  // to the create form so a new goal is a new course, not a silent overwrite. `try_again` re-queues
  // the brief the job itself stored under a key derived from that job, so a double click replays the
  // same run and the rejected draft is never deleted.
  const runPlanRepair = useCallback(async () => {
    if (!shownRejection || rejectBusy) return
    const action = shownRejection.action.id
    if (action === 'edit_plan') {
      startEditing()
      return
    }
    if (action === 'change_goal') {
      if (typeof onChangeGoal !== 'function') {
        setRejectError('The create form is not reachable from this surface. Open Courses and start a new course with this goal.')
        return
      }
      const source = (planRun && planRun.brief) || {}
      onChangeGoal({
        goal: source.goal || '',
        title: (course && course.title) || '',
        recipe: source.recipe || null,
        dials: source.dials || null,
        locale: source.locale || null,
        level: source.level || null,
        subjectDomain: source.subject_domain || null,
        scope: source.scope || null
      })
      return
    }
    const source = planRun
    if (!source || !source.brief || !source.job_id) {
      setRejectError('The saved brief could not be read yet, so this run cannot be repeated. Try again once the job line finishes reading.')
      return
    }
    setRejectBusy(true)
    setRejectError(null)
    if (!retryPlanKey.current || retryPlanKey.current.jobId !== source.job_id || !retryPlanKey.current.key) {
      retryPlanKey.current = { jobId: source.job_id, key: `cb-plan-retry-${source.job_id}` }
    }
    const response = await rpc(
      'jobs.create',
      { kind: source.kind || 'plan', brief: source.brief },
      { idempotencyKey: retryPlanKey.current.key }
    )
    setRejectBusy(false)
    if (!response.ok) {
      setRejectError(
        `${response.error && response.error.code ? response.error.code + ': ' : ''}${describeError(response.error)} The saved draft is unchanged.`
      )
      return
    }
    // A new job id is a new attempt: the next click gets its own key instead of replaying this one.
    retryPlanKey.current = { jobId: response.result.job_id, key: null }
    setRetryPlanJobId(response.result.job_id)
    setNotice('A fresh planning run started from the same brief. The rejected draft stays readable until a new plan replaces it.')
    if (onChanged) onChanged()
  }, [shownRejection, rejectBusy, startEditing, onChangeGoal, planRun, course, onChanged])

  // Clear the gap when the screen moves to another plan version (a replan or a fresh authoring job
  // that completed and reloaded the outline).
  useEffect(() => setLessonDocumentGap(null), [planIdOnScreen])
  useEffect(() => {
    setRejectionHandled(false)
    setRejectError(null)
  }, [planIdOnScreen])

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
    // A rejected draft is never replaced by a blank "no plan yet" screen. The panel names what
    // failed and the one repair; the draft (or the saved brief, when nothing was written) is the
    // page, so a reload cannot turn a refusal into an empty course.
    if (shownRejection) {
      return jsxs('div', {
        className: 'flex flex-col gap-4',
        'data-cb-plan-draft': shownRejection.draftKept ? 'kept' : 'none',
        children: [
          jsx(PlanRejectPanel, {
            model: shownRejection,
            busy: rejectBusy,
            error: rejectError,
            onAction: runPlanRepair
          }),
          plan && plan.plan_id
            ? jsx('div', {
                className: 'text-xs text-(--ui-text-secondary)',
                children: `Draft plan ${String(plan.plan_id)} · version ${plan.version || 1} is still stored.`
              })
            : null
        ]
      })
    }
    return jsx(EmptyState, {
      title: planJobId ? 'The plan is being written' : 'No plan yet',
      description: planJobId
        ? 'Research and drafting run in the background; this screen fills itself when the plan is written. Nothing is shown from a template, and there is no progress percentage to show.'
        : learner
          ? 'This course has no plan job attached. Start a new course to generate one; nothing is invented to fill the gap.'
          : 'No plan job is attached to this course, so there is nothing to review. Start a new brief.',
      children: planJobId ? jsx(StudioJobLine, { jobId: planJobId, onSettled: onJobSettled, onRunAgain: onChanged }) : null
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
            children: shownRejection && !editing
              ? null
              : [
              isDraft && !editing && !learner
                ? jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: startEditing, children: 'Edit plan' })
                : null,
              editing
                ? jsx(CbAction, { size: 'sm', variant: 'primary', disabled: busy, onClick: savePlan, children: busy ? 'Saving' : 'Save changes' })
                : null,
              editing ? jsx(sdk.Button, { size: 'sm', variant: 'text', onClick: cancelEditing, children: 'Cancel' }) : null,
              isDraft && !editing
                ? jsx(CbAction, {
                    variant: 'primary',
                    disabled: busy || !supported('plan.approve') || Boolean(syllabusGate && syllabusGate.required && !syllabusGate.ready),
                    onClick: approvePlan,
                    children: 'Approve plan'
                  })
                : null,
              !isDraft && !editing && !lessonDocumentGap
                ? jsx(CbAction, {
                    variant: 'primary',
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

      shownRejection
        ? jsx(PlanRejectPanel, {
            model: shownRejection,
            busy: rejectBusy,
            error: rejectError,
            onAction: runPlanRepair
          })
        : jsx(PlanValidationLine, {
            // H-105: who checked this exact plan version, read from the job that wrote it. The
            // line never claims more than the stored record says; the enums stay in the disclosure.
            job: planRun,
            jobHint: planJobHint,
            plan,
            reading: Boolean(activePlanJobId && !planRun),
            learner
          }),
      shownRejection
        ? null
        : jsx(QuietNote, {
            children:
              'Approving the plan approves this outline and these activities. It does not approve a single generated page: the lesson set is approved later, by its own hash.'
          }),
      syllabusGate && syllabusGate.required && !syllabusGate.ready
        ? jsx('div', {
            className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
            'data-cb-syllabus-gate': 'blocked',
            children: syllabusGate.reason
          })
        : null,
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
      activePlanJobId && !shownRejection
        ? jsx(StudioJobLine, {
            jobId: activePlanJobId,
            job: planRun,
            onSettled: onJobSettled,
            onRunAgain: onChanged
          })
        : null,
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
              jsx('p', {
                className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
                'data-cb-breadth': 'plan',
                children: PLAN_BREADTH_DISCLOSURE
              }),
              jsx(CbLabel, { children: `OUTLINE AND ACTIVITIES (${objectives.length})` }),
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
                      jsx(CbLabel, { children: 'Add an objective' }),
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
              jsx(CbLabel, { children: 'Sources and review notes' }),
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
  scopeHint,
  reloadSignal,
  onChangeGoal,
  onNewSyllabus
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
  // The plan tab's approval is gated by the syllabus mapping on a companion course. The panel
  // reports readiness; the button reads it, and the backend enforces the same rule.
  const [syllabusGate, setSyllabusGate] = useState({ required: false, ready: true, reason: null, stale: false })

  const plan = outline.data && outline.data.plan
  const objectives = (outline.data && outline.data.objectives) || []
  const jobRows = (jobs.data && jobs.data.jobs) || []
  const planJob = jobRows.find((job) => ((job.brief || {}).stage || 'plan') === 'plan') || null
  const lessonsJob = jobRows.find((job) => (job.brief || {}).stage === 'lessons') || null
  const scope = (planJob && planJob.brief && planJob.brief.scope) || scopeHint || null
  const jobId = retryJobId || jobHint || (planJob && planJob.job_id) || null
  // A plan that is already readable does not need its finished job line repeated on every visit.
  // H-103: a rejected or stopped plan is the exception — plan review must read that job to explain
  // the refusal, so its id travels even when objectives already exist.
  const planRunStopped = Boolean(
    planJob &&
      (['failed', 'cancelled', 'interrupted_requires_retry'].includes(planJob.state) ||
        (planJob.checkpoint && planJob.checkpoint.validation_verdict === 'reject'))
  )
  const showJob = Boolean(
    jobId && (objectives.length === 0 || !planJob || !JOB_TERMINAL_STATES.has(planJob.state) || planRunStopped)
  )

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
                ? jsx(CbAction, {
                    variant: 'primary',
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
      jsx(SyllabusAlignmentPanel, {
        course,
        planId: plan ? plan.plan_id : null,
        planState: plan ? plan.state : null,
        reloadSignal,
        onGateChange: setSyllabusGate,
        onChanged: reloadAll,
        onNewSyllabus
      }),
      jsx(StudioPlanView, {
        course,
        revision,
        onRevision,
        outline,
        book,
        brief: null,
        planJobId: showJob ? jobId : null,
        // H-105: a finished plan job is not re-polled, but its checkpoint already carries the
        // validator record, so a revisit still shows who checked this version.
        planJobHint: planJob,
        onChangeGoal,
        onJobSettled: reloadAll,
        onChanged: reloadAll,
        supported: supports,
        surface: 'learner',
        outlineHidden: approved,
        syllabusGate
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
                      jsx(ProseText, { className: 'max-w-3xl', text: file.text }),
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
      jsx(CbLabel, { children: 'Export gate' }),
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
      jsx(CbLabel, { children: 'Final approval' }),
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

      jsx(CbLabel, { children: 'Formats' }),
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
      jsx(CbAction, {
        variant: 'primary',
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
              jsx(CbLabel, { children: 'Exported files' }),
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
      jsx(CbLabel, { children: 'How did it go?' }),
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
          jsx(CbAction, {
            variant: 'primary',
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
              jsx(CbLabel, { children: 'Recorded' }),
              jsx(PackReviewLine, { label: 'Difficulty', value: (STUDIO_DIFFICULTIES.find((item) => item.id === saved.difficulty) || {}).label || saved.difficulty }),
              jsx(PackReviewLine, { label: 'When', value: whenLabel(saved.created_at) }),
              jsx(PackReviewLine, { label: 'Plan hash', value: jsx('code', { className: 'text-xs break-all', children: saved.plan_hash || '—' }) })
            ]
          })
        : null,
      jsx(CbLabel, { children: `REFLECTIONS (${list.length})` }),
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

/**
 * H-145 — the product wordmark. It is type, not an ornament: the seal read as an avatar or a
 * refresh glyph and needed an explanation, so the route header carries the name instead. It is a
 * plain div, never a heading, so the page `h1` stays the only page label.
 */
function CoursebookWordmark() {
  return jsx('div', {
    'data-cb-wordmark': '',
    style: {
      fontFamily: CB_SERIF,
      fontSize: CB_TYPE.meta,
      fontWeight: 600,
      letterSpacing: '0.14em',
      textTransform: 'uppercase',
      lineHeight: 1.2,
      color: 'var(--cb-ink-soft)'
    },
    children: 'Coursebook'
  })
}

function CoursebookPage() {
  const { state: health, reload: reloadHealth } = useHealth()
  const implemented = useRuntime(health.status)
  // The scoped Ink & Field Notes layer: every Coursebook surface paints from `--cb-*`, and the
  // layer stops at this root, so Hermes chrome keeps its own theme untouched.
  const cbMode = useCbMode()
  const cbMotion = useCbMotion()
  const [destination, setDestination] = useState(rememberedDestination)
  const [creating, setCreating] = useState(false)
  const [importing, setImporting] = useState(false)
  const [syllabusFlow, setSyllabusFlow] = useState(false)
  const [syllabusSupersedes, setSyllabusSupersedes] = useState(null)
  const [companionTarget, setCompanionTarget] = useState(null)
  const [courseReloadTick, setCourseReloadTick] = useState(0)
  // Set by the mounted course surface when the welcome (first run) is what is on screen. The header
  // then drops its duplicate "New course" button: one screen, one primary action (UX-01).
  const [coursesEmpty, setCoursesEmpty] = useState(false)
  const [openCourse, setOpenCourse] = useState(null)
  // H-103: "Change the goal" carries the rejected plan's own choices into the create form instead
  // of asking the learner to retype them. It is a seed, not an automatic submit.
  const [createSeed, setCreateSeed] = useState(null)
  // Every door into the create form clears the previous seed; only the plan-rejection action seeds.
  const beginCreate = useCallback((seed = null) => {
    setCreateSeed(seed)
    setCreating(true)
  }, [])
  const [studioCourse, setStudioCourse] = useState(null)
  const [studioSeed, setStudioSeed] = useState(null)
  const [studioRevision, setStudioRevision] = useState(0)
  const [studioReload, setStudioReload] = useState(0)

  const changeDestination = useCallback((next) => {
    rememberedDestination = next
    setCreating(false)
    setImporting(false)
    setSyllabusFlow(false)
    setOpenCourse(null)
    setStudioCourse(null)
    setStudioSeed(null)
    setDestination(next)
  }, [])

  // A created companion course is opened from the library read, never from the create response:
  // the row carries the enrolment revision the plan tab fences on, and the plan itself is still a
  // background job. This waits for the row to appear instead of inventing one.
  useEffect(() => {
    if (!companionTarget) return undefined
    let cancelled = false
    let attempts = 0
    const find = async () => {
      attempts += 1
      const response = await rpc('library.list', { filter: 'all', limit: 100, sort: 'recent' })
      if (cancelled) return
      const rows = response && response.ok && response.result && Array.isArray(response.result.items) ? response.result.items : []
      const row = rows.find((candidate) => candidate.course_id === companionTarget.courseId)
      if (row) {
        rememberedDestination = 'courses'
        setDestination('courses')
        setOpenCourse({ row, objectiveId: null, view: 'plan' })
        setCompanionTarget(null)
        return
      }
      if (attempts >= 20) setCompanionTarget(null)
    }
    find()
    const handle = setInterval(find, 1500)
    return () => {
      cancelled = true
      clearInterval(handle)
    }
  }, [companionTarget])

  const openNewSyllabusRevision = useCallback((target) => {
    setSyllabusSupersedes(target || {})
    setSyllabusFlow(true)
  }, [])

  useRouteIntent(
    useCallback((intent) => {
      if (!intent) return
      if (intent.kind === 'create') {
        rememberedDestination = 'courses'
        setDestination('courses')
        setCreateSeed(null)
        setCreating(true)
        setSyllabusFlow(false)
        setImporting(false)
        setStudioCourse(null)
        setStudioSeed(null)
      } else if (intent.kind === 'import') {
        rememberedDestination = 'library'
        setDestination('library')
        setCreating(false)
        setSyllabusFlow(false)
        setImporting(true)
        setStudioCourse(null)
        setStudioSeed(null)
      } else if (intent.kind === 'syllabus') {
        rememberedDestination = 'library'
        setDestination('library')
        setCreating(false)
        setImporting(false)
        setSyllabusFlow(true)
        setStudioCourse(null)
        setStudioSeed(null)
      } else if (intent.kind === 'library') {
        rememberedDestination = 'library'
        setDestination('library')
        setCreating(false)
        setSyllabusFlow(false)
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
  const canSyllabus = Boolean(implemented && implemented.has('syllabus.intake.create'))
  const canAuthor = Boolean(implemented && implemented.has('parent.brief.create'))
  // `4vw` measures the window, not the route: with a chat and the explorer open the route is
  // ~400px wide but the window is ~1050, so the old padding took 84px of a 407px column. The
  // route's own measured width picks a gutter that leaves the reading/work column room.
  const measuredRoute = useCbViewportWidth()
  const routePad = measuredRoute > 0 && measuredRoute < 760 ? '0.7rem' : 'clamp(1.25rem, 4vw, 4rem)'

  let body
  if (health.status === 'loading' && !health.result) {
    body = jsx('div', { className: 'py-10', children: jsx(sdk.Loader, { label: 'Reading the Coursebook backend' }) })
  } else if (health.status === 'unavailable') {
    body = jsx(BackendUnavailable, { error: health.error, reload: reloadHealth })
  } else if (health.status === 'degraded') {
    body = jsx(DegradedBody, { reload: reloadHealth, result: health.result })
  } else if (creating) {
    body = jsx(CreateCourseFlow, {
      seed: createSeed,
      onCancel: () => {
        setCreating(false)
        setCreateSeed(null)
      },
      onCreated: () => {
        setCreateSeed(null)
        reloadHealth()
      }
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
  } else if (syllabusFlow) {
    body = jsx(SyllabusIntakeFlow, {
      revisionOnly: Boolean(syllabusSupersedes),
      supersedes: syllabusSupersedes,
      onCancel: () => {
        setSyllabusFlow(false)
        setSyllabusSupersedes(null)
      },
      // The course and its plan job are real ids the backend returned; the desk reloads so the
      // new companion course appears from `library.list`, not from this screen's memory.
      onCreated: (created) => {
        const revising = Boolean(syllabusSupersedes)
        setSyllabusFlow(false)
        setSyllabusSupersedes(null)
        if (revising) setCourseReloadTick((value) => value + 1)
        else if (created && created.courseId) setCompanionTarget({ courseId: created.courseId })
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
    body = jsx(LibraryView, {
      createOpen: creating,
      implemented,
      onStartSyllabus: canSyllabus ? () => setSyllabusFlow(true) : null,
      onStartImport: canImport ? onImportPlaceholder : null
    })
  } else if (openCourse) {
    body = jsx(CourseDetail, {
      row: openCourse.row,
      focusObjectiveId: openCourse.objectiveId,
      focusBlockId: openCourse.blockId || null,
      focusView: openCourse.view || null,
      implemented,
      profile: currentScope().profile,
      onBack: () => setOpenCourse(null),
      onChanged: () => reloadHealth(),
      reloadSignal: courseReloadTick,
      onChangeGoal: (seed) => {
        setOpenCourse(null)
        rememberedDestination = 'courses'
        setDestination('courses')
        beginCreate(seed || null)
      },
      onNewSyllabus: openNewSyllabusRevision
    })
  } else if (destination === 'courses') {
    body = jsx(CoursesView, {
      createOpen: creating,
      implemented,
      onEmptyChange: setCoursesEmpty,
      onStartCreate: () => beginCreate(),
      onStartSyllabus: canSyllabus ? () => setSyllabusFlow(true) : null,
      onOpen: (row) => setOpenCourse({ row, objectiveId: null }),
      onShowDesk: () => changeDestination('home')
    })
  } else {
    // H-145: Home is the launcher. It carries exactly one Continue surface for the selected
    // classroom; the all-courses catalog lives behind the Courses destination, not here.
    body = jsx(FieldDesk, {
      implemented,
      profile: currentScope().profile,
      onEmptyChange: setCoursesEmpty,
      onOpen: (row, objectiveId, blockId, view) =>
        setOpenCourse({ row, objectiveId: objectiveId || null, blockId: blockId || null, view: view || null }),
      onShowAll: () => changeDestination('courses'),
      onStartCreate: () => beginCreate(),
      onStartSyllabus: canSyllabus ? () => setSyllabusFlow(true) : null
    })
  }

  const statusCopy = backendCopy(health.status)
  const online = useOnline()
  const showDestinationNav = health.status === 'ready' && !creating && !importing && !syllabusFlow
  // One stable page title per surface. It is the route's only `h1` in every health and flow
  // state, so the first heading is the page title and never a card's objective; every surface
  // below it is an `h2` region. An open course is its own page ("Course"), not a second "Home"
  // or a second course title (CourseDetail already prints the course name at h2).
  const pageTitle = openCourse
    ? 'Course'
    : ((DESTINATIONS.find((item) => item.id === destination) || {}).label) || ROUTE_TITLE

  return jsxs('div', {
    className: 'relative flex h-full min-h-0 flex-col',
    'data-cb-destination': destination,
    'data-cb-route': ROUTE_PATH,
    'data-cb-scope': cbMode,
    'data-cb-motion': cbMotion,
    style: { ...cbScopeStyle(cbMode), paddingLeft: routePad, paddingRight: routePad },
    children: [
      jsx(SkipToContent, {}),
      jsxs('header', {
        className: 'flex shrink-0 flex-col gap-2 pt-3',
        children: [
          jsxs('div', {
            className: 'flex flex-wrap items-start justify-between gap-3',
            children: [
              jsxs('div', {
                className: 'flex min-w-0 flex-col gap-1',
                children: [
                  jsx(CoursebookWordmark, {}),
                  jsx('h1', {
                    'data-cb-page-title': '',
                    style: {
                      margin: 0,
                      fontFamily: CB_SERIF,
                      fontSize: CB_TYPE.display,
                      fontWeight: 600,
                      lineHeight: 1.05,
                      letterSpacing: '-0.02em',
                      color: 'var(--cb-ink)'
                    },
                    children: pageTitle
                  })
                ]
              }),
              jsxs('div', {
                // The actions must give way before the route does: at a 460 px window the route pane
                // is ~214 px, and two nowrap buttons refused to shrink (V2-2: 19 px at 900, 45 px at
                // 460). Shrinkable + wrapping lets them stack onto their own rows instead of clipping.
                className: 'flex min-w-0 flex-wrap items-center justify-end gap-2',
                children: [
                  online ? null : jsx(sdk.Badge, { variant: 'warn', children: 'Offline' }),
                  statusCopy ? jsx(sdk.Badge, { variant: health.status === 'unavailable' ? 'warn' : 'muted', children: statusCopy }) : null,
                  health.status === 'ready' && online && !creating && !importing && destination === 'courses' && canCreate && !coursesEmpty && !openCourse
                    ? jsx(CbAction, { onClick: () => beginCreate(), variant: 'secondary', children: 'New course' })
                    : null,
                  health.status === 'ready' && !creating && !importing && !syllabusFlow && destination === 'library' && canSyllabus
                    ? jsx(CbAction, { onClick: () => setSyllabusFlow(true), variant: 'secondary', children: SYLLABUS_COPY.action })
                    : null,
                  health.status === 'ready' && !creating && !importing && !syllabusFlow && destination === 'library' && canImport
                    ? jsx(CbAction, { onClick: onImportPlaceholder, variant: 'primary', children: 'Import pack' })
                    : null,
                  // H-91 P2-4: the Parent Studio landing plate already carries the one
                  // "New lesson plan" primary, so the route header must not repeat it (the gate
                  // counted two primaries with the same label on that surface).
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
            ? jsx(CbDestinationNav, { value: destination, onChange: changeDestination })
            : null
        ]
      }),
      jsx(PageBody, { label: `${pageTitle} content`, children: body })
    ]
  })
}

/**
 * The three destinations, named, with a selected state a colour-blind learner can still read:
 * weight and a lamp underline, plus `aria-current="page"`. It replaces a segmented control whose
 * active state was a fill only.
 */
function CbDestinationNav({ value, onChange }) {
  return jsx('nav', {
    'data-cb-destination-nav': '',
    'aria-label': 'Coursebook sections',
    className: 'flex flex-wrap items-center gap-x-4',
    children: DESTINATIONS.map((item) => {
      const current = item.id === value
      return jsx(
        'button',
        {
          type: 'button',
          'data-cb-nav-item': item.id,
          'aria-current': current ? 'page' : undefined,
          onClick: () => {
            if (!current) onChange(item.id)
          },
          style: {
            background: 'none',
            border: 'none',
            borderRadius: 0,
            padding: '0.35rem 0',
            cursor: current ? 'default' : 'pointer',
            fontFamily: CB_SANS,
            fontSize: CB_TYPE.meta,
            fontWeight: current ? 600 : 400,
            color: current ? 'var(--cb-ink)' : 'var(--cb-ink-soft)',
            borderBottom: current ? '2px solid var(--cb-lamp)' : '2px solid transparent',
            minHeight: '32px'
          },
          children: item.label
        },
        item.id
      )
    })
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
  const routingUnavailable = profileRouteState.status === 'unavailable'
  const [bindNote, setBindNote] = useState(null)
  const attemptedBind = useRef(null)
  // Which bundled learner skill this chat's next turn loads. Read from the backend's own rule
  // (`GET /sessions/skill` -> coursebook.lesson_skills), the same function the pre_llm_call hook
  // calls, so the note cannot describe a different skill than the turn loads.
  const [skillNote, setSkillNote] = useState(null)

  useEffect(() => {
    if (!storedId) {
      setSkillNote(null)
      return undefined
    }
    let cancelled = false
    rest(`/sessions/skill?session_id=${encodeURIComponent(storedId)}`)
      .then((answer) => {
        if (cancelled) return
        setSkillNote(answer && answer.skill ? answer : null)
      })
      .catch(() => {
        if (!cancelled) setSkillNote(null)
      })
    return () => {
      cancelled = true
    }
  }, [storedId, state.status, state.binding])

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
  const armedRun = pendingBindFor(scopeProfile)
  if (armedRun && (state.status === 'no-session' || state.status === 'idle')) {
    // H-64: a fresh run this Desktop just started is armed to this exact chat. A blank "no durable
    // chat yet" panel here is where the old Start lesson dead end ended up; this state names the
    // run, the objective and the one action that turns this chat into a lesson.
    body = jsx(sdk.PanelEmpty, {
      icon: 'book',
      title: armedRun.objectiveTitle ? `Lesson run ready: ${armedRun.objectiveTitle}` : 'Lesson run ready',
      description:
        'This chat belongs to that lesson. Send the first message and Coursebook connects it to the run; ' +
        'the section stays open beside it with the teaching, the sources and the check.',
      action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: openCoursebook, children: 'Open the section' })
    })
  } else if (state.status === 'no-session' || state.status === 'idle') {
    body = jsx(sdk.PanelEmpty, {
      icon: 'book',
      title: 'No lesson chat open',
      description:
        'A lesson runs in a chat. Open Coursebook, pick a course and start a run; the teaching stays beside the chat once it begins.',
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
      description: 'This chat is not part of a lesson yet. A lesson chat shows its current objective and check here.',
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
      jsx(CbLabel, { children: 'Coursebook' }),
      routingUnavailable
        ? jsx('div', {
            className: 'pb-2 text-xs text-(--ui-text-secondary)',
            role: 'status',
            'data-cb-routing': 'unavailable',
            children:
              'Routing unavailable: Coursebook could not read this window’s profile routes, so ' +
              'requests go without a connection id. Reopen the pane or restart Desktop; on a ' +
              'single-connection install nothing is lost.'
          })
        : null,
      bindNote ? jsx('div', { className: 'pb-2 text-xs text-(--ui-text-secondary)', children: bindNote }) : null,
      skillNote
        ? jsx('div', {
            className: 'pb-2 text-xs text-(--ui-text-secondary)',
            'data-cb-skill': skillNote.skill,
            'data-cb-skill-reason': skillNote.reason || '',
            children:
              skillNote.reason === 'lesson_binding'
                ? `Tutor skill: ${skillNote.skill} — loads on this chat's next message.`
                : `Coach skill: ${skillNote.skill} — no live lesson run for this chat.`
          })
        : null,
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
      jsx(CbLabel, { children: 'Session binding' }),
      jsx(SessionDiagnostics, {}),
      jsx(CbLabel, { children: 'Contracts' }),
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
  useOpenCheck,
  BackendUnavailable,
  CB_TOKENS,
  CB_TOKEN_NAMES,
  CB_TYPE,
  CB_TYPE_STEPS,
  COURSE_SCOPES,
  CREATE_RESULT_COPY,
  FieldDesk,
  deskEstimateState,
  CreateCourseFlow,
  FIRST_RUN_COPY,
  FirstRun,
  GOAL_EXAMPLES,
  GOAL_PLACEHOLDER,
  GoalGallery,
  LIBRARY_COPY,
  TITLE_PLACEHOLDER,
  EvidenceClassText,
  EVIDENCE_TARGET_OPTIONS,
  RECIPE_COPY,
  courseToolsVisible,
  dialLabel,
  enrollmentStatusLabel,
  FieldRail,
  FieldDeskHome,
  FieldNotesStrip,
  DeskFacts,
  FieldQuestView,
  LESSON_VIEWS,
  LEARNING_VIEWS,
  SELF_REPORTED_CONFIRM_COPY,
  SELF_REPORTED_EVIDENCE_COPY,
  StudioLanding,
  SYLLABUS_ACCEPT,
  SYLLABUS_COPY,
  SYLLABUS_LIMITS,
  SYLLABUS_MIME_HINTS,
  ALIGNMENT_STATE_COPY,
  SyllabusAlignmentReview,
  SyllabusAlignmentPanel,
  SyllabusAnchorPanel,
  SyllabusEntry,
  SyllabusIntakeFlow,
  SyllabusParseReview,
  SyllabusValue,
  queueSyllabusAlignment,
  startCompanionCourse,
  syllabusAlignmentView,
  syllabusAlignPayload,
  syllabusAnchorLabel,
  syllabusAssessmentRows,
  syllabusCourseFields,
  syllabusCoursePayload,
  syllabusFormatFor,
  syllabusIntakePayload,
  syllabusItemView,
  syllabusParseView,
  syllabusPlanGate,
  syllabusPlanBrief,
  syllabusReviewPayload,
  syllabusScopeProposal,
  syllabusStaleNotice,
  LearnerPlanView,
  LessonDocumentView,
  MediaFrame,
  NotebookView,
  OBSERVATION_NOTE_MAX,
  OverviewView,
  ParentObservation,
  ParentObservationRecorded,
  TextbookView,
  PronunciationSeat,
  PronunciationStudio,
  QuestMission,
  SectionPage,
  SnapshotLossNotice,
  LessonPaneBody,
  WorkspaceShell,
  blockSaveExcerpt,
  buildDeskModel,
  cbCourseGoalLine,
  cbCourseMonogram,
  cbCoursePathCaption,
  cbCoursePathSegments,
  cbSealStation,
  cbShelfFingerprint,
  cbShelfGroupKey,
  cbStableHash,
  CourseCover,
  PackShelfRow,
  CoursePath,
  groupShelfRows,
  ShelfDisclosure,
  cbLayoutFor,
  cbModeFromTheme,
  cbMotionPreference,
  cbScopeStyle,
  checklistAnswer,
  checklistItems,
  parentObservationKey,
  parentObservationPayload,
  nextObservationSubmission,
  recordParentObservation,
  deskEstimateLabel,
  learnerEvidenceTarget,
  objectiveProgress,
  progressStatement,
  lessonViewOptions,
  lessonViewChoices,
  mainlineObjective,
  notebookSourceRef,
  pronPercent,
  pronunciationAvailabilityCopy,
  questMissions,
  planJobBrief,
  planRejectView,
  PlanRejectPanel,
  PLAN_VALIDATION_LINES,
  planValidationView,
  PlanValidationLine,
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
    // cache instead of calling it from render, where a Promise is not an array. A failed read is
    // retried twice, then kept as a visible `unavailable` state rather than an empty route list.
    profileRouteState = { status: 'loading', error: null }
    loadProfileRoutes()

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
      ctx.register({
        id: 'syllabus',
        area: AREAS.palette,
        data: {
          id: 'coursebook.syllabus',
          label: SYLLABUS_COPY.action,
          keywords: ['syllabus', 'college', 'class', 'student', 'import', 'companion'],
          run: () => requestIntent({ kind: 'syllabus' })
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
