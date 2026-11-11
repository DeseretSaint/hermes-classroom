#!/usr/bin/env node
/**
 * CP-000 — the one capture door for Coursebook concept-parity evidence.
 *
 * Every screenshot used as parity evidence must come from this script and must be accompanied by
 * its `<name>.stamp.json`. The stamp is what makes a frame checkable: it records the module sha the
 * window itself read, the backend contract it talked to, the route geometry, the theme, the text
 * scale, motion/forced-colors posture, font status, image decode state and capture hash.
 *
 * The script REFUSES to capture — and exits 2 with `<name>.refused.json` — unless:
 *   1. the plugin source the window reads hashes to the checkout module sha (or --expect-sha);
 *   2. `[data-cb-route]` exists and no render-error marker is present;
 *   3. `document.fonts.status === 'loaded'`;
 *   4. every `img` inside the route is complete with naturalWidth > 0;
 *   5. no host element is painted above the route box (grid hit-test); a contaminated clip needs
 *      --crop-to-content, which records the overlay geometry and crops the unoccluded content rect;
 *   6. the captured pixels are not a significant share of the document background (pixel veto);
 *   7. the page zoom is 100% during capture (normalised through the host zoom bridge, restored after);
 *   8. with --require-v3, `[data-cb-v3-ready]` is present AND `[data-cb-v3-textures]` is `ready`
 *      (a ground whose tiles fell back to flat paper is not v3 evidence);
 *   9. the renderer logged no React duplicate/missing `key` warning (console.errors is read, not
 *      inferred from a clean DOM).
 *
 * Why the sha is read through the window: `window.hermesDesktop.readPluginSource(path)` is the same
 * IPC door the host's runtime loader uses to fetch `plugin.js` before evaluating it. Hashing that
 * text and comparing it to the checkout is the only in-window proof of which module is on screen;
 * reading the file from Node alone would prove what is on disk, not what the renderer loaded. The
 * script also hard-reloads with `ignoreCache` before probing, so a repointed rig cannot answer from
 * a pre-swap module.
 *
 * Usage (live Electron window):
 *   node scripts/cp-capture.mjs --name home-1049-light --out docs/concept-parity/captures \
 *     --cdp-port 9411 --state "$COURSEBOOK_TEST_STATE" --plugin desktop/plugin.js \
 *     --backend-url http://127.0.0.1:44311 --token "$CB013_TOKEN" \
 *     --route-width 1049 [--require-v3] [--keep-console] [--crop-to-content]
 *
 * Deep screens (a course home, a classroom) are shell state, not a URL, so a hard reload lands on
 * the destination. Those cells add an opt-in driver that clicks what a learner clicks after the
 * reload, and a selector the probe waits for:
 *
 *   --after-reload docs/visual-review/cp-024/drive-course-home.js \
 *   --after-reload-wait '[data-cb-course-home-v3]'
 *
 * Both flags are off by default; a frame that used them says so in its stamp (`capture.driver`).
 *
 * Usage (recorded fixture page, used by tests — no Electron host):
 *   node scripts/cp-capture.mjs --name fixture-ok --out <dir> --fixture tests/fixtures/cp-capture/ok.html \
 *     --expect-sha <sha256>
 */
import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { dirname, resolve } from 'node:path'

const args = process.argv.slice(2)
const flag = (name, fallback = null) => {
  // Last occurrence wins: the capture matrix puts shared defaults in the `BASE` array and lets a
  // cell override one of them by appending the flag (e.g. `--root-font 32px` for the 200 % cell).
  // With first-wins the shared `--root-font 16px` silently won and the 200 % cell was shot at 100 %
  // (CP-024 review round 4).
  let index = -1
  for (let cursor = 0; cursor < args.length; cursor += 1) {
    if (args[cursor] === `--${name}`) index = cursor
  }
  if (index < 0) return fallback
  const value = args[index + 1]
  return value && !value.startsWith('--') ? value : true
}
const outDir = resolve(String(flag('out', 'docs/concept-parity/captures')))
const name = String(flag('name', `capture-${Date.now()}`))
const cdpPort = String(flag('cdp-port', process.env.CB015_CDP_PORT || '9337'))
const pluginPath = resolve(String(flag('plugin', 'desktop/plugin.js')))
const stateDir = flag('state', process.env.COURSEBOOK_TEST_STATE || null)
const loadedPluginArg = flag('loaded-plugin', null)
const fixture = flag('fixture', null)
const requireV3 = Boolean(flag('require-v3', false))
const backendUrl = flag('backend-url', null)
const token = flag('token', process.env.CB013_TOKEN || '')
const routeWidth = Number(flag('route-width', 1049))
const expectSha = flag('expect-sha', null)
const timeoutMs = Number(flag('timeout', 45000))
const keepConsole = Boolean(flag('keep-console', false))
const cropToContent = Boolean(flag('crop-to-content', false))
// CP-038: addressable destinations and click-through states. `--click` is repeatable; every
// value is a CSS selector resolved on the current surface, clicked in order, after the
// destination has rendered and before the frame is measured.
const destinationRaw = flag('destination', null)
const clickSelectors = args.reduce((all, value, index) => {
  if (value === '--click' && args[index + 1] && !args[index + 1].startsWith('--')) all.push(args[index + 1])
  return all
}, [])
const scrollArg = flag('scroll', null)
const clickWaitMs = Number(flag('click-wait', 800))
// CP-038 B3: the Coursebook palette is a product setting stored per profile, not the media
// feature. `--color-scheme` emulates `prefers-color-scheme` and is refused when the route keeps
// painting the host's theme; `--appearance` drives the product's own settings sheet instead, so a
// real light/dark frame is produced by the product, not by an emulation the host ignores.
const appearanceArg = flag('appearance', null)
const APPEARANCE_OPTIONS = ['system', 'light', 'dark']
const appearance = appearanceArg == null
  ? null
  : (APPEARANCE_OPTIONS.includes(String(appearanceArg).trim().toLowerCase())
      ? { requested: String(appearanceArg).trim().toLowerCase(), raw: String(appearanceArg) }
      : {
          invalid: true,
          raw: String(appearanceArg),
          reason: `unknown --appearance "${appearanceArg}" (known: ${APPEARANCE_OPTIONS.join(', ')})`
        })

/**
 * A destination is a hash-like route name, not a hash to write: the plugin's destinations are
 * product state (`data-cb-destination`), so the door *clicks the product control* that reaches
 * one and then refuses unless the rendered route proves it arrived. Supported forms:
 *   home | courses | workshop | studio      (optionally prefixed `#/`)
 *   #/course/<course_id>                    (opens that course's own surface)
 *   #/learn/<objective_id>                  (opens that section's lesson, if its row is reachable)
 */
const parseDestination = (raw) => {
  if (raw == null) return null
  const text = String(raw).trim().replace(/^#\/?/, '').replace(/\/+$/, '')
  if (!text) return { kind: 'invalid', raw: String(raw), reason: 'empty --destination value' }
  if (['home', 'courses', 'workshop', 'studio'].includes(text)) return { kind: 'nav', id: text, raw: String(raw) }
  const course = /^course\/(.+)$/.exec(text)
  if (course) return { kind: 'course', id: decodeURIComponent(course[1]), raw: String(raw) }
  const learn = /^learn\/(.+)$/.exec(text)
  if (learn) return { kind: 'learn', id: decodeURIComponent(learn[1]), raw: String(raw) }
  return {
    kind: 'invalid',
    raw: String(raw),
    reason: `unknown --destination "${raw}" (known: home, courses, workshop, studio, #/course/<id>, #/learn/<id>)`
  }
}
const destination = parseDestination(destinationRaw)

class CaptureRefusal extends Error {
  constructor(stage, reasons, extra = null) {
    super(reasons.join('; '))
    this.stage = stage
    this.reasons = reasons
    this.extra = extra
  }
}

mkdirSync(outDir, { recursive: true })
const pngPath = resolve(outDir, `${name}.png`)
const stampPath = resolve(outDir, `${name}.stamp.json`)
const refusedPath = resolve(outDir, `${name}.refused.json`)

const sha256File = (path) => createHash('sha256').update(readFileSync(path)).digest('hex')
const sleep = (ms) => new Promise((done) => setTimeout(done, ms))

const RENDER_ERROR_SELECTORS = [
  '[data-cb-render-error]',
  '[data-cb-route-error]',
  '[data-cb-render-failed]',
  '[data-cb-error-page]'
]

/**
 * Probe run inside the page. `SRC_PATH` is injected. In live mode it asks the host for the raw
 * plugin source through the runtime loader's own read door and hashes it in-page.
 *
 * It also measures host *occlusion*: for a grid of points inside the route box, which elements sit
 * ABOVE the route in the hit-test stack. A fixed host rail or status bar painted over the route is
 * capture contamination, not product UI, and must never reach a parity frame. The same geometry is
 * used to derive `content_width` / `content_height`, the actually usable painted surface.
 */
const probeExpression = (srcPath, wantSource) => `(async () => {
  const hashText = async (text) => {
    const bytes = new TextEncoder().encode(text)
    const digest = await crypto.subtle.digest('SHA-256', bytes)
    return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
  }
  const fixture = window.__CP000_FIXTURE__ || null
  const round = (n) => Math.round(n * 100) / 100
  const root = document.querySelector('[data-cb-route]')
  const rect = root ? root.getBoundingClientRect() : null
  const imgs = root ? [...root.querySelectorAll('img')] : []
  const styleSheets = [...document.styleSheets]
  let cssRuleCount = 0
  for (const sheet of styleSheets) {
    try { cssRuleCount += sheet.cssRules ? sheet.cssRules.length : 0 } catch { /* cross-origin */ }
  }
  const h1 = document.querySelector('[data-cb-route] h1')
  const bodyFont = getComputedStyle(document.body).fontFamily
  const isBoundary = (el) => el === root || root.contains(el) || el.contains(root)
  const overlayProbe = () => {
    const trims = { left: 0, right: 0, top: 0, bottom: 0 }
    if (!root || !rect || rect.width < 1 || rect.height < 1) {
      return { overlays: [], sampled: 0, occluded_points: 0, occluded_fraction: 0, trims, content_rect: null }
    }
    const cols = 16
    const rows = 24
    const seen = new Map()
    let sampled = 0
    let occluded = 0
    for (let col = 0; col < cols; col += 1) {
      for (let row = 0; row < rows; row += 1) {
        const x = rect.left + ((col + 0.5) * rect.width) / cols
        const y = rect.top + ((row + 0.5) * rect.height) / rows
        sampled += 1
        const stack = document.elementsFromPoint(x, y)
        const above = []
        for (const el of stack) {
          if (isBoundary(el)) break
          if (el === document.documentElement || el === document.body) continue
          above.push(el)
        }
        if (!above.length) continue
        occluded += 1
        const el = above[0]
        const er = el.getBoundingClientRect()
        const key = el.tagName + '|' + String(el.className || '').split(/\\s+/).slice(0, 3).join('.') + '|' +
          Math.round(er.x) + ',' + Math.round(er.y) + ',' + Math.round(er.width) + 'x' + Math.round(er.height)
        if (!seen.has(key)) {
          seen.set(key, {
            tag: el.tagName.toLowerCase(),
            class_fragment: String(el.className || '').split(/\\s+/).slice(0, 4).join('.'),
            slot: el.getAttribute('data-slot'),
            rect: { x: round(er.x), y: round(er.y), width: round(er.width), height: round(er.height) },
            background: getComputedStyle(el).backgroundColor,
            position: getComputedStyle(el).position,
            z_index: getComputedStyle(el).zIndex,
            points: 0
          })
        }
        seen.get(key).points += 1
      }
    }
    const overlays = [...seen.values()].sort((a, b) => b.points - a.points)
    for (const overlay of overlays) {
      const r = overlay.rect
      const spansV = r.height >= rect.height * 0.5
      const spansH = r.width >= rect.width * 0.5
      if (spansV && r.x > rect.left + 1 && r.x + r.width >= rect.right - 1) trims.right = Math.max(trims.right, rect.right - r.x)
      if (spansV && r.x <= rect.left + 1 && r.x + r.width < rect.right - 1) trims.left = Math.max(trims.left, r.x + r.width - rect.left)
      if (spansH && r.y > rect.top + 1 && r.y + r.height >= rect.bottom - 1) trims.bottom = Math.max(trims.bottom, rect.bottom - r.y)
      if (spansH && r.y <= rect.top + 1 && r.y + r.height < rect.bottom - 1) trims.top = Math.max(trims.top, r.y + r.height - rect.top)
    }
    const contentX = rect.left + trims.left
    const contentY = rect.top + trims.top
    return {
      overlays,
      sampled,
      occluded_points: occluded,
      occluded_fraction: sampled ? round(occluded / sampled) : 0,
      trims,
      content_rect: {
        x: round(contentX),
        y: round(contentY),
        width: round(Math.max(0, rect.width - trims.left - trims.right)),
        height: round(Math.max(0, rect.height - trims.top - trims.bottom))
      }
    }
  }
  const occlusion = overlayProbe()
  const out = {
    plugin: { window_sha256: null, loaded_path: ${JSON.stringify(srcPath || null)}, bytes: null, error: null },
    route: {
      selector: '[data-cb-route]',
      present: Boolean(root),
      marker: root ? root.getAttribute('data-cb-route') : null,
      // CP-038: the rendered destination is product state, and the stamp must record it so a
      // frame named for Workshop cannot be a Home frame. course_home / lesson_view record the
      // surface below a destination (an opened course, a rendered lesson).
      destination: root ? root.getAttribute('data-cb-destination') : null,
      course_home: (() => { const el = document.querySelector('[data-cb-course-home]'); return el ? el.getAttribute('data-cb-course-home') : null })(),
      course_detail: (() => { const el = document.querySelector('[data-cb-course-detail]'); return el ? el.getAttribute('data-cb-course-detail') : null })(),
      lesson_view: (() => { const el = document.querySelector('[data-cb-lesson-view]'); return el ? el.getAttribute('data-cb-lesson-view') : null })(),
      lesson_document: (() => { const el = document.querySelector('[data-cb-lesson-view][data-cb-document]'); return el ? el.getAttribute('data-cb-document') : null })(),
      scroll_y: root && root.ownerDocument ? Math.round(window.scrollY) : 0,
      // CP-038: a summary of the route's own data markers, so a click-through state can be proved
      // from the stamp rather than assumed from the click dispatch alone.
      marker_names: root
        ? [...new Set([
            ...[...root.attributes].map((a) => a.name),
            ...[...root.querySelectorAll('*')].flatMap((el) => [...el.attributes].map((a) => a.name))
          ].filter((name) => name.startsWith('data-cb-')))].sort().slice(0, 120)
        : [],
      width: rect ? Math.round(rect.width * 100) / 100 : null,
      height: rect ? Math.round(rect.height * 100) / 100 : null,
      top: rect ? Math.round(rect.top * 100) / 100 : null,
      left: rect ? Math.round(rect.left * 100) / 100 : null,
      window_width: window.innerWidth,
      window_height: window.innerHeight,
      theme: root ? root.getAttribute('data-cb-scope') : null,
      motion: root ? root.getAttribute('data-cb-motion') : null,
      text_scale_root_px: getComputedStyle(document.documentElement).fontSize,
      reduced_motion: matchMedia('(prefers-reduced-motion: reduce)').matches,
      forced_colors: matchMedia('(forced-colors: active)').matches,
      fonts_status: document.fonts.status,
      font_faces: [...document.fonts].map((face) => face.family + ' ' + face.weight + ' ' + face.status).slice(0, 40),
      images_total: imgs.length,
      images_decoded: imgs.filter((img) => img.complete && img.naturalWidth > 0).length,
      images_broken: imgs.filter((img) => !img.complete || img.naturalWidth === 0).map((img) => (img.currentSrc || img.src || '').slice(0, 160)),
      render_error_markers: ${JSON.stringify(RENDER_ERROR_SELECTORS)}.filter((sel) => document.querySelector(sel)),
      v3_ready: Boolean(document.querySelector('[data-cb-v3-ready]')),
      v3_textures: root ? root.getAttribute('data-cb-v3-textures') : null,
      // Word-wrap probe (CP-024 review round 2): a course title may wrap between words, never
      // inside one. For every word in the course title and the plate's type field, count the line
      // boxes its own Range paints; more than one box means the renderer split a word.
      plate_title: (() => {
        const el = document.querySelector('[data-cb-course-plate-title]')
        if (!el) return null
        const style = getComputedStyle(el)
        return {
          font_size: style.fontSize,
          client_height: el.clientHeight,
          scroll_height: el.scrollHeight,
          clipped_vertically: el.scrollHeight > el.clientHeight + 1
        }
      })(),
      word_wraps: (() => {
        const out = []
        for (const sel of ['[data-cb-course-title]', '[data-cb-course-plate-title]']) {
          const el = document.querySelector(sel)
          if (!el) continue
          const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
          let node = walker.nextNode()
          while (node) {
            const value = node.nodeValue || ''
            const re = /\\S+/g
            let match = re.exec(value)
            while (match) {
              const range = document.createRange()
              range.setStart(node, match.index)
              range.setEnd(node, match.index + match[0].length)
              const rects = [...range.getClientRects()].filter((r) => r.width > 0)
              const tops = new Set(rects.map((r) => Math.round(r.top / 2)))
              if (tops.size > 1) out.push({ selector: sel, word: match[0], line_boxes: rects.length })
              match = re.exec(value)
            }
            node = walker.nextNode()
          }
        }
        return out
      })(),
      style_sheet_count: styleSheets.length,
      css_rule_count: cssRuleCount,
      host_slots: document.querySelectorAll('[data-slot]').length,
      host_shell: Boolean(document.querySelector('#root')) && !document.body.className.includes('cb-standalone'),
      heading_font_family: h1 ? getComputedStyle(h1).fontFamily : null,
      body_font_family: bodyFont,
      route_ancestors: root ? (() => { const out = []; let n = root.parentElement; while (n && out.length < 4) { out.push(n.tagName.toLowerCase() + '.' + String(n.className || '').split(/\\s+/).slice(0, 3).join('.')); n = n.parentElement } return out })() : [],
      html_background: getComputedStyle(document.documentElement).backgroundColor,
      body_background: getComputedStyle(document.body).backgroundColor,
      background_color: root ? getComputedStyle(root).backgroundColor : null,
      host_overlays: occlusion.overlays,
      host_overlay_points: occlusion.occluded_points,
      host_overlay_sampled: occlusion.sampled,
      host_overlay_fraction: occlusion.occluded_fraction,
      host_overlay_trims: occlusion.trims,
      content_rect: occlusion.content_rect,
      content_width: occlusion.content_rect ? occlusion.content_rect.width : null,
      content_height: occlusion.content_rect ? occlusion.content_rect.height : null
    },
    console: { errors: [], warnings: 0 }
  }
  if (${wantSource ? 'true' : 'false'} && ${JSON.stringify(srcPath || null)} && window.hermesDesktop && window.hermesDesktop.readPluginSource) {
    try {
      const read = await window.hermesDesktop.readPluginSource(${JSON.stringify(srcPath || null)})
      out.plugin.loaded_path = read.path || out.plugin.loaded_path
      out.plugin.bytes = read.byteSize || read.text.length
      out.plugin.window_sha256 = await hashText(read.text)
    } catch (error) {
      out.plugin.error = String(error && error.message ? error.message : error)
    }
  }
  if (fixture) {
    if (fixture.plugin) out.plugin = Object.assign({}, out.plugin, fixture.plugin)
    if (fixture.route) out.route = Object.assign(out.route, fixture.route)
    if (fixture.console) out.console = fixture.console
  }
  return out
})()`

const runGates = ({ probe, expectedSha, requireV3, pixelCheck, zoom, cropMode, colorScheme = null, appearance = null }) => {
  const gates = {}
  const reasons = []
  const pluginSha = probe.plugin && probe.plugin.window_sha256 ? probe.plugin.window_sha256 : null
  gates.plugin_sha_match = Boolean(pluginSha) && pluginSha === expectedSha
  if (!pluginSha) reasons.push(`plugin sha unavailable in window${probe.plugin && probe.plugin.error ? `: ${probe.plugin.error}` : ''}`)
  else if (pluginSha !== expectedSha) reasons.push(`stale module: window reads ${pluginSha}, expected ${expectedSha}`)

  const route = probe.route || {}
  gates.route_present = route.present === true
  if (!gates.route_present) reasons.push('no [data-cb-route] element — the route did not render')

  gates.no_render_error = Array.isArray(route.render_error_markers) && route.render_error_markers.length === 0
  if (!gates.no_render_error) reasons.push(`render-error marker present: ${(route.render_error_markers || []).join(', ')}`)

  gates.fonts_loaded = route.fonts_status === 'loaded'
  if (!gates.fonts_loaded) reasons.push(`document.fonts.status is ${String(route.fonts_status)} — fonts not settled`)

  gates.images_decoded = (route.images_broken || []).length === 0
  if (!gates.images_decoded) reasons.push(`undecoded image(s) in the route: ${(route.images_broken || []).join(' | ')}`)

  // Host chrome painted over the route box is capture contamination (a rail, a status bar, a chat
  // pane). Refuse unless the caller explicitly crops to the unoccluded content rect, in which case
  // the overlay geometry is recorded in the stamp and the crop excludes it.
  const occluded = Number(route.host_overlay_points || 0)
  if (cropMode === 'content') {
    gates.no_host_overlay = true
    gates.host_overlay_excluded = true
  } else {
    gates.no_host_overlay = occluded === 0
    if (!gates.no_host_overlay) {
      const overlays = (route.host_overlays || []).slice(0, 3)
        .map((o) => `${o.tag}.${o.class_fragment || '(no class)'} ${o.rect.width}x${o.rect.height} bg=${o.background}`)
        .join('; ')
      reasons.push(`host chrome occludes the route box (${occluded}/${route.host_overlay_sampled} sample points; ` +
        `content ${route.content_width}x${route.content_height} of route ${route.width}x${route.height}): ${overlays}` +
        ' — rerun with --crop-to-content to crop the usable surface and record the overlay geometry')
    }
  }

  // Post-capture pixel assertion: when the route paints a different background from the document,
  // a significant share of host-background pixels inside the clip means part of the route was never
  // painted (the historical Class C band). Only meaningful when the two colours differ.
  if (pixelCheck && pixelCheck.ok) {
    gates.no_unpainted_region = !pixelCheck.distinct_backgrounds || Number(pixelCheck.host_bg_fraction) <= 0.02
    if (!gates.no_unpainted_region) {
      reasons.push(`host background ${pixelCheck.html_bg} covers ${(Number(pixelCheck.host_bg_fraction) * 100).toFixed(1)}% ` +
        `of the route crop while the route paints ${pixelCheck.route_bg} — part of the frame was not painted`)
    }
  } else {
    gates.no_unpainted_region = false
    reasons.push(`pixel contamination check did not run${pixelCheck && pixelCheck.error ? `: ${pixelCheck.error}` : ''}`)
  }

  gates.zoom_neutral = !zoom || zoom.capture_percent === 100
  if (!gates.zoom_neutral) reasons.push(`page zoom was ${String(zoom && zoom.capture_percent)}% during capture; the capture door requires 100% so the emulated viewport is fully painted`)

  if (requireV3) {
    // "Ready" must mean the ground actually painted. `data-cb-v3-textures` says which state the
    // material tiles settled in; a fallback ground is flat paper and is not v3 evidence.
    gates.v3_ready = route.v3_ready === true && route.v3_textures === 'ready'
    if (route.v3_textures !== 'ready') {
      reasons.push(`--require-v3 set but the ground textures settled as ${String(route.v3_textures)}`)
    } else if (route.v3_ready !== true) {
      reasons.push('--require-v3 set but [data-cb-v3-ready] is absent')
    }
  }

  // A mode frame is only a mode frame if the emulated scheme actually reached the host theme.
  if (colorScheme) {
    gates.theme_matches_emulation = route.theme === colorScheme
    if (!gates.theme_matches_emulation) {
      reasons.push(`--color-scheme ${String(colorScheme)} was emulated but the route painted ` +
        `${String(route.theme)}; the host theme did not follow prefers-color-scheme`)
    }
  }
  // CP-038 B3: when the door drove the product's appearance setting, the still must prove the
  // route painted it. This is what stops a dark frame being filed under a `-light` name.
  if (appearance && appearance.applied && appearance.requested !== 'system') {
    gates.appearance_applied = route.theme === appearance.requested
    if (!gates.appearance_applied) {
      reasons.push(`--appearance ${appearance.requested} was chosen in the settings sheet but the ` +
        `route paints ${String(route.theme)}`)
    }
  }

  // A renderer that logs React's duplicate/missing `key` warning renders a tree the other gates
  // cannot see. The frame is not evidence of a clean surface, so the door refuses it.
  const keyWarnings = ((probe.console && probe.console.errors) || [])
    .filter((line) => /unique "key"/.test(String(line)))
  gates.no_react_key_warning = keyWarnings.length === 0
  if (!gates.no_react_key_warning) {
    reasons.push(`the route render logged a React key warning: ${keyWarnings[0].slice(0, 160)}`)
  }
  return { gates, reasons, ok: reasons.length === 0 }
}

const writeRefusal = (stage, probe, gate, extra = null) => {
  const record = {
    stamp_version: 1,
    tool: 'scripts/cp-capture.mjs',
    name,
    captured_at: new Date().toISOString(),
    ok: false,
    stage,
    reasons: gate.reasons,
    gates: gate.gates,
    plugin: probe ? probe.plugin : null,
    route: probe ? probe.route : null,
    ...(extra || {})
  }
  writeFileSync(refusedPath, `${JSON.stringify(record, null, 2)}\n`)
  console.error(`REFUSED (${name}): ${gate.reasons.join('; ')}`)
  console.error(`wrote ${refusedPath}`)
  process.exit(2)
}

class CDP {
  constructor(socket) {
    this.socket = socket
    this.nextId = 1
    this.pending = new Map()
    this.listeners = []
    socket.addEventListener('message', (event) => {
      const message = JSON.parse(event.data)
      if (message.id && this.pending.has(message.id)) {
        const { done, fail } = this.pending.get(message.id)
        this.pending.delete(message.id)
        if (message.error) fail(new Error(JSON.stringify(message.error)))
        else done(message.result)
        return
      }
      for (const listener of this.listeners) listener(message)
    })
  }
  send(method, params = {}) {
    return new Promise((done, fail) => {
      const id = this.nextId++
      this.pending.set(id, { done, fail })
      this.socket.send(JSON.stringify({ id, method, params }))
    })
  }
  on(listener) { this.listeners.push(listener) }
  close() { try { this.socket.close() } catch { /* already gone */ } }
}

const connectSocket = async (url) => {
  const socket = new WebSocket(url)
  await new Promise((done, fail) => {
    socket.addEventListener('open', done, { once: true })
    socket.addEventListener('error', fail, { once: true })
  })
  return new CDP(socket)
}

const attachLive = async () => {
  const base = `http://127.0.0.1:${cdpPort}`
  let targets = null
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      targets = await (await fetch(`${base}/json`)).json()
      if (targets && targets.length) break
    } catch { targets = null }
    await sleep(250)
  }
  if (!targets || !targets.length) throw new Error(`no CDP target on ${base}`)
  const pages = targets.filter((entry) => entry.type === 'page')
  const page = pages.find((entry) => /Hermes/i.test(entry.title || '')) || pages[0]
  const cdp = await connectSocket(page.webSocketDebuggerUrl)
  await cdp.send('Page.enable', {})
  await cdp.send('Runtime.enable', {})
  await cdp.send('Log.enable', {})
  return { cdp, page }
}

const collectConsole = (cdp) => {
  const errors = []
  let warnings = 0
  cdp.on((message) => {
    if (message.method === 'Runtime.consoleAPICalled') {
      const { type, args } = message.params
      if (type === 'error') errors.push(args.map((arg) => String(arg.value ?? arg.description ?? '')).join(' ').slice(0, 400))
      if (type === 'warning') warnings += 1
    }
    if (message.method === 'Log.entryAdded') {
      const entry = message.params.entry
      if (entry.level === 'error') errors.push(String(entry.text || '').slice(0, 400))
      if (entry.level === 'warning') warnings += 1
    }
  })
  return () => ({ errors: errors.slice(0, 40), warnings })
}

const evaluate = async (cdp, expression, { timeout = 30000 } = {}) => {
  let timer = null
  const timeoutPromise = new Promise((_, fail) => {
    timer = setTimeout(() => fail(new Error(`Runtime.evaluate timed out after ${timeout}ms`)), timeout)
  })
  let result
  try {
    // A dead host bridge (e.g. `window.hermesDesktop.zoom.get` after a gateway exit) never settles
    // its IPC promise. Without a timeout the whole capture hangs with no record; a timeout turns
    // that into a loud refusal instead.
    result = await Promise.race([
      cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }),
      timeoutPromise
    ])
  } finally {
    if (timer) clearTimeout(timer)
  }
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || 'evaluate failed')
  }
  return result.result.value
}

/* ── CP-038 · destination, click and scroll driving ──────────────────────────────────────────
 * A destination is reached through the product's own control, never by writing state: the nav
 * item (`[data-cb-nav-item]`), the shelf card overlay (`[data-cb-home-card-action]`) or the
 * section row (`[data-cb-section-row]`). After the click the door waits for the surface to prove
 * it arrived; a mismatch is a refusal, so a Home frame can never be saved under a Workshop name.
 */
const destinationControlSelector = (dest) => {
  if (!dest) return null
  if (dest.kind === 'nav') return `[data-cb-nav-item="${dest.id}"]`
  if (dest.kind === 'course') {
    return `[data-cb-home-card-action="${dest.id}"], [data-cb-course-id="${dest.id}"] [data-cb-home-card-action], ` +
      `[data-cb-course-id="${dest.id}"] button, [data-cb-all-courses-row="${dest.id}"] button`
  }
  if (dest.kind === 'learn') return `[data-cb-section-row="${dest.id}"]`
  return null
}

const destinationStateExpression = () => `(() => {
  const root = document.querySelector('[data-cb-route]')
  const attr = (selector, name) => {
    const el = document.querySelector(selector)
    return el ? el.getAttribute(name) : null
  }
  return {
    route: root ? root.getAttribute('data-cb-destination') : null,
    course_home: attr('[data-cb-course-home]', 'data-cb-course-home'),
    course_detail: attr('[data-cb-course-detail]', 'data-cb-course-detail'),
    lesson_view: attr('[data-cb-lesson-view]', 'data-cb-lesson-view'),
    lesson_document: attr('[data-cb-lesson-view][data-cb-document]', 'data-cb-document')
  }
})()`

const destinationMatches = (dest, state) => {
  if (!dest) return true
  if (!state) return false
  if (dest.kind === 'nav') return state.route === dest.id
  if (dest.kind === 'course') return state.course_home === dest.id || Boolean(state.course_detail)
  if (dest.kind === 'learn') return Boolean(state.lesson_view)
  return false
}

const clickExpression = (selector) => `(() => {
  const el = document.querySelector(${JSON.stringify(String(selector))})
  if (!el) return { found: false, selector: ${JSON.stringify(String(selector))} }
  try { el.scrollIntoView({ block: 'nearest', inline: 'nearest' }) } catch { /* detached */ }
  el.click()
  return {
    found: true,
    selector: ${JSON.stringify(String(selector))},
    tag: el.tagName.toLowerCase(),
    label: String(el.getAttribute('aria-label') || el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 80)
  }
})()`

const settlePage = async (cdp) => {
  await evaluate(cdp, `new Promise((done) => {
    requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(done, 80)))
  })`).catch(() => null)
}

/**
 * CP-024: `Emulation.setDeviceMetricsOverride` resizes the layout viewport but does not deliver a
 * ResizeObserver frame in this host, so a v3 surface that measures its own route (the Coursebook
 * route width hook) kept the width it was mounted at. The route geometry recorded by the probe was
 * right while the composition on screen was still the old breakpoint's — a frame that would have
 * been stamped as a 1049 cell and painted the 460 layout. Dispatching `resize` makes the route's
 * own measurement run again, and two frames let React commit it before anything is measured.
 */
const settleLayout = async (cdp) => {
  await evaluate(cdp, `(() => { window.dispatchEvent(new Event('resize')); return true })()`).catch(() => null)
  await evaluate(cdp, `new Promise((done) => {
    requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(done, 120)))
  })`).catch(() => null)
}

const waitForSelector = async (cdp, selector, ms) => {
  const deadline = Date.now() + ms
  while (Date.now() < deadline) {
    const found = await evaluate(cdp, `Boolean(document.querySelector(${JSON.stringify(String(selector))}))`).catch(() => false)
    if (found) return true
    await sleep(120)
  }
  return false
}

const driveDestination = async (cdp, dest, ms) => {
  const record = {
    requested: dest ? dest.raw : null,
    normalized: dest ? (dest.kind === 'nav' ? dest.id : `${dest.kind}/${dest.id}`) : null,
    controls: [],
    rendered: null,
    match: null
  }
  if (!dest) return record
  if (dest.kind === 'invalid') throw new CaptureRefusal('destination', [dest.reason])
  const selector = destinationControlSelector(dest)
  if (!(await waitForSelector(cdp, selector, Math.min(ms, 15000)))) {
    throw new CaptureRefusal('destination', [
      `requested destination ${dest.raw} has no addressable control on the current surface (${selector})`
    ], { destination: record })
  }
  const clicked = await evaluate(cdp, clickExpression(selector))
  record.controls.push({ purpose: 'destination', ...clicked })
  const deadline = Date.now() + ms
  let state = null
  while (Date.now() < deadline) {
    await settlePage(cdp)
    state = await evaluate(cdp, destinationStateExpression())
    if (destinationMatches(dest, state)) break
    await sleep(150)
  }
  record.rendered = state
  record.match = destinationMatches(dest, state)
  if (!record.match) {
    throw new CaptureRefusal('destination', [
      `requested destination ${dest.raw} was not rendered: route=${String(state && state.route)}, ` +
      `course_home=${String(state && state.course_home)}, lesson_view=${String(state && state.lesson_view)}; ` +
      'refusing to save a frame that is not the requested destination'
    ], { destination: record })
  }
  return record
}

const driveClicks = async (cdp, selectors, ms) => {
  const record = []
  for (const selector of selectors) {
    if (!(await waitForSelector(cdp, selector, ms))) {
      throw new CaptureRefusal('click', [`--click ${selector} matched no element within ${ms}ms`], { clicks: record })
    }
    const clicked = await evaluate(cdp, clickExpression(selector))
    if (!clicked || !clicked.found) {
      throw new CaptureRefusal('click', [`--click ${selector} did not resolve to a clickable element`], { clicks: record })
    }
    record.push({ purpose: 'click', ...clicked })
    await settlePage(cdp)
    await sleep(120)
  }
  return record
}

/**
 * CP-038: a route image must be loaded, not merely present. A `loading="lazy"` image below the
 * capture viewport never starts loading on its own, so a route taller than the frame (the
 * Workshop shelf's non-hero covers) could never pass the decoded-images gate: the door polled
 * `{total:3,pending:1}` until it refused. Force every pending route image to eager and decode it,
 * then poll. Two early-return traps are closed here too: a transient `null` (route not mounted
 * yet) and a zero-image route are not success. Zero is accepted only after it has been stable for
 * three polls, so an image that mounts on a later paint is still waited for.
 */
const waitForImages = async (cdp, ms) => {
  const deadline = Date.now() + ms
  let state = null
  let zeroPolls = 0
  while (Date.now() < deadline) {
    state = await evaluate(cdp, `(async () => {
      const root = document.querySelector('[data-cb-route]')
      if (!root) return null
      const imgs = [...root.querySelectorAll('img')]
      const withTimeout = (promise, ms) => Promise.race([
        promise,
        new Promise((done) => setTimeout(() => done(false), ms))
      ])
      const forceDecode = (img) => {
        if (img.complete && img.naturalWidth > 0) return Promise.resolve(true)
        const start = () => {
          try { img.loading = 'eager' } catch { /* attribute is read-only in some engines */ }
          return img.decode().catch(() => {
            // img.decode() does not always begin a lazy image's load; re-assigning the source does.
            const src = img.currentSrc || img.src
            if (!src) return false
            try { img.src = src } catch { /* detached */ }
            return img.decode().catch(() => false)
          })
        }
        return withTimeout(start(), 4000)
      }
      await Promise.all(imgs.map(forceDecode))
      const pending = imgs.filter((img) => !img.complete || img.naturalWidth === 0)
      return {
        total: imgs.length,
        pending: pending.length,
        pending_srcs: pending.map((img) => (img.currentSrc || img.src || '').slice(0, 120)),
        pending_lazy: pending.filter((img) => img.loading === 'lazy').length
      }
    })()`).catch(() => null)
    if (!state) { await sleep(250); continue }
    if (state.total === 0) {
      zeroPolls += 1
      if (zeroPolls >= 3) return state
      await sleep(250)
      continue
    }
    zeroPolls = 0
    if (state.pending === 0) return state
    await sleep(250)
  }
  return state
}

/**
 * CP-038 B3: drive the product's own appearance setting. The Coursebook palette is a per-profile
 * setting (`data-cb-scope`), not `prefers-color-scheme`; emulating the media feature leaves the
 * route painting the host's theme, which is why a dark frame was once filed as `-light`. This opens
 * the settings sheet, chooses the requested option, waits for the route to repaint and closes the
 * sheet. It refuses if the option does not exist or the route does not paint the requested palette.
 */
const driveAppearance = async (cdp, want, ms) => {
  if (!want) return null
  if (want.invalid) throw new CaptureRefusal('appearance', [want.reason], { appearance: { requested: want.raw } })
  const control = '[data-cb-settings-control="appearance"]'
  const openSelector = '[data-cb-settings-open]'
  const closeSelector = '[data-cb-settings-close]'
  const sheetSelector = '[data-cb-settings-sheet]'
  const optionSelector = `${control} button:nth-of-type(${APPEARANCE_OPTIONS.indexOf(want.requested) + 1})`
  const record = { requested: want.requested, before: null, applied: false, rendered_scope: null, clicks: [] }
  const sheetOpen = () => evaluate(cdp, `(() => {
    const el = document.querySelector(${JSON.stringify(sheetSelector)})
    return Boolean(el) && el.hidden !== true && el.getClientRects().length > 0
  })()`).catch(() => false)
  if (!(await waitForSelector(cdp, openSelector, Math.min(ms, 15000)))) {
    throw new CaptureRefusal('appearance', [
      `--appearance ${want.requested} needs the Coursebook settings control (${openSelector}) on this surface`
    ], { appearance: record })
  }
  if (!(await sheetOpen())) {
    record.clicks.push({ purpose: 'appearance-open', ...(await evaluate(cdp, clickExpression(openSelector))) })
    if (!(await waitForSelector(cdp, control, Math.min(ms, 15000)))) {
      throw new CaptureRefusal('appearance', [
        `the settings sheet opened but has no appearance control (${control})`
      ], { appearance: record })
    }
  }
  record.before = await evaluate(cdp, `(() => {
    const el = document.querySelector(${JSON.stringify(control)})
    return el ? el.getAttribute('data-cb-settings-value') : null
  })()`).catch(() => null)
  if (!(await waitForSelector(cdp, optionSelector, Math.min(ms, 15000)))) {
    throw new CaptureRefusal('appearance', [
      `the appearance control has no ${want.requested} option (${optionSelector})`
    ], { appearance: record })
  }
  record.clicks.push({ purpose: `appearance-${want.requested}`, ...(await evaluate(cdp, clickExpression(optionSelector))) })
  const deadline = Date.now() + ms
  let state = null
  while (Date.now() < deadline) {
    await settlePage(cdp)
    state = await evaluate(cdp, `(() => {
      const root = document.querySelector('[data-cb-route]')
      const control = document.querySelector(${JSON.stringify(control)})
      return {
        setting: control ? control.getAttribute('data-cb-settings-value') : null,
        scope: root ? root.getAttribute('data-cb-scope') : null
      }
    })()`)
    if (state && state.setting === want.requested) break
    await sleep(150)
  }
  record.rendered_scope = state ? state.scope : null
  record.applied = Boolean(state && state.setting === want.requested)
  if (!record.applied) {
    throw new CaptureRefusal('appearance', [
      `the appearance control did not accept ${want.requested} (setting=${String(state && state.setting)})`
    ], { appearance: record })
  }
  if (await sheetOpen()) {
    record.clicks.push({ purpose: 'appearance-close', ...(await evaluate(cdp, clickExpression(closeSelector))) })
    const closeDeadline = Date.now() + Math.min(ms, 5000)
    while (Date.now() < closeDeadline) {
      if (!(await sheetOpen())) break
      await sleep(120)
    }
  }
  // Capture hygiene: the trigger keeps keyboard focus after the sheet closes and its focus ring is
  // not part of the evidence frame (it differed from a plain Home capture by ~31 pixels).
  await evaluate(cdp, `(() => {
    const el = document.activeElement
    if (el && typeof el.blur === 'function') el.blur()
    return true
  })()`).catch(() => null)
  await settlePage(cdp)
  return record
}

/**
 * Scroll is applied after the viewport is sized so a measurement pass cannot reset it. It is
 * deliberately non-destructive to the crop: a numeric value scrolls the route's first nested
 * scroll region (a long list or card body), otherwise the route scroller; a selector is scrolled
 * into view with `block: 'nearest'`. If a scroll would move `[data-cb-route]` itself out of the
 * viewport the crop no longer means the route, so that is a refusal. The resolved position is
 * recorded in the stamp.
 */
const applyScroll = async (cdp, target) => {
  if (target == null) return null
  const text = String(target).trim()
  const numeric = /^-?\d+(\.\d+)?$/.test(text)
  const expression = numeric
    ? `(() => {
        const y = ${Number(text)}
        const route = document.querySelector('[data-cb-route]')
        const isScrollable = (el) => {
          if (!el) return false
          const style = getComputedStyle(el)
          return (el.scrollHeight - el.clientHeight > 2) && /auto|scroll/.test(style.overflowY)
        }
        const nested = route ? [...route.querySelectorAll('*')].find(isScrollable) : null
        const host = document.querySelector('main#cb-main-content')
        const scroller = nested || host
        if (scroller) scroller.scrollTop = y
        else window.scrollTo(0, y)
        const rect = route ? route.getBoundingClientRect() : null
        return {
          kind: 'px',
          target: ${JSON.stringify(text)},
          y: Math.round(scroller ? scroller.scrollTop : window.scrollY),
          window_y: Math.round(window.scrollY),
          scroller: nested ? 'route-descendant' : host ? 'main#cb-main-content' : 'window',
          scroller_tag: scroller ? scroller.tagName.toLowerCase() : 'window',
          route_top: rect ? Math.round(rect.top) : null,
          route_bottom: rect ? Math.round(rect.bottom) : null,
          viewport_height: window.innerHeight
        }
      })()`
    : `(() => {
        const el = document.querySelector(${JSON.stringify(text)})
        if (!el) return null
        el.scrollIntoView({ block: 'nearest', inline: 'nearest' })
        const route = document.querySelector('[data-cb-route]')
        const host = document.querySelector('main#cb-main-content')
        const rect = route ? route.getBoundingClientRect() : null
        const targetRect = el.getBoundingClientRect()
        return {
          kind: 'selector',
          target: ${JSON.stringify(text)},
          y: Math.round(host ? host.scrollTop : window.scrollY),
          window_y: Math.round(window.scrollY),
          scroller: host ? 'main#cb-main-content' : 'window',
          offset_top: Math.round(targetRect.top),
          route_top: rect ? Math.round(rect.top) : null,
          route_bottom: rect ? Math.round(rect.bottom) : null,
          viewport_height: window.innerHeight
        }
      })()`
  const result = await evaluate(cdp, expression)
  if (!result) throw new CaptureRefusal('scroll', [`--scroll ${text} matched no element`])
  await settlePage(cdp)
  const outOfFrame = result.route_top != null &&
    (result.route_top < -1 || (result.route_bottom != null && result.route_bottom > result.viewport_height + 1))
  if (outOfFrame) {
    throw new CaptureRefusal('scroll', [
      `--scroll ${text} moved [data-cb-route] out of the capture frame ` +
      `(route ${result.route_top}..${result.route_bottom}, viewport ${result.viewport_height}px); ` +
      'scroll a region inside the route instead'
    ], { scroll: result })
  }
  return result
}

/**
 * Decode the freshly captured PNG back inside the page and count how much of the crop is the
 * document (host) background. A route that paints its own paper must leave almost none; the
 * historical Class C defect left an L-shaped host-coloured band because the emulated viewport was
 * clipped by the rig's page zoom.
 */
const pixelContamination = async (cdp, png, routeBackground, htmlBackground) => {
  const dataUrl = `data:image/png;base64,${png.toString('base64')}`
  const expression = `(async () => {
    try {
      const img = new Image()
      img.src = ${JSON.stringify(dataUrl)}
      await img.decode()
      const canvas = document.createElement('canvas')
      canvas.width = img.width
      canvas.height = img.height
      const ctx = canvas.getContext('2d', { willReadFrequently: true })
      ctx.drawImage(img, 0, 0)
      const parse = (value) => {
        const match = String(value || '').match(/rgba?\\(([^)]+)\\)/)
        if (!match) return null
        const parts = match[1].split(',').map((entry) => Number(entry.trim()))
        if (parts.length < 3 || parts.some((entry) => Number.isNaN(entry))) return null
        return [parts[0], parts[1], parts[2], parts.length > 3 ? parts[3] : 1]
      }
      const html = parse(${JSON.stringify(String(htmlBackground || ''))})
      const route = parse(${JSON.stringify(String(routeBackground || ''))})
      if (!html) return { ok: false, error: 'html background is not an rgb colour: ' + String(htmlBackground) }
      if (html[3] === 0) {
        return { ok: true, sampled: 0, host_bg_pixels: 0, host_bg_fraction: 0, html_bg: 'transparent', route_bg: route ? route.slice(0, 3).join(', ') : null, distinct_backgrounds: false }
      }
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data
      const stepX = Math.max(1, Math.floor(canvas.width / 320))
      const stepY = Math.max(1, Math.floor(canvas.height / 320))
      let sampled = 0
      let host = 0
      for (let y = 0; y < canvas.height; y += stepY) {
        for (let x = 0; x < canvas.width; x += stepX) {
          const index = (y * canvas.width + x) * 4
          sampled += 1
          if (Math.abs(data[index] - html[0]) <= 2 && Math.abs(data[index + 1] - html[1]) <= 2 && Math.abs(data[index + 2] - html[2]) <= 2) host += 1
        }
      }
      return {
        ok: true,
        sampled,
        host_bg_pixels: host,
        host_bg_fraction: sampled ? Math.round((host / sampled) * 10000) / 10000 : 0,
        html_bg: html.join(', '),
        route_bg: route ? route.join(', ') : null,
        distinct_backgrounds: Boolean(route) && (route[0] !== html[0] || route[1] !== html[1] || route[2] !== html[2])
      }
    } catch (error) {
      return { ok: false, error: String(error && error.message ? error.message : error) }
    }
  })()`
  return evaluate(cdp, expression)
}

const readZoom = async (cdp) => evaluate(cdp, `(async () => {
  const zoom = window.hermesDesktop && window.hermesDesktop.zoom
  if (!zoom || !zoom.get) return null
  try {
    const state = await zoom.get()
    return { percent: state.percent, level: state.level }
  } catch (error) {
    return { error: String(error && error.message ? error.message : error) }
  }
})()`)

const setZoomPercent = async (cdp, percent) => evaluate(cdp, `(async () => {
  const zoom = window.hermesDesktop && window.hermesDesktop.zoom
  if (!zoom || !zoom.setPercent) return false
  await zoom.setPercent(${Number(percent)})
  return true
})()`)

const waitForRoute = async (cdp, ms) => {
  const deadline = Date.now() + ms
  while (Date.now() < deadline) {
    const state = await evaluate(cdp, `(() => {
      const root = document.querySelector('[data-cb-route]')
      return { route: Boolean(root), ready: document.readyState, destination: root ? root.getAttribute('data-cb-destination') : null }
    })()`)
    if (state.route) return state
    await sleep(200)
  }
  return null
}

const liveCapture = async () => {
  const { cdp, page } = await attachLive()
  const consoleReader = collectConsole(cdp)

  // Point the host at the route *before* the hard reload (CP-038): the earlier order (reload, then
  // set the hash) let the plugin mount on its remembered Home state and photograph Home under any
  // requested name. Reloading after the hash is set lands on the plugin directly, and the route
  // is re-asserted below for host builds that restore a session route instead.
  //
  // `--no-reload` (CP-024) is for a deep screen the host cannot re-enter after a reload: the caller
  // has already driven the window there and restarted it on the installed module, and the stamp
  // records `capture.reloaded: false` so the frame is never mistaken for a fresh-boot frame.
  const reloaded = !flag('no-reload', false)
  await evaluate(cdp, `location.hash = '#/coursebook'`).catch(() => null)
  await sleep(250)
  if (reloaded) {
    await cdp.send('Page.reload', { ignoreCache: true })
    await sleep(400)
  }
  let state = await waitForRoute(cdp, timeoutMs)
  if (!state) {
    await evaluate(cdp, `location.hash = '#/coursebook'`).catch(() => null)
    state = await waitForRoute(cdp, timeoutMs)
  }
  if (!state) {
    const probe = { plugin: { window_sha256: null, loaded_path: null, error: 'route never appeared' }, route: { present: false, render_error_markers: [] } }
    const gate = { gates: { route_present: false }, reasons: ['[data-cb-route] never appeared after reload'], ok: false }
    writeRefusal('route-wait', probe, gate)
  }

  // Reach the requested destination through its product control and click through any requested
  // state, before geometry is measured. Both steps refuse loudly rather than capture the wrong
  // surface.
  let destinationRecord = null
  let clicks = []
  let appearanceRecord = null
  try {
    // The palette is a profile setting, so it is chosen on the surface that owns the settings
    // control (Home) before the door navigates away from it.
    appearanceRecord = await driveAppearance(cdp, appearance, timeoutMs)
    destinationRecord = await driveDestination(cdp, destination, timeoutMs)
    clicks = await driveClicks(cdp, clickSelectors, timeoutMs)
  } catch (error) {
    if (error instanceof CaptureRefusal) {
      writeRefusal(error.stage, null, { gates: {}, reasons: error.reasons, ok: false }, error.extra)
    }
    throw error
  }

  // Optional post-reload driver (CP-024). A deep screen that the door's destination vocabulary
  // does not address (a course home on `#/coursebook`) is shell state, not a URL: `--after-reload
  // <file>` runs that screen's own real-click driver after the route is up and before any
  // measurement, and `--after-reload-wait <selector>` holds the probe until it is on screen. Both
  // are opt-in; a driver that invents UI state instead of clicking what a learner clicks would
  // defeat the stamp, so the wait selector is what proves the surface arrived.
  const afterReload = flag('after-reload', null)
  if (afterReload && afterReload !== true) {
    const driver = readFileSync(resolve(String(afterReload)), 'utf8')
    await evaluate(cdp, `(async () => { ${driver} })()`)
    const waitSelector = flag('after-reload-wait', null)
    if (waitSelector && waitSelector !== true) {
      const selector = JSON.stringify(String(waitSelector))
      const deadline = Date.now() + timeoutMs
      let arrived = false
      while (Date.now() < deadline) {
        arrived = Boolean(await evaluate(cdp, `Boolean(document.querySelector(${selector}))`))
        if (arrived) break
        await sleep(200)
      }
      if (!arrived) {
        throw new Error(`after-reload driver finished but ${String(waitSelector)} never appeared`)
      }
    }
  }

  // Text scale. The matrix's text scale is the root font size, not page zoom, and each cell names
  // it (`--100--` / `--200--`). The door therefore sets the root font explicitly for EVERY cell —
  // default 16px — and restores the page's prior inline value afterwards. Setting it only for the
  // 200 % cell and never restoring it is what let a prior cell's 32px leak into later `--100--`
  // frames on a `--no-reload` rig (CP-024 review round 3: 14 of 15 frames shot at 32px while every
  // name said 100 %). The requested value is recorded in `capture.root_font`.
  const rootFontArg = flag('root-font', null)
  const rootFont = rootFontArg && rootFontArg !== true ? String(rootFontArg) : '16px'
  const rootFontPrior = await evaluate(cdp, `document.documentElement.style.fontSize || ''`)
  await evaluate(cdp, `document.documentElement.style.fontSize = ${JSON.stringify(rootFont)}`)
  await sleep(450)
  const rootFontRecord = { requested: rootFont, prior_inline: rootFontPrior || null }

  // Neutralise the rig's page zoom. Under a non-100% zoom, `Emulation.setDeviceMetricsOverride`
  // makes the layout viewport larger than the surface Chromium actually paints, so a route crop
  // keeps an unpainted host-coloured band on the right/bottom. The capture door requires 100% zoom
  // and restores the operator's setting afterwards.
  const originalZoom = await readZoom(cdp)
  const zoomApplied = Boolean(originalZoom && typeof originalZoom.percent === 'number')
  if (zoomApplied && Math.abs(originalZoom.percent - 100) > 0.01) {
    await setZoomPercent(cdp, 100)
    await sleep(600)
  }
  const captureZoom = (await readZoom(cdp)) || null
  const zoomRecord = {
    original_percent: zoomApplied ? originalZoom.percent : null,
    capture_percent: captureZoom && typeof captureZoom.percent === 'number' ? captureZoom.percent : null,
    bridge_available: zoomApplied
  }

  try {
  // Measure host chrome offset once, then size the viewport so the ROUTE is the requested width.
  let emWidth = routeWidth + 240
  let targetHeight = 1200
  let zoom = 1
  for (let pass = 0; pass < 6; pass += 1) {
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: emWidth,
      height: targetHeight,
      deviceScaleFactor: 2,
      mobile: false
    })
    await sleep(250)
    await settleLayout(cdp)
    const measured = await evaluate(cdp, `(() => {
      const root = document.querySelector('[data-cb-route]')
      const rect = root.getBoundingClientRect()
      const scroller = document.querySelector('main#cb-main-content')
      if (scroller) scroller.scrollTop = 0
      return { route: rect.width, height: rect.height, window: window.innerWidth }
    })()`)
    zoom = measured.window / emWidth || 1
    const chrome = Math.max(0, measured.window - measured.route)
    const innerTarget = routeWidth + chrome
    if (Math.abs(measured.route - routeWidth) <= 1.5) break
    emWidth = Math.max(320, Math.round(innerTarget / zoom))
  }

  // Grow the viewport to contain the whole route so the crop never cuts a scroll container.
  const box = await evaluate(cdp, `(() => {
    const root = document.querySelector('[data-cb-route]')
    const rect = root.getBoundingClientRect()
    const scroller = document.querySelector('main#cb-main-content')
    if (scroller) scroller.scrollTop = 0
    // The route box can be shorter than its content when the host clamps the main scroller to the
    // viewport (seen at 200 % text, where the plate and route overflow below a 1126 px box); the
    // scroller's scrollHeight is then the truth for the crop.
    const inner = scroller ? scroller.scrollHeight : 0
    return {
      height: Math.max(rect.height, inner),
      content_height: Math.max(root.scrollHeight || 0, inner),
      top: rect.top,
      left: rect.left,
      width: rect.width
    }
  })()`)
  const wantedHeight = Math.min(5000, Math.max(targetHeight, Math.ceil(Math.max(box.height, box.content_height) + box.top + 40)))
  if (wantedHeight !== targetHeight) {
    targetHeight = wantedHeight
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: emWidth,
      height: targetHeight,
      deviceScaleFactor: 2,
      mobile: false
    })
    await sleep(300)
    await settleLayout(cdp)
  }

  // Ask the page for the scroll offset only after the viewport is sized: the sizing pass resets
  // each scroller to the top, so applying it earlier would be silently undone.
  let scroll = null
  try {
    scroll = await applyScroll(cdp, scrollArg)
  } catch (error) {
    if (error instanceof CaptureRefusal) {
      writeRefusal(error.stage, null, { gates: {}, reasons: error.reasons, ok: false }, error.extra)
    }
    throw error
  }

  // Apply reduced-motion / forced-colors / colour-scheme emulation only when asked; never silently.
  // `--color-scheme` is how a mode frame is produced: the host theme follows
  // `prefers-color-scheme`, so the stamp has to record that the mode was emulated, not inferred.
  const colorScheme = flag('color-scheme', null)
  const emulatedMedia = []
  if (colorScheme) emulatedMedia.push({ name: 'prefers-color-scheme', value: String(colorScheme) })
  if (flag('reduced-motion', false)) emulatedMedia.push({ name: 'prefers-reduced-motion', value: 'reduce' })
  if (flag('forced-colors', false)) emulatedMedia.push({ name: 'forced-colors', value: 'active' })
  if (emulatedMedia.length) {
    await cdp.send('Emulation.setEmulatedMedia', { features: emulatedMedia })
    await sleep(350)
  }

  const loadedPlugin = loadedPluginArg
    ? resolve(String(loadedPluginArg))
    : stateDir
      ? resolve(String(stateDir), 'home', 'desktop-plugins', 'coursebook', 'plugin.js')
      : null
  // A data: cover that is still decoding at probe time is not a broken image; wait for the route's
  // images to settle before asserting they decoded (a genuinely broken one still refuses).
  await waitForImages(cdp, Number(flag('image-wait', 15000)))
  const probe = await evaluate(cdp, probeExpression(loadedPlugin, Boolean(loadedPlugin)))
  probe.console = consoleReader()
  probe.route.backend = null

  const cropMode = cropToContent ? 'content' : 'route'
  const routeCrop = await evaluate(cdp, `(() => {
    const root = document.querySelector('[data-cb-route]')
    const rect = root.getBoundingClientRect()
    return { x: rect.left, y: rect.top, width: rect.width, height: rect.height }
  })()`)
  const contentCrop = probe.route.content_rect
  const crop = cropToContent && contentCrop && contentCrop.width > 0 && contentCrop.height > 0 ? contentCrop : routeCrop
  if (cropToContent && crop === routeCrop) {
    probe.route.host_overlay_trims = probe.route.host_overlay_trims || null
  }

  let png = null
  let pixelCheck = { ok: false, error: 'screenshot not attempted' }
  let captureError = null
  try {
    const shot = await cdp.send('Page.captureScreenshot', {
      format: 'png',
      captureBeyondViewport: false,
      clip: { x: crop.x, y: crop.y, width: crop.width, height: crop.height, scale: 1 }
    })
    png = Buffer.from(shot.data, 'base64')
    pixelCheck = await pixelContamination(cdp, png, probe.route.background_color, probe.route.html_background)
  } catch (error) {
    captureError = String(error && error.message ? error.message : error)
  } finally {
    if (zoomApplied && Math.abs(originalZoom.percent - 100) > 0.01) {
      await setZoomPercent(cdp, originalZoom.percent).catch(() => false)
      await sleep(250)
    }
    zoomRecord.restored_percent = zoomApplied ? (await readZoom(cdp).catch(() => null) || {}).percent ?? null : null
  }
  if (captureError) throw new Error(`screenshot failed: ${captureError}`)

  const expectedSha = expectSha ? String(expectSha) : sha256File(pluginPath)
  const gate = runGates({ probe, expectedSha, requireV3, pixelCheck, zoom: zoomRecord, cropMode, colorScheme, appearance: appearanceRecord })
  if (!gate.ok) writeRefusal('gates', probe, gate)

  writeFileSync(pngPath, png)
  return finishStamp({ probe, gate, png, expectedSha, pageUrl: page.url, shotBox: crop, mode: 'live', cropMode, pixelCheck, zoom: zoomRecord, emulatedMedia, destinationRecord, clicks, scroll, appearanceRecord, driver: afterReload && afterReload !== true ? String(afterReload) : null, reloaded, rootFont: rootFontRecord })
  } finally {
    // Restore the page's own root font before the window is used by another cell. A `--no-reload`
    // matrix shares one page across every frame, so an unrestored 32px is a silent scale change.
    await evaluate(cdp, `(() => {
      const prior = ${JSON.stringify(rootFontPrior || '')}
      if (prior) document.documentElement.style.fontSize = prior
      else document.documentElement.style.removeProperty('font-size')
      return document.documentElement.style.fontSize || null
    })()`).catch(() => null)
    if (zoomApplied && Math.abs(originalZoom.percent - 100) > 0.01) {
      await setZoomPercent(cdp, originalZoom.percent).catch(() => false)
    }
  }
}

const fixtureCapture = async () => {
  const target = /^https?:|^file:/.test(String(fixture)) ? String(fixture) : `file://${resolve(String(fixture))}`
  const port = 9500 + Math.floor(Math.random() * 200)
  const chromium = spawn('chromium', [
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    '--hide-scrollbars',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${resolve(outDir, '.chromium-fixture')}`,
    'about:blank'
  ], { stdio: 'ignore' })
  let cdp = null
  const cleanup = () => {
    if (cdp) { try { cdp.close() } catch { /* already gone */ } cdp = null }
    try { chromium.kill() } catch { /* already gone */ }
  }
  try {
    let targets = null
    for (let attempt = 0; attempt < 80; attempt += 1) {
      try {
        targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
        if (targets && targets.length) break
      } catch { targets = null }
      await sleep(250)
    }
    if (!targets || !targets.length) throw new Error('fixture chromium did not open a CDP port')
    const page = targets.find((entry) => entry.type === 'page')
    cdp = await connectSocket(page.webSocketDebuggerUrl)
    await cdp.send('Page.enable', {})
    await cdp.send('Runtime.enable', {})
    await cdp.send('Page.navigate', { url: target })
    await sleep(500)

    // The destination/click/scroll hooks run against a recorded page exactly as they run against
    // the live rig, so their refusal paths are testable without an Electron host.
    const appearanceRecord = await driveAppearance(cdp, appearance, timeoutMs)
    const destinationRecord = await driveDestination(cdp, destination, timeoutMs)
    const clicks = await driveClicks(cdp, clickSelectors, timeoutMs)

    await cdp.send('Emulation.setDeviceMetricsOverride', { width: routeWidth, height: 900, deviceScaleFactor: 2, mobile: false })
    await sleep(150)
    // Clicking may have nudged a scroller; reset the page so the route box starts at the top of
    // the frame before the requested scroll is applied.
    await evaluate(cdp, `window.scrollTo(0, 0)`)
    const scroll = await applyScroll(cdp, scrollArg)

    await waitForImages(cdp, Number(flag('image-wait', 15000)))
    const probe = await evaluate(cdp, probeExpression(null, false))
    const routeBox = await evaluate(cdp, `(() => {
      const root = document.querySelector('[data-cb-route]')
      const rect = root.getBoundingClientRect()
      return { x: rect.left, y: rect.top, width: rect.width, height: rect.height }
    })()`)
    const contentBox = probe.route.content_rect
    const cropMode = cropToContent ? 'content' : 'route'
    const box = cropToContent && contentBox && contentBox.width > 0 && contentBox.height > 0 ? contentBox : routeBox
    const shot = await cdp.send('Page.captureScreenshot', {
      format: 'png',
      captureBeyondViewport: false,
      clip: { x: box.x, y: box.y, width: box.width, height: box.height, scale: 1 }
    })
    const png = Buffer.from(shot.data, 'base64')
    const pixelCheck = await pixelContamination(cdp, png, probe.route.background_color, probe.route.html_background)
    const expectedSha = expectSha ? String(expectSha) : sha256File(pluginPath)
    const gate = runGates({ probe, expectedSha, requireV3, pixelCheck, zoom: null, cropMode, appearance: appearanceRecord })
    if (!gate.ok) {
      cleanup()
      writeRefusal('gates', probe, gate)
    }
    writeFileSync(pngPath, png)
    return finishStamp({ probe, gate, png, expectedSha, pageUrl: target, shotBox: box, mode: 'fixture', cropMode, pixelCheck, zoom: null, destinationRecord, clicks, scroll, appearanceRecord })
  } catch (error) {
    if (error instanceof CaptureRefusal) {
      cleanup()
      writeRefusal(error.stage, null, { gates: {}, reasons: error.reasons, ok: false }, error.extra)
    }
    throw error
  } finally {
    cleanup()
  }
}

const fetchRuntime = async (probe) => {
  if (!backendUrl) {
    probe.route.backend = null
    return
  }
  try {
    const response = await fetch(`${String(backendUrl).replace(/\/$/, '')}/api/plugins/coursebook/runtime`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    if (!response.ok) {
      probe.route.backend = { error: `HTTP ${response.status}`, url: String(backendUrl) }
      return
    }
    const runtime = await response.json()
    probe.route.backend = {
      url: String(backendUrl),
      wire_contract: runtime.wire_contract || null,
      wire_version: runtime.wire_version || null,
      contract_methods: runtime.contract_methods || null,
      implemented_count: Array.isArray(runtime.implemented_methods) ? runtime.implemented_methods.length : null,
      plugin_root: runtime.plugin_root || null,
      backend_package: runtime.backend_package || null
    }
  } catch (error) {
    probe.route.backend = { error: String(error && error.message ? error.message : error), url: String(backendUrl) }
  }
}

const finishStamp = async ({ probe, gate, png, expectedSha, pageUrl, shotBox, mode, cropMode = 'route', pixelCheck = null, zoom = null, emulatedMedia = null, destinationRecord = null, clicks = [], scroll = null, appearanceRecord = null, driver = null, reloaded = true, rootFont = null }) => {
  await fetchRuntime(probe)
  const stamp = {
    stamp_version: 1,
    tool: 'scripts/cp-capture.mjs',
    mode,
    name,
    captured_at: new Date().toISOString(),
    ok: true,
    gates: gate.gates,
    plugin: {
      expected_sha256: expectedSha,
      window_sha256: probe.plugin.window_sha256,
      loaded_path: probe.plugin.loaded_path,
      checkout_path: pluginPath,
      bytes: probe.plugin.bytes
    },
    backend: probe.route.backend,
    route: {
      selector: probe.route.selector,
      marker: probe.route.marker,
      destination: probe.route.destination || null,
      width: probe.route.width,
      height: probe.route.height,
      window_width: probe.route.window_width,
      window_height: probe.route.window_height,
      theme: probe.route.theme,
      text_scale_root_px: probe.route.text_scale_root_px,
      motion: probe.route.motion,
      reduced_motion: probe.route.reduced_motion,
      forced_colors: probe.route.forced_colors,
      fonts_status: probe.route.fonts_status,
      font_faces: probe.route.font_faces,
      images_total: probe.route.images_total,
      images_decoded: probe.route.images_decoded,
      v3_ready: probe.route.v3_ready,
      v3_textures: probe.route.v3_textures,
      style_sheet_count: probe.route.style_sheet_count,
      css_rule_count: probe.route.css_rule_count,
      host_slots: probe.route.host_slots,
      host_shell: probe.route.host_shell,
      heading_font_family: probe.route.heading_font_family,
      body_font_family: probe.route.body_font_family,
      route_ancestors: probe.route.route_ancestors,
      html_background: probe.route.html_background,
      background_color: probe.route.background_color,
      host_overlays: probe.route.host_overlays || [],
      host_overlay_points: probe.route.host_overlay_points,
      host_overlay_sampled: probe.route.host_overlay_sampled,
      host_overlay_fraction: probe.route.host_overlay_fraction,
      host_overlay_trims: probe.route.host_overlay_trims,
      content_width: probe.route.content_width,
      content_height: probe.route.content_height,
      content_rect: probe.route.content_rect,
      course_home: probe.route.course_home || null,
      course_detail: probe.route.course_detail || null,
      lesson_view: probe.route.lesson_view || null,
      lesson_document: probe.route.lesson_document || null,
      scroll_y: probe.route.scroll_y,
      word_wraps: probe.route.word_wraps || [],
      plate_title: probe.route.plate_title || null,
      marker_names: probe.route.marker_names || []
    },
    // CP-038: the frame's provenance is not only the plugin sha. A still must say which
    // destination was requested, which one actually rendered, what was clicked to get there and
    // where the page was scrolled. `route.destination` alone is not enough: a Home frame under a
    // Workshop name would otherwise be indistinguishable in the packet.
    destination: {
      requested: destinationRecord ? destinationRecord.requested : (destination ? destination.raw : null),
      normalized: destinationRecord ? destinationRecord.normalized : null,
      rendered: probe.route.destination || null,
      rendered_course_home: probe.route.course_home || null,
      rendered_lesson_view: probe.route.lesson_view || null,
      match: destinationRecord ? destinationRecord.match : (destination ? false : null),
      controls: destinationRecord ? destinationRecord.controls : []
    },
    clicks: Array.isArray(clicks) ? clicks : [],
    // CP-038 B3: which palette was requested through the product's settings sheet and which one
    // the route actually painted, so a `-light` still can never be a dark frame.
    appearance: appearanceRecord || null,
    scroll: scroll || null,
    zoom: zoom,
    emulated_media: emulatedMedia && emulatedMedia.length ? emulatedMedia : null,
    console: probe.console
      ? {
          errors: probe.console.errors || [],
          warnings: probe.console.warnings || 0,
          key_warnings: (probe.console.errors || []).filter((line) => /unique "key"/.test(String(line))).length
        }
      : { errors: [], warnings: 0, key_warnings: 0 },
    capture: {
      file: pngPath.split('/').pop(),
      sha256: createHash('sha256').update(png).digest('hex'),
      bytes: png.length,
      crop_mode: cropMode,
      clip: { x: shotBox.x, y: shotBox.y, width: shotBox.width, height: shotBox.height },
      pixel_check: pixelCheck,
      driver,
      reloaded,
      root_font: rootFont ? { requested: rootFont.requested, prior_inline: rootFont.prior_inline } : null
    },
    page_url: pageUrl
  }
  writeFileSync(stampPath, `${JSON.stringify(stamp, null, 2)}\n`)
  // CP-038: a refusal record from an earlier run of the same name must not survive a success —
  // otherwise a packet carries both "REFUSED" and "OK" for one still.
  try { rmSync(refusedPath, { force: true }) } catch { /* best effort */ }
  console.log(`OK ${name}: route=${stamp.route.width}x${stamp.route.height} theme=${stamp.route.theme} ` +
    `fonts=${stamp.route.fonts_status} images=${stamp.route.images_decoded}/${stamp.route.images_total} ` +
    `sha=${String(stamp.plugin.window_sha256).slice(0, 12)}`)
  console.log(`wrote ${pngPath}`)
  console.log(`wrote ${stampPath}`)
  if (keepConsole && stamp.console.errors.length) {
    console.error(`console errors (${stamp.console.errors.length}):`)
    for (const error of stamp.console.errors) console.error(`  ${error}`)
  }
  return stamp
}

const main = async () => {
  if (flag('help', false)) {
    console.log('usage: node scripts/cp-capture.mjs --name <name> --out <dir> [--fixture <page>] [--cdp-port N]')
    console.log('       [--destination home|courses|workshop|studio|#/course/<id>|#/learn/<id>]')
    console.log('       [--click <selector>]... [--scroll <selector|px>] [--click-wait <ms>]')
    console.log('       [--appearance system|light|dark] [--color-scheme light|dark] [--image-wait <ms>]')
    return
  }
  if (fixture) {
    await fixtureCapture()
    process.exit(0)
  }
  await liveCapture()
  process.exit(0)
}

main().catch((error) => {
  if (error instanceof CaptureRefusal) {
    writeRefusal(error.stage, null, { gates: {}, reasons: error.reasons, ok: false }, error.extra)
  }
  const record = {
    stamp_version: 1,
    tool: 'scripts/cp-capture.mjs',
    name,
    captured_at: new Date().toISOString(),
    ok: false,
    stage: 'error',
    reasons: [String(error && error.stack ? error.stack.split('\n')[0] : error)]
  }
  writeFileSync(refusedPath, `${JSON.stringify(record, null, 2)}\n`)
  console.error(`CAPTURE ERROR (${name}): ${record.reasons[0]}`)
  process.exit(3)
})
