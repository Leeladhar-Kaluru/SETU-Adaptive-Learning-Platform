import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { Download, Check, HelpCircle, X, ChevronRight, FileSearch, ArrowLeft, RefreshCw } from 'lucide-react';
import { VisualRenderer } from '../components/visuals/VisualRenderer';
import { db, saveLessonOffline, getOfflineLesson, queueDoubtOffline, queueAttemptOffline } from '../db/indexedDB';
import { api, type AttemptResult, type AttemptSubmission } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { syncManager } from '../services/syncManager';
import styles from './LessonReaderPage.module.css';

export const LessonReaderPage: React.FC = () => {
  const { lessonId = '' } = useParams<{ lessonId: string }>();
  const [searchParams] = useSearchParams();
  const pathId = searchParams.get('pathId') || '';
  const navigate = useNavigate();
  const { user } = useAuth();

  const [activeTab, setActiveTab] = useState<'learn' | 'solve' | 'test'>('learn');
  const [lessonPackage, setLessonPackage] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [notReady, setNotReady] = useState(false);
  const [readyMessage, setReadyMessage] = useState('This lesson is still being prepared from your document.');
  const [isSavedOffline, setIsSavedOffline] = useState(false);
  const [savingOffline, setSavingOffline] = useState(false);
  const [saveOfflineError, setSaveOfflineError] = useState<string | null>(null);

  // Provenance Drawer State
  const [activeCitation, setActiveCitation] = useState<any | null>(null);

  // Doubt Drawer State
  const [doubtDrawerOpen, setDoubtDrawerOpen] = useState(false);
  const [doubtText, setDoubtText] = useState('');
  const [doubtBlockId, setDoubtBlockId] = useState<string | undefined>(undefined);
  const [doubtPage, setDoubtPage] = useState<number | undefined>(undefined);
  const [submittingDoubt, setSubmittingDoubt] = useState(false);
  const [doubtResponse, setDoubtResponse] = useState<any | null>(null);
  const [lastDoubtPayload, setLastDoubtPayload] = useState<any | null>(null);

  // Practice & Test Interactive State
  const [practiceAnswers, setPracticeAnswers] = useState<Record<string, string>>({});
  const [revealedHints, setRevealedHints] = useState<Record<string, number>>({});
  const [testAnswers, setTestAnswers] = useState<Record<string, string>>({});
  const [testSubmitted, setTestSubmitted] = useState(false);
  const [attemptResults, setAttemptResults] = useState<Record<string, AttemptResult>>({});
  const [attemptErrors, setAttemptErrors] = useState<Record<string, string>>({});
  const [submittingQuestion, setSubmittingQuestion] = useState<string | null>(null);
  const [checkpointResult, setCheckpointResult] = useState<{
    correct: number;
    total: number;
    mastery: AttemptResult['mastery'] | null;
    nextAction: AttemptResult['nextAction'] | null;
    offline: boolean;
  } | null>(null);

  const questionStartedAt = useRef<Record<string, number>>({});
  const readingStartedAt = useRef<number | null>(null);

  const markQuestionStarted = (questionId: string) => {
    if (!questionStartedAt.current[questionId]) {
      questionStartedAt.current[questionId] = Date.now();
    }
  };

  const flushReadingTime = useCallback(() => {
    if (!lessonPackage || !readingStartedAt.current) return;
    const seconds = Math.max(0, Math.min(1800, Math.round((Date.now() - readingStartedAt.current) / 1000)));
    readingStartedAt.current = null;
    if (seconds < 5) return;
    api.recordStudy({
      eventType: 'reading',
      pathId: pathId || undefined,
      lessonId,
      lessonTitle: lessonPackage.title,
      seconds,
    }).catch(() => undefined);
  }, [lessonPackage, lessonId, pathId]);

  const loadLesson = async (quiet = false) => {
    if (!lessonId) {
      setLoading(false);
      setNotReady(true);
      setReadyMessage('Choose a lesson from your learning path.');
      return;
    }
    if (!quiet) setLoading(true);
    const offlineCopy = user ? await getOfflineLesson(user.id, lessonId) : undefined;
    if (offlineCopy) {
      setLessonPackage(offlineCopy.packageData);
      setIsSavedOffline(true);
      setNotReady(false);
      if (!readingStartedAt.current) readingStartedAt.current = Date.now();
      setLoading(false);
      return;
    }

    try {
      const pkg = await api.getLesson(lessonId);
      setLessonPackage(pkg);
      setNotReady(false);
      if (!readingStartedAt.current) readingStartedAt.current = Date.now();
    } catch (err: any) {
      setLessonPackage(null);
      setNotReady(true);
      setReadyMessage(err?.message || 'This lesson is still being prepared from your document.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLesson();
  }, [lessonId]);

  useEffect(() => {
    if (!notReady || !lessonId) return;
    const timer = window.setInterval(() => {
      loadLesson(true);
    }, 4000);
    return () => window.clearInterval(timer);
  }, [notReady, lessonId]);

  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') flushReadingTime();
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      flushReadingTime();
    };
  }, [flushReadingTime]);

  const handleSaveOffline = async () => {
    if (!lessonPackage || !user) return;
    setSavingOffline(true);
    setSaveOfflineError(null);
    try {
      await saveLessonOffline(lessonPackage, user.id);
      setIsSavedOffline(true);
    } catch {
      setSaveOfflineError('Could not save this lesson on this device. Check browser storage and try again.');
    } finally {
      setSavingOffline(false);
    }
  };

  const openDoubtDrawer = (blockId?: string, page?: number) => {
    setDoubtBlockId(blockId);
    setDoubtPage(page);
    setDoubtResponse(null);
    setDoubtDrawerOpen(true);
  };

  const submitDoubt = async (payload: any) => {
    if (!user) {
      setDoubtResponse({ status: 'failed', message: 'Sign in to ask a doubt.' });
      return;
    }
    setSubmittingDoubt(true);
    setDoubtResponse(null);
    setLastDoubtPayload(payload);

    if (!navigator.onLine) {
      await queueDoubtOffline({ ...payload, ownerId: user.id });
      await syncManager.refreshPending();
      setDoubtResponse({
        status: 'queued',
        message: 'You are offline. Your doubt is stored on this device and will sync when you reconnect.'
      });
      setSubmittingDoubt(false);
      return;
    }

    try {
      const res = await api.askDoubt(payload);
      const answerPayload = res.answerJson;

      if (res.status === 'answered' && answerPayload?.answer) {
        await db.doubtOutbox.put({
          clientDoubtId: payload.clientDoubtId,
          ownerId: user.id,
          pathId: payload.pathId,
          blockId: payload.blockId,
          sourcePage: payload.sourcePage,
          questionText: payload.questionText,
          status: 'answered',
          synced: true,
          submittedAt: new Date().toISOString(),
          answerPayload: {
            answer: answerPayload.answer,
            citations: answerPayload.citations || [],
            answeredAt: answerPayload.answeredAt || new Date().toISOString()
          }
        });

        await db.cachedAnswers.put({
          clientDoubtId: payload.clientDoubtId,
          ownerId: user.id,
          doubtId: res.id,
          questionText: payload.questionText,
          answer: answerPayload.answer,
          citations: answerPayload.citations || [],
          cachedAt: answerPayload.answeredAt || new Date().toISOString()
        });

        setDoubtResponse({
          status: 'answered',
          answer: answerPayload.answer,
          citations: answerPayload.citations || [],
          limitations: answerPayload.limitations || null
        });
      } else {
        setDoubtResponse({
          status: 'failed',
          retryable: true,
          message: answerPayload?.message || 'The tutor could not answer this yet. Try again.'
        });
      }
    } catch (err: any) {
      if (!navigator.onLine) {
        await queueDoubtOffline({ ...payload, ownerId: user.id });
        await syncManager.refreshPending();
        setDoubtResponse({
          status: 'queued',
          message: 'You are offline. Your doubt is stored on this device and will sync when you reconnect.'
        });
      } else if (err instanceof TypeError) {
        setDoubtResponse({
          status: 'failed',
          retryable: true,
          message: 'Could not reach SETU. Check your connection and try again.'
        });
      } else {
        setDoubtResponse({
          status: 'failed',
          retryable: true,
          message: err?.message || 'The tutor could not answer this yet. Try again.'
        });
      }
    } finally {
      setSubmittingDoubt(false);
    }
  };

  const handleAskDoubt = async () => {
    if (!doubtText.trim() || !lessonPackage) return;
    if (!user) {
      setDoubtResponse({ status: 'failed', message: 'Sign in to ask a doubt.' });
      return;
    }
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    const candidatePath = String(lessonPackage.pathId || pathId || '');
    const payload = {
      clientDoubtId: 'doubt_' + Date.now(),
      pathId: uuidPattern.test(candidatePath) ? candidatePath : '',
      blockId: doubtBlockId,
      sourcePage: doubtPage,
      questionText: doubtText
    };
    await submitDoubt(payload);
  };

  const handlePracticeSelect = (qId: string, opt: string) => {
    if (attemptResults[qId]) return;
    markQuestionStarted(qId);
    setPracticeAnswers(prev => ({ ...prev, [qId]: opt }));
  };

  const handlePracticeSubmit = async (q: any) => {
    const selected = practiceAnswers[q.questionId];
    if (!selected || !lessonPackage?.lessonVersionId || !user) return;

    const startedAt = questionStartedAt.current[q.questionId] || Date.now();
    const elapsedSeconds = Math.max(0, Math.min(1800, Math.round((Date.now() - startedAt) / 1000)));
    const hintsUsed = (q.hints || []).slice(0, revealedHints[q.questionId] || 0);
    const payload: AttemptSubmission = {
      lessonVersionId: lessonPackage.lessonVersionId,
      questionKey: q.questionId,
      response: selected,
      hintLevel: hintsUsed.length,
      hintsUsed,
      elapsedSeconds,
      attemptKind: 'practice',
      syncIdempotencyKey: `practice-${lessonPackage.lessonVersionId}-${q.questionId}`,
    };

    setSubmittingQuestion(q.questionId);
    setAttemptErrors(prev => ({ ...prev, [q.questionId]: '' }));
    try {
      const result = await api.submitAttempt(payload);
      setAttemptResults(prev => ({ ...prev, [q.questionId]: result }));
    } catch (err: any) {
      if (!navigator.onLine) {
        await queueAttemptOffline({
          clientAttemptId: payload.syncIdempotencyKey!,
          ownerId: user.id,
          lessonId,
          lessonVersionId: payload.lessonVersionId,
          questionKey: payload.questionKey,
          response: payload.response,
          hintLevel: payload.hintLevel || 0,
          hintsUsed: payload.hintsUsed || [],
          attemptKind: payload.attemptKind || 'practice',
          elapsedSeconds: payload.elapsedSeconds || 0,
        });
        await syncManager.refreshPending();
        setAttemptErrors(prev => ({
          ...prev,
          [q.questionId]: 'Saved offline. This answer will be graded when you reconnect.',
        }));
      } else {
        setAttemptErrors(prev => ({
          ...prev,
          [q.questionId]: err?.message || 'The answer could not be graded. Try again.',
        }));
      }
    } finally {
      setSubmittingQuestion(null);
    }
  };

  const handleRevealHint = (qId: string) => {
    markQuestionStarted(qId);
    setRevealedHints(prev => ({ ...prev, [qId]: (prev[qId] || 0) + 1 }));
  };

  const handleTestSelect = (qId: string, opt: string) => {
    if (testSubmitted) return;
    markQuestionStarted(qId);
    setTestAnswers(prev => ({ ...prev, [qId]: opt }));
  };

  const handleTestSubmit = async () => {
    if (!lessonPackage?.checkpointTest?.length || !lessonPackage.lessonVersionId || !user) return;
    setTestSubmitted(true);
    const results: AttemptResult[] = [];
    let queuedOffline = false;

    for (const q of lessonPackage.checkpointTest) {
      const selected = testAnswers[q.questionId];
      if (!selected) continue;
      const startedAt = questionStartedAt.current[q.questionId] || Date.now();
      const elapsedSeconds = Math.max(0, Math.min(1800, Math.round((Date.now() - startedAt) / 1000)));
      const payload: AttemptSubmission = {
        lessonVersionId: lessonPackage.lessonVersionId,
        questionKey: q.questionId,
        response: selected,
        hintLevel: 0,
        hintsUsed: [],
        elapsedSeconds,
        attemptKind: 'checkpoint',
        syncIdempotencyKey: `checkpoint-${lessonPackage.lessonVersionId}-${q.questionId}`,
      };
      try {
        const result = await api.submitAttempt(payload);
        results.push(result);
        setAttemptResults(prev => ({ ...prev, [q.questionId]: result }));
      } catch (err: any) {
        if (!navigator.onLine) {
          await queueAttemptOffline({
            clientAttemptId: payload.syncIdempotencyKey!,
            ownerId: user.id,
            lessonId,
            lessonVersionId: payload.lessonVersionId,
            questionKey: payload.questionKey,
            response: payload.response,
            hintLevel: 0,
            hintsUsed: [],
            attemptKind: 'checkpoint',
            elapsedSeconds,
          });
          await syncManager.refreshPending();
          queuedOffline = true;
        } else {
          setCheckpointResult({
            correct: 0,
            total: lessonPackage.checkpointTest.length,
            mastery: null,
            nextAction: null,
            offline: false,
          });
          setAttemptErrors(prev => ({
            ...prev,
            checkpoint: err?.message || 'The checkpoint could not be graded. Try again.',
          }));
          return;
        }
      }
    }

    const correct = results.filter(item => item.isCorrect).length;
    const last = results[results.length - 1];
    setCheckpointResult({
      correct,
      total: lessonPackage.checkpointTest.length,
      mastery: last?.mastery || null,
      nextAction: last?.nextAction || null,
      offline: queuedOffline,
    });
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh', gap: '8px', color: '#4A5873' }}>
        <RefreshCw size={18} className="spin" />
        <span>Loading lesson package...</span>
      </div>
    );
  }

  if (!lessonPackage) {
    return (
      <div className={styles.container}>
        <div style={{ padding: '32px', textAlign: 'center' }}>
          <h2>{notReady ? 'Preparing this lesson' : 'Lesson not found'}</h2>
          <p>{readyMessage}</p>
          <button className={styles.offlineBtn} onClick={() => navigate('/')}>
            <ArrowLeft size={16} /> Return to Desk
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {/* Top Header Card */}
      <div className={styles.headerCard}>
        <div className={styles.headerMain}>
          <div className={styles.metaRow}>
            <button onClick={() => navigate('/')} style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#4A5873', fontSize: '13px', cursor: 'pointer' }}>
              <ArrowLeft size={14} /> Desk
            </button>
            <span>•</span>
            <span className={styles.gradeBadge}>Class {lessonPackage.grade}</span>
            <span>•</span>
            <span>{lessonPackage.subjectId}</span>
          </div>
          <h1 className={styles.lessonTitle}>{lessonPackage.title}</h1>
        </div>

        <div className={styles.actionsRow}>
          <button
            className={`${styles.offlineBtn} ${isSavedOffline ? styles.offlineBtnSaved : ''}`}
            onClick={handleSaveOffline}
            disabled={savingOffline || isSavedOffline}
            title={isSavedOffline ? 'Lesson saved to local IndexedDB' : 'Download lesson package for offline study'}
          >
            {isSavedOffline ? (
              <>
                <Check size={14} /> Saved Offline
              </>
            ) : (
              <>
                <Download size={14} /> {savingOffline ? 'Saving...' : 'Save Offline'}
              </>
            )}
          </button>

          <button
            className={styles.offlineBtn}
            onClick={() => openDoubtDrawer()}
            title="Ask a doubt grounded strictly in the source material"
          >
            <HelpCircle size={14} /> Ask Doubt
          </button>
        </div>
        {saveOfflineError && (
          <p role="alert" style={{ marginTop: 8, fontSize: 13, color: 'var(--color-error)' }}>
            {saveOfflineError}
          </p>
        )}
      </div>

      {/* Learn / Solve / Test Tab Navigation */}
      <div className={styles.tabBar}>
        <button
          className={`${styles.tab} ${activeTab === 'learn' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('learn')}
        >
          1. Learn (Source Explanation)
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'solve' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('solve')}
        >
          2. Solve (Guided Practice)
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'test' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('test')}
        >
          3. Test (Checkpoint Assessment)
        </button>
      </div>

      {/* TAB 1: LEARN */}
      {activeTab === 'learn' && (
        <div className={styles.contentCard}>
          {/* Objectives */}
          {lessonPackage.objectives?.length > 0 && (
            <div className={styles.objectivesBox}>
              <div className={styles.objectivesTitle}>Learning Objectives</div>
              <ul className={styles.objectivesList}>
                {lessonPackage.objectives.map((obj: string, i: number) => (
                  <li key={i}>{obj}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Educational Visuals */}
          {lessonPackage.visuals?.map((vis: any, idx: number) => (
            <VisualRenderer key={idx} visual={vis} />
          ))}

          {/* Text Content Blocks with Grounded Citations */}
          {lessonPackage.blocks?.map((block: any) => (
            <section key={block.blockId} className={styles.blockSection}>
              <h2 className={styles.blockHeading}>{block.heading}</h2>
              <p className={styles.blockContent}>
                {block.content}
                {block.sourceRefs?.map((ref: any, rIdx: number) => (
                  <span
                    key={rIdx}
                    className={styles.citationBadge}
                    onClick={() => setActiveCitation(ref)}
                    title={`Click to view source evidence (Page ${ref.pageStart})`}
                  >
                    <FileSearch size={11} /> Page {ref.pageStart}
                  </span>
                ))}
              </p>

              <div className={styles.doubtPromptBar}>
                <span className={styles.doubtText}>Have a question on this section?</span>
                <button
                  className={styles.doubtBtn}
                  onClick={() => openDoubtDrawer(block.blockId, block.sourceRefs?.[0]?.pageStart)}
                >
                  Ask Tutor
                </button>
              </div>
            </section>
          ))}

          {/* Worked Examples */}
          {lessonPackage.workedExamples?.map((we: any, idx: number) => (
            <div key={idx} className={styles.workedExampleBox}>
              <div className={styles.workedExamplePrompt}>💡 Worked Problem: {we.prompt}</div>
              {we.steps?.map((step: string, sIdx: number) => (
                <div key={sIdx} className={styles.workedExampleStep}>
                  Step {sIdx + 1}: {step}
                </div>
              ))}
              <div className={styles.workedExampleAnswer}>
                ✓ Solution: {we.answer}
              </div>
            </div>
          ))}

          {/* Takeaways */}
          {lessonPackage.takeaways?.length > 0 && (
            <div style={{ marginTop: '16px', padding: '20px', background: '#FAFAF8', border: '1px solid #D9DEEA', borderRadius: '8px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '8px', color: '#15233B' }}>
                Key Takeaways
              </h3>
              <ul style={{ paddingLeft: '20px', fontSize: '14px', lineHeight: 1.6, color: '#4A5873' }}>
                {lessonPackage.takeaways.map((t: string, i: number) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
            <button className={styles.offlineBtn} onClick={() => setActiveTab('solve')}>
              Proceed to Practice Problems <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* TAB 2: SOLVE (GUIDED PRACTICE) */}
      {activeTab === 'solve' && (
        <div className={styles.contentCard}>
          <h2 style={{ fontSize: '20px', fontWeight: 700, color: '#15233B' }}>
            Guided Practice Problems
          </h2>
          <p style={{ fontSize: '14px', color: '#4A5873', marginTop: '-16px' }}>
            Work through these problems with progressive hints. Attempts are recorded for your teacher evidence matrix.
          </p>

          {lessonPackage.practice?.map((q: any) => {
            const result = attemptResults[q.questionId];
            const isSubmitted = Boolean(result);
            const isCorrect = result?.isCorrect === true;
            const selected = practiceAnswers[q.questionId];
            const hintCount = revealedHints[q.questionId] || 0;
            const isSubmitting = submittingQuestion === q.questionId;

            return (
              <div key={q.questionId} className={styles.questionCard}>
                <div className={styles.questionPrompt}>{q.prompt}</div>

                <div className={styles.optionsList}>
                  {q.options?.map((opt: string, idx: number) => {
                    const isThisSelected = selected === opt;
                    let optClass = styles.optionBtn;
                    if (isSubmitted) {
                      if (opt === result?.correctAnswer) optClass = `${styles.optionBtn} ${styles.optionCorrect}`;
                      else if (isThisSelected) optClass = `${styles.optionBtn} ${styles.optionIncorrect}`;
                    } else if (isThisSelected) {
                      optClass = `${styles.optionBtn} ${styles.optionSelected}`;
                    }

                    return (
                      <button
                        key={idx}
                        className={optClass}
                        onClick={() => handlePracticeSelect(q.questionId, opt)}
                      >
                        {String.fromCharCode(65 + idx)}. {opt}
                      </button>
                    );
                  })}
                </div>

                {/* Progressive Hints */}
                {q.hints?.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {q.hints.slice(0, hintCount).map((hint: string, hIdx: number) => (
                      <div key={hIdx} className={styles.hintBox}>
                        <strong>Hint {hIdx + 1}:</strong> {hint}
                      </div>
                    ))}
                    {!isSubmitted && hintCount < q.hints.length && (
                      <button
                        onClick={() => handleRevealHint(q.questionId)}
                        style={{ alignSelf: 'flex-start', fontSize: '12px', fontWeight: 600, color: '#4055D9', textDecoration: 'underline' }}
                      >
                        Need help? Reveal Hint {hintCount + 1}
                      </button>
                    )}
                  </div>
                )}

                {/* Submit Action & Feedback */}
                {!isSubmitted ? (
                  <button
                    className={styles.offlineBtn}
                    style={{ alignSelf: 'flex-start', background: '#4055D9', color: '#FFFFFF' }}
                    onClick={() => handlePracticeSubmit(q)}
                    disabled={!selected || isSubmitting}
                  >
                    {isSubmitting ? 'Checking…' : 'Check Answer'}
                  </button>
                ) : (
                  <div className={`${styles.feedbackBox} ${isCorrect ? styles.feedbackSuccess : styles.feedbackWarning}`}>
                    <strong>{isCorrect ? '✓ Correct.' : '✕ Not quite.'}</strong> {result?.feedback}
                    {result?.nextAction?.title ? (
                      <div style={{ marginTop: '6px', fontSize: '13px' }}>
                        {result.nextAction.title}: {result.nextAction.reason}
                      </div>
                    ) : null}
                  </div>
                )}
                {attemptErrors[q.questionId] && (
                  <div className={styles.feedbackWarning}>{attemptErrors[q.questionId]}</div>
                )}
              </div>
            );
          })}

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '16px' }}>
            <button className={styles.offlineBtn} onClick={() => setActiveTab('learn')}>
              <ArrowLeft size={16} /> Back to Learn
            </button>
            <button className={styles.offlineBtn} onClick={() => setActiveTab('test')}>
              Start Checkpoint Test <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* TAB 3: TEST (CHECKPOINT ASSESSMENT) */}
      {activeTab === 'test' && (
        <div className={styles.contentCard}>
          <h2 style={{ fontSize: '20px', fontWeight: 700, color: '#15233B' }}>
            Checkpoint Test
          </h2>
          <p style={{ fontSize: '14px', color: '#4A5873', marginTop: '-16px' }}>
            Independent assessment without hints. Complete all questions to calculate your adaptive mastery score.
          </p>

          {lessonPackage.checkpointTest?.map((q: any, qIdx: number) => {
            const selected = testAnswers[q.questionId];
            const result = attemptResults[q.questionId];
            return (
              <div key={q.questionId} className={styles.questionCard}>
                <div className={styles.questionPrompt}>
                  {qIdx + 1}. {q.prompt}
                </div>

                <div className={styles.optionsList}>
                  {q.options?.map((opt: string, optIdx: number) => {
                    const isSelected = selected === opt;
                    let optClass = styles.optionBtn;
                    if (testSubmitted) {
                      if (opt === result?.correctAnswer) optClass = `${styles.optionBtn} ${styles.optionCorrect}`;
                      else if (isSelected) optClass = `${styles.optionBtn} ${styles.optionIncorrect}`;
                    } else if (isSelected) {
                      optClass = `${styles.optionBtn} ${styles.optionSelected}`;
                    }

                    return (
                      <button
                        key={optIdx}
                        className={optClass}
                        onClick={() => handleTestSelect(q.questionId, opt)}
                      >
                        {String.fromCharCode(65 + optIdx)}. {opt}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}

          {!testSubmitted ? (
            <button
              className={styles.offlineBtn}
              style={{ alignSelf: 'flex-start', background: '#4055D9', color: '#FFFFFF', padding: '12px 24px', fontSize: '14px' }}
              onClick={handleTestSubmit}
              disabled={Object.keys(testAnswers).length < (lessonPackage.checkpointTest?.length || 1)}
            >
              Submit Checkpoint Test
            </button>
          ) : !checkpointResult ? (
            <div style={{ padding: '24px', borderRadius: '8px', background: '#FAFAF8', border: '1px solid #D9DEEA' }}>
              <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#15233B', marginBottom: '8px' }}>
                Checking your answers…
              </h3>
              <p style={{ fontSize: '14px', color: '#4A5873', lineHeight: 1.6 }}>
                Each answer is being graded by SETU. This usually takes a moment.
              </p>
            </div>
          ) : (
            <div style={{ padding: '24px', borderRadius: '8px', background: '#E8F5F0', border: '1px solid #A3D9C4' }}>
              <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#23795B', marginBottom: '8px' }}>
                {checkpointResult.offline
                  ? 'Checkpoint saved offline'
                  : `Checkpoint: ${checkpointResult.correct} of ${checkpointResult.total} correct`}
              </h3>
              {checkpointResult.offline ? (
                <p style={{ fontSize: '14px', color: '#15233B', lineHeight: 1.6 }}>
                  The answers are stored on this device. Results appear after they sync.
                </p>
              ) : (
                <>
                  <p style={{ fontSize: '14px', color: '#15233B', lineHeight: 1.6 }}>
                    Mastery: {checkpointResult.mastery?.band || 'not enough evidence'}
                    {checkpointResult.mastery ? ` — ${checkpointResult.mastery.explanation}` : ''}
                  </p>
                  {checkpointResult.nextAction && (
                    <p style={{ fontSize: '14px', color: '#15233B', lineHeight: 1.6 }}>
                      {checkpointResult.nextAction.title}: {checkpointResult.nextAction.reason}
                    </p>
                  )}
                  <div style={{ marginTop: '16px' }}>
                    <button className={styles.offlineBtn} onClick={() => navigate('/')}>
                      Back to Desk
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
          {attemptErrors.checkpoint && (
            <div className={styles.feedbackWarning}>{attemptErrors.checkpoint}</div>
          )}
        </div>
      )}

      {/* PROVENANCE MODAL / DRAWER */}
      {activeCitation && (
        <div className={styles.drawerOverlay} onClick={() => setActiveCitation(null)}>
          <div className={styles.drawer} onClick={e => e.stopPropagation()}>
            <div className={styles.drawerHeader}>
              <h3 className={styles.drawerTitle}>Source Provenance</h3>
              <button className={styles.closeBtn} onClick={() => setActiveCitation(null)}>
                <X size={18} />
              </button>
            </div>
            <div>
              <div style={{ fontSize: '12px', fontWeight: 700, color: '#4055D9', textTransform: 'uppercase' }}>
                Source citation
              </div>
              <h4 style={{ fontSize: '16px', fontWeight: 700, marginTop: '4px', color: '#15233B' }}>
                {activeCitation.sourceTitle || 'Uploaded source'}
              </h4>
              <div style={{ fontSize: '13px', color: '#7E8B9F', marginTop: '2px' }}>
                Page {activeCitation.pageStart}
              </div>
            </div>

            <div style={{ padding: '16px', background: '#FAFAF8', borderRadius: '8px', border: '1px solid #D9DEEA', fontSize: '14px', lineHeight: 1.6, color: '#15233B' }}>
              {activeCitation.excerpt || activeCitation.text || 'Excerpt from the document you uploaded.'}
            </div>

            <div style={{ fontSize: '12px', color: '#4A5873' }}>
              ✓ Extracted from the document you uploaded.
            </div>
          </div>
        </div>
      )}

      {/* DOUBT DRAWER */}
      {doubtDrawerOpen && (
        <div className={styles.drawerOverlay} onClick={() => setDoubtDrawerOpen(false)}>
          <div className={styles.drawer} onClick={e => e.stopPropagation()}>
            <div className={styles.drawerHeader}>
              <h3 className={styles.drawerTitle}>Ask Academic Doubt</h3>
              <button className={styles.closeBtn} onClick={() => setDoubtDrawerOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: '13px', color: '#4A5873' }}>
              Ask any question about this lesson. Your answer is grounded in the document you uploaded{doubtPage ? ` (Page ${doubtPage})` : ''}.
            </p>

            <textarea
              className={styles.doubtInput}
              placeholder="e.g., Ask any question or clarification about this concept..."
              value={doubtText}
              onChange={e => setDoubtText(e.target.value)}
            />

            <button
              className={styles.offlineBtn}
              style={{ background: '#4055D9', color: '#FFFFFF', justifyContent: 'center' }}
              onClick={handleAskDoubt}
              disabled={submittingDoubt || !doubtText.trim()}
            >
              {submittingDoubt ? 'Resolving Citations...' : 'Submit Doubt'}
            </button>

            {doubtResponse && (
              <div style={{
                padding: '16px',
                borderRadius: '8px',
                background: doubtResponse.status === 'answered' ? '#E8F5F0' : '#FDF5EB',
                border: `1px solid ${doubtResponse.status === 'answered' ? '#A3D9C4' : '#F1CE9C'}`
              }}>
                <div style={{ fontWeight: 700, fontSize: '14px', color: doubtResponse.status === 'answered' ? '#23795B' : '#A65B12', marginBottom: '6px' }}>
                  {doubtResponse.status === 'answered'
                    ? 'Answer from your sources'
                    : doubtResponse.status === 'queued'
                      ? 'Stored in Offline Queue'
                      : 'Could not answer yet'}
                </div>
                <div style={{ fontSize: '13px', lineHeight: 1.6, color: '#15233B' }}>
                  {doubtResponse.answer || doubtResponse.message}
                </div>
                {doubtResponse.limitations === 'insufficient_source_evidence' && (
                  <div style={{ marginTop: '6px', fontSize: '12px', color: '#A65B12' }}>
                    The uploaded source does not contain enough evidence for a grounded answer.
                  </div>
                )}
                {doubtResponse.retryable && (
                  <button
                    type="button"
                    className={styles.offlineBtn}
                    style={{ marginTop: '10px' }}
                    onClick={() => lastDoubtPayload && void submitDoubt(lastDoubtPayload)}
                    disabled={submittingDoubt}
                  >
                    {submittingDoubt ? 'Retrying…' : 'Retry'}
                  </button>
                )}

                {doubtResponse.citations?.length > 0 && (
                  <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid #A3D9C4', fontSize: '12px', color: '#23795B' }}>
                    <strong>Citations: </strong>
                    {doubtResponse.citations.map((c: any, i: number) => (
                      <span key={i} style={{ marginRight: '8px' }}>Page {c.pageNumber || c.pageStart}</span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
