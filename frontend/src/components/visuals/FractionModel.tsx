import React from 'react';

interface FractionModelProps {
  numerator?: number;
  denominator?: number;
  mode?: 'strip' | 'circle';
  label?: string;
  altText?: string;
}

export const FractionModel: React.FC<FractionModelProps> = ({
  numerator = 3,
  denominator = 4,
  mode = 'strip',
  label,
  altText = `Fraction model showing ${numerator} out of ${denominator}`
}) => {
  const width = 500;
  const height = 110;
  const safeDenom = Math.max(1, denominator);
  const safeNum = Math.min(safeDenom, Math.max(0, numerator));

  return (
    <div style={{ textAlign: 'center', margin: '16px 0' }} role="img" aria-label={altText}>
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', maxWidth: '500px', height: 'auto', background: '#FAFAF8', borderRadius: '8px', border: '1px solid #D9DEEA', padding: '12px' }}>
        {mode === 'strip' ? (
          <g transform="translate(30, 20)">
            {/* Outline Bar */}
            <rect x="0" y="0" width="440" height="50" rx="6" fill="#FFFFFF" stroke="#15233B" strokeWidth="2" />
            
            {/* Parts */}
            {Array.from({ length: safeDenom }).map((_, i) => {
              const partWidth = 440 / safeDenom;
              const isFilled = i < safeNum;
              return (
                <g key={i}>
                  <rect
                    x={i * partWidth}
                    y="0"
                    width={partWidth}
                    height="50"
                    fill={isFilled ? '#EEF1FC' : '#FFFFFF'}
                    stroke="#15233B"
                    strokeWidth="1.5"
                  />
                  {isFilled && (
                    <rect
                      x={i * partWidth + 2}
                      y="2"
                      width={partWidth - 4}
                      height="46"
                      fill="#4055D9"
                      opacity="0.85"
                    />
                  )}
                  <text
                    x={i * partWidth + partWidth / 2}
                    y="30"
                    fill={isFilled ? '#FFFFFF' : '#7E8B9F'}
                    fontSize="13"
                    fontWeight="600"
                    textAnchor="middle"
                    fontFamily="sans-serif"
                  >
                    1/{safeDenom}
                  </text>
                </g>
              );
            })}

            <text x="220" y="74" fill="#15233B" fontSize="13" fontWeight="700" textAnchor="middle" fontFamily="sans-serif">
              {label || `Selected: ${safeNum}/${safeDenom}`}
            </text>
          </g>
        ) : (
          <g transform="translate(250, 55)">
            {/* Circle representation */}
            <circle cx="0" cy="0" r="40" fill="#FFFFFF" stroke="#15233B" strokeWidth="2" />
            <text x="0" y="5" fill="#4055D9" fontSize="16" fontWeight="700" textAnchor="middle">
              {safeNum}/{safeDenom}
            </text>
          </g>
        )}
      </svg>
      <div style={{ fontSize: '12px', color: '#7E8B9F', marginTop: '6px' }}>{altText}</div>
    </div>
  );
};
