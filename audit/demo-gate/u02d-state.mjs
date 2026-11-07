// Full state dump of the import surface after the header "Import pack" click.
import { connect, writeJson, rel } from '../../scripts/cb015-lib.mjs'
const cdp = await connect()
const dump = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const routeText = root ? root.innerText : '(no route)'
  const allButtons = [...document.querySelectorAll('button')].map(b => ({
    label: (b.innerText||b.getAttribute('aria-label')||'').trim(), disabled: b.disabled,
    inRoute: root ? root.contains(b) : false
  })).filter(b => b.label)
  return {
    hash: location.hash,
    routeText: routeText.replace(/\\n{2,}/g,'\\n').slice(0, 3000),
    buttons: allButtons.slice(0, 60),
    dialogs: [...document.querySelectorAll('[role=dialog],[aria-modal=true]')].map(d => ({ role: d.getAttribute('role'), label: d.getAttribute('aria-label'), text: (d.innerText||'').slice(0,600) })),
    fileTreePresent: /Show gitignored files|Refresh tree|Collapse all folders/.test(document.body.innerText)
  }
})()`)
writeJson(rel('audit/demo-gate/u02d-state.json'), dump)
console.log(JSON.stringify(dump, null, 2))
cdp.close()
