// CP-015g: capture the create screen after the plan job has failed, and the Courses list.
import { connect } from './cb015-lib.mjs'

const out = process.env.CP015G_OUT || 'docs/concept-parity/demo/cp015g'
const cdp = await connect()
await cdp.setViewport(1344, 768)
await cdp.wait(500)
const now = await cdp.json(`(() => ({
  hash: location.hash,
  text: (document.querySelector('[data-cb-route]') || document.body).innerText.slice(0, 1200)
}))()`)
await cdp.shot(`${out}/06-after-job-failed.png`)
console.log('CREATE SCREEN', JSON.stringify(now, null, 2))
// open Courses
await cdp.eval(`(() => {
  const nav = [...document.querySelectorAll('button, a')].find((e) => (e.innerText || '').trim() === 'Courses')
  if (nav) nav.click()
  return Boolean(nav)
})()`)
await cdp.wait(2500)
const courses = await cdp.json(`(() => ({
  hash: location.hash,
  text: (document.querySelector('[data-cb-route]') || document.body).innerText.slice(0, 1500)
}))()`)
await cdp.shot(`${out}/07-courses.png`)
console.log('COURSES', JSON.stringify(courses, null, 2))
cdp.close()
