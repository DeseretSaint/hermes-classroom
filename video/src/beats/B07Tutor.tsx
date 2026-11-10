import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {CaptureScene} from '../components/CaptureScene';
import {Caption} from '../components/Caption';
import {Push} from '../components/Push';
import {palette} from '../tokens';

const CAPTION_FRAMES = 120;

/**
 * §3 B07 · 38.0–47.0 s · tutor rail: select a line → ask → cited answer →
 * citation walkthrough. The 2 px terracotta underline comes from the slot's
 * `highlight` rect in captures.ts, never from a guessed position: with a
 * placeholder it is simply absent.
 */
export const B07Tutor: React.FC<{durationInFrames: number}> = ({
  durationInFrames,
}) => (
  <AbsoluteFill style={{backgroundColor: palette.ground}}>
    <Push durationInFrames={durationInFrames} delta={0.04}>
      <CaptureScene id="beat-07 tutor-cited" />
    </Push>

    <Sequence durationInFrames={Math.min(CAPTION_FRAMES, durationInFrames)}>
      <Caption text="Ask the lesson. Get the page." />
    </Sequence>
  </AbsoluteFill>
);
