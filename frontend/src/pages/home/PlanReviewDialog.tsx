import React from 'react';
import { IngestionStatus } from '../../services/api';
import { GRADES, gradeLabel } from '../../lib/academic';
import styles from './PlanReviewDialog.module.css';

interface PlanReviewDialogProps {
  outline: IngestionStatus;
  reviewError: string | null;
  isGeneratingPath: boolean;
  grade: string;
  subject: string;
  subjectOptions: { id: string; label: string }[];
  taxonomy: { loading: boolean; error: string | null; retry: () => void };
  dialogRef: React.RefObject<HTMLDivElement | null>;
  onGradeChange: (value: string) => void;
  onSubjectChange: (value: string) => void;
  onClose: () => void;
  onBuild: () => void;
}

export const PlanReviewDialog: React.FC<PlanReviewDialogProps> = ({
  outline,
  reviewError,
  isGeneratingPath,
  grade,
  subject,
  subjectOptions,
  taxonomy,
  dialogRef,
  onGradeChange,
  onSubjectChange,
  onClose,
  onBuild,
}) => {
  const chapters = outline.chapters || [];

  return (
    <div className={styles.modalBackdrop}>
      <div
        className={`${styles.modalContent} ${styles.planDialog}`}
        ref={dialogRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="plan-dialog-title"
      >
        <header className={styles.dialogHead}>
          <div className={styles.dialogHeading}>
            <span className={styles.dialogKicker}>Source review</span>
            <h2 id="plan-dialog-title">{outline.filename}</h2>
            <p className={styles.dialogMeta}>
              {outline.pageCount || 0} pages · {outline.chunkCount || 0} indexed sections
            </p>
          </div>
          <button
            type="button"
            className={styles.dialogClose}
            aria-label="Close plan review"
            onClick={onClose}
            disabled={isGeneratingPath}
          >
            ×
          </button>
        </header>

        {(reviewError ||
          outline.outlineMessage ||
          (typeof outline.pagesNeedingOcr === 'number' && outline.pagesNeedingOcr > 0)) && (
          <div className={styles.dialogAlerts}>
            {reviewError && <p className={styles.bad} role="alert">{reviewError}</p>}
            {outline.outlineMessage && (
              <p className={styles.bad} role="alert">{outline.outlineMessage}</p>
            )}
            {typeof outline.pagesNeedingOcr === 'number' && outline.pagesNeedingOcr > 0 && (
              <p className={styles.bad}>
                {outline.pagesNeedingOcr}{' '}
                {outline.pagesNeedingOcr === 1 ? 'page' : 'pages'} could not be read after text
                extraction and OCR. Those pages are not indexed and will not appear in your lessons.
              </p>
            )}
          </div>
        )}

        <div className={styles.dialogBody}>
          <section className={styles.dialogSetup} aria-label="Plan settings">
            <div className={styles.dialogCount}>
              <span>Outline found</span>
              <strong>
                {chapters.length} {chapters.length === 1 ? 'chapter' : 'chapters'}
              </strong>
            </div>
            <p className={styles.dialogHint}>
              Check the chapters on the right, then choose the class and subject for this book.
              Units are generated only after you approve the plan.
            </p>
            <div className={styles.contextRow}>
              <label className={styles.contextField}>
                Class
                <select value={grade} onChange={(e) => onGradeChange(e.target.value)}>
                  <option value="">Select class</option>
                  {GRADES.map((gradeOption) => (
                    <option key={gradeOption} value={gradeOption}>{gradeLabel(gradeOption)}</option>
                  ))}
                </select>
              </label>
              <label className={styles.contextField}>
                Subject
                <select
                  value={subject}
                  onChange={(e) => onSubjectChange(e.target.value)}
                  disabled={taxonomy.loading || subjectOptions.length === 0}
                >
                  <option value="">
                    {taxonomy.loading
                      ? 'Loading subjects…'
                      : subjectOptions.length > 0
                        ? 'Select subject'
                        : 'No subjects available'}
                  </option>
                  {subjectOptions.map((option) => (
                    <option key={option.id} value={option.id}>{option.label}</option>
                  ))}
                </select>
              </label>
            </div>
            {taxonomy.error && (
              <div className={styles.dialogInlineError}>
                <span>{taxonomy.error}</span>
                <button type="button" onClick={taxonomy.retry}>Retry</button>
              </div>
            )}
            {!taxonomy.loading && !taxonomy.error && subjectOptions.length === 0 && (
              <p className={styles.bad}>
                No subjects are configured in the catalogue. Add a subject before building a plan.
              </p>
            )}
            {!taxonomy.loading && !taxonomy.error && subjectOptions.length > 0 && (!grade || !subject) && (
              <p className={styles.contextNote}>Choose a class and subject to continue.</p>
            )}
          </section>

          <section className={styles.dialogChapters} aria-label="Chapters found">
            <div className={styles.dialogChapterHead}>
              <h3>Chapters found</h3>
              <span>{chapters.length}</span>
            </div>
            {chapters.length > 0 ? (
              <ol className={styles.chapterList}>
                {chapters.map((chapter, index) => (
                  <li key={`${chapter.title}-${index}`} className={styles.chapterItem}>
                    <span className={styles.chapterNumber}>{String(index + 1).padStart(2, '0')}</span>
                    <span className={styles.chapterTitle}>{chapter.title}</span>
                    <span className={styles.chapterPages}>pp. {chapter.pageStart}–{chapter.pageEnd}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className={styles.dialogEmpty}>
                No chapter headings were detected in this source. SETU will not invent an outline.
              </p>
            )}
          </section>
        </div>

        <footer className={styles.dialogFooter}>
          <span>Nothing is generated until you approve this outline.</span>
          <div className={styles.rowActions}>
            <button
              type="button"
              className={styles.secondary}
              onClick={onClose}
              disabled={isGeneratingPath}
            >
              Not now
            </button>
            <button
              type="button"
              className={styles.primary}
              disabled={isGeneratingPath || !grade || !subject || !outline.canBuildPath}
              onClick={onBuild}
            >
              {isGeneratingPath ? 'Preparing the first units…' : 'Build my learning plan'}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
};
