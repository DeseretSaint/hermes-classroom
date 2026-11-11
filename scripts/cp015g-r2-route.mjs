import { connect } from './cb015-lib.mjs'
const cdp = await connect()
const v = await cdp.json(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const main = document.querySelector('[data-cb-main]')
  return { routeHTML: route ? route.outerHTML.slice(0, 800) : null,
    mainText: main ? main.innerText.slice(0,500) : null,
    bodyTail: document.body.innerText.slice(-800) }
})()`)
console.log(JSON.stringify(v,null,2))
cdp.close()
