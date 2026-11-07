import { connect } from '../../scripts/cb015-lib.mjs'
const cdp = await connect()
const out = await cdp.json(`(() => ({
  keys: Object.keys(localStorage).filter(k => /plugin|desktop/i.test(k)),
  decisions: localStorage.getItem('hermes.desktop.pluginDecisions.v2'),
  disabled: localStorage.getItem('hermes.desktop.disabledPlugins.v1'),
  index: localStorage.getItem('hermes.desktop.pluginIndex.v1'),
  allPluginKeys: Object.keys(localStorage).filter(k => /coursebook/i.test(k)),
  coursebookLoadError: localStorage.getItem('hermes.desktop.pluginLoadError.coursebook')
}))()`)
console.log(JSON.stringify(out, null, 2))
cdp.close()
