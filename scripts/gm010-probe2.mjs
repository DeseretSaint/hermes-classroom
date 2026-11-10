#!/usr/bin/env node
/** GM-010 probe step 2: open the Japanese course home and read the play layer. */
import { connect } from './cb015-lib.mjs'

const wait = (ms) => new Promise((done) => setTimeout(done, ms))
const cdp = await connect()
await cdp.send('Page.enable')
await cdp.send('Runtime.enable')

const clicked = await cdp.eval(`(() => {
  const card = [...document.querySelectorAll('[data-cb-home-card]')].find((n) => /Japanese at home/.test(n.innerText))
  if (!card) return false
  const button = card.querySelector('button, a') || card
  button.click()
  return true
})()`)
console.log('clicked', clicked)
await wait(3500)
const out = await cdp.eval(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const game = document.querySelector('[data-cb-game]')
  const journal = document.querySelector('[data-cb-game-journal]')
  return {
    hash: location.hash,
    courseHome: Boolean(document.querySelector('[data-cb-course-home]')),
    routeText: root ? root.innerText.replace(/\\s+/g, ' ').slice(0, 700) : null,
    game: game ? game.getAttribute('data-cb-game') : null,
    xp: document.querySelector('[data-cb-game-xp]')?.getAttribute('data-cb-game-xp') || null,
    level: document.querySelector('[data-cb-game-level]')?.getAttribute('data-cb-game-level') || null,
    journal: journal ? journal.getAttribute('data-cb-game-journal') : null,
    cards: [...document.querySelectorAll('[data-cb-game-card]')].map((n) => n.getAttribute('data-cb-game-card')),
    continueText: (document.querySelector('[data-cb-trail]')?.innerText || '').replace(/\\s+/g, ' ').slice(0, 200)
  }
})()`)
console.log(JSON.stringify(out, null, 2))
cdp.close()
