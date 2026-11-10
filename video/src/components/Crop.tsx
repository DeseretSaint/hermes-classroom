import React from 'react';
import {Img, staticFile} from 'remotion';
import {frame} from '../tokens';
import type {CaptureSlot, CropRect} from '../captures';

export type CropProps = {
  /** The capture slot, so the same geometry serves placeholder and still. */
  capture: CaptureSlot & {file: string};
  /** Override the slot's crop region. */
  crop?: CropRect;
};

/**
 * Image placement maths for a real capture.
 *
 * A capture is a screenshot of a route of known *logical* width (`routeWidth`,
 * 1920 px per §6) taken at 2× device pixel ratio, so the file is 3840 px wide.
 * The DPR multiplies pixels, not geometry: nothing here divides by 2, and that
 * is the point. `crop` is the region of the route that should fill the frame,
 * in logical px. We compute the frame-px-per-logical-px factor once and position
 * the image so the crop's top-left lands on the frame's top-left:
 *
 *   s    = max(1920 / crop.w, 1080 / crop.h)   cover, never squash
 *   W    = routeWidth * s                      rendered image width
 *   left = -(crop.x * s) + (1920 - crop.w * s) / 2
 *   top  = -(crop.y * s) + (1080 - crop.h * s) / 2
 *
 * Because `width` is fixed in frame px and `height` is auto, the natural height
 * never enters the maths — a taller capture than the crop just overhangs and is
 * clipped by the parent. A 16:9 crop therefore fills the frame exactly at every
 * zoom level a 3–6 % push can reach.
 */
export const Crop: React.FC<CropProps> = ({capture, crop}) => {
  const rect = crop ?? capture.crop;
  const s = Math.max(frame.width / rect.w, frame.height / rect.h);
  const width = capture.routeWidth * s;
  const left = -(rect.x * s) + (frame.width - rect.w * s) / 2;
  const top = -(rect.y * s) + (frame.height - rect.h * s) / 2;

  return (
    <Img
      src={staticFile(capture.file)}
      style={{
        position: 'absolute',
        left,
        top,
        width,
        height: 'auto',
        maxWidth: 'none',
      }}
    />
  );
};
