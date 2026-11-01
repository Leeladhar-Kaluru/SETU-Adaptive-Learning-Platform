import React from 'react';
import styles from './DynamicActivityIndicator.module.css';

export type ActivityPhase =
  | 'extracting'
  | 'chunking'
  | 'generating'
  | 'retrieving'
  | 'answering'
  | 'syncing'
  | 'ready'
  | 'failed';

interface DynamicActivityIndicatorProps {
  phase: ActivityPhase;
  customMessage?: string;
  detail?: string;
  progressPercent?: number; // 0 to 100, or undefined for indeterminate
  onCancel?: () => void;
}

const PHASE_CONFIG: Record<
  ActivityPhase,
  { label: string; defaultMessage: string; icon: string }
> = {
  extracting: {
    label: 'Extraction',
    defaultMessage: 'Reading your document...',
    icon: '📄'
  },
  chunking: {
    label: 'Outline Analysis',
    defaultMessage: 'Finding the concepts and prerequisites...',
    icon: '🔍'
  },
  generating: {
    label: 'Lesson Generation',
    defaultMessage: 'Preparing your first lessons...',
    icon: '⚙️'
  },
  retrieving: {
    label: 'Textbook Retrieval',
    defaultMessage: 'Checking the source passages...',
    icon: '📚'
  },
  answering: {
    label: 'Grounded Answer',
    defaultMessage: 'Writing an explanation from your material...',
    icon: '✍️'
  },
  syncing: {
    label: 'Cloud Sync',
    defaultMessage: 'Syncing your saved doubts...',
    icon: '🔄'
  },
  ready: {
    label: 'Complete',
    defaultMessage: 'Content is ready for study',
    icon: '✅'
  },
  failed: {
    label: 'Action Required',
    defaultMessage: 'Processing could not be completed',
    icon: '⚠️'
  }
};

export const DynamicActivityIndicator: React.FC<DynamicActivityIndicatorProps> = ({
  phase,
  customMessage,
  detail,
  progressPercent,
  onCancel
}) => {
  const config = PHASE_CONFIG[phase] || PHASE_CONFIG.generating;
  const isComplete = phase === 'ready';
  const isFailed = phase === 'failed';
  const isLoading = !isComplete && !isFailed;

  return (
    <div
      className={`${styles.container} ${
        isLoading
          ? styles.containerLoading
          : isComplete
          ? styles.containerSuccess
          : styles.containerError
      }`}
      role="status"
      aria-live="polite"
    >
      <div className={styles.iconWrapper}>
        {isLoading && <div className={styles.pulseRing} />}
        <span>{config.icon}</span>
      </div>

      <div className={styles.content}>
        <div className={styles.statusHeader}>
          <span className={styles.statusText}>
            {customMessage || config.defaultMessage}
          </span>
          <span className={styles.statusPhase}>{config.label}</span>
        </div>

        {detail && <div className={styles.detailText}>{detail}</div>}

        {isLoading && (
          <div className={styles.progressTrack}>
            {typeof progressPercent === 'number' ? (
              <div
                className={styles.progressBar}
                style={{ width: `${Math.min(100, Math.max(0, progressPercent))}%` }}
              />
            ) : (
              <div className={styles.indeterminateBar} />
            )}
          </div>
        )}
      </div>

      {isLoading && onCancel && (
        <button
          type="button"
          className={styles.cancelButton}
          onClick={onCancel}
          aria-label="Cancel current activity"
        >
          Cancel
        </button>
      )}
    </div>
  );
};

