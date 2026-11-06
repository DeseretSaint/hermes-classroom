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
 * Phase boundary: this file registers the real surfaces (route, sidebar row, pane, palette
 * command, settings page) and renders only states that are true in this build. Course creation,
 * import and lesson flows are added by their owning work packages together with the backend
 * commands they call; a button that does nothing is not a skeleton, it is a lie.
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
  palette: sdk.PALETTE_AREA || 'palette'
}

/** Set once in register(); components read the scoped context from here. */
let pluginContext = null

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

/**
 * Lesson-context pane. Registered globally, but scoped: it never shows a lesson from another
 * chat. With no bound lesson it stays a minimal entry point instead of pretending.
 */
function CoursebookPane() {
  const openCoursebook = useCallback(() => {
    sdk.host.navigate(ROUTE_PATH)
  }, [])

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col px-3 py-2',
    children: [
      jsx(sdk.PanelSectionLabel, { children: 'COURSEBOOK' }),
      jsx(sdk.PanelEmpty, {
        icon: 'book',
        title: 'No lesson bound to this chat',
        description:
          'The Coursebook pane shows the current objective, the check and its evidence only for a bound lesson chat.',
        action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: openCoursebook, children: 'Open Coursebook' })
      })
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
          run: () => sdk.host.navigate(ROUTE_PATH)
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
