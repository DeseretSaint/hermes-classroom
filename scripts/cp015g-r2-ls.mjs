import { connect } from './cb015-lib.mjs'
const cdp = await connect()
const v = await cdp.json(`(() => {
  const ls = {}; for (let i=0;i<localStorage.length;i++){const k=localStorage.key(i); if(/plugin|Decision|coursebook|hermes\./i.test(k)) ls[k]=localStorage.getItem(k).slice(0,200)}
  return { keys: Object.keys(localStorage).filter(k=>/plugin|decision|coursebook/i.test(k)), values: ls }
})()`)
console.log(JSON.stringify(v,null,2))
cdp.close()
