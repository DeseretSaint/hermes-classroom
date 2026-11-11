import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {CaptureScene} from '../components/CaptureScene';
import {Caption} from '../components/Caption';
import {Push} from '../components/Push';
import {palette} from '../tokens';

const CAPTION_FRAMES = 120;

/** §3 B10 · 64.0–70.0 s · Discover grid, real packs and covers, 100→103 % push. */
export const B10Discover: React.FC<{durationInFrames: number}> = ({
  durationInFrames,
}) => (
  <AbsoluteFill style={{backgroundColor: palette.ground}}>
    <Push durationInFrames={durationInFrames} delta={0.03}>
      <CaptureScene id="beat-10 discover-grid" />
    </Push>

    <Sequence durationInFrames={Math.min(CAPTION_FRAMES, durationInFrames)}>
      <Caption text="Your next world is already on the shelf." />
    </Sequence>
  </AbsoluteFill>
);
