/**
 * F-01 light-theme contrast measurement over the seven audited Coursebook states.
 *
 * Uses the shared Sentinel harness (`attach`/`measure`/`setMode`) and the same state induction as
 * `scripts/audit-ux-run.mjs`, so the numbers are directly comparable with audit/ux/results.json.
 *
 *   CB015_CDP_PORT=9361 node scripts/f01-contrast.mjs out.json label
 *   CB015_CDP_PORT=9361 node scripts/f01-contrast.mjs out.json token-66 --token=66
 *
 * `--token=<pct>` is a MEASUREMENT-ONLY host-token simulation: it overrides the host's
 * `--ui-text-tertiary` alpha in the renderer for the duration of the run and removes it after.
 * It exists to prove what the host token owner's fix would buy; the plugin never ships a colour.
 */
import { writeFileSync, readFileSync, existsSync } from 'node:fs'
import { attach, measure, setMode, clearRootText } from './audit-ux-lib.mjs'
import { SCENARIOS, setFault, wait, routeText, has } from './f01-states.mjs'

const OUT = process.argv[2] || 'audit/ux/f01-light.json'
const LABEL = process.argv[3] || 'run'
const TOKEN = (process.argv.find((a) => a.startsWith('--token=')) || '').split('=')[1]
const MODE = (process.argv.find((a) => a.startsWith('--mode=')) || '').split('=')[1] || 'light'
const only = process.argv.slice(4).filter((a) => !a.startsWith('--'))
const HOST_TOKEN = '--ui-text-tertiary'

async function simulateHostToken(cdp, pct) {
  await cdp.eval(`document.documentElement.style.setProperty(${JSON.stringify(HOST_TOKEN)}, 'color-mix(in srgb, var(--ui-base) ${pct}%, transparent)')`)
  await wait(cdp, 300)
  return cdp.eval(`getComputedStyle(document.documentElement).getPropertyValue(${JSON.stringify(HOST_TOKEN)}).trim()`)
}

async function restoreHostToken(cdp) {
  await cdp.eval(`document.documentElement.style.removeProperty(${JSON.stringify(HOST_TOKEN)})`)
}

const results = existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : {}
results.label = LABEL
if (TOKEN) results.hostTokenSimulation = `${TOKEN}%`
results.states = results.states || {}

const cdp = await attach()

let totalFailures = 0
for (const scenario of SCENARIOS) {
  if (only.length && !only.includes(scenario.id)) continue
  console.log(`\n=== ${scenario.id}`)
  setFault(scenario.fault || {})
  await scenario.setup(cdp)
  await wait(cdp, 1200)
  if (scenario.expect && !(await has(cdp, scenario.expect))) {
    console.log('  WARN expected copy absent:', scenario.expect)
    console.log('  saw:', (await routeText(cdp)).slice(0, 200).replace(/\n+/g, ' | '))
  }
  await clearRootText(cdp)
  await setMode(cdp, MODE)
  await wait(cdp, 700)
  // The app rewrites the html inline theme block on every mode change, so the simulation has to be
  // applied after the switch — otherwise it is clobbered and silently measures the old token.
  if (TOKEN) {
    const applied = await simulateHostToken(cdp, TOKEN)
    const probe = await cdp.eval(`getComputedStyle(document.querySelector('[data-cb-route]')).getPropertyValue(${JSON.stringify(HOST_TOKEN)}).trim()`)
    console.log(`  host token now: ${probe} (html: ${applied})`)
    results.hostTokenApplied = probe
  }
  const m = await measure(cdp)
  const total = m.contrastTotal ?? m.contrast.length
  totalFailures += total
  console.log(`  light: contrast=${total} nodes (list=${m.contrast.length}) bySize=${JSON.stringify(m.contrastBySize)} mode=${m.mode}`)
  if (m.contrast.length) console.log('  first:', JSON.stringify(m.contrast.slice(0, 5)))
  results.states[scenario.id] = {
    mode: m.mode,
    contrastTotal: total,
    contrastListed: m.contrast.length,
    contrastBySize: m.contrastBySize,
    contrast: m.contrast,
    contrastAll: m.contrastAll || m.contrast,
    textLength: m.textLength,
    snippet: (m.routeText || '').slice(0, 200),
    at: new Date().toISOString()
  }
  writeFileSync(OUT, `${JSON.stringify(results, null, 2)}\n`)
}
results.totalFailures = totalFailures
setFault({})
await setMode(cdp, 'dark')
if (TOKEN) await restoreHostToken(cdp)
writeFileSync(OUT, `${JSON.stringify(results, null, 2)}\n`)
console.log(`\ntotal failing nodes: ${totalFailures}`)
console.log('wrote', OUT)
process.exit(0)
