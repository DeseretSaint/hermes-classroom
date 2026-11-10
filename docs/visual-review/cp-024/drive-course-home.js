// CP-024 capture driver — the course home of the L0 demonstration course.
//
// `scripts/cp-capture.mjs` hard-reloads before probing, and a course home is shell state rather
// than a URL, so the reload lands on Home. This driver does what a learner does: it clicks the
// Courses destination and then the course's own row. It invents no state and sets no attribute;
// the capture tool then waits for `[data-cb-course-home-v3]` before it measures anything.
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const nav = [...document.querySelectorAll('button,a,[role=button],[role=link]')].find(
  (el) => (el.innerText || '').trim() === 'Courses'
)
if (!nav) throw new Error('course-home driver: no Courses destination in the tab strip')
nav.click()
await sleep(1500)
const row = [...document.querySelectorAll('button[data-cb-shelf-member-open]')].find((el) =>
  /an L0 demonstration classroom/i.test(el.getAttribute('aria-label') || '')
)
if (!row) throw new Error('course-home driver: the L0 demonstration course is not on the Courses list')
row.click()
await sleep(2000)
