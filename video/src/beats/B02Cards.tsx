import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {motion, palette, type} from '../tokens';

/** One card per 96 BPM beat (§8), so the three cards land on the three taps. */
const beatFrames = 19;

const CARDS = ['A textbook.', 'A flashcard app.', "A tutor you can't afford."];

/** §3 B02 · 3.5–7.5 s · three flat paper cards land one per beat, 6 px settle. */
export const B02Cards: React.FC<{durationInFrames: number}> = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill
      style={{
        backgroundColor: palette.ground,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div style={{display: 'flex', flexDirection: 'column', gap: 32}}>
        {CARDS.map((text, index) => {
          const land = index * beatFrames;
          const settle = interpolate(
            frame,
            [land, land + motion.ms.d120],
            [motion.settlePx, 0],
            {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
              easing: Easing.bezier(...motion.cubicBezier),
            },
          );
          const visible = frame >= land;

          return (
            <div
              key={text}
              style={{
                width: 1080,
                height: 168,
                backgroundColor: palette.cardStock,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transform: `translateY(${settle}px)`,
                opacity: visible ? 1 : 0,
              }}
            >
              <span
                style={{
                  fontFamily: type.display.fontFamily,
                  fontWeight: type.display.fontWeight,
                  fontSize: type.display.minSize,
                  lineHeight: type.display.lineHeight,
                  letterSpacing: type.display.letterSpacing,
                  color: palette.ink,
                }}
              >
                {text}
              </span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
