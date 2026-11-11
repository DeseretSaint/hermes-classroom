import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {CaptureScene} from '../components/CaptureScene';
import {Caption} from '../components/Caption';
import {Push} from '../components/Push';
import {palette} from '../tokens';

const CAPTION_FRAMES = 120; // §3: lower third for the first 4 s

/**
 * §3 B05 · 14.0–24.0 s · Home → `Start a new course` → type the topic → plan.
 * Two real states: `create-topic-light` then `plan-sections-light`, cut hard when
 * the plan lands. Nothing here draws a cursor: §6 wants the click and the typing
 * inside the capture, so the placeholder holds the whole interaction.
 */
export const B05CreateTopic: React.FC<{durationInFrames: number}> = ({
  durationInFrames,
}) => {
  const planIn = Math.round(durationInFrames * 0.6);

  return (
    <AbsoluteFill style={{backgroundColor: palette.ground}}>
      <Push durationInFrames={durationInFrames} delta={0.05}>
        <Sequence durationInFrames={planIn}>
          <CaptureScene id="beat-05 create-topic" />
        </Sequence>
        <Sequence from={planIn} durationInFrames={durationInFrames - planIn}>
          <CaptureScene id="beat-05 plan-sections" />
        </Sequence>
      </Push>

      <Sequence durationInFrames={Math.min(CAPTION_FRAMES, durationInFrames)}>
        <Caption text="Any topic becomes a real course." />
      </Sequence>
    </AbsoluteFill>
  );
};
