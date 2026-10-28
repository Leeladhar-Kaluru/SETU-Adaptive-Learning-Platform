import React from 'react';

interface CellMembraneProps {
  altText?: string;
  labels?: {
    outer?: string;
    bilayer?: string;
    channel?: string;
    inner?: string;
  };
}

export const CellMembrane: React.FC<CellMembraneProps> = ({
  altText = 'Fluid Mosaic Model: Plasma Membrane Bilayer with Channel Protein',
  labels = {
    outer: 'Extracellular Fluid (Outside)',
    bilayer: 'Phospholipid Bilayer (Hydrophilic heads & Hydrophobic tails)',
    channel: 'Transport / Carrier Protein',
    inner: 'Cytoplasm (Inside Cell)'
  }
}) => {
  const width = 600;
  const height = 240;

  // Lipids coordinates
  const headsTop: number[] = [];
  const headsBottom: number[] = [];
  for (let x = 40; x <= 560; x += 22) {
    // Leave gap for protein channel at 260-340
    if (x >= 250 && x <= 350) continue;
    headsTop.push(x);
    headsBottom.push(x);
  }

  return (
    <div style={{ textAlign: 'center', margin: '16px 0' }} role="img" aria-label={altText}>
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', maxWidth: '600px', height: 'auto', background: '#FAFAF8', borderRadius: '8px', border: '1px solid #D9DEEA' }}>
        {/* Background Regions */}
        <rect x="0" y="0" width={width} height="60" fill="#E8F1FC" opacity="0.6" />
        <rect x="0" y="180" width={width} height="60" fill="#E8F5F0" opacity="0.6" />

        {/* Labels for regions */}
        <text x="30" y="25" fill="#1E66B4" fontSize="12" fontWeight="700" fontFamily="sans-serif">
          {labels.outer}
        </text>
        <text x="30" y="225" fill="#23795B" fontSize="12" fontWeight="700" fontFamily="sans-serif">
          {labels.inner}
        </text>

        {/* Top Phospholipid Heads and Tails */}
        {headsTop.map((x) => (
          <g key={`top-${x}`}>
            <circle cx={x} cy={75} r="7" fill="#4055D9" />
            <line x1={x - 2} y1={82} x2={x - 3} y2={105} stroke="#7E8B9F" strokeWidth="2" strokeLinecap="round" />
            <line x1={x + 2} y1={82} x2={x + 3} y2={105} stroke="#7E8B9F" strokeWidth="2" strokeLinecap="round" />
          </g>
        ))}

        {/* Bottom Phospholipid Heads and Tails */}
        {headsBottom.map((x) => (
          <g key={`bottom-${x}`}>
            <line x1={x - 2} y1={135} x2={x - 3} y2={158} stroke="#7E8B9F" strokeWidth="2" strokeLinecap="round" />
            <line x1={x + 2} y1={135} x2={x + 3} y2={158} stroke="#7E8B9F" strokeWidth="2" strokeLinecap="round" />
            <circle cx={x} cy={165} r="7" fill="#4055D9" />
          </g>
        ))}

        {/* Central Carrier / Channel Protein */}
        <g transform="translate(300, 120)">
          <path
            d="M -35 -55 C -55 -20, -55 20, -35 55 L -10 55 C -25 20, -25 -20, -10 -55 Z"
            fill="#23795B"
            stroke="#15233B"
            strokeWidth="1.5"
          />
          <path
            d="M 35 -55 C 55 -20, 55 20, 35 55 L 10 55 C 25 20, 25 -20, 10 -55 Z"
            fill="#23795B"
            stroke="#15233B"
            strokeWidth="1.5"
          />
          {/* Pore opening */}
          <line x1="0" y1="-45" x2="0" y2="45" stroke="#FFFFFF" strokeWidth="2" strokeDasharray="3 3" />
          {/* Label */}
          <text x="0" y="4" fill="#FFFFFF" fontSize="10" fontWeight="700" textAnchor="middle" fontFamily="sans-serif">
            PORE
          </text>
        </g>

        {/* Arrow showing selective diffusion */}
        <g transform="translate(300, 50)">
          <line x1="0" y1="-10" x2="0" y2="135" stroke="#A65B12" strokeWidth="2" strokeDasharray="4 2" />
          <polygon points="0,140 -5,130 5,130" fill="#A65B12" />
          <text x="50" y="70" fill="#A65B12" fontSize="11" fontWeight="600" textAnchor="start" fontFamily="sans-serif">
            Selective Molecules (Diffusion)
          </text>
        </g>
      </svg>
      <div style={{ fontSize: '12px', color: '#7E8B9F', marginTop: '6px' }}>{altText}</div>
    </div>
  );
};
