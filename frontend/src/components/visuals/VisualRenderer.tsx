import React from 'react';
import { NumberLine } from './NumberLine';
import { FractionModel } from './FractionModel';
import { ConceptMap } from './ConceptMap';
import { CoordinateGrid } from './CoordinateGrid';
import { CellMembrane } from './CellMembrane';
import { ProcessDiagram } from './ProcessDiagram';

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
      return (
        <CellMembrane
          altText={altText}
          labels={data.labels}
        />
      );
    case 'science_process': {
      const steps = Array.isArray(data.steps) ? data.steps : [];
      return steps.length > 0 ? (
        <ProcessDiagram title={data.title} steps={steps} altText={altText} />
      ) : (
        <p>This process visual is not available for this lesson.</p>
      );
    }
    default:
      return <p>{altText || 'This visual is not available for this lesson.'}</p>;
  }
};

