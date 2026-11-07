import { connect } from '../../scripts/cb015-lib.mjs'
const cdp = await connect()
await cdp.eval(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
await cdp.send('Page.reload', { ignoreCache: false })
await cdp.wait(9000)
const out = await cdp.json(`(() => ({
  hasCoursebookWord: /Coursebook/i.test(document.body.innerText),
  coursebookButton: [...document.querySelectorAll('button, a')].some(e => (e.innerText||'').trim() === 'Coursebook'),
  decisions: localStorage.getItem('hermes.desktop.pluginDecisions.v2'),
  hash: location.hash
}))()`)
console.log(JSON.stringify(out, null, 2))
cdp.close()
