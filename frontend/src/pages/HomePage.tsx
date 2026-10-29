import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload } from 'lucide-react';
import { api, LearningPathItem, IngestionStatus, UserDocument } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { AuthModal } from '../components/AuthModal';
import { DynamicActivityIndicator, ActivityPhase } from '../components/DynamicActivityIndicator';
import { saveLessonOffline } from '../db/indexedDB';
import styles from './HomePage.module.css';

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { user, openTour } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [activePaths, setActivePaths] = useState<LearningPathItem[]>([]);
  const [materials, setMaterials] = useState<UserDocument[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [studySummary, setStudySummary] = useState<Awaited<ReturnType<typeof api.getStudySummary>> | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  // Classroom Join State
  const [joinCode, setJoinCode] = useState('');
  const [joinStatus, setJoinStatus] = useState<{ success?: boolean; message?: string } | null>(null);
  const [isJoining, setIsJoining] = useState(false);

  // Document Ingestion State
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [activityPhase, setActivityPhase] = useState<ActivityPhase>('extracting');
  const [activityDetail, setActivityDetail] = useState('');
  const [progressPercent, setProgressPercent] = useState<number | undefined>(undefined);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Outline Review Modal State
  const [reviewOutline, setReviewOutline] = useState<IngestionStatus | null>(null);
  const [isGeneratingPath, setIsGeneratingPath] = useState(false);
  const [pathGrade, setPathGrade] = useState<string>(user?.grade ? String(user.grade) : '');
  const [pathSubject, setPathSubject] = useState<string>(user?.subjectsInterested?.[0] || '');

  // Polling ref
  const pollIntervalRef = useRef<any>(null);
  const uploadRequestRef = useRef<XMLHttpRequest | null>(null);

  const fetchPaths = useCallback(async () => {
    if (!user) return;
    try {
      const res = await api.getLearningPaths();
      setActivePaths(res);
    } catch (err: any) {
      console.warn('Could not load active paths:', err);
    }
  }, [user]);

  const fetchMaterials = useCallback(async () => {
    if (!user) return;
    try {
      const docs = await api.listDocuments();
      setMaterials(docs);
    } catch (err: any) {
      console.warn('Could not load materials:', err);
    }
  }, [user]);

  const fetchSummary = useCallback(async () => {
    if (!user) return;
    try {
      setStudySummary(await api.getStudySummary());
    } catch {
      setStudySummary(null);
    }
  }, [user]);

  useEffect(() => {
    if (!user) {
      setActivePaths([]);
      setMaterials([]);
      setStudySummary(null);
      setErrorMessage(null);
      return;
    }
    fetchPaths();
    fetchMaterials();
    fetchSummary();
  }, [user, fetchPaths, fetchMaterials, fetchSummary]);

  useEffect(() => {
    if (!user) return;
    const waiting = activePaths.some((path) =>
      (path.lessons || []).some((lesson) => lesson.status !== 'ready' && lesson.status !== 'failed')
    );
    const reading = materials.some((item) =>
      ['uploading', 'stored', 'extracting', 'indexing', 'extracted'].includes(item.status)
    );
    if (!waiting && !reading) return;
    const timer = window.setInterval(() => {
      if (waiting) fetchPaths();
      if (reading) fetchMaterials();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [user, activePaths, materials, fetchPaths, fetchMaterials]);

  // Clean up polling timer
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  useEffect(() => {
    if (user?.grade && !pathGrade) setPathGrade(String(user.grade));
    if (user?.subjectsInterested?.[0] && !pathSubject) setPathSubject(user.subjectsInterested[0]);
  }, [user, pathGrade, pathSubject]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileUpload(e.target.files[0]);
    }
  };

  const applyPhase = (status: string, filename: string) => {
    setProgressPercent(undefined);
    if (status === 'stored' || status === 'uploading') {
      setActivityPhase('extracting');
      setActivityDetail(`Stored ${filename}. Waiting for the worker to read the file.`);
    } else if (status === 'extracting') {
      setActivityPhase('extracting');
      setActivityDetail('Reading your document');
    } else if (status === 'indexing' || status === 'extracted') {
      setActivityPhase('chunking');
      setActivityDetail('Indexing document');
    }
  };

  const pollDocumentStatus = (docId: string, initialFilename: string) => {
    applyPhase('stored', initialFilename);
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    pollIntervalRef.current = setInterval(async () => {
      try {
        const statusData = await api.getDocumentStatus(docId);
        setMaterials((current) => {
          const rest = current.filter((item) => item.documentId !== docId);
          return [{ ...statusData, id: docId, documentId: docId, filename: statusData.filename || initialFilename }, ...rest];
        });
        applyPhase(statusData.status, initialFilename);

        if (statusData.status === 'ready' || statusData.status === 'awaiting_review') {
          clearInterval(pollIntervalRef.current);
          setIsUploading(false);
          setReviewOutline(statusData);
          fetchMaterials();
        } else if (statusData.status === 'failed' || statusData.status === 'needs_ocr') {
          clearInterval(pollIntervalRef.current);
          setIsUploading(false);
          setErrorMessage(statusData.errorMessage || 'Document processing failed.');
          fetchMaterials();
        }
      } catch (err: any) {
        clearInterval(pollIntervalRef.current);
        setIsUploading(false);
        setErrorMessage(err.message || 'Status check failed.');
      }
    }, 2000);
  };

  const handleFileUpload = async (file: File) => {
    const MAX_SIZE = 50 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      setErrorMessage(`File exceeds the 50MB size limit (${(file.size / (1024 * 1024)).toFixed(1)}MB).`);
      return;
    }

    setErrorMessage(null);
    setIsUploading(true);
    setActivityPhase('extracting');
    setActivityDetail(`Uploading ${file.name}`);
    setProgressPercent(0);

    try {
      const data = await api.uploadDocument(file, (percent) => {
        setProgressPercent(percent);
        setActivityDetail(`Uploading ${file.name}`);
      }, uploadRequestRef);
      setProgressPercent(undefined);
      setMaterials((current) => {
        const rest = current.filter((item) => item.documentId !== data.documentId);
        return [{ ...data, id: data.documentId }, ...rest];
      });

      if (data.status === 'ready' || data.status === 'awaiting_review') {
        setIsUploading(false);
        const statusData = await api.getDocumentStatus(data.documentId);
        setReviewOutline(statusData);
      } else if (data.status === 'failed') {
        setIsUploading(false);
        setErrorMessage(data.errorMessage || 'Upload failed.');
      } else {
        pollDocumentStatus(data.documentId, file.name);
      }
    } catch (err: any) {
      setIsUploading(false);
      setProgressPercent(undefined);
      if (err?.message !== 'Upload cancelled.') {
        setErrorMessage(err.message || 'Upload failed.');
      }
    } finally {
      uploadRequestRef.current = null;
      fetchMaterials();
    }
  };

  const handleCreatePathFromOutline = async () => {
    if (!reviewOutline) return;
    if (!pathGrade || !pathSubject) return;
    setIsGeneratingPath(true);
    setErrorMessage(null);

    try {
      const res = await api.createLearningPath({
        documentId: reviewOutline.documentId,
        grade: Number(pathGrade),
        subjectId: pathSubject,
      });

      setReviewOutline(null);
      await fetchPaths();
      setIsGeneratingPath(false);
      if (!res.firstLessonId) {
        setErrorMessage('The learning path was created, but it has no lessons yet.');
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to create learning path.');
      setIsGeneratingPath(false);
    }
  };

  const openMaterialReview = async (documentId: string) => {
    setErrorMessage(null);
    try {
      const statusData = await api.getDocumentStatus(documentId);
      if (statusData.status === 'awaiting_review' || statusData.status === 'ready') {
        setReviewOutline(statusData);
      } else if (statusData.status === 'failed' || statusData.status === 'needs_ocr') {
        setErrorMessage(statusData.errorMessage || 'This file needs another attempt.');
      } else {
        setIsUploading(true);
        pollDocumentStatus(documentId, statusData.filename);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Could not load this document.');
    }
  };

  const retryMaterial = async (documentId: string) => {
    setErrorMessage(null);
    try {
      await api.retryDocument(documentId);
      setIsUploading(true);
      pollDocumentStatus(documentId, materials.find((item) => item.documentId === documentId)?.filename || 'document');
      fetchMaterials();
    } catch (err: any) {
      setErrorMessage(err.message || 'Could not retry this document.');
    }
  };

  const handleJoinClassroom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!joinCode.trim()) return;

    setIsJoining(true);
    setJoinStatus(null);
    try {
      const res = await api.joinClassroom(joinCode.trim());
      setJoinStatus({
        success: true,
        message: `Joined ${res.classroom?.name || 'the classroom'}.`
      });
      setJoinCode('');
    } catch (err: any) {
      setJoinStatus({
        success: false,
        message: err.message || 'Invalid join code.'
      });
    } finally {
      setIsJoining(false);
    }
  };

  const currentBook = materials.find((m) => m.documentId === selectedDocId) || materials[0];
  const plan = activePaths[0];
  const readyLesson = plan?.lessons?.find((lesson) => lesson.status === 'ready');
  const pace = studySummary?.pace || user?.accessibilityPreferences?.pace || 'steady';
  const paceLabel = pace === 'short' ? 'Short sessions' : pace === 'long' ? 'Longer sessions' : 'Steady pace';
  const bookStatus = currentBook?.status || '';
  const phaseRank = ['uploading', 'stored', 'extracting', 'extracted', 'indexing', 'awaiting_review', 'ready'].indexOf(bookStatus);
  const firstUnitsReady = (plan?.lessons || []).filter((lesson) => lesson.sequence <= 2 && lesson.status === 'ready').length;
  const laterQueued = (plan?.lessons || []).some((lesson) => lesson.sequence > 2 && lesson.status !== 'ready');

  const timeline = [
    { id: 'upload', label: 'Uploading the file', done: phaseRank > 0 || (!isUploading && !!currentBook), active: isUploading && typeof progressPercent === 'number' },
    { id: 'stored', label: 'Stored', done: phaseRank > 1, active: bookStatus === 'stored' },
    { id: 'read', label: 'Reading pages', done: phaseRank > 2, active: bookStatus === 'extracting' },
    { id: 'index', label: 'Indexing', done: phaseRank > 4, active: bookStatus === 'indexing' || bookStatus === 'extracted' },
    { id: 'first', label: 'First two units', done: firstUnitsReady === 2, active: !!plan && firstUnitsReady < 2 },
    { id: 'later', label: 'Remaining units', done: !!plan && (plan.lessons || []).length > 2 && !laterQueued, active: laterQueued },
  ];

  const downloadLesson = async (lessonId: string) => {
    if (!user) return;
    const pkg = await api.getLesson(lessonId);
    await saveLessonOffline(pkg, user.id);
  };

  const subjectLabel = (value: string) => {
    const base = value.replace(/^subject-/, '').replace(/-/g, ' ');
    return base.charAt(0).toUpperCase() + base.slice(1);
  };

  if (!user) {
    return (
      <div className={styles.welcomeContainer}>
        <section className={styles.welcomeHero}>
          <span className={styles.welcomeBadge}>Adaptive Learning Desk · Classes 6–10</span>
          <h1 className={styles.welcomeTitle}>Welcome to SETU</h1>
          <p className={styles.welcomeSubtitle}>
            A purpose-built, source-grounded learning desk for Indian school students. Learn directly from verified textbooks, practice with progressive hints, and test real mastery — online or offline.
          </p>
          <div className={styles.welcomeActions}>
            <button
              type="button"
              className={styles.welcomePrimaryBtn}
              onClick={openTour}
            >
              Get Started →
            </button>
            <button
              type="button"
              className={styles.welcomeSecondaryBtn}
              onClick={() => setIsAuthModalOpen(true)}
            >
              Sign In
            </button>
          </div>
        </section>

        <section className={styles.welcomeCards}>
          <article className={styles.welcomeCard}>
            <span className={styles.welcomeCardIcon}>📖</span>
            <h3 className={styles.welcomeCardTitle}>Source-Grounded Curriculum</h3>
            <p className={styles.welcomeCardDesc}>
              Upload textbooks up to 50MB and 300–500 pages. Every lesson concept, hint, and quiz question references exact textbook pages with full OCR and zero hallucinations.
            </p>
          </article>

          <article className={styles.welcomeCard}>
            <span className={styles.welcomeCardIcon}>⚡</span>
            <h3 className={styles.welcomeCardTitle}>Learn · Solve · Test Flow</h3>
            <p className={styles.welcomeCardDesc}>
              Step through foundational lessons, solve guided practice items with multi-tier hints, and complete diagnostic checkpoint tests that adapt to your understanding.
            </p>
          </article>

          <article className={styles.welcomeCard}>
            <span className={styles.welcomeCardIcon}>📡</span>
            <h3 className={styles.welcomeCardTitle}>Durable Offline Support</h3>
            <p className={styles.welcomeCardDesc}>
              Download lessons to your browser's IndexedDB. Study without internet, queue doubts offline, and sync automatically as soon as you reconnect.
            </p>
          </article>
        </section>

        <AuthModal isOpen={isAuthModalOpen} onClose={() => setIsAuthModalOpen(false)} />
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.greeting}>
        <div>
          <h1>{user ? `Hello, ${user.displayName}` : 'Your learning desk'}</h1>
          <p>{paceLabel}. The first two units are prepared while you start reading. The rest follow in the background.</p>
        </div>
        <form onSubmit={handleJoinClassroom} className={styles.joinForm}>
          <label htmlFor="join-code">Classroom code</label>
          <div>
            <input id="join-code" maxLength={15} value={joinCode} onChange={(e) => setJoinCode(e.target.value.toUpperCase())} placeholder="6 characters" />
            <button type="submit" disabled={isJoining || !joinCode}>{isJoining ? '…' : 'Join'}</button>
          </div>
          {joinStatus && <p className={joinStatus.success ? styles.ok : styles.bad}>{joinStatus.message}</p>}
        </form>
      </header>

      {errorMessage && <div className={styles.errorBanner} role="alert">{errorMessage}</div>}

      <section className={styles.split}>
        <article className={styles.panel}>
          <h2>Current book</h2>
          {materials.length > 1 && (
            <div style={{ display: 'flex', gap: '6px', marginBottom: '12px', overflowX: 'auto', paddingBottom: '4px' }}>
              {materials.map((m) => {
                const isSelected = (currentBook?.documentId === m.documentId);
                return (
                  <button
                    key={m.documentId}
                    type="button"
                    onClick={() => setSelectedDocId(m.documentId)}
                    style={{
                      padding: '4px 10px',
                      fontSize: '12px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-subtle)',
                      background: isSelected ? 'var(--brand-primary)' : 'var(--bg-canvas)',
                      color: isSelected ? '#ffffff' : 'var(--ink-primary)',
                      cursor: 'pointer',
                      fontWeight: 600,
                      whiteSpace: 'nowrap'
                    }}
                  >
                    {m.filename}
                  </button>
                );
              })}
            </div>
          )}
          {currentBook ? (
            <>
              <p className={styles.bookName}>{currentBook.filename}</p>
              <p className={styles.meta}>
                {currentBook.pageCount ? `${currentBook.pageCount} pages · ` : ''}
                {bookStatus.replace(/_/g, ' ')}
              </p>
              {currentBook.errorMessage && <p className={styles.bad}>{currentBook.errorMessage}</p>}
              <div className={styles.rowActions}>
                {(bookStatus === 'failed' || bookStatus === 'needs_ocr') && (
                  <button type="button" className={styles.secondary} onClick={() => retryMaterial(currentBook.documentId)}>Retry</button>
                )}
                {(bookStatus === 'awaiting_review' || bookStatus === 'ready') && !plan && (
                  <button type="button" className={styles.primary} disabled={isGeneratingPath} onClick={() => openMaterialReview(currentBook.documentId)}>
                    {isGeneratingPath ? 'Building the plan…' : 'Build my learning plan'}
                  </button>
                )}
              </div>
            </>
          ) : (
            <p className={styles.meta}>No book yet. Upload one and a plan is built from its units.</p>
          )}
        </article>

        <article className={styles.panel}>
          <h2>Units</h2>
          {plan?.lessons?.length ? (
            <ol className={styles.rail}>
              {plan.lessons.map((lesson) => (
                <li
                  key={lesson.id}
                  className={lesson.status === 'ready' ? styles.unitReady : styles.unitWait}
                  onClick={() => {
                    if (lesson.status === 'ready') {
                      navigate(`/lesson/${lesson.id}?pathId=${plan.id}`);
                    }
                  }}
                  style={{ cursor: lesson.status === 'ready' ? 'pointer' : 'default' }}
                >
                  <span>{lesson.sequence}. {lesson.title}</span>
                  <small>
                    {lesson.status === 'ready'
                      ? 'Open →'
                      : lesson.status === 'failed'
                        ? 'Could not prepare'
                        : lesson.sequence <= 2
                          ? 'Preparing'
                          : 'Queued'}
                  </small>
                </li>
              ))}
            </ol>
          ) : (
            <p className={styles.meta}>Units appear here after the book has been read and you build the plan.</p>
          )}
        </article>
      </section>

      <section className={styles.panel}>
        <h2>Continue</h2>
        {readyLesson && plan ? (
          <div className={styles.continueRow}>
            <div>
              <p className={styles.bookName}>{readyLesson.title}</p>
              <p className={styles.meta}>{studySummary?.focus || 'Start with this unit.'}</p>
            </div>
            <div className={styles.rowActions}>
              <button type="button" className={styles.primary} onClick={() => navigate(`/lesson/${readyLesson.id}?pathId=${plan.id}`)}>Read</button>
              <button type="button" className={styles.secondary} onClick={() => downloadLesson(readyLesson.id)}>Download</button>
            </div>
          </div>
        ) : (
          <p className={styles.meta}>The first units are not ready yet.</p>
        )}
      </section>

      <section className={styles.panel}>
        <h2>Upload</h2>
        <input ref={fileInputRef} type="file" hidden accept=".pdf,.docx,.pptx,.txt,.md,.png,.jpg,.jpeg" onChange={handleFileChange} />
        <button
          type="button"
          className={`${styles.drop} ${isDragging ? styles.dropOn : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload size={22} />
          <span>Choose a PDF, DOCX, PPTX, TXT, MD, or image. Up to 50MB.</span>
        </button>
        <ol className={styles.timeline}>
          {timeline.map((step) => (
            <li key={step.id} className={step.done ? styles.stepDone : step.active ? styles.stepNow : ''}>
              <span>{step.done ? 'Done' : step.active ? 'Now' : 'Waiting'}</span>
              {step.label}
              {step.id === 'upload' && step.active && typeof progressPercent === 'number' ? ` · ${progressPercent}%` : ''}
            </li>
          ))}
        </ol>
        {isUploading && (
          <DynamicActivityIndicator
            phase={activityPhase}
            detail={activityDetail}
            progressPercent={progressPercent}
            onCancel={() => {
              uploadRequestRef.current?.abort();
              if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
              setIsUploading(false);
              setProgressPercent(undefined);
            }}
          />
        )}
      </section>

      <section className={styles.panel}>
        <h2>Study record</h2>
        {studySummary && (studySummary.minutesStudied > 0 || studySummary.checkpointCount > 0) ? (
          <>
            <p className={styles.meta}>
              {studySummary.minutesStudied} minutes recorded
              {studySummary.readingTitle ? ` · Last opened: ${studySummary.readingTitle}` : ''}
              {studySummary.accuracyRate !== null ? ` · Checks ${Math.round(studySummary.accuracyRate * 100)}%` : ' · No checks yet'}
              {studySummary.improvement === 'improving' ? ' · Recent checks are stronger than earlier ones.' : ''}
              {studySummary.improvement === 'needs_support' ? ' · Recent checks were harder. Stay with the current unit.' : ''}
            </p>
            <div className={styles.heatmap} aria-label="Study time for the last seven days">
              {studySummary.heatmap.map((day) => (
                <div key={day.date} title={`${day.date}: ${Math.round(day.seconds / 60)} min`}>
                  <span style={{ height: `${Math.min(100, Math.max(day.seconds ? 12 : 0, Math.round(day.seconds / 36)))}%` }} />
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className={styles.meta}>Nothing has been studied yet. Time and check results appear after you open a unit.</p>
        )}
        {studySummary?.suggestions?.length ? (
          <ul className={styles.notes}>
            {studySummary.suggestions.map((item) => (
              <li key={item.id}>{item.note}</li>
            ))}
          </ul>
        ) : null}
      </section>

      {reviewOutline && (
        <div className={styles.modalBackdrop} role="dialog" aria-modal="true">
          <div className={styles.modalContent}>
            <h2>Plan from {reviewOutline.filename}</h2>
            <p className={styles.meta}>{reviewOutline.pageCount || 0} pages · {reviewOutline.chunkCount || 0} indexed sections</p>
            {reviewOutline.chapters && reviewOutline.chapters.length > 0 && (
              <ul className={styles.notes}>
                {reviewOutline.chapters.map((chapter, index) => (
                  <li key={index}>{chapter.title} · pages {chapter.pageStart}–{chapter.pageEnd}</li>
                ))}
              </ul>
            )}
            <div className={styles.contextRow}>
              <label className={styles.contextField}>
                Class
                <select value={pathGrade} onChange={(e) => setPathGrade(e.target.value)}>
                  <option value="">Select class</option>
                  {[6, 7, 8, 9, 10].map((grade) => (
                    <option key={grade} value={grade}>{`Class ${grade}`}</option>
                  ))}
                </select>
              </label>
              <label className={styles.contextField}>
                Subject
                <select value={pathSubject} onChange={(e) => setPathSubject(e.target.value)}>
                  <option value="">Select subject</option>
                  {(user?.subjectsInterested || []).map((subject) => (
                    <option key={subject} value={subject}>{subjectLabel(subject)}</option>
                  ))}
                </select>
              </label>
            </div>
            {(!pathGrade || !pathSubject) && (
              <p className={styles.contextNote}>Finish onboarding to set your class and subject.</p>
            )}
            <div className={styles.rowActions}>
              <button type="button" className={styles.secondary} onClick={() => setReviewOutline(null)}>Not now</button>
              <button type="button" className={styles.primary} disabled={isGeneratingPath || !pathGrade || !pathSubject} onClick={handleCreatePathFromOutline}>
                {isGeneratingPath ? 'Preparing the first units…' : 'Build my learning plan'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

