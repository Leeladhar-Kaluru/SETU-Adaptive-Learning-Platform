import React from 'react';
import { VisualUnavailable } from './VisualUnavailable';

interface NumberLineProps {
  min?: number;
  max?: number;
  step?: number;
  highlights?: number[];
  intervals?: Array<{ start: number; end: number; label?: string }>;
  altText?: string;
}

export const NumberLine: React.FC<NumberLineProps> = ({
  min,
  max,
  step = 1,
  highlights = [],
  intervals = [],
  altText,
}) => {
  if (
    !altText ||
    !Number.isFinite(min) ||
    !Number.isFinite(max) ||
    !Number.isFinite(step) ||
    (step as number) <= 0 ||
    (max as number) <= (min as number)
  ) {
    return <VisualUnavailable reason="This number line has no usable range in the lesson source." />;
  }

  const safeMin = min as number;
  const safeMax = max as number;
  const width = 600;
  const height = 120;
  const padding = 50;
  const lineY = 60;
  const availableWidth = width - padding * 2;

  const toX = (val: number) => padding + ((val - safeMin) / (safeMax - safeMin)) * availableWidth;

  const ticks: number[] = [];
  for (let v = safeMin; v <= safeMax; v += step) {
    ticks.push(v);
  }

  return (
    <div style={{ textAlign: 'center', margin: '16px 0' }} role="img" aria-label={altText}>
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', maxWidth: '600px', height: 'auto', background: '#FAFAF8', borderRadius: '8px', border: '1px solid #D9DEEA' }}>
        <defs>
          <marker id="arrow-right" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#15233B" />
          </marker>
          <marker id="arrow-left" viewBox="0 0 10 10" refX="2" refY="5" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M 10 1 L 0 5 L 10 9 z" fill="#15233B" />
          </marker>
        </defs>
        {/* Main Axis Line */}
        <line x1={padding - 15} y1={lineY} x2={width - padding + 15} y2={lineY} stroke="#15233B" strokeWidth="2.5" markerEnd="url(#arrow-right)" markerStart="url(#arrow-left)" />

        {/* Intervals */}
        {intervals.map((inv, idx) => {
          const x1 = toX(inv.start);
          const x2 = toX(inv.end);
          return (
            <g key={idx}>
              <line x1={x1} y1={lineY - 20} x2={x2} y2={lineY - 20} stroke="#4055D9" strokeWidth="3" />
              <circle cx={x1} cy={lineY - 20} r="4" fill="#4055D9" />
              <circle cx={x2} cy={lineY - 20} r="4" fill="#4055D9" />
              {inv.label && (
                <text x={(x1 + x2) / 2} y={lineY - 26} fill="#4055D9" fontSize="12" fontWeight="600" textAnchor="middle" fontFamily="sans-serif">
                  {inv.label}
                </text>
              )}
            </g>
          );
        })}

        {/* Ticks & Numbers */}
        {ticks.map((t) => {
          const x = toX(t);
          const isHighlighted = highlights.includes(t);
          const isZero = t === 0;
          return (
            <g key={t}>
              <line x1={x} y1={lineY - 8} x2={x} y2={lineY + 8} stroke={isHighlighted ? '#4055D9' : '#4A5873'} strokeWidth={isHighlighted ? '2.5' : '1.5'} />
              <text x={x} y={lineY + 24} fill={isHighlighted ? '#4055D9' : '#15233B'} fontSize="13" fontWeight={isHighlighted || isZero ? '700' : '500'} textAnchor="middle" fontFamily="sans-serif">
                {t}
              </text>
              {isHighlighted && (
                <circle cx={x} cy={lineY} r="5" fill="#4055D9" />
              )}
            </g>
          );
        })}
      </svg>
      <div style={{ fontSize: '12px', color: '#7E8B9F', marginTop: '6px' }}>{altText}</div>
    </div>
  );
};
