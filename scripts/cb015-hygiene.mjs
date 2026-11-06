#!/usr/bin/env node
/**
 * CB-015 source-level visual hygiene audit for `desktop/plugin.js`.
 *
 * The DESIGN.md contract is enforceable at the source level for the things a screenshot cannot
 * prove deterministically: raw colours, ad-hoc shadows/gradients, arbitrary type sizes, primitive
 * chrome overrides, hand-rolled buttons, native `title=` on buttons, decorative emoji, the literal
 * "Loading…", and page-gutter semantics (UX_SPEC §14 wants `PAGE_INSET_X`, not a fixed `px-4`).
 *
 * This is a *source* audit, not a rendering proof: it says "no call site re-specifies chrome".
 * Live checks (computed colours, focus, overflow, reduced motion) live in cb015-live.mjs.
 *
 *   node scripts/cb015-hygiene.mjs            # table + JSON summary, exit 1 on violations
 *   node scripts/cb015-hygiene.mjs --json     # machine output only
 */
import { readFileSync } from 'node:fs'

const FILE = new URL('../desktop/plugin.js', import.meta.url)
const source = readFileSync(FILE, 'utf8')
const lines = source.split('\n')

/** A rule returns [{line, text}] violations. */
const PRIMITIVES = [
  'Button',
  'Badge',
  'SearchField',
  'SegmentedControl',
  'ListRow',
  'ToggleRow',
  'Select',
  'Tabs',
  'Tab',
  'Loader',
  'ErrorState',
  'EmptyState',
  'ConfirmDialog',
  'Tip',
  'PanelHeader',
  'PanelList',
  'PanelListRow',
  'PanelSectionLabel',
  'PanelEmpty',
  'SandboxedFrame',
  'MessageTextContent',
  'Codicon'
]

const CHROME_OVERRIDE =
  /\b(px-|py-|pt-|pb-|pl-|pr-|p-\d|h-\d|size-\d|rounded|shadow|font-(?:medium|semibold|bold)|text-(?:xs|sm|base|lg|xl|\d|\[|length:))/

const rules = [
  {
    id: 'raw-color',
    why: 'tokens, not literals (DESIGN §Stroke & color tokens)',
    run: () => scan((text) => /#[0-9a-fA-F]{3,8}\b(?![\w-])|rgba?\(|hsla?\(/.test(text))
  },
  {
    id: 'ad-hoc-shadow',
    why: 'elevation is the shared shadow token (DESIGN §Surfaces)',
    run: () => scan((text) => /\bshadow-|boxShadow/.test(text))
  },
  {
    id: 'gradient',
    why: 'no custom gradients (UX_SPEC §14)',
    run: () => scan((text) => /gradient/i.test(text))
  },
  {
    id: 'transition-all',
    why: 'name the property, ~100ms only (DESIGN §Motion)',
    run: () => scan((text) => /\btransition-(all|\[)|transition: *all/.test(text))
  },
  {
    id: 'arbitrary-type-size',
    why: 'type scale, not px literals (DESIGN §Buttons / UX_SPEC §14)',
    run: () => scan((text) => /text-\[(?:\d+px|0?\.\d+rem|length:)/.test(text), {
      allow: /var\(--conversation-text-font-size\)/
    })
  },
  {
    id: 'primitive-chrome-override',
    why: 'style lives in the primitive; pass variant/size (DESIGN §Buttons)',
    run: () => {
      const out = []
      // Brace-match each `sdk.X, { … }` prop object instead of a lazy regex: a lazy scan runs
      // past a one-line `jsx(sdk.Badge, { … })` and reports the *next* block's className.
      const head = new RegExp(`sdk\\.(${PRIMITIVES.join('|')})\\s*,\\s*\\{`, 'g')
      for (const match of source.matchAll(head)) {
        const open = source.indexOf('{', match.index + match[0].length - 1)
        const body = sliceObject(open)
        if (!body) continue
        const className = /className:\s*'([^']*)'/.exec(body)
        if (!className) continue
        const offending = className[1]
          .split(/\s+/)
          .filter((token) => CHROME_OVERRIDE.test(token))
          .filter((token) => !/^self-|^m[tblrxy]?-|^min-w-|^max-w-|^w-/.test(token))
          .filter((token) => !/^text-\(--/.test(token))
        if (offending.length) {
          out.push({ line: lineOf(match.index), text: `sdk.${match[1]} className "${offending.join(' ')}"` })
        }
      }
      return out
    }
  },
  {
    id: 'hand-rolled-button',
    why: 'one Button component — a bordered padded anchor is a second button (DESIGN §Buttons)',
    run: () => {
      const out = []
      const pattern = /jsx(?:s)?\('a',\s*\{([\s\S]*?)\n\s*\}\)/g
      for (const match of source.matchAll(pattern)) {
        const body = match[1]
        const className = /className:\s*'([^']*)'/.exec(body)
        if (!className) continue
        if (/\bborder\b/.test(className[1]) && /\b(px|py)-\d/.test(className[1])) {
          out.push({ line: lineOf(match.index), text: `anchor styled as a button: "${className[1]}"` })
        }
      }
      return out
    }
  },
  {
    id: 'native-title',
    why: 'never native title= on a button (DESIGN §Buttons)',
    run: () => scan((text) => /\btitle=/.test(text))
  },
  {
    id: 'decorative-emoji',
    why: 'no decorative emoji (UX_SPEC §14)',
    run: () => scan((text) => /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(text))
  },
  {
    id: 'loading-literal',
    why: 'never the literal "Loading…" (DESIGN §Feedback)',
    run: () => scan((text) => /Loading(?:…|\.\.\.)/.test(text))
  },
  {
    id: 'page-gutter',
    why: 'page bodies use PAGE_INSET_X semantics once, on the route column (DESIGN §Layout)',
    run: () => {
      const out = []
      const root = /'data-cb-route': ROUTE_PATH/.exec(source)
      if (!root) return [{ line: 0, text: 'route root not found' }]
      const before = source.slice(Math.max(0, root.index - 400), root.index)
      if (!/px-\[clamp\(1\.25rem,4vw,4rem\)\]/.test(before)) {
        out.push({ line: lineOf(root.index), text: 'route column does not carry the PAGE_INSET_X gutter' })
      }
      const body = /function PageBody\([\s\S]*?\n\}/.exec(source)
      const cls = body && /className:\s*'([^']*)'/.exec(body[0])
      if (!cls) out.push({ line: lineOf(body ? body.index : 0), text: 'PageBody not found' })
      else if (/\bpx-/.test(cls[1])) {
        out.push({ line: lineOf(body.index), text: `PageBody adds a second gutter: "${cls[1]}"` })
      }
      return out
    }
  },
  {
    id: 'boxed-block',
    why: 'flat, not boxed — group with whitespace or one hairline, never a nested rounded box (DESIGN §Principles)',
    run: () => {
      const out = []
      const pattern = /className:\s*'([^']*)'/g
      for (const match of source.matchAll(pattern)) {
        const value = match[1]
        if (!/\brounded\b/.test(value)) continue
        if (!/\bborder\b/.test(value)) continue
        if (!/\bp[xytrbl]?-\d/.test(value)) continue
        out.push({ line: lineOf(match.index), text: `boxed block: "${value}"` })
      }
      return out
    }
  },
  {
    id: 'second-markdown',
    why: 'one renderer — transcript-style text uses MessageTextContent (UX_SPEC §14)',
    run: () => scan((text) => /\bfrom ['"](?:marked|markdown-it|remark|react-markdown)|ReactMarkdown|jsx\(['"]ReactMarkdown/.test(text))
  }
]

function lineOf(index) {
  return source.slice(0, index).split('\n').length
}

/** Return the source between `{` at `open` and its matching `}`, skipping string literals. */
function sliceObject(open) {
  let depth = 0
  let quote = null
  for (let i = open; i < source.length; i += 1) {
    const ch = source[i]
    if (quote) {
      if (ch === '\\') i += 1
      else if (ch === quote) quote = null
      continue
    }
    if (ch === "'" || ch === '"' || ch === '`') quote = ch
    else if (ch === '{') depth += 1
    else if (ch === '}') {
      depth -= 1
      if (depth === 0) return source.slice(open + 1, i)
    }
  }
  return null
}

function scan(test, { allow } = {}) {
  const out = []
  lines.forEach((text, index) => {
    if (allow && allow.test(text)) return
    if (test(text)) out.push({ line: index + 1, text: text.trim() })
  })
  return out
}

const findings = []
for (const rule of rules) {
  for (const hit of rule.run()) {
    findings.push({ rule: rule.id, why: rule.why, line: hit.line, text: hit.text })
  }
}

const byRule = findings.reduce((acc, item) => {
  acc[item.rule] = (acc[item.rule] || 0) + 1
  return acc
}, {})

const summary = {
  file: 'desktop/plugin.js',
  lines: lines.length,
  rules: rules.length,
  findings: findings.length,
  byRule
}

if (process.argv.includes('--json')) {
  console.log(JSON.stringify({ summary, findings }, null, 2))
} else {
  console.log(`CB-015 hygiene — ${summary.file} (${summary.lines} lines), ${rules.length} rules`)
  for (const [id, count] of Object.entries(byRule)) console.log(`  ${id.padEnd(28)} ${count}`)
  console.log(`  ${'TOTAL'.padEnd(28)} ${findings.length}`)
  for (const item of findings) console.log(`\n  ${item.rule} ${item.line ? `L${item.line}` : ''}\n    ${item.text.slice(0, 160)}`)
}

process.exit(findings.length === 0 ? 0 : 1)
