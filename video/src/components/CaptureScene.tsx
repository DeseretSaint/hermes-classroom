import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {frame, palette} from '../tokens';
import {isDropped, slot, type CaptureId} from '../captures';
import {Crop} from './Crop';
import {Placeholder} from './Placeholder';

export type CaptureSceneProps = {
  id: CaptureId;
};

/**
 * One beat-picture: the real capture when the slot has a file, a labelled
 * placeholder when it does not. Beats call this and never branch themselves,
 * which is what keeps "drop a capture in" a one-line change.
 */
export const CaptureScene: React.FC<CaptureSceneProps> = ({id}) => {
  const capture = slot(id);
  if (!isDropped(capture)) {
    return <Placeholder id={id} state={capture.state} />;
  }
  return (
    <AbsoluteFill style={{backgroundColor: palette.canvas, overflow: 'hidden'}}>
      <Crop capture={capture} />
      {capture.highlight ? (
        <Highlight capture={capture} rect={capture.highlight} />
      ) : null}
    </AbsoluteFill>
  );
};

/** §3 beat 7: 2 px terracotta underline on the selected line. */
const Highlight: React.FC<{
  capture: Parameters<typeof Crop>[0]['capture'];
  rect: {x: number; y: number; w: number; h: number};
}> = ({capture, rect}) => {
  const frameNow = useCurrentFrame();
  const s = Math.max(frame.width / capture.crop.w, frame.height / capture.crop.h);
  const left = -(capture.crop.x * s) + (frame.width - capture.crop.w * s) / 2;
  const top = -(capture.crop.y * s) + (frame.height - capture.crop.h * s) / 2;
  const grow = interpolate(frameNow, [0, 9], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div
      style={{
        position: 'absolute',
        left: left + rect.x * s,
        top: top + (rect.y + rect.h) * s,
        width: rect.w * s * grow,
        height: 2,
        backgroundColor: palette.terracotta,
      }}
    />
  );
};
