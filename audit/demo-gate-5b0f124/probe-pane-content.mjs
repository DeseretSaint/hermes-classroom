import { connect } from '../../scripts/cb015-lib.mjs'
const cdp = await connect()
const out = await cdp.json(`(() => {
  const host = window.__HERMES_PLUGIN_SDK__.host
  const paneIds = [...document.querySelectorAll('[data-pane-id], [data-pane], [data-contribution-id]')].map(e => e.getAttribute('data-pane-id') || e.getAttribute('data-pane') || e.getAttribute('data-contribution-id')).filter(Boolean)
  const text = document.body.innerText || ''
  return {
    paneVisibility: (() => { try { return host.paneVisibility('coursebook:pane').get() } catch (e) { return 'ERR' } })(),
    paneIds,
    hasCurrentCheck: /CURRENT CHECK/.test(text),
    hasCourseWord: /Japanese affection and register/i.test(text),
    hasObjective: /Tell everyday affection/i.test(text),
    hasWaking: /Waking up/i.test(text),
    wakingIndex: text.indexOf('Waking up'),
    textAroundWaking: text.slice(Math.max(0, text.indexOf('Waking up') - 200), text.indexOf('Waking up') + 200),
    bodyTail: text.slice(-1200),
    textareas: [...document.querySelectorAll('textarea, [contenteditable=true]')].map(t => ({ tag: t.tagName, ph: t.placeholder || null, aria: t.getAttribute('aria-label'), disabled: t.disabled })),
    composerButtons: [...document.querySelectorAll('button')].map(b => (b.innerText || '').trim()).filter(Boolean).slice(-12)
  }
})()`)
console.log(JSON.stringify(out, null, 2).slice(0, 5000))
cdp.close()
