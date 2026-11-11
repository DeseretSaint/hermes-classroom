import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {CaptureScene} from '../components/CaptureScene';
import {Caption} from '../components/Caption';
import {Push} from '../components/Push';
import {palette} from '../tokens';

const CAPTION_FRAMES = 120;

/**
 * §3 B08 · 47.0–56.0 s · Game mode: XP chip, level, challenge card, completion.
 *
 * The XP counter (§3: 0→40 in 900 ms) lives inside the product UI, so it belongs
 * to the capture, not to this file. Drawing an XP chip here would be inventing
 * product UI and §3 rules forbid it; the capture is taken mid-count and the
 * montage must supply the value, or CP-033b records the count as `still-only`.
 */
export const B08Game: React.FC<{durationInFrames: number}> = ({
  durationInFrames,
}) => {
  const completeIn = Math.round(durationInFrames * 0.67);

  return (
    <AbsoluteFill style={{backgroundColor: palette.ground}}>
      <Push durationInFrames={durationInFrames} delta={0.04}>
        <Sequence durationInFrames={completeIn}>
          <CaptureScene id="beat-08 game-challenge" />
        </Sequence>
        <Sequence from={completeIn} durationInFrames={durationInFrames - completeIn}>
          <CaptureScene id="beat-08 game-complete" />
        </Sequence>
      </Push>

      <Sequence durationInFrames={Math.min(CAPTION_FRAMES, durationInFrames)}>
        <Caption text="Practice that remembers where you are." />
      </Sequence>
    </AbsoluteFill>
  );
};
