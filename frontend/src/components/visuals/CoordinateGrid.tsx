import React from 'react';
import { VisualUnavailable } from './VisualUnavailable';

interface Point {
  x: number;
  y: number;
  label?: string;
}

interface CoordinateGridProps {
  xRange?: [number, number];
  yRange?: [number, number];
  points?: Point[];
  altText?: string;
}

const isRange = (value?: [number, number]): value is [number, number] =>
  Array.isArray(value) &&
  value.length === 2 &&
  Number.isFinite(value[0]) &&
  Number.isFinite(value[1]) &&
  value[1] > value[0];

export const CoordinateGrid: React.FC<CoordinateGridProps> = ({
  xRange,
  yRange,
  points = [],
  altText,
}) => {
  if (!altText || !isRange(xRange) || !isRange(yRange)) {
    return <VisualUnavailable reason="This coordinate grid has no usable axes in the lesson source." />;
  }

  const size = 320;
  const padding = 30;
  const innerSize = size - padding * 2;

  const toScreenX = (val: number) => padding + ((val - xRange[0]) / (xRange[1] - xRange[0])) * innerSize;
  const toScreenY = (val: number) => size - (padding + ((val - yRange[0]) / (yRange[1] - yRange[0])) * innerSize);

  const originX = toScreenX(0);
  const originY = toScreenY(0);

  return (
    <div style={{ textAlign: 'center', margin: '16px 0' }} role="img" aria-label={altText}>
      <svg viewBox={`0 0 ${size} ${size}`} style={{ width: '100%', maxWidth: '320px', height: 'auto', background: '#FAFAF8', borderRadius: '8px', border: '1px solid #D9DEEA' }}>
        {/* Grid lines */}
        {Array.from({ length: xRange[1] - xRange[0] + 1 }).map((_, i) => {
          const val = xRange[0] + i;
          const x = toScreenX(val);
          return (
            <line key={`gx-${val}`} x1={x} y1={padding} x2={x} y2={size - padding} stroke="#E8ECF4" strokeWidth="1" />
          );
        })}
        {Array.from({ length: yRange[1] - yRange[0] + 1 }).map((_, i) => {
          const val = yRange[0] + i;
          const y = toScreenY(val);
          return (
            <line key={`gy-${val}`} x1={padding} y1={y} x2={size - padding} y2={y} stroke="#E8ECF4" strokeWidth="1" />
          );
        })}

        {/* Axes */}
        <line x1={padding - 5} y1={originY} x2={size - padding + 5} y2={originY} stroke="#15233B" strokeWidth="1.8" />
        <line x1={originX} y1={size - padding + 5} x2={originX} y2={padding - 5} stroke="#15233B" strokeWidth="1.8" />

        {/* Points */}
        {points.map((p, idx) => {
          const px = toScreenX(p.x);
          const py = toScreenY(p.y);
          return (
            <g key={idx}>
              <circle cx={px} cy={py} r="4.5" fill="#4055D9" />
              {p.label && (
                <text x={px + 7} y={py - 6} fill="#15233B" fontSize="11" fontWeight="700" fontFamily="sans-serif">
                  {p.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <div style={{ fontSize: '12px', color: '#7E8B9F', marginTop: '6px' }}>{altText}</div>
    </div>
  );
};
