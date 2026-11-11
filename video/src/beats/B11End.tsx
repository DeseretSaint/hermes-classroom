import React from 'react';
import {AbsoluteFill} from 'remotion';
import {families, palette, safe, type} from '../tokens';

/**
 * §3 B11 · 70.0–75.0 s · end card. This one is final, not a placeholder:
 * wordmark, repo URL, MIT, "Built with Hermes". Type only, no motion.
 * The 6-frame fade to black is applied by the composition, not here.
 *
 * Measured height of the block is ~330 px, so centring with a 120 px bottom
 * inset puts the footer near y = 705 — far above the y = 972 chrome limit.
 */
export const B11End: React.FC<{durationInFrames: number}> = () => (
  <AbsoluteFill
    style={{
      backgroundColor: palette.ground,
      alignItems: 'center',
      justifyContent: 'center',
      paddingLeft: safe.margin,
      paddingRight: safe.margin,
      paddingBottom: safe.margin,
    }}
  >
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 28,
      }}
    >
      <div
        style={{
          fontFamily: type.display.fontFamily,
          fontWeight: type.display.fontWeight,
          fontSize: type.display.maxSize,
          lineHeight: type.display.lineHeight,
          letterSpacing: type.display.letterSpacing,
          color: palette.canvas,
        }}
      >
        Coursebook
      </div>

      <div
        style={{
          width: 240,
          height: 2,
          backgroundColor: palette.rule,
          marginTop: 4,
          marginBottom: 4,
        }}
      />

      <div
        style={{
          fontFamily: type.endUrl.fontFamily,
          fontWeight: type.endUrl.fontWeight,
          fontSize: type.endUrl.size,
          lineHeight: type.endUrl.lineHeight,
          color: palette.canvas,
          letterSpacing: '0.01em',
        }}
      >
        github.com/DeseretSaint/hermes-classroom
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 18,
          fontFamily: type.endUrl.fontFamily,
          fontSize: type.endUrl.size,
          lineHeight: type.endUrl.lineHeight,
          color: palette.canvas,
        }}
      >
        <span
          style={{
            fontWeight: 600,
            color: palette.gold,
            letterSpacing: '0.08em',
          }}
        >
          MIT
        </span>
        <span style={{color: palette.rule}}>·</span>
        {/*
          "Built with Hermes" is set in Fraunces italic, not Source Sans 3 italic:
          it is a signature line under the wordmark, and it keeps the bundled face
          count at four rather than adding a fifth face for one clause (§5 allows
          either family in the end card; this is the recorded choice).
        */}
        <span
          style={{
            fontFamily: families.display,
            fontWeight: type.display.fontWeight,
            fontStyle: 'italic',
            fontSize: type.endUrl.size,
          }}
        >
          Built with Hermes
        </span>
      </div>
    </div>
  </AbsoluteFill>
);
