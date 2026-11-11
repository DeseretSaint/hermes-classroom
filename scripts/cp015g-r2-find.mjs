import { connect } from './cb015-lib.mjs'
const cdp = await connect()
const v = await cdp.json(`(() => {
  const want = ${JSON.stringify(process.env.WANT || 'Start a new course')}
  return [...document.querySelectorAll('*')].filter(e => (e.innerText||'').trim() === want).map(e => {
    const r = e.getBoundingClientRect()
    return { tag: e.tagName, role: e.getAttribute('role'), cb: [...e.attributes].filter(a=>a.name.startsWith('data-cb')).map(a=>a.name+'='+a.value), x: r.x+r.width/2, y: r.y+r.height/2, w: r.width, h: r.height, vis: r.width>0&&r.height>0 }
  })
})()`)
console.log(JSON.stringify(v,null,2))
cdp.close()
