import React from 'react';
import {Composition} from 'remotion';
import './fonts';
import {FontProbe} from './FontProbe';
import {Cut} from './Cut';
import {hero30, hero75, assertContiguous, totalFrames} from './schedule';
import {fadeFrames, frame} from './tokens';

assertContiguous(hero75, frame.hero75);
assertContiguous(hero30, frame.hero30);

/** Hero cut: 75.0 s, 2250 frames (§3, §7). */
export const Hero75: React.FC = () => <Cut spans={hero75} fade={fadeFrames} />;

/**
 * Cutdown for quote posts: beats 1, 3, 4, 5, 6, 11 in 900 frames (§11, §12).
 * Same fade at the tail.
 */
export const Hero30: React.FC = () => <Cut spans={hero30} fade={fadeFrames} />;

export const Root: React.FC = () => (
  <>
    <Composition
      id="FontProbe"
      component={FontProbe}
      durationInFrames={1}
      fps={frame.fps}
      width={frame.width}
      height={frame.height}
    />
    <Composition
      id="Hero75"
      component={Hero75}
      durationInFrames={totalFrames(hero75)}
      fps={frame.fps}
      width={frame.width}
      height={frame.height}
    />
    <Composition
      id="Hero30"
      component={Hero30}
      durationInFrames={totalFrames(hero30)}
      fps={frame.fps}
      width={frame.width}
      height={frame.height}
    />
  </>
);
