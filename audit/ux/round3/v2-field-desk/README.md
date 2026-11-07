# Atlas Lamp on the Field Desk (H-82 evidence)

Rendered from the shipped `desktop/plugin.js` through real React (`renderToStaticMarkup`) and
captured with headless Chromium. Each plate is the Field Desk at the audit width, both modes.

| Plate | Width | Mode |
|---|---|---|
| `field-desk-light-1049.png` | 1049 | light |
| `field-desk-light-900.png` | 900 | light |
| `field-desk-light-460.png` | 460 | light |
| `field-desk-dark-1049.png` | 1049 | dark |
| `field-desk-dark-900.png` | 900 | dark |
| `field-desk-dark-460.png` | 460 | dark |

Reproduce:

```
cd audit/ux/round3/v2-field-desk
node render.mjs
chromium --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
  --window-size=460,1700 --screenshot=field-desk-light-460.png field-desk-light-460.html
```

The rendered document carries an `#overflow-report` element with `scrollWidth`, `clientWidth` and
`overflowX` for the route node; `overflowX` is 0 at every captured width.

Honest limitation: these are not live-CDP frames of the installed desktop app. The card forbids
installing into the profile or restarting the gateway, and the running window still holds the
previous plugin build, so a live frame would show the old surface, not this one. The plates prove
the shipped module's own markup and layout; they do not prove the host has loaded it.
