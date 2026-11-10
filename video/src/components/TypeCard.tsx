import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {frame, motion, palette, type} from '../tokens';

export type TypeCardLine = {
  text: string;
  /** Clamped to the §5 display band, 96–132 px. Defaults to 132. */
  size?: number;
  italic?: boolean;
};

export type TypeCardProps = {
  lines: TypeCardLine[];
  /** §3 beat 1: type rises 8 px over 300 ms. */
  rise?: boolean;
  /** Gap between lines in px. */
  gap?: number;
  align?: 'center' | 'left';
};

/**
 * Display type card. Fraunces 600 at 96–132 px with −1.5 % tracking, centred as a
 * group inside the 120 px safe area. Line breaks are explicit because §5 caps a
 * display line at 18 characters — the copy deck's pauses are the break points.
 */
export const TypeCard: React.FC<TypeCardProps> = ({
  lines,
  rise = false,
  gap = 16,
  align = 'center',
}) => {
  const frameNow = useCurrentFrame();
  const offset = rise
    ? interpolate(frameNow, [0, motion.ms.d300], [motion.risePx, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.bezier(...motion.cubicBezier),
      })
    : 0;

  return (
    <AbsoluteFill
      style={{
        alignItems: align === 'center' ? 'center' : 'flex-start',
        justifyContent: 'center',
        paddingLeft: 120,
        paddingRight: 120,
        paddingBottom: 120, // keeps the group clear of the lower third and chrome
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap,
          maxWidth: frame.width - 240,
          textAlign: align,
          transform: `translateY(${offset}px)`,
        }}
      >
        {lines.map((line) => {
          const size = Math.min(
            Math.max(line.size ?? type.display.maxSize, type.display.minSize),
            type.display.maxSize,
          );
          return (
            <div
              key={line.text}
              style={{
                fontFamily: type.display.fontFamily,
                fontWeight: type.display.fontWeight,
                fontStyle: line.italic ? 'italic' : 'normal',
                fontSize: size,
                lineHeight: type.display.lineHeight,
                letterSpacing: type.display.letterSpacing,
                color: palette.canvas,
              }}
            >
              {line.text}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
