import React from 'react';
import { VisualUnavailable } from './VisualUnavailable';

interface Node {
  id: string;
  label: string;
}

interface ConceptMapProps {
  nodes?: Node[];
  edges?: [string, string][];
  altText?: string;
}

const hasUsableNodes = (nodes?: Node[]): nodes is Node[] =>
  Array.isArray(nodes) &&
  nodes.length > 0 &&
  nodes.every((node) => node && typeof node.id === 'string' && typeof node.label === 'string' && node.label.trim().length > 0);

export const ConceptMap: React.FC<ConceptMapProps> = ({
  nodes,
  edges = [],
  altText,
}) => {
  if (!altText || !hasUsableNodes(nodes)) {
    return <VisualUnavailable reason="This concept map has no concepts in the lesson source." />;
  }

  const width = 600;
  const height = 220;

  // Compute simple positions for up to 6 nodes
  const nodeCoords: Record<string, { x: number; y: number }> = {};
  if (nodes.length <= 4) {
    nodeCoords[nodes[0].id] = { x: 300, y: 40 };
    if (nodes[1]) nodeCoords[nodes[1].id] = { x: 300, y: 110 };
    if (nodes[2]) nodeCoords[nodes[2].id] = { x: 160, y: 180 };
    if (nodes[3]) nodeCoords[nodes[3].id] = { x: 440, y: 180 };
  } else {
    // Dynamic circular or layered layout
    nodes.forEach((n, idx) => {
      const angle = (idx / nodes.length) * 2 * Math.PI - Math.PI / 2;
      nodeCoords[n.id] = {
        x: 300 + Math.cos(angle) * 160,
        y: 110 + Math.sin(angle) * 70
      };
    });
  }

  return (
    <div style={{ textAlign: 'center', margin: '16px 0' }} role="img" aria-label={altText}>
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', maxWidth: '600px', height: 'auto', background: '#FAFAF8', borderRadius: '8px', border: '1px solid #D9DEEA' }}>
        <defs>
          <marker id="concept-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#8E9FB8" />
          </marker>
        </defs>

        {/* Edges */}
        {edges.map(([fromId, toId], idx) => {
          const from = nodeCoords[fromId];
          const to = nodeCoords[toId];
          if (!from || !to) return null;
          return (
            <line
              key={idx}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              stroke="#BDC8DA"
              strokeWidth="2"
              markerEnd="url(#concept-arrow)"
            />
          );
        })}

        {/* Nodes */}
        {nodes.map((node, idx) => {
          const pos = nodeCoords[node.id] || { x: 100 + idx * 80, y: 100 };
          const isRoot = idx === 0;
          return (
            <g key={node.id} transform={`translate(${pos.x}, ${pos.y})`}>
              <rect
                x="-80"
                y="-18"
                width="160"
                height="36"
                rx="8"
                fill={isRoot ? '#15233B' : '#FFFFFF'}
                stroke={isRoot ? '#15233B' : '#4055D9'}
                strokeWidth="1.5"
                filter="drop-shadow(0 2px 4px rgba(0,0,0,0.06))"
              />
              <text
                x="0"
                y="5"
                fill={isRoot ? '#FFFFFF' : '#15233B'}
                fontSize="12"
                fontWeight="600"
                textAnchor="middle"
                fontFamily="sans-serif"
              >
                {node.label.length > 22 ? node.label.slice(0, 20) + '…' : node.label}
              </text>
            </g>
          );
        })}
      </svg>
      <div style={{ fontSize: '12px', color: '#7E8B9F', marginTop: '6px' }}>{altText}</div>
    </div>
  );
};
