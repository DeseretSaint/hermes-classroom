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
export const Button = (props) =>
  el('button', {
    type: 'button',
    disabled: Boolean(props.disabled),
    'data-variant': props.variant || null,
    style: props.style || null,
    className: props.className || null,
    'aria-current': props['aria-current'] || null,
    onClick: props.onClick
  }, textOf(props))
export const Badge = (props) => el('span', { className: 'badge', 'data-variant': props.variant || null }, textOf(props))
export const PanelSectionLabel = (props) => el('div', { className: 'panel-label' }, textOf(props))
export const PanelEmpty = (props) => el('div', { className: 'panel-empty' }, textOf(props))
export const Loader = (props) => el('div', { className: 'loader' }, props.label || null)
export const ErrorState = (props) => el('div', { className: 'error-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description), props.children])
export const EmptyState = (props) => el('div', { className: 'empty-state' }, [el('div', { key: 't', className: 'empty-title' }, props.title), el('div', { key: 'd' }, props.description)])
export const MessageTextContent = (props) => el('div', { className: 'md' }, props.text)
export const SegmentedControl = (props) => el('div', { className: 'segmented' }, (props.options || []).map((option) => el('button', { key: option.id, 'aria-pressed': option.id === props.value, type: 'button' }, option.label)))
export const Input = () => null
export const Textarea = () => null
export const SearchField = () => null
export const Select = () => null
export const SelectTrigger = () => null
export const SelectValue = () => null
export const SelectContent = () => null
export const SelectItem = () => null
export const ListRow = (props) => el('div', { className: 'list-row' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description), el('div', { key: 'b' }, props.below), el('div', { key: 'a' }, props.action)])
export const ConfirmDialog = () => null
export const DropdownMenu = (props) => el('div', null, props.children)
export const DropdownMenuItem = (props) => el('button', { type: 'button' }, textOf(props))
export const DropdownMenuTrigger = (props) => el('div', null, props.children)
export const DropdownMenuContent = (props) => el('div', null, props.children)
export const Codicon = () => null
export const Checkbox = () => null
export const SandboxedFrame = () => null
export const Tabs = () => null
export const Tip = (props) => el('div', null, props.children)
export const Panel = (props) => el('div', null, props.children)
export const PanelHeader = (props) => el('div', null, props.children)
export const host = { notify: () => {}, state: {}, newChat: async () => null, openSession: async () => null }
export const pluginContext = null
export const register = () => {}
