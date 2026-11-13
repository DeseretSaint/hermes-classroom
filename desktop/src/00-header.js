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
  // H-196: the pack Library is one surface of the Workshop now (Discover / Library / Provenance),
  // so the route keeps four destinations instead of growing a fifth that would compete with Home.
  { id: 'workshop', label: 'Workshop' },
  { id: 'studio', label: 'Parent Studio' }
]

/**
 * H-147 — the one Home settings document.
 *
 * `ctx.storage` is the host's namespaced JSON store (VS Code `globalState`'s analog); it writes
 * under `hermes.plugin.coursebook.*` and there is no account-level preference API. The document is
 * therefore honestly device state — the sheet says "On this device" and nothing claims a sync —
 * and it is keyed by the Hermes profile the route is scoped to, so two profiles on this machine
 * keep separate settings.
 *
 * `appearance` and `reducedMotion` default to `system`: the host's own theme and the OS motion
 * preference stay authoritative until the learner says otherwise.
 */
const CB_HOME_PREF_DEFAULTS = Object.freeze({
  appearance: 'system',
  defaultMode: 'game',
  sound: false,
  reducedMotion: 'system',
  // H-156 — the one number a parent sets for a child-facing lesson. It is a calm default, not a
  // timer: nothing counts down and no session is ended by it.
  sessionMinutes: 15,
  // H-176 — the learner's own Hermes pet may stand at the trailhead. It is identity, not an
  // avatar system: when the host has no pet sprite the plate simply carries no companion.
  companion: true,
  // GM-010 — the one play-layer switch a learner owns on this device. It hides the XP chip, the
  // cosmetic level and the `Game progress` bar; it never deletes a ledger row and never touches the
  // course. The backend's own `game_feedback` setting hides the same layer profile-wide, and
  // `engagement.read` reports that as `progress.feedback_visible = false`.
  gameFeedback: true,
  classrooms: Object.freeze({})
})
const CB_APPEARANCE_OPTIONS = Object.freeze([
  { id: 'system', label: 'System' },
  { id: 'light', label: 'Light' },
  { id: 'dark', label: 'Dark' }
])
/** Learner-facing names; the stored id is the setting, the lesson view is what it opens. */
const CB_PRESENTATION_OPTIONS = Object.freeze([
  { id: 'game', label: 'Game' },
  { id: 'guided', label: 'Guided' },
  { id: 'textbook', label: 'Textbook' }
])
const CB_PRESENTATION_VIEW = Object.freeze({ game: 'field_quest', guided: 'guided', textbook: 'textbook' })
const CB_PRESENTATION_LABEL = Object.freeze({ game: 'Game', guided: 'Guided', textbook: 'Textbook' })
const CB_REDUCED_MOTION_OPTIONS = Object.freeze([
  { id: 'system', label: 'Follow system' },
  { id: 'reduce', label: 'Reduce motion' }
])
/**
 * H-156 — the child-safe floor and the session length a parent can set.
 *
 * The rules are fixed facts about this build, not switches: Coursebook has no reminder
 * scheduler, no public ranking, no random reward and no streak. The one play layer is Game
 * mode's XP and levels, which are cosmetic feedback the Game feedback switch can hide — never a
 * score, a streak or a gate. A test scans the shipped copy so the floor cannot regress quietly.
 */
const CB_CHILD_SAFE_RULES = Object.freeze([
  { id: 'reminders', label: 'Loss-framed reminders', state: 'Never' },
  { id: 'leaderboard', label: 'Public leaderboard', state: 'Never' },
  { id: 'rewards', label: 'Loot or random rewards', state: 'Never' },
  { id: 'streaks', label: 'Streaks', state: 'Never' },
  { id: 'xp', label: 'XP and levels', state: 'Game only' }
])
const CB_SESSION_OPTIONS = Object.freeze([
  { id: '10', label: '10 min' },
  { id: '15', label: '15 min' },
  { id: '20', label: '20 min' },
  { id: '30', label: '30 min' }
])
const CB_SESSION_CHOICES = CB_SESSION_OPTIONS.map((option) => Number(option.id))
const CB_SETTINGS_TITLE_ID = 'cb-home-settings-title'

/** One listener set, one cache: every mounted Coursebook surface reads the same document. */
const cbHomePrefsListeners = new Set()
const cbHomePrefsCache = new Map()

function cbPrefsProfile() {
  try {
    return currentScope().profile || 'default'
  } catch (error) {
    return 'default'
  }
}

function cbPrefsStorage() {
  const storage = pluginContext && pluginContext.storage
  return storage && typeof storage.get === 'function' && typeof storage.set === 'function' ? storage : null
}

/** Nothing stored is trusted: a partial, hand-edited or older document reads as its defaults. */
function sanitizeCbHomePrefs(raw) {
  const source = raw && typeof raw === 'object' ? raw : {}
  const oneOf = (value, allowed, fallback) => (allowed.indexOf(value) >= 0 ? value : fallback)
  const classrooms = {}
  if (source.classrooms && typeof source.classrooms === 'object') {
    for (const courseId of Object.keys(source.classrooms)) {
      const mode = source.classrooms[courseId]
      if (courseId && CB_PRESENTATION_VIEW[mode]) classrooms[courseId] = mode
    }
  }
  return {
    appearance: oneOf(source.appearance, ['system', 'light', 'dark'], CB_HOME_PREF_DEFAULTS.appearance),
    defaultMode: oneOf(
      source.defaultMode,
      Object.keys(CB_PRESENTATION_VIEW),
      CB_HOME_PREF_DEFAULTS.defaultMode
    ),
    sound: source.sound === true,
    reducedMotion: oneOf(source.reducedMotion, ['system', 'reduce'], CB_HOME_PREF_DEFAULTS.reducedMotion),
    sessionMinutes: CB_SESSION_CHOICES.indexOf(Number(source.sessionMinutes)) >= 0
      ? Number(source.sessionMinutes)
      : CB_HOME_PREF_DEFAULTS.sessionMinutes,
    // Only an explicit `false` hides the companion; an absent or hand-edited value keeps the
    // default of showing the pet the learner already installed.
    companion: source.companion !== false,
    // GM-010: only an explicit `false` hides the play layer, so an older stored document shows it.
    gameFeedback: source.gameFeedback !== false,
    classrooms
  }
}

function cbHomePrefsKey(profile) {
  return `home-preferences.${profile || 'default'}`
}

function readCbHomePrefs(profile) {
  const key = profile || 'default'
  if (cbHomePrefsCache.has(key)) return cbHomePrefsCache.get(key)
  let raw = null
  const storage = cbPrefsStorage()
  try {
    raw = storage ? storage.get(cbHomePrefsKey(key), null) : null
  } catch (error) {
    raw = null
  }
  const value = sanitizeCbHomePrefs(raw)
  cbHomePrefsCache.set(key, value)
  return value
}

function writeCbHomePrefs(profile, next) {
  const key = profile || 'default'
  const clean = sanitizeCbHomePrefs(next)
  cbHomePrefsCache.set(key, clean)
  const storage = cbPrefsStorage()
  try {
    // A failed write must not look saved. The cache still changes for this session, and the
    // sheet's next mount re-reads storage, so the loss is visible rather than silently assumed.
    if (storage) storage.set(cbHomePrefsKey(key), clean)
  } catch (error) {
    // Leave the in-memory value; there is no sync claim to protect.
  }
  for (const listener of cbHomePrefsListeners) {
    try {
      listener(clean)
    } catch (error) {
      // One broken subscriber must not stop the others.
    }
  }
  return clean
}

function updateCbHomePrefs(profile, patch) {
  const current = readCbHomePrefs(profile)
  return writeCbHomePrefs(profile, { ...current, ...patch })
}

/** One section's reset. The classroom map is one section; every scalar is its own. */
function resetCbHomePrefsSection(profile, section) {
  const current = readCbHomePrefs(profile)
  const next = { ...current }
  if (section === 'classroom') next.classrooms = {}
  else if (Object.prototype.hasOwnProperty.call(CB_HOME_PREF_DEFAULTS, section)) {
    next[section] = CB_HOME_PREF_DEFAULTS[section]
  }
  return writeCbHomePrefs(profile, next)
}

/** The effective view for one classroom: its own override wins, else the home default. */
function cbEffectiveMode(prefs, courseId) {
  const document = prefs || CB_HOME_PREF_DEFAULTS
  const override = courseId && document.classrooms ? document.classrooms[courseId] : null
  return override || document.defaultMode
}

/** The palette the route paints: an explicit appearance wins, `system` follows the host. */
function cbAppliedMode(hostMode, appearance) {
  return appearance === 'light' || appearance === 'dark' ? appearance : hostMode
}

/**
 * When the learner picks an appearance that differs from the host theme, the SDK controls inside
 * Coursebook (buttons, rows, switches) would keep the host's own text/background variables and go
 * unreadable on the plugin's palette. These are the host variables those controls consume, mapped
 * onto the scoped `--cb-*` table so one surface has one palette. `system` changes nothing.
 */
function cbHostVars(appearance) {
  if (appearance !== 'light' && appearance !== 'dark') return {}
  return {
    '--background': 'var(--cb-paper)',
    '--foreground': 'var(--cb-ink)',
    '--card': 'var(--cb-paper-raised)',
    '--card-foreground': 'var(--cb-ink)',
    '--popover': 'var(--cb-paper-raised)',
    '--popover-foreground': 'var(--cb-ink)',
    '--muted': 'var(--cb-paper)',
    '--muted-foreground': 'var(--cb-ink-soft)',
    '--border': 'var(--cb-rule)',
    '--input': 'var(--cb-rule)',
    '--accent': 'var(--cb-accent-soft)',
    '--accent-foreground': 'var(--cb-ink)',
    '--primary': 'var(--cb-lamp)',
    '--primary-foreground': 'var(--cb-on-lamp)',
    '--ui-text-primary': 'var(--cb-ink)',
    '--ui-text-secondary': 'var(--cb-ink-soft)',
    '--ui-text-tertiary': 'var(--cb-ink-soft)',
    '--ui-bg-primary': 'var(--cb-paper)',
    '--ui-bg-secondary': 'var(--cb-paper-raised)',
    '--ui-bg-tertiary': 'var(--cb-paper)'
  }
}

/**
 * The one sound this build owns when `sound` is on: a short, quiet tone at a check verdict.
 * It is never narration and never autoplays a media file; a host without Web Audio stays silent.
 */
function cbPlayCheckCue(verdict) {
  const prefs = readCbHomePrefs(cbPrefsProfile())
  if (!prefs.sound) return false
  try {
    const Ctor =
      typeof window !== 'undefined' ? window.AudioContext || window.webkitAudioContext : null
    if (!Ctor) return false
    const context = new Ctor()
    const osc = context.createOscillator()
    const gain = context.createGain()
    osc.type = 'sine'
    osc.frequency.value = verdict === 'needs_retry' ? 261.63 : 392
    gain.gain.value = 0.04
    osc.connect(gain)
    gain.connect(context.destination)
    osc.onended = () => {
      try {
        context.close()
      } catch (error) {
        // Already closed.
      }
    }
    osc.start()
    osc.stop(context.currentTime + 0.14)
    return true
  } catch (error) {
    return false
  }
}

/**
 * The hook every Coursebook surface uses. `update` and `reset` apply immediately — there is no
 * Save step — and notify every other mounted surface in the same frame.
 */
function useCbHomePrefs() {
  const profile = cbPrefsProfile()
  const [prefs, setPrefs] = useState(() => readCbHomePrefs(profile))
  useEffect(() => {
    setPrefs(readCbHomePrefs(profile))
    const listener = (value) => setPrefs(value)
    cbHomePrefsListeners.add(listener)
    return () => {
      cbHomePrefsListeners.delete(listener)
    }
  }, [profile])
  const update = useCallback((patch) => updateCbHomePrefs(profile, patch), [profile])
  const reset = useCallback((section) => resetCbHomePrefsSection(profile, section), [profile])
  return [prefs, update, reset, profile]
}

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

/**
 * Forget the cached wire facts and probe again.
 *
 * Only an explicit control calls this: the registry is static for a mounted process, so a surface
 * that says "this build cannot run it" offers one re-read rather than polling `/runtime`.
 */
function reloadBackendWire() {
  wireReady = null
  return ensureBackendWire()
}

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
async function beginLessonFor({ row, objectiveId, objectiveTitle, mode, profile, acknowledgePrerequisites = false }) {
  if (!row || !row.enrollment_id) return { ok: false, message: 'No course was read for this action.' }
  const target = objectiveId || (row.evidence_summary && row.evidence_summary.current_objective_id)
  if (!target) {
    return { ok: false, message: 'This course has no current objective yet; approve the plan first.' }
  }
  const response = await rpc(
    'lesson.begin',
    {
      enrollment_id: row.enrollment_id,
      objective_id: target,
      mode,
      // R6: an unmet prerequisite edge refuses once, naming the learner's choice. "Start anyway"
      // retries this same call with the acknowledgment, so the decision is the learner's and the
      // response records it as `prerequisite_state: unmet_acknowledged`.
      ...(acknowledgePrerequisites ? { acknowledge_prerequisites: true } : {})
    },
    {
      idempotencyKey: `cb-lesson-${target}-${mode}-${
        mode === 'fresh' ? newOperationId('run') : 'resume'
      }${acknowledgePrerequisites ? '-ack' : ''}`
    }
  )
  if (!response.ok) {
    const error = response.error || {}
    // The refusal is actionable, so it travels as a reason the caller can turn into a control.
    if (error.code === 'PREREQUISITE_UNMET') {
      return {
        ok: false,
        reason: 'prerequisite-unmet',
        objectiveId: target,
        prerequisiteState: (error.details && error.details.prerequisite_state) || null,
        message: describeError(error)
      }
    }
    return { ok: false, message: `${error.code}: ${describeError(error)}` }
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

