import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  Sequence,
  useCurrentFrame,
} from 'remotion';
import {B01Hook} from './beats/B01Hook';
import {B02Cards} from './beats/B02Cards';
import {B03Turn} from './beats/B03Turn';
import {B04Reveal} from './beats/B04Reveal';
import {B05CreateTopic} from './beats/B05CreateTopic';
import {B06Classroom} from './beats/B06Classroom';
import {B07Tutor} from './beats/B07Tutor';
import {B08Game} from './beats/B08Game';
import {B09Parent} from './beats/B09Parent';
import {B10Discover} from './beats/B10Discover';
import {B11End} from './beats/B11End';
import type {BeatId} from './schedule';

const BEATS: Record<BeatId, React.FC<{durationInFrames: number}>> = {
  B01: B01Hook,
  B02: B02Cards,
  B03: B03Turn,
  B04: B04Reveal,
  B05: B05CreateTopic,
  B06: B06Classroom,
  B07: B07Tutor,
  B08: B08Game,
  B09: B09Parent,
  B10: B10Discover,
  B11: B11End,
};

export const BeatRenderer: React.FC<{id: BeatId; durationInFrames: number}> = ({
  id,
  durationInFrames,
}) => {
  const Component = BEATS[id];
  return (
    <AbsoluteFill>
      <Component durationInFrames={durationInFrames} />
    </AbsoluteFill>
  );
};

/** The only dissolve in the film (§3 rules): N frames to encode black at the tail. */
const FadeOut: React.FC<{frames: number; total: number}> = ({frames, total}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [total - frames, total - 1], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill
      style={{backgroundColor: '#000', opacity, pointerEvents: 'none'}}
    />
  );
};

export type CutProps = {
  spans: {id: BeatId; from: number; durationInFrames: number}[];
  /** Tail fade length in frames. 0 = hard end. */
  fade?: number;
};

/** Renders one cut's beat sequence from the schedule table. */
export const Cut: React.FC<CutProps> = ({spans, fade = 0}) => {
  const total = spans.reduce((sum, span) => sum + span.durationInFrames, 0);

  return (
    <AbsoluteFill>
      {spans.map((span) => (
        <Sequence
          key={span.id}
          from={span.from}
          durationInFrames={span.durationInFrames}
        >
          <BeatRenderer id={span.id} durationInFrames={span.durationInFrames} />
        </Sequence>
      ))}
      {fade > 0 ? <FadeOut frames={fade} total={total} /> : null}
    </AbsoluteFill>
  );
};
