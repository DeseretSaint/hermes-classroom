import React from 'react';
import {AbsoluteFill} from 'remotion';
import {TypeCard} from '../components/TypeCard';
import {palette} from '../tokens';

/** §3 B01 · 0.0–3.5 s · forest ground, one line, type rises 8 px over 300 ms. */
export const B01Hook: React.FC<{durationInFrames: number}> = () => (
  <AbsoluteFill style={{backgroundColor: palette.ground}}>
    <TypeCard rise lines={[{text: "You don't need"}, {text: 'another course.'}]} />
  </AbsoluteFill>
);
