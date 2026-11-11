import React from 'react';
import {AbsoluteFill} from 'remotion';
import {families, palette} from './tokens';

/**
 * Font A/B probe. Six rows of the same string at the same size; `scripts/check-fonts.sh`
 * renders it and asserts, by pixel comparison, that the bundled faces are not the
 * Times fallback. A silent fallback is invisible in review but obvious here — this
 * composition is the regression guard for the quoting bug described in tokens.ts.
 *
 * Row order is fixed: the check script addresses rows by index.
 */
export const ROWS = [
  {label: 'Source Sans 3 600', family: families.ui, weight: 600, style: 'normal'},
  {label: 'Source Sans 3 400', family: families.ui, weight: 400, style: 'normal'},
  {label: 'Fraunces 600', family: families.display, weight: 600, style: 'normal'},
  {label: 'Fraunces 600 italic', family: families.display, weight: 600, style: 'italic'},
  {label: 'generic serif (fallback control)', family: 'serif', weight: 400, style: 'normal'},
  {label: 'generic sans (control)', family: 'sans-serif', weight: 400, style: 'normal'},
] as const;

export const ROW_HEIGHT = 170;

export const FontProbe: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: palette.cardStock}}>
    {ROWS.map((row, index) => (
      <div
        key={row.label}
        style={{
          position: 'absolute',
          top: index * ROW_HEIGHT,
          left: 40,
          width: 1840,
          height: ROW_HEIGHT,
          backgroundColor: palette.cardStock,
        }}
      >
        <div
          style={{
            fontFamily: families.ui,
            fontSize: 18,
            color: palette.terracotta,
            height: 22,
          }}
        >
          {row.label}
        </div>
        <div
          style={{
            fontFamily: row.family,
            fontWeight: row.weight,
            fontStyle: row.style,
            fontSize: 88,
            lineHeight: 1.2,
            color: palette.ink,
            whiteSpace: 'nowrap',
          }}
        >
          Coursebook 00
        </div>
      </div>
    ))}
  </AbsoluteFill>
);
