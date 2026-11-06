/**
 * CB-049 polish proof: every Coursebook surface in dark + light, plus narrow and 200% text.
 * Navigation is through the app's own controls; no fixture state.
 */
import { connect, setMode } from './cb015-lib.mjs'
import { mkdirSync, writeFileSync } from 'node:fs'

const outDir = process.env.CB_SHOTS || 'docs/cb049-shots'
mkdirSync(outDir, { recursive: true })
const cdp = await connect()
const shots = []
const audits = []

const dismissSetup = async () => {
  const present = await cdp.eval(`/Let's get you setup/.test(document.body.innerText || '')`)
  if (!present) return false
  await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('button, a')].find(x => /choose a provider later/i.test((x.innerText || '').trim()))
    if (b) b.click()
    return !!b
  })()`)
  await cdp.wait(1500)
  return true
}
const shoot = async (name) => {
  await dismissSetup()
  const path = await cdp.shot(`${outDir}/${name}.png`)
  shots.push(path)
  console.log('shot', name)
}
const tab = async (label) => {
  const ok = await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button[aria-pressed]')].find(x=>(x.innerText||'').trim()===${JSON.stringify(label)}); if(b){b.click();return true} return false })()`)
  await cdp.wait(1500)
  if (!ok) console.log('tab missing:', label)
  return ok
}
const clickText = async (text) => {
  const ok = await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button, [data-cb-route] a')].find(x=>(x.innerText||'').trim()===${JSON.stringify(text)}); if(b){b.click();return true} return false })()`)
  await cdp.wait(1800)
  if (!ok) console.log('control missing:', text)
  return ok
}
const openCourse = async (needle) => {
  await cdp.eval(`location.hash = '#/coursebook'`)
  await cdp.wait(1500)
  // destination nav first (Courses / Library / Parent Studio)
  await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>(x.innerText||'').trim()==='Courses'); if(b){b.click();return true} return false })()`)
  await cdp.wait(1400)
  const back = await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>(x.innerText||'').trim()==='All courses'); if(b){b.click();return true} return false })()`)
  if (back) await cdp.wait(1600)
  const opened = await cdp.eval(`(() => {
    const needle = ${JSON.stringify(needle)}
    const root = document.querySelector('[data-cb-route]')
    const titles = [...root.querySelectorAll('*')].filter(el => {
      const own = (el.innerText || '').trim()
      return own.includes(needle) && ![...el.children].some(c => (c.innerText || '').includes(needle))
    })
    const title = titles[titles.length - 1]
    if (!title) return 'no-title'
    let node = title
    for (let depth = 0; depth < 8 && node; depth += 1, node = node.parentElement) {
      const b = [...node.querySelectorAll('button')].find(x => (x.innerText || '').trim() === 'Open')
      if (b) { b.click(); return 'clicked' }
    }
    return 'no-open-for-title'
  })()`)
  if (opened !== 'clicked') throw new Error('open course ' + needle + ': ' + opened)
  await cdp.wait(2400)
}
const openSection = async (index) => {
  await tab('Textbook')
  const opened = await cdp.eval(`(() => {
    const bs = [...document.querySelectorAll('[data-cb-route] button')].filter(b => (b.innerText||'').trim() === 'Open section')
    if (!bs[${index}]) return 'missing(' + bs.length + ')'
    bs[${index}].click(); return 'clicked'
  })()`)
  if (opened !== 'clicked') throw new Error('open section ' + index + ': ' + opened)
  await cdp.wait(2600)
}

/** Structural audit: shadows, heavy borders, nested bordered boxes, markdown residue. */
const audit = async (label) => {
  const result = await cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    if (!root) return { label: ${JSON.stringify(label)}, missing: true }
    const all = [...root.querySelectorAll('*')]
    const shadows = []
    const heavy = []
    const bordered = []
    for (const el of all) {
      const cs = getComputedStyle(el)
      const w = ['Top','Right','Bottom','Left'].map(s => parseFloat(cs['border'+s+'Width'] || '0'))
      const box = el.getBoundingClientRect()
      if (cs.boxShadow && cs.boxShadow !== 'none' && !/rgba\\(0, 0, 0, 0\\) 0px 0px 0px 0px, rgba\\(0, 0, 0, 0\\) 0px 0px 0px 0px, rgba\\(0, 0, 0, 0\\) 0px 0px 0px 0px, rgba\\(0, 0, 0, 0\\) 0px 0px 0px 0px, rgba\\(0, 0, 0, 0\\) 0px 0px 0px 0px/.test(cs.boxShadow)) {
        shadows.push({ cls: (el.className||'').toString().slice(0, 90), shadow: cs.boxShadow.slice(0, 120) })
      }
      if (w.some(v => v > 1.4)) heavy.push({ cls: (el.className||'').toString().slice(0, 110), w })
      if (w.some(v => v > 0) && box.width > 60 && box.height > 24 && el.tagName !== 'BUTTON' && el.tagName !== 'INPUT' && el.tagName !== 'TEXTAREA' && !el.closest('span.inline-flex')) bordered.push(el)
    }
    const nested = []
    for (const el of bordered) {
      let node = el.parentElement
      for (let d = 0; d < 6 && node && node !== root; d += 1, node = node.parentElement) {
        if (bordered.includes(node)) { nested.push({ child: (el.className||'').toString().slice(0,90), parent: (node.className||'').toString().slice(0,90) }); break }
      }
    }
    const md = []
    for (const el of all) {
      if (el.children.length) continue
      const t = (el.textContent || '').trim()
      if (/\\*\\*[^*]{2,80}\\*\\*/.test(t) || /\\|\\s*---/.test(t) || /^(#|##)\\s/.test(t)) md.push({ tag: el.tagName, cls: (el.className||'').toString().slice(0,80), sample: t.slice(0, 80) })
    }
    return {
      label: ${JSON.stringify(label)},
      mode: document.documentElement.dataset.hermesMode,
      shadows: shadows.slice(0, 8),
      heavy: heavy.slice(0, 8),
      borderedCount: bordered.length,
      nested: nested.slice(0, 8),
      markdownResidue: md.slice(0, 8),
      textColor: getComputedStyle(root).color,
      bg: getComputedStyle(root).backgroundColor
    }
  })()`)
  audits.push(result)
  return result
}

await dismissSetup()

// ---- dark
await setMode(cdp, 'dark')
await openCourse('Japanese affection and register')
await shoot('030-overview-dark')
await audit('overview-dark')
await tab('Textbook')
await shoot('031-textbook-dark')
await audit('textbook-dark')
await openSection(0)
await shoot('032-section-dark')
console.log('section audit', JSON.stringify(await audit('section-dark')))
await tab('Notebook')
await shoot('033-notebook-dark')
console.log('notebook audit', JSON.stringify(await audit('notebook-dark')))
await tab('Quizzes')
await shoot('034-quizzes-dark')
await audit('quizzes-dark')
await clickText('All courses')
await shoot('035-courses-dark')
await audit('courses-dark')
await clickText('Library')
await shoot('036-library-dark')
await audit('library-dark')
await clickText('Parent Studio')
await shoot('037-studio-dark')
await audit('studio-dark')

// ---- light
await setMode(cdp, 'light')
await cdp.wait(500)
await openCourse('Japanese affection and register')
await shoot('040-overview-light')
await audit('overview-light')
await tab('Textbook')
await openSection(0)
await shoot('041-section-light')
console.log('section light audit', JSON.stringify(await audit('section-light')))
await tab('Notebook')
await shoot('042-notebook-light')
await tab('Quizzes')
await shoot('043-quizzes-light')
await clickText('All courses')
await shoot('044-courses-light')
await clickText('Library')
await shoot('045-library-light')
await clickText('Parent Studio')
await shoot('046-studio-light')
await audit('studio-light')

// ---- narrow + 200% text on the lesson body
await setMode(cdp, 'dark')
await openCourse('Japanese affection and register')
await openSection(0)
await cdp.setViewport(460, 900)
await cdp.wait(900)
await shoot('050-section-narrow-dark')
await cdp.clearViewport()
await cdp.eval(`document.documentElement.style.fontSize = '32px'`)
await cdp.wait(800)
await shoot('051-section-text200-dark')
await cdp.eval(`document.documentElement.style.fontSize = ''`)
await cdp.wait(600)

// ---- reduced motion smoke (host preference via emulation is not a plugin surface; capture state only)
await cdp.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
await cdp.wait(500)
await shoot('052-section-reduced-motion-dark')
await cdp.send('Emulation.setEmulatedMedia', { features: [] })

writeFileSync(`${outDir}/audit.json`, `${JSON.stringify({ capturedAt: new Date().toISOString(), shots, audits }, null, 2)}\n`)
console.log('wrote', `${outDir}/audit.json`, 'with', shots.length, 'shots')
cdp.close()
