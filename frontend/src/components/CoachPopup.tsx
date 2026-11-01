import React, { useEffect, useRef } from 'react';
import { X, Sparkles, Target, BookOpen, Lightbulb, ArrowRight, Brain } from 'lucide-react';
import type { CoachCard, PersonalCoachNote } from '../services/api';
import styles from './CoachPopup.module.css';

interface CoachPopupProps {
  card: CoachCard | null;
  onClose: () => void;
  onContinue?: () => void;
  continueLabel?: string;
  personalNote?: PersonalCoachNote | null;
  personalNotePending?: boolean;
}

export const CoachPopup: React.FC<CoachPopupProps> = ({
  card,
  onClose,
  onContinue,
  continueLabel,
  personalNote,
  personalNotePending,
}) => {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!card) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    const timer = window.setTimeout(() => closeRef.current?.focus(), 120);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      window.clearTimeout(timer);
    };
  }, [card, onClose]);

  if (!card) return null;

  const isCelebrate = card.tone === 'celebrate';
  const rootGap = card.rootGap;
  const hasEvidence =
    card.keyPoint || card.source || card.studyTip || rootGap || card.nextStep?.title;

  return (
    <aside
      className={`${styles.layer} ${isCelebrate ? styles.celebrate : styles.retry}`}
      role="status"
      aria-live="polite"
      aria-label="SETU coach"
    >
      <div className={styles.card}>
        <span className={styles.accent} aria-hidden="true" />
        <header className={styles.head}>
          <span className={styles.kicker}>
            {isCelebrate ? <Sparkles size={14} /> : <Target size={14} />}
            {isCelebrate ? 'Evidence updated' : 'SETU coach'}
          </span>
          <button
            ref={closeRef}
            type="button"
            className={styles.close}
            onClick={onClose}
            aria-label="Dismiss coaching card"
          >
            <X size={16} />
          </button>
        </header>

        <h3 className={styles.headline}>
          {card.headline || (isCelebrate ? 'That moved your mastery forward.' : 'Let us pin this down.')}
        </h3>
        <p className={styles.body}>{card.body}</p>

        {rootGap && (
          <div className={styles.rootGap}>
            <span className={styles.blockLabel}>Root gap detected</span>
            <strong>{rootGap.label}</strong>
            <p>{rootGap.reason}</p>
          </div>
        )}

        {card.keyPoint && (
          <div className={styles.keyPoint}>
            <span className={styles.blockLabel}>
              <Lightbulb size={12} /> {card.keyPoint.title}
            </span>
            <p>{card.keyPoint.body}</p>
          </div>
        )}

        {card.source && (
          <blockquote className={styles.source}>
            <span className={styles.blockLabel}>
              <BookOpen size={12} /> From your book · page {card.source.page}
            </span>
            <p>“{card.source.excerpt}”</p>
            <cite>{card.source.title}</cite>
          </blockquote>
        )}

        {card.studyTip && (
          <div className={styles.studyTip}>
            <span className={styles.blockLabel}>{card.studyTip.title}</span>
            <p>{card.studyTip.body}</p>
          </div>
        )}

        {card.nextStep?.title && (
          <div className={styles.nextStep}>
            <span className={styles.blockLabel}>Next step</span>
            <strong>{card.nextStep.title}</strong>
            {card.nextStep.reason && <p>{card.nextStep.reason}</p>}
          </div>
        )}

        {personalNotePending && !personalNote && (
          <div className={styles.personalNote}>
            <span className={styles.blockLabel}>
              <Brain size={12} /> SETU is analyzing your last answers…
            </span>
            <p>This note is written from your real attempts, so it takes a few seconds.</p>
          </div>
        )}

        {personalNote && (
          <div className={styles.personalNote}>
            <span className={styles.blockLabel}>
              <Brain size={12} /> Personal coach note · from your last {personalNote.analyzedAttempts} attempts
            </span>
            <strong>{personalNote.headline}</strong>
            <p>{personalNote.body}</p>
            <div className={styles.personalTip}>
              <span className={styles.blockLabel}>{personalNote.studyTipTitle}</span>
              <p>{personalNote.studyTipBody}</p>
            </div>
          </div>
        )}

        {!hasEvidence && (
          <p className={styles.honestNote}>
            No extra source sentence is stored for this answer, so SETU is not inventing one.
          </p>
        )}

        <footer className={styles.foot}>
          <button type="button" className={styles.dismiss} onClick={onClose}>
            {isCelebrate ? 'Keep going' : 'I will try that'}
          </button>
          {onContinue && (
            <button type="button" className={styles.continue} onClick={onContinue}>
              {continueLabel || 'Continue'} <ArrowRight size={14} />
            </button>
          )}
        </footer>
      </div>
    </aside>
  );
};
