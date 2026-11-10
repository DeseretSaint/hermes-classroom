// CP-024 capture driver — the course home of a course whose recorded next step is plan review.
//
// Same real clicks as `drive-course-home.js`; only the row differs. The course is a shipped rig
// course whose `library_item.next_step.kind` is `review_plan`, so the aside renders the review
// plate with the backend's own label. Nothing here fabricates that step.
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const waitFor = async (find, label, timeout = 12000) => {
  const deadline = Date.now() + timeout
  while (Date.now() < deadline) {
    const found = find()
    if (found) return found
    await sleep(200)
  }
  throw new Error(`course-home driver: ${label} never appeared`)
}
const byText = (text) =>
  [...document.querySelectorAll('button,a,[role=button],[role=link]')].find(
    (el) => (el.innerText || '').trim() === text
  )
const back = document.querySelector('[data-cb-course-back]')
if (back) {
  back.click()
  await sleep(1200)
}
const nav = byText('Courses')
if (nav) nav.click()
const row = await waitFor(
  () =>
    [...document.querySelectorAll('button[data-cb-shelf-member-open]')].find((el) =>
      /^Open Order coffee and ask for the bill in Kyoto, politely/.test(
        el.getAttribute('aria-label') || ''
      )
    ),
  'the plan-review course row'
)
row.click()
await waitFor(() => document.querySelector('[data-cb-course-home-v3]'), 'the course home')
