#!/usr/bin/env node
/**
 * CP-033 — flat animatic renderer.
 *
 * Builds the 75-second animatic from a beat spec (`docs/launch/animatic/beats.json`) as static
 * frames, then cuts them on the beat grid into an H.264 MP4 with ffmpeg.
 *
 * What this script does NOT do: it never draws product UI. Word cards are editorial type on the
 * contract's own paper ground; `plate` and `reveal` frames show a pinned reference plate from
 * `docs/concept-parity/refs/` inside a mat, with a visible PLACEHOLDER chip. Every number and every
 * product string on a card is either a `docs/concept-parity/COPY.md` row (with `{braces}` left in
 * place, because the value is live state) or a bare fact about the build.
 *
 * Type is the product's own: `assets/fonts/CBDisplay-VF.woff2` (Fraunces, OFL) and
 * `assets/fonts/CBUI-VF.woff2` (Source Sans 3, OFL). Colours are read at render time from
 * `contracts/cb.tokens.v3.json` `modes.light`; a raw hex in this file would be a second contract.
 *
 * Usage:
 *   node scripts/cp-animatic.mjs [--spec docs/launch/animatic/beats.json]
 *                                [--out docs/launch/animatic] [--no-video]
 *
 * Requires: chromium (headless), ffmpeg, ffprobe. Writes `frames/*.png`, `animatic.mp4` and
 * `manifest.json` (frame hashes, durations, mp4 hash and probed duration).
 */
import { createHash } from 'node:crypto'
import { mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { dirname, isAbsolute, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repo = resolve(here, '..')
const args = process.argv.slice(2)
const flag = (name, fallback = null) => {
  const index = args.indexOf(`--${name}`)
  if (index < 0) return fallback
  const value = args[index + 1]
  return value && !value.startsWith('--') ? value : true
}
const specPath = resolve(repo, String(flag('spec', 'docs/launch/animatic/beats.json')))
const outDir = resolve(repo, String(flag('out', 'docs/launch/animatic')))
const buildVideo = !Boolean(flag('no-video', false))
const chromium = process.env.CHROMIUM || 'chromium'

const spec = JSON.parse(readFileSync(specPath, 'utf8'))
const tokens = JSON.parse(readFileSync(resolve(repo, spec.tokens), 'utf8'))
const c = tokens.modes.light
const W = spec.width || 1920
const H = spec.height || 1080
const fps = spec.fps || 30

const sha256 = (buf) => createHash('sha256').update(buf).digest('hex')
const fileSha = (path) => sha256(readFileSync(path))
const esc = (text) => String(text ?? '').replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]))

const framesDir = join(outDir, 'frames')
const tmpDir = join(process.env.TMPDIR || '/tmp', 'cp-animatic-html')
mkdirSync(framesDir, { recursive: true })
rmSync(tmpDir, { recursive: true, force: true })
mkdirSync(tmpDir, { recursive: true })

const displayUrl = `file://${resolve(repo, spec.type.display)}`
const uiUrl = `file://${resolve(repo, spec.type.ui)}`
const mainWoff = `@font-face { font-family:'CB Display'; src:url('${displayUrl}') format('woff2'); font-weight: 100 900; font-display: block; }
@font-face { font-family:'CB UI'; src:url('${uiUrl}') format('woff2'); font-weight: 100 900; font-display: block; }`

const shell = (inner, extra = '') => `<!doctype html>
<html><head><meta charset="utf-8"><title>animatic</title><style>
${mainWoff}
:root { --canvas:${c.canvas}; --canvas-edge:${c['canvas-edge']}; --card:${c['card-stock']}; --ink:${c.ink}; --ink-soft:${c['ink-soft']}; --rule:${c.rule}; --forest:${c.forest}; --on-forest:${c['on-forest']}; --terracotta:${c.terracotta}; --on-terracotta:${c['on-terracotta']}; --terracotta-quiet:${c['terracotta-quiet']}; --gold:${c.gold}; }
* { box-sizing: border-box; }
html,body { margin:0; width:${W}px; height:${H}px; overflow:hidden; background:var(--canvas); color:var(--ink);
  font-family:'CB UI', system-ui, sans-serif; -webkit-font-smoothing:antialiased; }
.vignette { position:absolute; inset:0; background:radial-gradient(ellipse at 50% 38%, rgba(0,0,0,0) 52%, ${c['canvas-edge']} 125%); opacity:.85; }
.frame { position:absolute; inset:0; padding:132px 160px 112px; display:flex; flex-direction:column; }
.kicker { font-size:22px; letter-spacing:.14em; text-transform:uppercase; color:var(--ink-soft); margin:0 0 26px; }
.caption { font-family:'CB Display', Georgia, serif; font-weight:600; line-height:1.06; margin:0; letter-spacing:-0.01em; }
.sub { font-size:30px; line-height:1.45; color:var(--ink-soft); margin:26px 0 0; max-width:30ch; }
.rule { width:74px; height:3px; background:var(--terracotta); margin:34px 0 0; }
.footer { position:absolute; right:160px; bottom:44px; font-size:17px; letter-spacing:.06em; color:var(--ink-soft); }
.mark { position:absolute; left:160px; bottom:44px; font-family:'CB Display', Georgia, serif; font-size:20px; color:var(--ink-soft); }
.plate-head { margin-top:34px; }
.plate-wrap { position:relative; background:var(--card); border:1px solid var(--rule); padding:16px; width:fit-content; }
.plate-wrap img { display:block; width:980px; height:auto; }
.chip { display:inline-block; background:var(--terracotta-quiet); color:var(--ink); border:1px solid var(--rule);
  font-size:15px; letter-spacing:.12em; padding:9px 14px; text-transform:uppercase; margin:0 0 10px; }
.strike-row { display:flex; align-items:center; gap:22px; font-size:34px; color:var(--ink-soft); margin:0 0 22px; }
.strike-row span.txt { position:relative; }
.strike-row span.txt::after { content:''; position:absolute; left:-6px; right:-6px; top:52%; height:2px; background:var(--terracotta); }
.strike-row .no { font-family:'CB Display', Georgia, serif; color:var(--terracotta); font-size:26px; width:44px; }
.end { justify-content:center; align-items:flex-start; }
.end .wordmark { font-family:'CB Display', Georgia, serif; font-weight:600; font-size:150px; line-height:1; margin:0; }
.end .sub { margin-top:28px; font-size:32px; }
.end .repo { margin-top:44px; font-family:'CB UI', system-ui, sans-serif; font-size:28px; color:var(--ink); border-top:1px solid var(--rule); padding-top:22px; }
${extra}
</style></head><body><div class="vignette"></div>${inner}</body></html>`

const footer = `<div class="footer">flat animatic · CP-033 · not the final take</div>`

function frameHtml(frame) {
  const kicker = frame.kicker ? `<p class="kicker">${esc(frame.kicker)}</p>` : ''
  const footerHtml = `<div class="mark">Coursebook</div>${footer}`
  if (frame.kind === 'word') {
    return shell(`<div class="frame">${kicker}<h1 class="caption" style="font-size:${(frame.caption || '').length > 34 ? 78 : 96}px; max-width:19ch;">${esc(frame.caption)}</h1>
      ${frame.sub ? `<p class="sub">${esc(frame.sub)}</p>` : ''}<div class="rule"></div></div>${footerHtml}`)
  }
  if (frame.kind === 'reveal') {
    return shell(`<div class="frame">${kicker}<h1 class="caption" style="font-size:128px;">${esc(frame.caption)}</h1>
      <p class="sub" style="max-width:34ch;">${esc(frame.sub)}</p>
      ${plateHtml(frame, 900)}</div>${footerHtml}`)
  }
  if (frame.kind === 'plate') {
    return shell(`<div class="frame">${kicker}<h1 class="caption" style="font-size:62px; max-width:26ch;">${esc(frame.caption)}</h1>
      ${frame.sub ? `<p class="sub" style="font-size:26px; margin-top:16px; max-width:52ch;">${esc(frame.sub)}</p>` : ''}
      ${plateHtml(frame, 980)}</div>${footerHtml}`)
  }
  if (frame.kind === 'struck') {
    const rows = (frame.strike || []).map((line) => `<div class="strike-row"><span class="no">✕</span><span class="txt">${esc(line)}</span></div>`).join('')
    return shell(`<div class="frame">${kicker}<h1 class="caption" style="font-size:66px; max-width:24ch;">${esc(frame.caption)}</h1>
      <div style="margin-top:44px;">${rows}</div>
      ${frame.sub ? `<p class="sub" style="font-size:24px; margin-top:8px; max-width:60ch;">${esc(frame.sub)}</p>` : ''}</div>${footerHtml}`)
  }
  if (frame.kind === 'end') {
    return shell(`<div class="frame end"><p class="kicker">${esc(frame.kicker)}</p><h1 class="wordmark">${esc(frame.caption)}</h1>
      <p class="sub">${esc(frame.sub)}</p><div class="repo">${esc(frame.repo)}</div></div>${footer}`)
  }
  throw new Error(`unknown frame kind: ${frame.kind}`)
}

function plateHtml(frame, width) {
  const platePath = resolve(repo, frame.plate)
  return `<div class="plate-head"><span class="chip">${esc(frame.chip || 'PLACEHOLDER')}</span></div>
  <div class="plate-wrap"><img src="file://${platePath}" style="width:${width}px" alt=""></div>`
}

const manifestFrames = []
let clock = 0
for (const frame of spec.frames) {
  const htmlPath = join(tmpDir, `${frame.id}.html`)
  const pngPath = join(framesDir, `${frame.id}.png`)
  writeFileSync(htmlPath, frameHtml(frame))
  const shot = spawnSync(chromium, [
    '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
    '--allow-file-access-from-files', `--window-size=${W},${H}`,
    `--screenshot=${pngPath}`, `file://${htmlPath}`
  ], { encoding: 'utf8' })
  if (shot.status !== 0) {
    throw new Error(`chromium failed on ${frame.id}: ${shot.stderr || shot.stdout}`)
  }
  const start = clock
  clock += frame.seconds
  manifestFrames.push({
    id: frame.id,
    kind: frame.kind,
    start_seconds: start,
    end_seconds: clock,
    start_beat: frame.start_beat,
    seconds: frame.seconds,
    png: `frames/${frame.id}.png`,
    png_sha256: fileSha(pngPath),
    caption: frame.caption,
    plate: frame.plate || null,
    plate_sha256_prefix: frame.plate_sha256_prefix || null,
    placeholder: Boolean(frame.plate)
  })
  console.log(`frame ${frame.id} ${start.toFixed(2)}–${clock.toFixed(2)}s`)
}

console.log(`total ${clock.toFixed(2)}s across ${manifestFrames.length} frames`)
if (clock > spec.ceiling_seconds) throw new Error(`over the ${spec.ceiling_seconds}s ceiling`)

const manifest = {
  tool: 'scripts/cp-animatic.mjs',
  spec: specPath.replace(`${repo}/`, ''),
  spec_sha256: fileSha(specPath),
  tokens: spec.tokens,
  tokens_sha256: fileSha(resolve(repo, spec.tokens)),
  claim: spec.claim,
  tempo_bpm: spec.tempo_bpm,
  seconds_per_beat: spec.seconds_per_beat,
  total_seconds: clock,
  ceiling_seconds: spec.ceiling_seconds,
  width: W,
  height: H,
  fps,
  frames: manifestFrames,
  notes: [
    'Every frame that shows a reference plate carries a visible PLACEHOLDER chip: no v3 screen exists on this branch.',
    'No frame contains product UI drawn by this script; captions are deck rows with {braces} intact for live values.',
    'The MP4 is silent. The final take needs a music bed and UI sound effects, both licensed before use.'
  ]
}

if (buildVideo) {
  // One looping input per frame, each capped at its beat duration, joined with the concat filter.
  // The concat *demuxer* over still PNGs overruns the last frame; this path is sample-accurate.
  const inputs = []
  const filters = []
  const labels = []
  manifestFrames.forEach((frame, index) => {
    inputs.push('-loop', '1', '-t', String(frame.seconds), '-i', join(framesDir, `${frame.id}.png`))
    filters.push(`[${index}:v]scale=${W}:${H},fps=${fps},setsar=1[v${index}]`)
    labels.push(`[v${index}]`)
  })
  filters.push(`${labels.join('')}concat=n=${manifestFrames.length}:v=1:a=0,format=yuv420p[outv]`)
  const mp4Path = join(outDir, 'animatic.mp4')
  const encode = spawnSync('ffmpeg', [
    '-y', '-hide_banner', '-loglevel', 'error',
    ...inputs,
    '-filter_complex', filters.join(';'),
    '-map', '[outv]',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-r', String(fps),
    '-movflags', '+faststart', mp4Path
  ], { encoding: 'utf8' })
  if (encode.status !== 0) throw new Error(`ffmpeg failed: ${encode.stderr}`)
  const probe = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration,size', '-of', 'default=nw=1', mp4Path], { encoding: 'utf8' })
  const probed = Object.fromEntries(probe.stdout.trim().split('\n').map((line) => line.split('=')))
  manifest.video = {
    file: 'animatic.mp4',
    sha256: fileSha(mp4Path),
    probed_duration_seconds: Number(probed.duration),
    probed_bytes: Number(probed.size),
    audio: 'none'
  }
  console.log(`animatic.mp4 ${probed.duration}s ${probed.size} bytes`)
}

writeFileSync(join(outDir, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`)
console.log(`manifest ${outDir.replace(`${repo}/`, '')}/manifest.json`)
