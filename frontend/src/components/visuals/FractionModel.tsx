import React from 'react';
import { VisualUnavailable } from './VisualUnavailable';

interface FractionModelProps {
  numerator?: number;
  denominator?: number;
  mode?: 'strip' | 'circle';
  label?: string;
  altText?: string;
}

export const FractionModel: React.FC<FractionModelProps> = ({
  numerator,
  denominator,
  mode = 'strip',
  label,
  altText,
}) => {
  if (
    !altText ||
    !Number.isFinite(numerator) ||
    !Number.isFinite(denominator) ||
    (denominator as number) < 1 ||
    (numerator as number) < 0
  ) {
    return <VisualUnavailable reason="This fraction model has no usable values in the lesson source." />;
  }

  const safeLabelAlt = altText || `Fraction model showing ${numerator} out of ${denominator}`;
  const width = 500;
  const height = 110;
  const safeDenom = Math.max(1, denominator as number);
  const safeNum = Math.min(safeDenom, Math.max(0, numerator as number));

  return (
    <div style={{ textAlign: 'center', margin: '16px 0' }} role="img" aria-label={safeLabelAlt}>
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', maxWidth: '500px', height: 'auto', background: '#FAFAF8', borderRadius: '8px', border: '1px solid #D9DEEA', padding: '12px' }}>
        {mode === 'strip' ? (
          <g transform="translate(30, 20)">
            {/* Outline Bar */}
            <rect x="0" y="0" width="440" height="50" rx="6" fill="#FFFFFF" stroke="#15233B" strokeWidth="2" />
            {/* Filled segments */}
            {Array.from({ length: safeDenom }).map((_, idx) => {
              const segWidth = 440 / safeDenom;
              const isFilled = idx < safeNum;
              return (
                <g key={idx}>
                  <rect
                    x={idx * segWidth}
                    y="0"
                    width={segWidth}
                    height="50"
                    fill={isFilled ? '#4055D9' : 'transparent'}
                  />
                  {idx > 0 && (
                    <line x1={idx * segWidth} y1="0" x2={idx * segWidth} y2="50" stroke="#15233B" strokeWidth="1.5" />
                  )}
                </g>
              );
            })}
            <rect x="0" y="0" width="440" height="50" rx="6" fill="none" stroke="#15233B" strokeWidth="2" />
          </g>
        ) : (
          <g transform="translate(250, 50)">
            {Array.from({ length: safeDenom }).map((_, idx) => {
              const startAngle = (idx / safeDenom) * 2 * Math.PI - Math.PI / 2;
              const endAngle = ((idx + 1) / safeDenom) * 2 * Math.PI - Math.PI / 2;
              const x1 = Math.cos(startAngle) * 40;
              const y1 = Math.sin(startAngle) * 40;
              const x2 = Math.cos(endAngle) * 40;
              const y2 = Math.sin(endAngle) * 40;
              const largeArc = endAngle - startAngle > Math.PI ? 1 : 0;
              const isFilled = idx < safeNum;
              return (
                <path
                  key={idx}
                  d={`M 0 0 L ${x1} ${y1} A 40 40 0 ${largeArc} 1 ${x2} ${y2} Z`}
                  fill={isFilled ? '#4055D9' : '#FFFFFF'}
                  stroke="#15233B"
                  strokeWidth="1.5"
                />
              );
            })}
          </g>
        )}
        <text x="250" y="100" fill="#15233B" fontSize="13" fontWeight="700" textAnchor="middle" fontFamily="sans-serif">
          {label || `${safeNum}/${safeDenom}`}
        </text>
      </svg>
      <div style={{ fontSize: '12px', color: '#7E8B9F', marginTop: '6px' }}>{safeLabelAlt}</div>
    </div>
  );
};
