import React from 'react';
import styles from './ProcessDiagram.module.css';

interface ProcessDiagramProps {
  title?: string;
  steps: Array<string | { label?: string; detail?: string }>;
  altText?: string;
}

export const ProcessDiagram: React.FC<ProcessDiagramProps> = ({ title, steps, altText }) => {
  const normalized = steps
    .map((step) =>
      typeof step === 'string'
        ? { label: step }
        : {
            label: String(step.label || ''),
            detail: step.detail ? String(step.detail) : undefined,
          }
    )
    .filter((step) => step.label);

  if (normalized.length === 0) return null;

  return (
    <figure className={styles.figure} role="img" aria-label={altText || title || 'Process diagram'}>
      {title && <figcaption className={styles.title}>{title}</figcaption>}
      <ol className={styles.steps}>
        {normalized.map((step, index) => (
          <li key={`${step.label}-${index}`} className={styles.step}>
            <span className={styles.number} aria-hidden="true">
              {index + 1}
            </span>
            <span>
              <strong>{step.label}</strong>
              {step.detail && <span className={styles.detail}>{step.detail}</span>}
            </span>
          </li>
        ))}
      </ol>
    </figure>
  );
};
