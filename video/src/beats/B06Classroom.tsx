import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {CaptureScene} from '../components/CaptureScene';
import {Caption} from '../components/Caption';
import {Push} from '../components/Push';
import {palette} from '../tokens';

const CAPTION_FRAMES = 120; // §3: lower third for the first 4 s

/**
 * §3 B06 · 24.0–38.0 s · stepper, kana with furigana + romaji, check card,
 * answer, feedback, evidence tray. Three real states, hard cuts on the beat:
 * the read line → the check card → the feedback hold.
 */
export const B06Classroom: React.FC<{durationInFrames: number}> = ({
  durationInFrames,
}) => {
  const checkIn = Math.round(durationInFrames * 0.42);
  const feedbackIn = Math.round(durationInFrames * 0.72);

  return (
    <AbsoluteFill style={{backgroundColor: palette.ground}}>
      <Push durationInFrames={durationInFrames} delta={0.04}>
        <Sequence durationInFrames={checkIn}>
          <CaptureScene id="beat-06 classroom-line" />
        </Sequence>
        <Sequence from={checkIn} durationInFrames={feedbackIn - checkIn}>
          <CaptureScene id="beat-06 classroom-check" />
        </Sequence>
        <Sequence from={feedbackIn} durationInFrames={durationInFrames - feedbackIn}>
          <CaptureScene id="beat-06 classroom-feedback" />
        </Sequence>
      </Push>

      <Sequence durationInFrames={Math.min(CAPTION_FRAMES, durationInFrames)}>
        <Caption text="Read it. Hear it. Answer it." />
      </Sequence>
    </AbsoluteFill>
  );
};
