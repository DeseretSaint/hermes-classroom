/**
 * Minimal `@hermes/plugin-sdk` stub for the GM-015 probe harness.
 *
 * The probes render the *shipped* `desktop/plugin.js` with `react-dom/server`.  A runtime plugin
 * may only import `@hermes/plugin-sdk`, `react` and `react/jsx-runtime`, so the harness needs a
 * stand-in for the SDK half the plugin reaches during render.  This stub is owned by the harness
 * (it is written into the harness's private temp `node_modules`), never into the host tree.
 *
 * It deliberately implements only what the rendered fixtures touch.  `host` carries no backend:
 * `request` rejects and there is no `rest`.  That is the point of the null-runtime probe.
 */
import React from 'react'

const el = (tag, props, children) => React.createElement(tag, props, children)
const textOf = (props) => (props && props.children !== undefined ? props.children : null)
const atom = (value) => ({ get: () => value })

export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'sidebar.nav'
export const PANES_AREA = 'panes'
export const PALETTE_AREA = 'palette'
export const KEYBINDS_AREA = 'keybinds'
export const SETTINGS_PLUGINS_AREA = 'settings.plugins'
export const TOOL_MEDIA_RENDERER_AREA = 'tool.media'

export const useValue = (a) => a.get()
export const useTheme = () => ({
  renderedMode: globalThis.__CB_TEST_MODE__ === 'dark' ? 'dark' : 'light',
  resolvedMode: globalThis.__CB_TEST_MODE__ === 'dark' ? 'dark' : 'light'
})

export const Button = (props) => {
  const attrs = {
    type: 'button',
    disabled: Boolean(props.disabled),
    'data-variant': props.variant || null,
    onClick: props.onClick
  }
  if (props.className) attrs.className = props.className
  if (props.title) attrs.title = props.title
  for (const [name, value] of Object.entries(props)) {
    if (name === 'children' || value === undefined || name in attrs) continue
    attrs[name] = value
  }
  return el('button', attrs, textOf(props))
}

export const RowButton = (props) => {
  const attrs = { type: 'button' }
  for (const [name, value] of Object.entries(props)) {
    if (name === 'children' || value === undefined) continue
    attrs[name] = value
  }
  return el('button', attrs, textOf(props))
}

export const Badge = (props) => el('span', { className: 'badge', 'data-variant': props.variant || null }, textOf(props))
export const PanelSectionLabel = (props) => el('div', { className: 'panel-label' }, textOf(props))
export const PanelEmpty = (props) => el('div', { className: 'panel-empty' }, textOf(props))
export const Loader = (props) => el('div', { className: 'loader', role: 'status' }, props.label || null)
export const ErrorState = (props) =>
  el('div', { className: 'error-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description), props.children])
export const EmptyState = (props) =>
  el('div', { className: 'empty-state' }, [el('div', { key: 't', className: 'empty-title' }, props.title), el('div', { key: 'd' }, props.description)])
export const MessageTextContent = (props) => el('div', { className: 'md' }, props.text)
export const SegmentedControl = (props) =>
  el('div', { className: 'segmented' }, (props.options || []).map((option) =>
    el('button', { key: option.id, 'aria-pressed': option.id === props.value, type: 'button' }, option.label)))
export const Input = () => null
export const Textarea = (props) =>
  el('textarea', {
    'aria-label': props['aria-label'] || props.placeholder || null,
    placeholder: props.placeholder || null,
    value: props.value || '',
    onChange: props.onChange || (() => {})
  })
export const SearchField = () => null
export const Select = () => null
export const SelectTrigger = () => null
export const SelectValue = () => null
export const SelectContent = () => null
export const SelectItem = () => null
export const ListRow = () => null
export const ConfirmDialog = () => null
export const DropdownMenu = () => null
export const DropdownMenuItem = () => null
export const DropdownMenuTrigger = () => null
export const DropdownMenuContent = () => null
export const Codicon = (props) => el('span', { className: 'codicon', 'aria-hidden': 'true' }, props.icon || null)
export const Checkbox = (props) =>
  el('input', {
    type: 'checkbox',
    checked: Boolean(props.checked),
    disabled: Boolean(props.disabled),
    id: props.id || null,
    'aria-label': props['aria-label'] || null,
    onChange: () => props.onCheckedChange && props.onCheckedChange(!props.checked)
  })
export const SandboxedFrame = () => null
export const Tabs = () => null
export const Tip = () => null
export const Panel = () => null
export const PanelHeader = () => null
export const PanelBody = () => null
export const PanelSection = () => null
export const ToggleRow = (props) =>
  el('button', {
    type: 'button',
    role: 'switch',
    'aria-checked': props.checked ? 'true' : 'false',
    'aria-label': props.label || props.title || null,
    onClick: () => props.onCheckedChange && props.onCheckedChange(!props.checked)
  }, props.label || props.title || null)

export const SIDEBAR = 'sidebar'
export const ROUTES = 'routes'
export const PANES = 'panes'
export const PALETTE = 'palette'
export const KEYBINDS = 'keybinds'

export const host = {
  state: {
    focusedSessionId: atom(null),
    focusedStoredSessionId: atom(null),
    focusedSessionProfile: atom('default'),
    profile: atom('default'),
    viewport: atom({ width: Number(globalThis.__CB_TEST_WIDTH__ || 1280), height: 900, narrow: false })
  },
  // No backend is mounted in the probe harness.  A cold / offline render must handle this.
  profileRoutes: async () => [],
  navigate: () => {},
  notify: () => {},
  openSession: async () => ({ ok: false, error: { code: 'NO_RUNTIME', message: 'no host runtime' } }),
  newChat: async () => ({ ok: false, error: { code: 'NO_RUNTIME', message: 'no host runtime' } })
}
