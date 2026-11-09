"""Rewrite §5 of docs/H178-EVIDENCE.md from the measured frames (H-204)."""
import json

DOC = 'docs/H178-EVIDENCE.md'
M = 'audit/visual/h178-field-stop/measurements.json'

data = json.load(open(M))
frames = sorted(data['frames'], key=lambda f: (f['theme'], f['width'], f['text']))
lines = []
lines.append('## 5. Field Stop frame matrix (H-204) — captured\n')
lines.append(
    'Rig: `~/.hermes/coursebook-test-h178-a` (after plugin), CDP **9385**, window restarted so the\n'
    'loaded bytes are the installed bytes. Installed `desktop-plugins/coursebook/plugin.js` sha256\n'
    f'`{data["plugin_sha256"]}` — byte-identical to `desktop/plugin.js` at base `2d7282a` (H-196 + H-197).\n'
    'State: the existing open check on section 2 (STOP 2 OF 4, step 2 of 2, written check `Check v4`,\n'
    'binding active), pending integrity chip **cold** — no answer was submitted for these frames.\n'
    'No course was re-authored and no backend state was advanced.\n'
)
lines.append(
    'Theme was set through the plugin\'s own Appearance control (Settings sheet, real click), never by\n'
    'forcing a class. Every row is read from the painted DOM of the live window; the PNG is the same\n'
    'window\'s `Page.captureScreenshot`.\n'
)
lines.append('| frame | viewport (CSS px) | root font | theme | state | horizontal overflow | PNG px | sha256 |')
lines.append('| --- | --- | --- | --- | --- | --- | --- | --- |')
for f in frames:
    s = f['state']
    state = f'header `{s["bar"].split(" Game")[0]}`; chip `{s["chip"]}`' + (
        ' (pending)' if s['chipPending'] == 'true' else '')
    lines.append(
        '| `{name}` | {w}×{h} | {root} | {scope} | {state} | {ovf} | {pw}×{ph} | `{sha}` |'.format(
            name=f['name'], w=f['viewport']['innerWidth'], h=f['viewport']['innerHeight'],
            root=f['rootFontSize'], scope=f['scope'], state=state,
            ovf=s['horizontalOverflow'], pw=f['pixels']['width'], ph=f['pixels']['height'],
            sha=f['sha256']))
lines.append('')
lines.append(
    'The PNG is narrower than the CSS viewport because this desktop window carries the display scale\n'
    '(`devicePixelRatio` 0.896): 1049 CSS px paints onto 941 device px. The layout width is the\n'
    'measured `innerWidth`; the file\'s pixel width is recorded separately so neither number is implied.\n'
    'The 200% rows are a 32px root font on a 1049 CSS px viewport, not a browser zoom.\n'
)
lines.append(
    'Not painted, and stated rather than synthesized:\n\n'
    '- **Before rig** (`~/.hermes/coursebook-test-h178-b`, CDP 9384): not running — `curl` to 9384\n'
    '  returns connection refused, and its installed plugin is the H-177 sha `6aeca221`. No before\n'
    '  frames are part of this card, so no rig was started for it.\n'
    '- **Driven sequence** (wrong answer → hint → hinted retry → pass → completion → trail) belongs to\n'
    '  H-205. These frames show one state only: the untouched cold check.\n'
    '- **M4 re-pin** deliberately not run (card forbids it); `tests.test_m4_visual_audit` stays red\n'
    '  until that separate step.\n'
)
lines.append('Measurements: `audit/visual/h178-field-stop/measurements.json`; capture: `scripts/h202-capture.mjs`.')
text = '\n'.join(lines) + '\n'

doc = open(DOC, encoding='utf-8').read()
head, sep, _ = doc.partition('## 5. Remaining work')
assert sep, 'section 5 heading not found'
if not head.endswith('\n\n'):
    head = head.rstrip('\n') + '\n\n'
open(DOC, 'w', encoding='utf-8').write(head + text)
print('wrote', DOC, 'rows', len(frames))
