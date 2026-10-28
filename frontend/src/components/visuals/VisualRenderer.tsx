import React from 'react';
import { NumberLine } from './NumberLine';
import { FractionModel } from './FractionModel';
import { ConceptMap } from './ConceptMap';
import { CoordinateGrid } from './CoordinateGrid';
import { CellMembrane } from './CellMembrane';

interface VisualRendererProps {
  visual: {
    visualId?: string;
    type: string;
    altText?: string;
    spec?: any;
  };
}

export const VisualRenderer: React.FC<VisualRendererProps> = ({ visual }) => {
  const { type, altText, spec } = visual;
  const data = spec?.data || {};

  switch (type) {
    case 'number_line':
      return (
        <NumberLine
          min={data.min}
          max={data.max}
          step={data.step}
          highlights={data.highlights}
          intervals={data.intervals}
          altText={altText}
        />
      );
    case 'fraction_model':
      return (
        <FractionModel
          numerator={data.numerator}
          denominator={data.denominator}
          mode={data.mode}
          label={data.label}
          altText={altText}
        />
      );
    case 'concept_map':
      return (
        <ConceptMap
          nodes={data.nodes}
          edges={data.edges}
          altText={altText}
        />
      );
    case 'coordinate_grid':
      return (
        <CoordinateGrid
          xRange={data.xRange}
          yRange={data.yRange}
          points={data.points}
          altText={altText}
        />
      );
    case 'cell_membrane':
    case 'science_process':
      return (
        <CellMembrane
          altText={altText}
          labels={data.labels}
        />
      );
    default:
      // Fallback clean structured diagram card
      return (
        <div style={{
          padding: '16px',
          margin: '12px 0',
          background: '#FAFAF8',
          border: '1px solid #D9DEEA',
          borderRadius: '8px',
          textAlign: 'center'
        }}>
          <div style={{ fontWeight: 600, fontSize: '13px', color: '#15233B' }}>
            📊 {altText || 'Pedagogical Concept Visual'}
          </div>
          {spec && (
            <div style={{ marginTop: '6px', fontSize: '11px', color: '#7E8B9F', fontFamily: 'monospace' }}>
              Type: {type}
            </div>
          )}
        </div>
      );
  }
};
