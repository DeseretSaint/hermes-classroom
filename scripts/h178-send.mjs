#!/usr/bin/env node
/** H-178 scratch: send one chat turn in the isolated window (binds the armed lesson run). */
import { connect } from './h149-cdp.mjs'

const port = process.env.CB009_CDP_PORT || '9385'
const text = process.argv[2] || 'Hello, I am starting this lesson stop.'
const { send, evaluate, wait, clickSelector } = await connect(port)
const clicked = await clickSelector('[contenteditable="true"]')
console.log('clicked', clicked)
await send('Input.insertText', { text })
await wait(500)
await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 })
await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter' })
await wait(Number(process.env.WAIT_MS || 20000))
const body = await evaluate("JSON.stringify({body:(document.body.innerText||'').replace(/\\s+/g,' ').slice(-900),hash:location.hash})")
console.log(body)
