# Ink & Field Notes: the Coursebook token contract (v1)

Status: implementation contract for M2-V1. It describes the layer that ships in
`desktop/plugin.js`; the normative values live in `contracts/cb.tokens.v1.json`.

## Why a scoped layer and not a theme

The Hermes Desktop SDK exposes exactly one theme seam, `THEMES_AREA`, and it registers an
**application-wide** `DesktopTheme`: selecting it repaints the whole window. A runtime plugin may
import only `@hermes/plugin-sdk`, `react` and `react/jsx-runtime`, so it cannot ship a second
stylesheet next to `plugin.js`, and it may not patch the host's `styles.css` or the desktop asar.

The smallest honest seam that gives Coursebook a product front while Hermes stays the spine is
therefore a **scoped route shell**:

- the token table is painted as CSS custom properties on the Coursebook route root
  (`[data-cb-route="/coursebook"]`) and the Coursebook pane root, via `style: cbScopeStyle(mode)`;
- every Coursebook surface reads `var(--cb-*)`;
- the painted light/dark value comes from the SDK's `useTheme().renderedMode`, never from a colour
  guess; on a host without `useTheme` the fallback reads the `.dark` class the host toggles on
  `:root`;
- Hermes chrome, the host's `--ui-*` tokens and the host contrast floor are untouched.

**Recorded limitation.** There is no per-route theme contribution in the current SDK. A future
`ctx.theme`/`THEMES_AREA`-scoped seam would replace this layer without changing the token names,
because no component names a colour directly.

## Tokens

| Token | Role | Light | Dark |
|---|---|---|---|
| `paper` | the reading surface | `#f7f3ea` | `#141312` |
| `paper-raised` | media frame, raised reading surface | `#fffdf7` | `#1e1c19` |
| `ink` | primary text | `#191713` | `#f2ece0` |
| `ink-soft` | captions, secondary text, rail labels | `#5a5347` | `#b5aa97` |
| `rule` | hairlines, table rules, frame edges | `#d9d1c2` | `#3b372f` |
| `accent` | active path, links, focus text | `#2f4a8a` | `#9db5ee` |
| `accent-soft` | selected block tint, focus surface | `#e4e9f4` | `#232b3c` |
| `field` | done, field-note state | `#3f5c33` | `#9cba87` |
| `ochre` | needs review | `#7a4e0d` | `#d7a94e` |
| `coral` | attention; never a substitute for the host error red | `#9e2f1d` | `#e38a76` |

Rules:

- No raw colour outside this table. `tests/test_desktop_tokens.py` strips the token literal from
  the shipped module and fails on any remaining hex.
- No gradients, decorative or otherwise. The test fails on `gradient(` in the module.
- Every token has a light and a dark value, and every value is a 6-digit hex.

## Contrast floor

Computed on the shipped values by `tests/test_desktop_tokens.py`, both modes:

| Pair | Floor | Why |
|---|---|---|
| `ink` on `paper` | 7.0 | reading text (AAA body) |
| `ink` on `paper-raised` | 7.0 | reading text in a raised frame |
| `ink-soft` on `paper` | 4.5 | secondary text and captions |
| `ink-soft` on `paper-raised` | 4.5 | secondary text in a raised frame |
| `accent` on `paper` | 4.5 | active path and links |
| `accent` on `paper-raised` | 4.5 | active path in a raised frame |
| `field` on `paper` | 4.5 | done / field-note text |
| `ochre` on `paper` | 4.5 | needs-review text |
| `coral` on `paper` | 4.5 | attention text |
| `ink` on `accent-soft` | 4.5 | selected block |
| `ink-soft` on `accent-soft` | 4.5 | secondary text on a selected block |
| `rule` on `paper` | 1.25 | hairline visibility (non-text) |

The host's light-mode tertiary-text override is the floor this layer must not lower: `ink-soft`
is held at or above 4.5:1 on both surfaces in both modes.

## Type and rhythm

- Reading measure: `68ch` (`CB_MEASURE`), between the plan's 62-72 character band.
- Lesson title: `clamp(1.45rem, 1.1rem + 1.2vw, 2rem)`; body and rail sizes are `rem`, so a 200%
  root-font change scales the whole shell. The test refuses a `px` font size in the shell markup.
- Rhythm comes from spacing and a single hairline per section, not from a border on every block.
- Motion: the shell has no transitions. `data-cb-motion` records the `prefers-reduced-motion`
  preference so any future 100-140 ms transition is gated on `full`.

## Layout primitives

| Primitive | Contract |
|---|---|
| `WorkspaceShell` | header (eyebrow, title, subtitle, actions), meta row, body. Body is a grid `minmax(0,1fr) 19rem` when the live viewport is at least 1024 px, and a column below that. The reading column never shrinks below its measure; the rail stacks first. |
| `FieldRail` | next action, the section's own facts, at most four source cards, at most three saved notes. It is the third part of the workspace; at narrow widths it is a bottom sheet, not a hidden control. |
| `MediaFrame` | a thin `rule` edge, the media element, a caption, a label + provenance line, and a `<details>` text-equivalent disclosure. Used by `MediaSegment` for the block-level media child; audio never autoplays. |

Layout is computed from `host.state.viewport` because a runtime plugin cannot ship a media query.
`cbLayoutFor(width)` is pure and tested: `>= 1024` is `wide`; an unknown width (`0`) stacks rather
than guessing wide.

## What is deliberately not here

- No second chat, no new RPC method, no grading change.
- No host `styles.css` or desktop asar edit; no fork of Hermes core.
- No `MEDIA:` renderer change: `MediaFrame` frames the existing artifact route output.
- Field Desk content (Continue card, path preview) is `t_0c732822`, not this card.
