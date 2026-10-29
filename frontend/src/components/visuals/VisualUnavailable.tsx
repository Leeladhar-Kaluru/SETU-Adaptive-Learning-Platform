import React from 'react';
import styles from './VisualUnavailable.module.css';

interface VisualUnavailableProps {
  reason?: string;
}

export const VisualUnavailable: React.FC<VisualUnavailableProps> = ({ reason }) => (
  <p className={styles.note} role="note">
    {reason || 'This visual is not available for this lesson.'}
  </p>
);
