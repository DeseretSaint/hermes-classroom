import React from 'react';
import {AbsoluteFill} from 'remotion';
import {frame, palette, safe, type} from '../tokens';

export type PlaceholderProps = {
  /** Capture id from captures.ts, e.g. `beat-05 create-topic`. */
  id: string;
  /** §6 state name, so CP-033b knows exactly which still belongs here. */
  state?: string;
};

/**
 * A capture slot before the capture exists. Deliberately reads as a placeholder
 * and never as product UI: dashed rule border, flat card stock, one label.
 * It disappears the moment `captures.ts` points the slot at a file.
 */
export const Placeholder: React.FC<PlaceholderProps> = ({id, state}) => {
  return (
    <AbsoluteFill
      style={{
        paddingLeft: safe.margin,
        paddingRight: safe.margin,
        paddingTop: safe.margin,
        paddingBottom: frame.height - safe.bottomLimit,
        backgroundColor: palette.ground,
      }}
    >
      <div
        style={{
          position: 'relative',
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 14,
          border: `2px dashed ${palette.rule}`,
          backgroundColor: palette.cardStock,
        }}
      >
        <div
          style={{
            fontFamily: type.placeholder.fontFamily,
            fontWeight: type.placeholder.fontWeight,
            fontSize: type.placeholder.size,
            lineHeight: type.placeholder.lineHeight,
            color: palette.ink,
          }}
        >
          {`PLACEHOLDER ${id}`}
        </div>
        {state ? (
          <div
            style={{
              fontFamily: type.caption.fontFamily,
              fontWeight: type.caption.fontWeight,
              fontSize: type.caption.size,
              lineHeight: type.caption.lineHeight,
              color: palette.terracotta,
            }}
          >
            {`expects ${state} · 1920×1080 @2×`}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
