// CP-024 capture driver — the course home of the L0 demonstration course.
//
// `scripts/cp-capture.mjs` cannot re-enter a deep screen after its hard reload: a course home is
// shell state rather than a URL, so the reload lands on Home. This driver does what a learner
// does — it leaves any open course, clicks the Courses destination and then the course's own row —
// and invents no state. The capture tool then waits for `[data-cb-course-home-v3]` before it
// measures anything. (Leaving through the course's own back control returns to the Courses list,
// not to Home, so the frame never re-renders a destination that is not under review.)
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
      /an L0 demonstration classroom/i.test(el.getAttribute('aria-label') || '')
    ),
  'the L0 demonstration course row'
)
row.click()
await waitFor(() => document.querySelector('[data-cb-course-home-v3]'), 'the course home')
