import React from 'react';
import { api } from '../../services/api';
import styles from './StudyRecordPanel.module.css';

type StudySummary = Awaited<ReturnType<typeof api.getStudySummary>>;

interface StudyRecordPanelProps {
  studySummary: StudySummary | null;
  suggestionErrors: Record<string, string>;
  respondingSuggestionId: string | null;
  onRespond: (id: string, decision: 'accept' | 'dismiss') => void;
}

export const StudyRecordPanel: React.FC<StudyRecordPanelProps> = ({
  studySummary,
  suggestionErrors,
  respondingSuggestionId,
  onRespond,
}) => {
  return (
    <>
      {studySummary && (studySummary.minutesStudied > 0 || studySummary.checkpointCount > 0) ? (
        <>
          <p className={styles.meta}>
            {studySummary.minutesStudied} minutes recorded
            {studySummary.readingTitle ? ` · Last opened: ${studySummary.readingTitle}` : ''}
            {studySummary.accuracyRate !== null
              ? ` · Checks ${Math.round(studySummary.accuracyRate * 100)}%`
              : ' · No checks yet'}
            {studySummary.improvement === 'improving'
              ? ' · Recent checks are stronger than earlier ones.'
              : ''}
            {studySummary.improvement === 'needs_support'
              ? ' · Recent checks were harder. Stay with the current unit.'
              : ''}
          </p>
          <div className={styles.heatmap} aria-label="Study time for the last seven days">
            {studySummary.heatmap.map((day) => (
              <div key={day.date} title={`${day.date}: ${Math.round(day.seconds / 60)} min`}>
                <span
                  style={{
                    height: `${Math.min(100, Math.max(day.seconds ? 12 : 0, Math.round(day.seconds / 36)))}%`,
                  }}
                />
              </div>
            ))}
          </div>
        </>
      ) : (
        <p className={styles.meta}>
          Nothing has been studied yet. Time and check results appear after you open a unit.
        </p>
      )}

      {studySummary?.suggestions?.length ? (
        <ul className={styles.notes}>
          {studySummary.suggestions.map((item) => (
            <li key={item.id} className={styles.suggestion}>
              <div className={styles.suggestionHead}>
                <strong>{item.teacherName || 'Your teacher'}</strong>
                {item.conceptId && (
                  <span className={styles.suggestionTopic}>
                    {item.conceptId.replace(/^concept[-_]/, '').replace(/[-_]/g, ' ')}
                  </span>
                )}
              </div>
              {item.explanation && (
                <p className={styles.suggestionExplanation}>{item.explanation}</p>
              )}
              <p className={styles.suggestionNote}>{item.note}</p>
              {suggestionErrors[item.id] && (
                <p className={styles.bad} role="alert">
                  {suggestionErrors[item.id]}{' '}
                  <button
                    type="button"
                    className={styles.inlineRetry}
                    onClick={() => onRespond(item.id, 'accept')}
                    disabled={respondingSuggestionId === item.id}
                  >
                    Retry
                  </button>
                </p>
              )}
              <div className={styles.suggestionActions}>
                <button
                  type="button"
                  className={styles.suggestionAccept}
                  onClick={() => onRespond(item.id, 'accept')}
                  disabled={respondingSuggestionId === item.id}
                >
                  {respondingSuggestionId === item.id ? 'Saving…' : 'Accept'}
                </button>
                <button
                  type="button"
                  className={styles.suggestionDismiss}
                  onClick={() => onRespond(item.id, 'dismiss')}
                  disabled={respondingSuggestionId === item.id}
                >
                  Dismiss
                </button>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </>
  );
};
