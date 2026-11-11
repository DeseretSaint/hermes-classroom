/**
 * Bundled type, loaded from local files only — no network at render (§7).
 *
 * Fraunces and Source Sans 3, both OFL; the licences sit beside the woff2 files
 * in `public/fonts/`. The woff2 files themselves are committed, so a render on a
 * machine with no network produces the same frames as one with it.
 *
 * Loading is explicit and failure-loud on purpose: a missing face silently falls
 * back to Times, which is how a launch film ships looking unofficial. Every face
 * is registered with `font-display: block`, awaited through `document.fonts.load`,
 * then *checked*; if any face is missing the render is cancelled rather than
 * producing a frame in the wrong typeface.
 */
import {cancelRender, continueRender, delayRender, staticFile} from 'remotion';

export type FontFaceSpec = {
  family: string;
  file: string;
  weight: string;
  style: 'normal' | 'italic';
  /** The string passed to FontFaceSet.load/check. */
  descriptor: string;
};

export const FACES: FontFaceSpec[] = [
  {
    family: 'Fraunces',
    file: 'fonts/fraunces-latin-600-normal.woff2',
    weight: '600',
    style: 'normal',
    descriptor: '600 132px "Fraunces"',
  },
  {
    family: 'Fraunces',
    file: 'fonts/fraunces-latin-600-italic.woff2',
    weight: '600',
    style: 'italic',
    descriptor: 'italic 600 132px "Fraunces"',
  },
  {
    family: 'Source Sans 3',
    file: 'fonts/source-sans-3-latin-400-normal.woff2',
    weight: '400',
    style: 'normal',
    descriptor: '400 44px "Source Sans 3"',
  },
  {
    family: 'Source Sans 3',
    file: 'fonts/source-sans-3-latin-600-normal.woff2',
    weight: '600',
    style: 'normal',
    descriptor: '600 44px "Source Sans 3"',
  },
];

const styleSheet = FACES.map(
  (face) => `
@font-face {
  font-family: '${face.family}';
  src: url('${staticFile(face.file)}') format('woff2');
  font-weight: ${face.weight};
  font-style: ${face.style};
  font-display: block;
}`,
).join('\n');

if (typeof document !== 'undefined') {
  const style = document.createElement('style');
  style.textContent = styleSheet;
  document.head.appendChild(style);

  const handle = delayRender('Loading bundled Fraunces + Source Sans 3');

  Promise.all(FACES.map((face) => document.fonts.load(face.descriptor)))
    .then(() => document.fonts.ready)
    .then(() => {
      const missing = FACES.filter(
        (face) => !document.fonts.check(face.descriptor),
      );
      if (missing.length > 0) {
        cancelRender(
          new Error(
            `Bundled font(s) failed to load: ${missing
              .map((face) => `${face.family} ${face.weight} ${face.style}`)
              .join(', ')}`,
          ),
        );
        return;
      }
      continueRender(handle);
    })
    .catch((error: unknown) => {
      cancelRender(error instanceof Error ? error : new Error(String(error)));
    });
}
