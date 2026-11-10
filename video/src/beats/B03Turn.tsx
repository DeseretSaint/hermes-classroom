import React from 'react';
import {AbsoluteFill} from 'remotion';
import {TypeCard} from '../components/TypeCard';
import {palette} from '../tokens';

/** §3 B03 · 7.5–11.0 s · same ground, one line, bigger. Hard cut, no motion. */
export const B03Turn: React.FC<{durationInFrames: number}> = () => (
  <AbsoluteFill style={{backgroundColor: palette.ground}}>
    <TypeCard
      lines={[
        {text: 'One course.', size: 132},
        {text: 'Finished.', size: 132},
      ]}
      gap={8}
    />
  </AbsoluteFill>
);
