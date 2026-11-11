import React from 'react';
import {AbsoluteFill} from 'remotion';
import {frame, palette, safe, type} from '../tokens';

export type CaptionProps = {
  text: string;
  /**
   * `on-ground` for type over forest ground; `over-capture` puts the words on a
   * card-stock paper label so 44 px type stays readable over a light UI capture.
   */
  tone?: 'on-ground' | 'over-capture';
};

/** The label's bottom edge, kept above X's player chrome (§5: nothing below y = 972). */
const labelBottom = frame.height - safe.bottomLimit + 20;

/**
 * Lower third. One message at a time (§3 rules); 44 px Source Sans 3 600 on a
 * 120 px safe margin, entirely above y = 972.
 */
export const Caption: React.FC<CaptionProps> = ({text, tone = 'over-capture'}) => {
  const onGround = tone === 'on-ground';

  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          left: safe.margin,
          bottom: labelBottom,
          maxWidth: frame.width - safe.margin * 2,
          padding: onGround ? 0 : '16px 26px',
          backgroundColor: onGround ? 'transparent' : palette.cardStock,
          color: onGround ? palette.canvas : palette.ink,
          fontFamily: type.lowerThird.fontFamily,
          fontWeight: type.lowerThird.fontWeight,
          fontSize: type.lowerThird.size,
          lineHeight: type.lowerThird.lineHeight,
          letterSpacing: '-0.005em',
          whiteSpace: 'pre-line',
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
