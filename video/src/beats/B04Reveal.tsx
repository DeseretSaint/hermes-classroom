import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {CaptureScene} from '../components/CaptureScene';
import {Caption} from '../components/Caption';
import {Push} from '../components/Push';
import {palette} from '../tokens';

/**
 * §3 B04 · 11.0–14.0 s · real Home v3, full bleed, 100→106 % push over 3 s.
 * Copy: "Coursebook." then "Your field library." — the second line takes the
 * lower third for the second half of the beat.
 */
export const B04Reveal: React.FC<{durationInFrames: number}> = ({
  durationInFrames,
}) => {
  const split = Math.round(durationInFrames * 0.5);

  return (
    <AbsoluteFill style={{backgroundColor: palette.ground}}>
      <Push durationInFrames={durationInFrames} delta={0.06}>
        <CaptureScene id="beat-04 home" />
      </Push>

      <Sequence durationInFrames={split}>
        <Caption text="Coursebook." />
      </Sequence>
      <Sequence from={split} durationInFrames={durationInFrames - split}>
        <Caption text="Your field library." />
      </Sequence>
    </AbsoluteFill>
  );
};
