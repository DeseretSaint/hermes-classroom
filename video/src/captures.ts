/**
 * Capture manifest — the only place a beat learns which pixels it shows.
 *
 * One slot per state required by VIDEO-PLAN.md §6. `file: null` means the beat
 * renders a labelled placeholder block instead of a capture, so the motion
 * system renders end to end before CP-033b's stills exist.
 *
 * Dropping a capture in is one line: set `file` to the file name under
 * `video/public/captures/`. Geometry (`routeWidth`, `crop`) already matches the
 * 2× capture spec in §6 and does not need editing for a like-for-like still.
 */

export type CropRect = {
  /** Left edge, logical px, in the captured route's coordinate space. */
  x: number;
  /** Top edge, logical px. */
  y: number;
  /** Width, logical px. */
  w: number;
  /** Height, logical px. */
  h: number;
};

export type CaptureSlot = {
  /** §6 state name, e.g. `classroom-line-light`. */
  state: string;
  /** File under public/captures/, or null for a placeholder. */
  file: string | null;
  /**
   * Logical CSS width of the route that was captured. A 2× capture of a
   * 1920-wide route is a 3840 px file; the DPR multiplies the pixels, never the
   * geometry, so this stays 1920 and the frame geometry is unchanged.
   */
  routeWidth: number;
  /** Region of the route that fills the 1920×1080 frame, logical px. 16:9. */
  crop: CropRect;
  /** Optional overlay geometry (beat 7's terracotta underline), logical px. */
  highlight?: CropRect;
};

const full: CropRect = {x: 0, y: 0, w: 1920, h: 1080};

export const captures = {
  'beat-04 home': {
    state: 'home-1049-light',
    file: null,
    routeWidth: 1920,
    // §3 beat 4: "full bleed, cropped to the shelf and headline".
    crop: {x: 0, y: 0, w: 1920, h: 1080},
  },
  'beat-05 create-topic': {
    state: 'create-topic-light',
    file: null,
    routeWidth: 1920,
    crop: {x: 0, y: 0, w: 1920, h: 1080},
  },
  'beat-05 plan-sections': {
    state: 'plan-sections-light',
    file: null,
    routeWidth: 1920,
    crop: {x: 0, y: 0, w: 1920, h: 1080},
  },
  'beat-06 classroom-line': {
    state: 'classroom-line-light',
    file: null,
    routeWidth: 1920,
    crop: {x: 0, y: 0, w: 1920, h: 1080},
  },
  'beat-06 classroom-check': {
    state: 'classroom-check-light',
    file: null,
    routeWidth: 1920,
    crop: {x: 0, y: 0, w: 1920, h: 1080},
  },
  'beat-06 classroom-feedback': {
    state: 'classroom-feedback-light',
    file: null,
    routeWidth: 1920,
    crop: {x: 0, y: 0, w: 1920, h: 1080},
  },
  'beat-07 tutor-cited': {
    state: 'tutor-cited-light',
    file: null,
    routeWidth: 1920,
    crop: {x: 0, y: 0, w: 1920, h: 1080},
    // §3 beat 7: selected line gets a 2 px terracotta underline. Set this rect
    // to the selected line's box (logical px) when the capture lands.
    highlight: undefined,
  },
  'beat-08 game-challenge': {
    state: 'game-challenge-light',
    file: null,
    routeWidth: 1920,
    crop: {x: 0, y: 0, w: 1920, h: 1080},
  },
  'beat-08 game-complete': {
    state: 'game-complete-light',
    file: null,
    routeWidth: 1920,
    crop: {x: 0, y: 0, w: 1920, h: 1080},
  },
  'beat-09 parent-observation': {
    state: 'parent-observation-light',
    file: null,
    routeWidth: 1920,
    crop: {x: 0, y: 0, w: 1920, h: 1080},
  },
  'beat-10 discover-grid': {
    state: 'discover-grid-light',
    file: null,
    routeWidth: 1920,
    crop: full,
  },
} as const satisfies Record<string, CaptureSlot>;

export type CaptureId = keyof typeof captures;

export const slot = (id: CaptureId): CaptureSlot => captures[id];

/** True once a real capture is wired in; false while the beat shows a placeholder. */
export const isDropped = (s: CaptureSlot): s is CaptureSlot & {file: string} =>
  typeof s.file === 'string' && s.file.length > 0;
