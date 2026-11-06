#!/usr/bin/env node
/** List the isolated window's CDP targets (page, iframe, webview) with their URLs. */
const PORT = process.env.CB009_CDP_PORT || '9337'
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
for (const t of targets) {
  console.log(`${t.type}\t${t.title}\t${t.url}`)
}
