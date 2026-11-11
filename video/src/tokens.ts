/**
 * Design tokens for the Coursebook launch film.
 *
 * Source of truth: docs/launch/VIDEO-PLAN.md §5 (palette + type) and §7 (motion).
 * Every hex and size below is copied from that section. Nothing else in `video/`
 * may declare a colour or a type size — import from here instead.
 */

/** §5 palette, from the v3 contract. */
export const palette = {
  /** forest ground */
  ground: '#0d281b',
  /** canvas */
  canvas: '#f5e3c8',
  /** card stock */
  cardStock: '#f4ecd9',
  /** ink */
  ink: '#1a1713',
  /** terracotta */
  terracotta: '#b4532f',
  /** gold */
  gold: '#a1741f',
  /** rule */
  rule: '#cdb894',
} as const;

export type PaletteName = keyof typeof palette;

/** §7: 1920×1080, 30 fps, 2250 frames for the hero cut; 900 for the cutdown. */
export const frame = {
  width: 1920,
  height: 1080,
  fps: 30,
  hero75: 2250,
  hero30: 900,
} as const;

/** §5 safe area: 120 px margins; nothing essential below y = 972 (X player chrome). */
export const safe = {
  margin: 120,
  bottomLimit: 972,
} as const;

/**
 * §5 type scale. Display 96–132, lower third 44, caption 34, end-card URL 30.
 *
 * NOTE ON QUOTING. React writes `fontFamily` into the CSSOM as-is and does not
 * add quotes. `font-family: Source Sans 3` is an *invalid* declaration — the
 * family list parses as three names and `3` is not an identifier — so Chrome
 * drops it and silently falls back to Times. A single-word family (Fraunces)
 * survives unquoted, which is exactly how half this film rendered in the wrong
 * typeface the first time. Family names that contain a digit must be quoted,
 * hence the inner quotes below.
 */
export const families = {
  display: 'Fraunces',
  ui: "'Source Sans 3'",
  kana: "'Noto Serif JP'", // reserved for kana in a real capture; never drawn here
} as const;

export const type = {
  display: {
    fontFamily: families.display,
    fontWeight: 600,
    minSize: 96,
    maxSize: 132,
    letterSpacing: '-0.015em', // tracking −1.5 %
    lineHeight: 1.05,
  },
  lowerThird: {
    fontFamily: families.ui,
    fontWeight: 600,
    size: 44,
    lineHeight: 1.25,
  },
  caption: {
    fontFamily: families.ui,
    fontWeight: 400,
    size: 34,
    lineHeight: 1.3,
  },
  endUrl: {
    fontFamily: families.ui,
    fontWeight: 400,
    size: 30,
    lineHeight: 1.4,
  },
  /** Internal label type for placeholder slots. Not a design size, it never ships. */
  placeholder: {
    fontFamily: families.ui,
    fontWeight: 600,
    size: 34,
    lineHeight: 1.35,
  },
} as const;

/**
 * §7 motion language: transform/opacity only, `cubic-bezier(.2,.8,.2,1)`,
 * durations 120 / 240 / 300 / 600 ms at 30 fps.
 */
export const motion = {
  /** Control points of cubic-bezier(.2,.8,.2,1). */
  cubicBezier: [0.2, 0.8, 0.2, 1] as const,
  ms: { d120: 4, d240: 8, d300: 9, d600: 18 },
  /** Push-in is scale-only and bounded at 3–6 % (§3 rules, §7). */
  push: { minDelta: 0.03, maxDelta: 0.06, defaultDelta: 0.04 },
  /** Beat 2 card settle distance. */
  settlePx: 6,
  /** Beat 1 type rise. */
  risePx: 8,
  /** Beat 9 lateral pan. */
  panPx: 40,
} as const;

/** End card fade: 6 frames (§3 rules; QC §9 item 4 allows exactly this run). */
export const fadeFrames = 6;
