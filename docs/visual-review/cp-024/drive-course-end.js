// CP-024 capture driver — the course home of a course whose every section is recorded complete.
//
// Same real clicks as `drive-course-home.js`; only the row differs. The rig has two courses titled
// "…a Sample L0 classroom", so `capture.sh` bumps this fixture course's enrollment timestamp
// (bookkeeping only) and this driver requires the row's own "updated just now" label: the click
// lands on the intended course without guessing from a shared title. The completed state itself is
// a documented fixture (see capture.sh): the objectives' recorded state is set to independent
// evidence for the frame and restored afterwards. Nothing here writes anything.
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const waitFor = async (find, label, timeout = 12000) => {
  const deadline = Date.now() + timeout
  while (Date.now() < deadline) {
    const found = find()
    if (found) return found
    await sleep(200)
  }
  throw new Error(`course-end driver: ${label} never appeared`)
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
await sleep(600)
const row = await waitFor(
  () =>
    [...document.querySelectorAll('button[data-cb-shelf-member-open]')].find((el) => {
      const label = el.getAttribute('aria-label') || ''
      return /Sample L0 classroom/.test(label) && /updated just now/.test(label)
    }),
  'the completed-course row'
)
row.click()
await waitFor(() => document.querySelector('[data-cb-course-home-v3]'), 'the course home')
// The route's own section titles resolve with `course.outline`, one frame after the home mounts.
await waitFor(
  () => /Choose the register for a close friend in public/.test(
    (document.querySelector('[data-cb-course-home-v3]') || {}).innerText || ''
  ),
  'the completed fixture course route (a different course was opened)'
)
