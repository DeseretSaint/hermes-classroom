import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {CaptureScene} from '../components/CaptureScene';
import {Caption} from '../components/Caption';
import {Push} from '../components/Push';
import {motion, palette} from '../tokens';

const CAPTION_FRAMES = 120;

/**
 * §3 B09 · 56.0–64.0 s · Parent Studio: observation row, evidence, no game
 * chrome. Motion is the specified 40 px lateral pan and a hold — no push.
 */
export const B09Parent: React.FC<{durationInFrames: number}> = ({
  durationInFrames,
}) => (
  <AbsoluteFill style={{backgroundColor: palette.ground}}>
    <Push durationInFrames={durationInFrames} delta={0} panPx={motion.panPx}>
      <CaptureScene id="beat-09 parent-observation" />
    </Push>

    <Sequence durationInFrames={Math.min(CAPTION_FRAMES, durationInFrames)}>
      <Caption text="And a parent sees the work, not the screen time." />
    </Sequence>
  </AbsoluteFill>
);
