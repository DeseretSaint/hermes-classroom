// CP-024 capture driver — the course home of a course whose recorded next step is plan review.
//
// Same real clicks as `drive-course-home.js`; only the row differs. The course is a shipped rig
// course whose `library_item.next_step.kind` is `review_plan`, so the aside renders the review
// plate with the backend's own label. Nothing here fabricates that step.
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const nav = [...document.querySelectorAll('button,a,[role=button],[role=link]')].find(
  (el) => (el.innerText || '').trim() === 'Courses'
)
if (!nav) throw new Error('course-home driver: no Courses destination in the tab strip')
nav.click()
await sleep(1500)
const row = [...document.querySelectorAll('button[data-cb-shelf-member-open]')].find((el) =>
  /^Open Order coffee and ask for the bill in Kyoto, politely/.test(el.getAttribute('aria-label') || '')
)
if (!row) throw new Error('course-home driver: no plan-review course is on the Courses list')
row.click()
await sleep(2000)
