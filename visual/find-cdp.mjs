#!/usr/bin/env node
// Print the CDP port of every local Electron instance that is showing the Coursebook route.
// Usage: node find-cdp.mjs        (prints one port per line, newest process first)
import { chromium } from 'playwright'
import { execSync } from 'node:child_process'

function candidatePorts() {
  const ports = []
  try {
    const out = execSync("ss -ltnp 2>/dev/null | grep electron", { encoding: 'utf8' })
    for (const line of out.split('\n')) {
      const m = line.match(/127\.0\.0\.1:(\d+)/)
      if (m) ports.push(Number(m[1]))
    }
  } catch { /* no ss */ }
  return [...new Set(ports)].sort((a, b) => b - a)
}

const found = []
for (const port of candidatePorts()) {
  try {
    const browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`, { timeout: 4000 })
    for (const ctx of browser.contexts()) {
      for (const page of ctx.pages()) {
        const has = await page.evaluate(() => Boolean(document.querySelector('[data-cb-route]'))).catch(() => false)
        if (has) { found.push(port); break }
      }
      if (found.includes(port)) break
    }
    await browser.close().catch(() => {})
  } catch { /* not a CDP port */ }
}

if (!found.length) {
  console.error('no Electron instance with a Coursebook route found; open the plugin first')
  process.exit(1)
}
for (const port of found) console.log(port)
