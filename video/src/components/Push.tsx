import React from 'react';
import {Easing, interpolate, useCurrentFrame} from 'remotion';
import {motion} from '../tokens';

export type PushProps = {
  children: React.ReactNode;
  /** Whole-beat duration in frames; the push spans it. */
  durationInFrames: number;
  /** Total scale change as a fraction. Clamped to the 3–6 % §7 bound. */
  delta?: number;
  /** Lateral pan in px — beat 9 only (§3). Pure transform, never a zoom. */
  panPx?: number;
  transformOrigin?: string;
  style?: React.CSSProperties;
};

/**
 * Scale-only push. No translate on the zoom axis, no rotation, no blur: §3 rules
 * forbid anything but a push-in, and §7 caps it at 3–6 % with the product's own
 * easing. Use it as the direct parent of a Crop or a capture scene.
 */
export const Push: React.FC<PushProps> = ({
  children,
  durationInFrames,
  delta = motion.push.defaultDelta,
  panPx = 0,
  transformOrigin = '50% 50%',
  style,
}) => {
  const frame = useCurrentFrame();
  // A beat that specifies a pan and no push (beat 9) passes delta 0 and gets no zoom.
  const zooming = delta !== 0;
  const clamped = zooming
    ? Math.min(Math.max(delta, motion.push.minDelta), motion.push.maxDelta)
    : 0;

  const scale = interpolate(
    frame,
    [0, Math.max(1, durationInFrames - 1)],
    [1, 1 + clamped],
    {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.bezier(...motion.cubicBezier),
    },
  );

  const x = interpolate(
    frame,
    [0, Math.max(1, durationInFrames - 1)],
    [0, -panPx],
    {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.bezier(...motion.cubicBezier),
    },
  );

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        overflow: 'hidden',
        transform: `translateX(${x}px) scale(${scale})`,
        transformOrigin,
        ...style,
      }}
    >
      {children}
    </div>
  );
};
