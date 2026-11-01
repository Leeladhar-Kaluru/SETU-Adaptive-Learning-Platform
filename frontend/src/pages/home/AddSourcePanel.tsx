import React from 'react';
import { Upload } from 'lucide-react';
import { DynamicActivityIndicator, ActivityPhase } from '../../components/DynamicActivityIndicator';
import styles from './AddSourcePanel.module.css';

export interface PipelineStep {
  id: string;
  label: string;
}

interface AddSourcePanelProps {
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  isDragging: boolean;
  isUploading: boolean;
  showPipelineProgress: boolean;
  pipeline: PipelineStep[];
  activePipelineIndex: number;
  progressPercent: number | undefined;
  currentBookFilename: string | undefined;
  activityPhase: ActivityPhase;
  activityDetail: string;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: () => void;
  onDrop: (e: React.DragEvent) => void;
  onFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onCancel: () => void;
}

export const AddSourcePanel: React.FC<AddSourcePanelProps> = ({
  fileInputRef,
  isDragging,
  isUploading,
  showPipelineProgress,
  pipeline,
  activePipelineIndex,
  progressPercent,
  currentBookFilename,
  activityPhase,
  activityDetail,
  onDragOver,
  onDragLeave,
  onDrop,
  onFileChange,
  onCancel,
}) => {
  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        hidden
        accept=".pdf,.docx,.pptx,.txt,.md,.png,.jpg,.jpeg"
        onChange={onFileChange}
      />
      <button
        type="button"
        className={`${styles.drop} ${isDragging ? styles.dropOn : ''}`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        aria-label="Add a source file"
      >
        <span className={styles.dropIcon} aria-hidden="true">
          <Upload size={22} />
        </span>
        <span className={styles.dropTitle}>Drop a file here or click to browse</span>
        <span className={styles.dropHint}>PDF, DOCX, PPTX, TXT, MD, or image. Up to 50MB.</span>
      </button>

      {showPipelineProgress ? (
        <>
          <p className={styles.pipelineCaption}>
            {isUploading
              ? 'A source is moving through the desk.'
              : `Source progress for ${currentBookFilename || 'your source'}.`}
          </p>
          <ol className={styles.pipeline}>
            {pipeline.map((step, index) => {
              const state =
                index < activePipelineIndex ? 'done' : index === activePipelineIndex ? 'now' : 'waiting';
              return (
                <li
                  key={step.id}
                  className={
                    state === 'done' ? styles.stepDone : state === 'now' ? styles.stepNow : undefined
                  }
                >
                  <span className={styles.stepState}>
                    {state === 'done' ? 'Done' : state === 'now' ? 'Now' : 'Waiting'}
                  </span>
                  <span className={styles.stepLabel}>
                    {step.label}
                    {step.id === 'upload' && state === 'now' && typeof progressPercent === 'number'
                      ? ` · ${progressPercent}%`
                      : ''}
                  </span>
                </li>
              );
            })}
          </ol>
        </>
      ) : (
        <p className={styles.meta}>
          A source moves through upload, storage, page reading, indexing, and your review
          before any unit is generated.
        </p>
      )}

      {isUploading && (
        <DynamicActivityIndicator
          phase={activityPhase}
          detail={activityDetail}
          progressPercent={progressPercent}
          onCancel={onCancel}
        />
      )}
    </>
  );
};
