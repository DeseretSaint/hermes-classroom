/**
 * Beat schedule — one table per cut, straight from VIDEO-PLAN.md §3.
 *
 * Frame numbers are the plan's, not derived: the reviewer can diff this file
 * against §3 without doing arithmetic. Both compositions and any QC script read
 * from here so there is exactly one place a timing can be wrong.
 */

export type BeatId =
  | 'B01'
  | 'B02'
  | 'B03'
  | 'B04'
  | 'B05'
  | 'B06'
  | 'B07'
  | 'B08'
  | 'B09'
  | 'B10'
  | 'B11';

export type BeatSpan = {
  id: BeatId;
  /** First frame, inclusive. */
  from: number;
  durationInFrames: number;
  /** §3 "In"–"Out" seconds, for QC. */
  inSeconds: number;
  outSeconds: number;
};

/** §3: 0.0 → 75.0, hard cuts. Sums to 2250. */
export const hero75: BeatSpan[] = [
  {id: 'B01', from: 0, durationInFrames: 105, inSeconds: 0.0, outSeconds: 3.5},
  {id: 'B02', from: 105, durationInFrames: 120, inSeconds: 3.5, outSeconds: 7.5},
  {id: 'B03', from: 225, durationInFrames: 105, inSeconds: 7.5, outSeconds: 11.0},
  {id: 'B04', from: 330, durationInFrames: 90, inSeconds: 11.0, outSeconds: 14.0},
  {id: 'B05', from: 420, durationInFrames: 300, inSeconds: 14.0, outSeconds: 24.0},
  {id: 'B06', from: 720, durationInFrames: 420, inSeconds: 24.0, outSeconds: 38.0},
  {id: 'B07', from: 1140, durationInFrames: 270, inSeconds: 38.0, outSeconds: 47.0},
  {id: 'B08', from: 1410, durationInFrames: 270, inSeconds: 47.0, outSeconds: 56.0},
  {id: 'B09', from: 1680, durationInFrames: 240, inSeconds: 56.0, outSeconds: 64.0},
  {id: 'B10', from: 1920, durationInFrames: 180, inSeconds: 64.0, outSeconds: 70.0},
  {id: 'B11', from: 2100, durationInFrames: 150, inSeconds: 70.0, outSeconds: 75.0},
];

/**
 * §11 cutdown: beats 1, 3, 4, 5, 6, 11 in 30.0 s. The plan fixes the beat list
 * but not the per-beat split, so the split here keeps the hero's *proportions*
 * of screen time for the proof beats (B05 and B06 at 9 s each) inside 900 frames.
 * Recorded as a decision, not a fact from §3.
 */
export const hero30: BeatSpan[] = [
  {id: 'B01', from: 0, durationInFrames: 90, inSeconds: 0.0, outSeconds: 3.0},
  {id: 'B03', from: 90, durationInFrames: 90, inSeconds: 3.0, outSeconds: 6.0},
  {id: 'B04', from: 180, durationInFrames: 90, inSeconds: 6.0, outSeconds: 9.0},
  {id: 'B05', from: 270, durationInFrames: 270, inSeconds: 9.0, outSeconds: 18.0},
  {id: 'B06', from: 540, durationInFrames: 270, inSeconds: 18.0, outSeconds: 27.0},
  {id: 'B11', from: 810, durationInFrames: 90, inSeconds: 27.0, outSeconds: 30.0},
];

export const totalFrames = (spans: BeatSpan[]): number =>
  spans.reduce((sum, span) => sum + span.durationInFrames, 0);

/** Guard used by the compositions and by `npm run check:schedule`. */
export const assertContiguous = (spans: BeatSpan[], expected: number): void => {
  let cursor = 0;
  for (const span of spans) {
    if (span.from !== cursor) {
      throw new Error(`${span.id} starts at ${span.from}, expected ${cursor}`);
    }
    cursor += span.durationInFrames;
  }
  if (cursor !== expected) {
    throw new Error(`schedule ends at ${cursor}, expected ${expected} frames`);
  }
};
