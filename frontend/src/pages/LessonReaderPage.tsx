import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { Download, Check, HelpCircle, X, ChevronRight, FileSearch, ArrowLeft, RefreshCw, Sparkles } from 'lucide-react';
import { VisualRenderer } from '../components/visuals/VisualRenderer';
import { CoachPopup } from '../components/CoachPopup';
import { Celebration } from '../components/Celebration';
import { db, saveLessonOffline, getOfflineLesson, queueDoubtOffline, queueAttemptOffline } from '../db/indexedDB';
import { api, type AttemptResult, type AttemptSubmission, type CoachCard, type LessonCoaching, type LessonCoachMoment } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useDialogFocus } from '../hooks/useDialogFocus';
import { syncManager } from '../services/syncManager';
import styles from './LessonReaderPage.module.css';

function momentToCard(moment: LessonCoachMoment, coaching: LessonCoaching): CoachCard {
  const keyPoint = coaching.moments.find((item) => item.kind === 'key_point');
  const source = coaching.moments.find(
    (item) => (item.kind === 'source_spotlight' || item.kind === 'fun_fact') && item.source
  );
  const tip = coaching.moments.find((item) => item.kind === 'study_tip');
  const base: CoachCard = {
    id: moment.id,
    scope: 'lesson',
    tone: moment.kind === 'challenge' ? 'retry' : 'celebrate',
    headline: moment.title,
    body: moment.body,
    keyPoint: keyPoint ? { title: keyPoint.title, body: keyPoint.body } : null,
    source:
      source && source.source
        ? {
            page: source.source.page,
            title: source.source.title,
            excerpt: source.body,
          }
        : null,
    studyTip: tip ? { title: tip.title, body: tip.body } : null,
  };
  if (moment.kind === 'key_point') {
    base.keyPoint = { title: moment.title, body: moment.body };
  }
  if ((moment.kind === 'source_spotlight' || moment.kind === 'fun_fact') && moment.source) {
    base.source = {
      page: moment.source.page,
      title: moment.source.title,
      excerpt: moment.body,
    };
  }
  if (moment.kind === 'study_tip') {
    base.studyTip = { title: moment.title, body: moment.body };
  }
  return base;
}

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
  const [coachCard, setCoachCard] = useState<CoachCard | null>(null);
  const [lessonCoach, setLessonCoach] = useState<LessonCoaching | null>(null);
  const [celebration, setCelebration] = useState<{ title: string; subtitle?: string } | null>(null);
  const coachShown = useRef<Set<string>>(new Set());
  const coachMomentIndex = useRef(0);

  const questionStartedAt = useRef<Record<string, number>>({});
  const readingStartedAt = useRef<number | null>(null);
  const citationDrawerRef = useRef<HTMLDivElement>(null);
  const doubtDrawerRef = useRef<HTMLDivElement>(null);

  useDialogFocus(citationDrawerRef, Boolean(activeCitation), () => setActiveCitation(null));
  useDialogFocus(doubtDrawerRef, doubtDrawerOpen, () => setDoubtDrawerOpen(false));

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
      void api
        .getLessonCoaching(lessonId)
        .then((coaching) => {
          setLessonCoach(coaching);
          if (!coachShown.current.has(lessonId) && coaching.moments.length > 0) {
            const auto =
              coaching.moments.find((moment) => moment.id === coaching.autoShowId) ||
              coaching.moments[0];
            coachShown.current.add(lessonId);
            setCoachCard(momentToCard(auto, coaching));
          }
        })
        .catch(() => undefined);
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
            answeredAt: answerPayload.answeredAt || new Date().toISOString(),
            limitations: answerPayload.limitations || null
          }
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

  const openCoachMoment = () => {
    if (!lessonCoach || lessonCoach.moments.length === 0) return;
    const index = coachMomentIndex.current % lessonCoach.moments.length;
    coachMomentIndex.current += 1;
    setCoachCard(momentToCard(lessonCoach.moments[index], lessonCoach));
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
      if (result.coaching) {
        setCoachCard(result.coaching);
      }
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
    const unanswered = lessonPackage.checkpointTest.some((q: any) => !testAnswers[q.questionId]?.trim());
    if (unanswered) return;
    setTestSubmitted(true);
    setCheckpointResult(null);
    setAttemptErrors(prev => ({ ...prev, checkpoint: '' }));
    const results: AttemptResult[] = [];
    let queuedOffline = false;

    for (const q of lessonPackage.checkpointTest) {
      const selected = testAnswers[q.questionId]?.trim();
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
          // A transport or grading failure is not a score. Keep the answers,
          // offer an honest retry, and never render "0 of N correct".
          setTestSubmitted(false);
          setCheckpointResult(null);
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
    const coachingCard = results.find((item) => item.coaching)?.coaching;
    if (coachingCard) setCoachCard(coachingCard);
    if (queuedOffline) {
      setCelebration({
        title: 'Checkpoint saved on this device',
        subtitle: 'It will be graded and added to your evidence when you reconnect.',
      });
    } else if (results.length > 0) {
      setCelebration({
        title:
          correct === lessonPackage.checkpointTest.length
            ? 'Checkpoint complete — every answer correct'
            : `Checkpoint complete · ${correct} of ${lessonPackage.checkpointTest.length}`,
        subtitle:
          last?.mastery?.explanation ||
          'Your answers are recorded and the next plan is already adapting.',
      });
    }
  };

  if (loading) {
    return (
      <div className={styles.loadingState}>
        <RefreshCw size={18} className="spin" />
        <span>Opening lesson package…</span>
      </div>
    );
  }

  if (!lessonPackage) {
    return (
      <div className={styles.container}>
        <div className={styles.emptyState}>
          <span className={styles.eyebrow}>Lesson</span>
          <h2 className={styles.emptyTitle}>{notReady ? 'Preparing this lesson' : 'Lesson not found'}</h2>
          <p className={styles.emptyText}>{readyMessage}</p>
          <button type="button" className={styles.offlineBtn} onClick={() => navigate('/')}>
            <ArrowLeft size={16} /> Return to Desk
          </button>
        </div>
      </div>
    );
  }

  const subjectLabel = String(lessonPackage.subjectId || '')
    .replace(/^subject-/, '')
    .replace(/-/g, ' ');

  return (
    <div className={styles.container}>
      {/* Top Header Card */}
      <div className={styles.headerCard}>
        <div className={styles.headerMain}>
          <div className={styles.metaRow}>
            <button type="button" className={styles.backButton} onClick={() => navigate('/')}>
              <ArrowLeft size={14} /> Desk
            </button>
            <span aria-hidden="true">·</span>
            <span className={styles.gradeBadge}>Class {lessonPackage.grade}</span>
            <span aria-hidden="true">·</span>
            <span className={styles.metaCode}>{subjectLabel}</span>
          </div>
          <h1 className={styles.lessonTitle}>{lessonPackage.title}</h1>
        </div>

        <div className={styles.actionsRow}>
          <button
            type="button"
            className={styles.offlineBtn}
            onClick={openCoachMoment}
            disabled={!lessonCoach || lessonCoach.moments.length === 0}
            title="Grounded key points, source lines and study tips from this lesson"
          >
            <Sparkles size={14} /> Coach
          </button>
          <button
            type="button"
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
            type="button"
            className={styles.offlineBtn}
            onClick={() => openDoubtDrawer()}
            title="Ask a doubt grounded strictly in the source material"
          >
            <HelpCircle size={14} /> Ask Doubt
          </button>
        </div>
        {saveOfflineError && (
          <p role="alert" className={styles.inlineError}>
            {saveOfflineError}
          </p>
        )}
      </div>

      {/* Learn / Solve / Test Tab Navigation */}
      <div className={styles.tabBar}>
        <button
          type="button"
          className={`${styles.tab} ${activeTab === 'learn' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('learn')}
        >
          1. Learn · Source explanation
        </button>
        <button
          type="button"
          className={`${styles.tab} ${activeTab === 'solve' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('solve')}
        >
          2. Solve · Guided practice
        </button>
        <button
          type="button"
          className={`${styles.tab} ${activeTab === 'test' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('test')}
        >
          3. Test · Checkpoint
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
                  <button
                    key={rIdx}
                    type="button"
                    className={styles.citationBadge}
                    onClick={() => setActiveCitation(ref)}
                    title={`Open source evidence from page ${ref.pageStart}`}
                  >
                    <FileSearch size={11} /> Page {ref.pageStart}
                  </button>
                ))}
              </p>

              <div className={styles.doubtPromptBar}>
                <span className={styles.doubtText}>Have a question on this section?</span>
                <button
                  type="button"
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
              <span className={styles.workedKicker}>Worked problem</span>
              <div className={styles.workedExamplePrompt}>{we.prompt}</div>
              {we.steps?.map((step: string, sIdx: number) => (
                <div key={sIdx} className={styles.workedExampleStep}>
                  <span className={styles.stepIndex}>{String(sIdx + 1).padStart(2, '0')}</span>
                  {step}
                </div>
              ))}
              <div className={styles.workedExampleAnswer}>
                <span className={styles.workedKicker}>Solution</span>
                {we.answer}
              </div>
            </div>
          ))}

          {/* Takeaways */}
          {lessonPackage.takeaways?.length > 0 && (
            <div className={styles.takeawaysBox}>
              <h3 className={styles.takeawaysTitle}>Key takeaways</h3>
              <ul className={styles.takeawaysList}>
                {lessonPackage.takeaways.map((t: string, i: number) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </div>
          )}

          <div className={styles.nextRow}>
            <button type="button" className={styles.offlineBtn} onClick={() => setActiveTab('solve')}>
              Proceed to Practice Problems <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* TAB 2: SOLVE (GUIDED PRACTICE) */}
      {activeTab === 'solve' && (
        <div className={styles.contentCard} aria-label="Guided practice">
          <div className={styles.sectionHead}>
            <h2 className={styles.sectionTitle}>Guided practice</h2>
            <p className={styles.sectionLede}>
              Work through these problems with progressive hints. Attempts are recorded for
              your teacher's evidence view.
            </p>
          </div>

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

                {q.options?.length ? (
                  <div className={styles.optionsList}>
                    {q.options.map((opt: string, idx: number) => {
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
                          type="button"
                          className={optClass}
                          onClick={() => handlePracticeSelect(q.questionId, opt)}
                          disabled={isSubmitted}
                        >
                          {String.fromCharCode(65 + idx)}. {opt}
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <label className={styles.textAnswer}>
                    <span className={styles.textAnswerLabel}>Your answer</span>
                    <input
                      className={styles.textAnswerInput}
                      type="text"
                      inputMode={q.type === 'numeric' ? 'decimal' : 'text'}
                      value={selected || ''}
                      onChange={(event) => handlePracticeSelect(q.questionId, event.target.value)}
                      placeholder={q.type === 'numeric' ? 'Enter a number' : 'Type your answer'}
                      disabled={isSubmitted}
                      autoComplete="off"
                    />
                  </label>
                )}

                {/* Progressive Hints */}
                {q.hints?.length > 0 && (
                  <div className={styles.hintsList}>
                    {q.hints.slice(0, hintCount).map((hint: string, hIdx: number) => (
                      <div key={hIdx} className={styles.hintBox}>
                        <strong>Hint {hIdx + 1}:</strong> {hint}
                      </div>
                    ))}
                    {!isSubmitted && hintCount < q.hints.length && (
                      <button
                        type="button"
                        className={styles.revealHintBtn}
                        onClick={() => handleRevealHint(q.questionId)}
                      >
                        Need help? Reveal hint {hintCount + 1}
                      </button>
                    )}
                  </div>
                )}

                {/* Submit Action & Feedback */}
                {!isSubmitted ? (
                  <button
                    type="button"
                    className={`${styles.offlineBtn} ${styles.submitBtn}`}
                    onClick={() => handlePracticeSubmit(q)}
                    disabled={!selected?.trim() || isSubmitting}
                  >
                    {isSubmitting ? 'Checking…' : 'Check Answer'}
                  </button>
                ) : (
                  <div
                    className={`${styles.feedbackBox} ${isCorrect ? styles.feedbackSuccess : styles.feedbackWarning}`}
                    role="status"
                  >
                    <strong>{isCorrect ? 'Correct.' : 'Incorrect.'}</strong> {result?.feedback}
                    {result?.nextAction?.title ? (
                      <div className={styles.feedbackNext}>
                        {result.nextAction.title}: {result.nextAction.reason}
                      </div>
                    ) : null}
                  </div>
                )}
                {attemptErrors[q.questionId] && (
                  <div className={styles.feedbackWarning} role="status">{attemptErrors[q.questionId]}</div>
                )}
              </div>
            );
          })}

          <div className={styles.betweenRow}>
            <button type="button" className={styles.offlineBtn} onClick={() => setActiveTab('learn')}>
              <ArrowLeft size={16} /> Back to Learn
            </button>
            <button type="button" className={styles.offlineBtn} onClick={() => setActiveTab('test')}>
              Start Checkpoint Test <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* TAB 3: TEST (CHECKPOINT ASSESSMENT) */}
      {activeTab === 'test' && (
        <div className={styles.contentCard} aria-label="Checkpoint test">
          <div className={styles.sectionHead}>
            <h2 className={styles.sectionTitle}>Checkpoint test</h2>
            <p className={styles.sectionLede}>
              Independent assessment without hints. Answer every question to calculate your
              mastery score from recorded evidence.
            </p>
          </div>

          {lessonPackage.checkpointTest?.map((q: any, qIdx: number) => {
            const selected = testAnswers[q.questionId];
            const result = attemptResults[q.questionId];
            return (
              <div key={q.questionId} className={styles.questionCard}>
                <div className={styles.questionPrompt}>
                  {qIdx + 1}. {q.prompt}
                </div>

                {q.options?.length ? (
                  <div className={styles.optionsList}>
                    {q.options.map((opt: string, optIdx: number) => {
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
                          type="button"
                          className={optClass}
                          onClick={() => handleTestSelect(q.questionId, opt)}
                          disabled={testSubmitted}
                        >
                          {String.fromCharCode(65 + optIdx)}. {opt}
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <label className={styles.textAnswer}>
                    <span className={styles.textAnswerLabel}>Your answer</span>
                    <input
                      className={styles.textAnswerInput}
                      type="text"
                      inputMode={q.type === 'numeric' ? 'decimal' : 'text'}
                      value={selected || ''}
                      onChange={(event) => handleTestSelect(q.questionId, event.target.value)}
                      placeholder={q.type === 'numeric' ? 'Enter a number' : 'Type your answer'}
                      disabled={testSubmitted}
                      autoComplete="off"
                    />
                  </label>
                )}
              </div>
            );
          })}

          {!testSubmitted ? (
            <>
              <button
                type="button"
                className={`${styles.offlineBtn} ${styles.submitBtn}`}
                onClick={handleTestSubmit}
                disabled={lessonPackage.checkpointTest?.some((q: any) => !testAnswers[q.questionId]?.trim())}
              >
                Submit Checkpoint Test
              </button>
              {attemptErrors.checkpoint && (
                <div className={styles.feedbackWarning} role="alert">
                  {attemptErrors.checkpoint} Your answers are still selected; submit again to retry.
                </div>
              )}
            </>
          ) : !checkpointResult ? (
            <div className={styles.resultBox}>
              <h3 className={styles.resultTitle}>Checking your answers…</h3>
              <p className={styles.resultText}>
                Each answer is being graded by SETU. This usually takes a moment.
              </p>
            </div>
          ) : checkpointResult.offline ? (
            <div className={`${styles.resultBox} ${styles.resultWarning}`}>
              <h3 className={styles.resultTitle}>Checkpoint saved offline</h3>
              <p className={styles.resultText}>
                The answers are stored on this device. Results appear after they sync.
              </p>
            </div>
          ) : (
            <div className={`${styles.resultBox} ${styles.resultSuccess}`}>
              <h3 className={styles.resultTitle}>
                Checkpoint: {checkpointResult.correct} of {checkpointResult.total} correct
              </h3>
              <p className={styles.resultText}>
                Mastery: {checkpointResult.mastery?.band.replace(/_/g, ' ') || 'not enough evidence'}
                {checkpointResult.mastery ? ` — ${checkpointResult.mastery.explanation}` : ''}
              </p>
              {checkpointResult.nextAction && (
                <p className={styles.resultText}>
                  {checkpointResult.nextAction.title}: {checkpointResult.nextAction.reason}
                </p>
              )}
              <div className={styles.nextRow}>
                <button type="button" className={styles.offlineBtn} onClick={() => navigate('/')}>
                  Back to Desk
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* PROVENANCE MODAL / DRAWER */}
      {activeCitation && (
        <div className={styles.drawerOverlay} onClick={() => setActiveCitation(null)}>
          <div
            className={styles.drawer}
            ref={citationDrawerRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-labelledby="provenance-title"
            onClick={e => e.stopPropagation()}
          >
            <div className={styles.drawerHeader}>
              <h3 id="provenance-title" className={styles.drawerTitle}>Source provenance</h3>
              <button
                type="button"
                className={styles.closeBtn}
                onClick={() => setActiveCitation(null)}
                aria-label="Close source provenance"
                autoFocus
              >
                <X size={18} />
              </button>
            </div>
            <div className={styles.drawerBody}>
              <span className={styles.drawerKicker}>Source citation</span>
              <h4 className={styles.sourceName}>
                {activeCitation.sourceTitle || 'Source title not recorded'}
              </h4>
              <div className={styles.sourcePage}>
                Page {activeCitation.pageStart}
                {activeCitation.pageEnd && activeCitation.pageEnd !== activeCitation.pageStart
                  ? `–${activeCitation.pageEnd}`
                  : ''}
              </div>
              {Array.isArray(activeCitation.headingPath) && activeCitation.headingPath.length > 0 && (
                <div className={styles.sourcePage}>{activeCitation.headingPath.join(' › ')}</div>
              )}
            </div>

            <div className={styles.excerptBox}>
              {activeCitation.excerpt || activeCitation.text ? (
                activeCitation.excerpt || activeCitation.text
              ) : (
                <span className={styles.excerptMissing}>
                  No excerpt was stored with this reference. It points to the page above in the
                  source you uploaded.
                </span>
              )}
            </div>

            <div className={styles.provenanceNote}>
              Extracted from the document you uploaded.
            </div>
          </div>
        </div>
      )}

      {/* DOUBT DRAWER */}
      {doubtDrawerOpen && (
        <div className={styles.drawerOverlay} onClick={() => setDoubtDrawerOpen(false)}>
          <div
            className={styles.drawer}
            ref={doubtDrawerRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-labelledby="doubt-title"
            onClick={e => e.stopPropagation()}
          >
            <div className={styles.drawerHeader}>
              <h3 id="doubt-title" className={styles.drawerTitle}>Ask a doubt</h3>
              <button
                type="button"
                className={styles.closeBtn}
                onClick={() => setDoubtDrawerOpen(false)}
                aria-label="Close doubt panel"
                autoFocus
              >
                <X size={18} />
              </button>
            </div>

            <p className={styles.drawerLede}>
              Ask any question about this lesson. Your answer is grounded in the document you
              uploaded{doubtPage ? ` (page ${doubtPage})` : ''}.
            </p>

            <label className={styles.inputLabel} htmlFor="doubt-question">Your question</label>
            <textarea
              id="doubt-question"
              className={styles.doubtInput}
              placeholder="e.g., Ask any question or clarification about this concept..."
              value={doubtText}
              onChange={e => setDoubtText(e.target.value)}
            />

            <button
              type="button"
              className={`${styles.offlineBtn} ${styles.submitBtn} ${styles.fullWidth}`}
              onClick={handleAskDoubt}
              disabled={submittingDoubt || !doubtText.trim()}
            >
              {submittingDoubt ? 'Resolving citations…' : 'Submit Doubt'}
            </button>

            {doubtResponse && (
              <div
                className={`${styles.doubtResponse} ${
                  doubtResponse.status === 'answered' ? styles.doubtAnswered : styles.doubtWarning
                }`}
              >
                <div
                  className={
                    doubtResponse.status === 'answered' ? styles.doubtTitleAnswered : styles.doubtTitleWarning
                  }
                >
                  {doubtResponse.status === 'answered'
                    ? doubtResponse.limitations === 'general_knowledge'
                      ? 'Answer from general knowledge'
                      : 'Answer from your sources'
                    : doubtResponse.status === 'queued'
                      ? 'Stored in Offline Queue'
                      : 'Could not answer yet'}
                </div>
                <div className={styles.doubtAnswer}>
                  {doubtResponse.answer || doubtResponse.message}
                </div>
                {doubtResponse.limitations === 'insufficient_source_evidence' && (
                  <div className={styles.limitationNote}>
                    The uploaded source does not contain enough evidence for a grounded answer.
                  </div>
                )}
                {doubtResponse.limitations === 'general_knowledge' && (
                  <div className={styles.limitationNote}>
                    General knowledge — not from your books. Add a source for page-cited answers.
                  </div>
                )}
                {doubtResponse.retryable && (
                  <button
                    type="button"
                    className={styles.retryBtn}
                    onClick={() => lastDoubtPayload && void submitDoubt(lastDoubtPayload)}
                    disabled={submittingDoubt}
                  >
                    {submittingDoubt ? 'Retrying…' : 'Retry'}
                  </button>
                )}

                {doubtResponse.citations?.length > 0 && (
                  <div className={styles.citationFootnote}>
                    <strong>Citations: </strong>
                    {doubtResponse.citations.map((c: any, i: number) => (
                      <span key={i} className={styles.citationRef}>
                        Page {c.pageNumber || c.pageStart}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
      <Celebration
        show={Boolean(celebration)}
        title={celebration?.title || ''}
        subtitle={celebration?.subtitle}
        onDone={() => setCelebration(null)}
      />
      <CoachPopup card={coachCard} onClose={() => setCoachCard(null)} />
    </div>
  );
};
