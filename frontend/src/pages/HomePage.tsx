import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Target, Brain, Clock3, Play, BookOpen } from 'lucide-react';
import { api, LearningPathItem, IngestionStatus, UserDocument, StudyPlan, LearnerInsights, SmartCheckQuestion, AttemptResult } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { ActivityPhase } from '../components/DynamicActivityIndicator';
import { saveLessonOffline } from '../db/indexedDB';
import { useDialogFocus } from '../hooks/useDialogFocus';
import { useTaxonomy } from '../hooks/useTaxonomy';
import { WelcomeHero } from './home/WelcomeHero';
import { PlanReviewDialog } from './home/PlanReviewDialog';
import { AddSourcePanel } from './home/AddSourcePanel';
import { StudyRecordPanel } from './home/StudyRecordPanel';
import styles from './HomePage.module.css';

const normalizeLabel = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const subjectHue = (subjectId: string): number => {
  let hash = 0;
  for (let i = 0; i < subjectId.length; i += 1) {
    hash = (hash * 31 + subjectId.charCodeAt(i)) % 360;
  }
  return hash;
};

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { user, openTour } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const taxonomy = useTaxonomy(Boolean(user));

  const [activePaths, setActivePaths] = useState<LearningPathItem[]>([]);
  const [materials, setMaterials] = useState<UserDocument[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [studySummary, setStudySummary] = useState<Awaited<ReturnType<typeof api.getStudySummary>> | null>(null);
  const [studyPlan, setStudyPlan] = useState<StudyPlan | null>(null);
  const [insights, setInsights] = useState<LearnerInsights | null>(null);
  const [smartQuestion, setSmartQuestion] = useState<SmartCheckQuestion | null>(null);
  const [smartSelected, setSmartSelected] = useState('');
  const [smartResult, setSmartResult] = useState<AttemptResult | null>(null);
  const [smartAnswered, setSmartAnswered] = useState<string[]>([]);
  const [smartMessage, setSmartMessage] = useState('');
  const [smartBusy, setSmartBusy] = useState(false);
  const [smartDone, setSmartDone] = useState(false);
  const [respondingSuggestionId, setRespondingSuggestionId] = useState<string | null>(null);
  const [suggestionErrors, setSuggestionErrors] = useState<Record<string, string>>({});
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [downloadingLessonId, setDownloadingLessonId] = useState<string | null>(null);
  const [downloadNotice, setDownloadNotice] = useState<{ kind: 'ok' | 'error'; message: string } | null>(null);

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
  const [loadFailures, setLoadFailures] = useState({ paths: false, materials: false });
  const [isDeskLoading, setIsDeskLoading] = useState(false);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);

  // Outline Review Modal State
  const [reviewOutline, setReviewOutline] = useState<IngestionStatus | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [isGeneratingPath, setIsGeneratingPath] = useState(false);
  const [pathGrade, setPathGrade] = useState<string>(user?.grade ? String(user.grade) : '');
  const [pathSubject, setPathSubject] = useState<string>(user?.subjectsInterested?.[0] || '');

  // Polling ref
  const pollIntervalRef = useRef<any>(null);
  const uploadRequestRef = useRef<XMLHttpRequest | null>(null);
  const autoSubjectDoc = useRef<string | null>(null);

  const suggestedSubjectId = useMemo(() => {
    if (!reviewOutline || taxonomy.subjects.length === 0) return '';
    const title = normalizeLabel(reviewOutline.filename);
    let best: { id: string; length: number } | null = null;

    for (const subject of taxonomy.subjects) {
      const labels = [
        subject.canonicalName,
        subject.name,
        subject.code.replace(/^subject-/, '').replace(/-/g, ' '),
      ];
      for (const label of labels) {
        const candidate = normalizeLabel(label || '');
        if (candidate.length < 3) continue;
        const matches = new RegExp(`(^| )${escapeRegExp(candidate)}( |$)`).test(title);
        if (matches && (!best || candidate.length > best.length)) {
          best = { id: subject.id, length: candidate.length };
        }
      }
    }

    return best?.id || '';
  }, [reviewOutline, taxonomy.subjects]);
  const planDialogRef = useRef<HTMLDivElement>(null);

  useDialogFocus(planDialogRef, Boolean(reviewOutline), () => {
    if (!isGeneratingPath) {
      setReviewOutline(null);
      setReviewError(null);
    }
  });

  const fetchPaths = useCallback(async () => {
    if (!user) return;
    try {
      const res = await api.getLearningPaths();
      setActivePaths(res);
      setLoadFailures((prev) => (prev.paths ? { ...prev, paths: false } : prev));
    } catch (err: any) {
      console.warn('Could not load active paths:', err);
      setLoadFailures((prev) => (prev.paths ? prev : { ...prev, paths: true }));
    }
  }, [user]);

  const fetchMaterials = useCallback(async () => {
    if (!user) return;
    try {
      const docs = await api.listDocuments();
      setMaterials(docs);
      setLoadFailures((prev) => (prev.materials ? { ...prev, materials: false } : prev));
    } catch (err: any) {
      console.warn('Could not load materials:', err);
      setLoadFailures((prev) => (prev.materials ? prev : { ...prev, materials: true }));
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

  const fetchPlanning = useCallback(async () => {
    if (!user) return;
    const [planResult, insightResult] = await Promise.allSettled([
      api.getStudyPlan(),
      api.getLearnerInsights(),
    ]);
    if (planResult.status === 'fulfilled') setStudyPlan(planResult.value);
    if (insightResult.status === 'fulfilled') setInsights(insightResult.value);
  }, [user]);

  const respondToSuggestion = async (id: string, decision: 'accept' | 'dismiss') => {
    setRespondingSuggestionId(id);
    setSuggestionErrors((prev) => ({ ...prev, [id]: '' }));
    try {
      await api.respondToRecommendation(id, decision);
      await fetchSummary();
    } catch (err: unknown) {
      setSuggestionErrors((prev) => ({
        ...prev,
        [id]: err instanceof Error ? err.message : 'SETU could not record your response.',
      }));
    } finally {
      setRespondingSuggestionId(null);
    }
  };

  useEffect(() => {
    if (!user) {
      setActivePaths([]);
      setMaterials([]);
      setStudySummary(null);
      setStudyPlan(null);
      setInsights(null);
      setErrorMessage(null);
      setSmartQuestion(null);
      setSmartResult(null);
      setSmartAnswered([]);
      setSmartDone(false);
      setLoadFailures({ paths: false, materials: false });
      setIsDeskLoading(false);
      return;
    }
    let active = true;
    setIsDeskLoading(true);
    void Promise.allSettled([fetchPaths(), fetchMaterials(), fetchSummary(), fetchPlanning()]).finally(() => {
      if (active) setIsDeskLoading(false);
    });
    return () => {
      active = false;
    };
  }, [user, fetchPaths, fetchMaterials, fetchSummary, fetchPlanning]);

  const retryWorkspace = async () => {
    setIsDeskLoading(true);
    await Promise.allSettled([fetchPaths(), fetchMaterials(), fetchSummary(), fetchPlanning()]);
    setIsDeskLoading(false);
  };


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
      if (waiting) {
        void fetchPaths();
        void fetchPlanning();
      }
      if (reading) fetchMaterials();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [user, activePaths, materials, fetchPaths, fetchMaterials, fetchPlanning]);

  // Clean up polling timer
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  useEffect(() => {
    if (user?.grade && !pathGrade) setPathGrade(String(user.grade));
    const catalogIds = taxonomy.subjects.map((subject) => subject.id);
    const interests = user?.subjectsInterested || [];
    const currentIsValid = catalogIds.includes(pathSubject) || interests.includes(pathSubject);
    if (!currentIsValid) {
      const preferred = interests.find((value) => catalogIds.includes(value));
      const onlyOption = taxonomy.subjects.length === 1 ? taxonomy.subjects[0].id : '';
      setPathSubject(preferred || onlyOption);
    }
  }, [user, taxonomy.subjects, pathGrade, pathSubject]);

  useEffect(() => {
    if (!reviewOutline || taxonomy.loading || taxonomy.subjects.length === 0) return;
    if (autoSubjectDoc.current === reviewOutline.documentId) return;
    autoSubjectDoc.current = reviewOutline.documentId;
    if (suggestedSubjectId && suggestedSubjectId !== pathSubject) {
      setPathSubject(suggestedSubjectId);
    }
  }, [reviewOutline, taxonomy.loading, taxonomy.subjects, suggestedSubjectId, pathSubject]);

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

  const applyPhase = (status: string, filename: string, progressMessage?: string | null) => {
    setProgressPercent(undefined);
    if (status === 'stored' || status === 'uploading') {
      setActivityPhase('extracting');
      setActivityDetail(progressMessage || `Stored ${filename}. Waiting for the processing worker.`);
    } else if (status === 'extracting') {
      setActivityPhase('extracting');
      setActivityDetail(progressMessage || 'Reading your document');
    } else if (status === 'indexing' || status === 'extracted') {
      setActivityPhase('chunking');
      setActivityDetail(progressMessage || 'Indexing document');
    }
  };

  const openReview = (status: IngestionStatus) => {
    setReviewError(null);
    setReviewOutline(status);
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
        applyPhase(statusData.status, initialFilename, statusData.progressMessage);

        if (statusData.status === 'ready' || statusData.status === 'awaiting_review') {
          clearInterval(pollIntervalRef.current);
          setIsUploading(false);
          openReview(statusData);
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
    setUploadNotice(null);
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
      if (data.deduplicated) {
        setUploadNotice('This file is already in your library, so SETU reused the existing copy instead of storing a duplicate.');
      }
      setMaterials((current) => {
        const rest = current.filter((item) => item.documentId !== data.documentId);
        return [{ ...data, id: data.documentId }, ...rest];
      });

      if (data.status === 'ready' || data.status === 'awaiting_review') {
        setIsUploading(false);
        const statusData = await api.getDocumentStatus(data.documentId);
        openReview(statusData);
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
    if (!reviewOutline || !reviewOutline.canBuildPath) return;
    if (!pathGrade || !pathSubject) return;
    setIsGeneratingPath(true);
    setReviewError(null);
    setErrorMessage(null);

    try {
      const res = await api.createLearningPath({
        documentId: reviewOutline.documentId,
        grade: Number(pathGrade),
        subjectId: pathSubject,
      });

      setReviewOutline(null);
      await fetchPaths();
      void fetchPlanning();
      setIsGeneratingPath(false);
      if (!res.firstLessonId) {
        setErrorMessage('The learning path was created, but it has no lessons yet.');
      }
    } catch (err: any) {
      setReviewError(err.message || 'SETU could not create a learning plan from this document.');
      setIsGeneratingPath(false);
    }
  };

  const openMaterialReview = async (documentId: string) => {
    setErrorMessage(null);
    try {
      const statusData = await api.getDocumentStatus(documentId);
      if (statusData.status === 'awaiting_review' || statusData.status === 'ready') {
        openReview(statusData);
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

  const startSmartCheck = async () => {
    setSmartBusy(true);
    setSmartMessage('');
    setSmartResult(null);
    setSmartDone(false);
    setSmartAnswered([]);
    setSmartSelected('');
    try {
      const res = await api.getNextSmartQuestion([]);
      if (res.state === 'question' && res.question) {
        setSmartQuestion(res.question);
        setSmartMessage(res.message);
      } else {
        setSmartQuestion(null);
        setSmartDone(true);
        setSmartMessage(res.message);
      }
    } catch (err: any) {
      setSmartQuestion(null);
      setSmartMessage(err?.message || 'SETU could not start the check.');
    } finally {
      setSmartBusy(false);
    }
  };

  const submitSmartAnswer = async () => {
    if (!smartQuestion || !smartSelected.trim()) return;
    setSmartBusy(true);
    try {
      const result = await api.submitAttempt({
        lessonVersionId: smartQuestion.lessonVersionId,
        questionKey: smartQuestion.questionKey,
        response: smartSelected.trim(),
        hintLevel: 0,
        hintsUsed: [],
        elapsedSeconds: 0,
        attemptKind: 'practice',
        syncIdempotencyKey: `smart-check-${smartQuestion.questionKey}-${Date.now()}`,
      });
      setSmartResult(result);
      setSmartAnswered((prev) =>
        prev.includes(smartQuestion.questionKey) ? prev : [...prev, smartQuestion.questionKey]
      );
      void fetchPlanning();
      void fetchSummary();
    } catch (err: any) {
      setSmartMessage(err?.message || 'That answer could not be graded. Try again.');
    } finally {
      setSmartBusy(false);
    }
  };

  const advanceSmartCheck = async () => {
    setSmartBusy(true);
    setSmartMessage('');
    try {
      const res = await api.getNextSmartQuestion(smartAnswered);
      if (res.state === 'question' && res.question) {
        setSmartQuestion(res.question);
        setSmartSelected('');
        setSmartResult(null);
        setSmartMessage(res.message);
      } else {
        setSmartQuestion(null);
        setSmartDone(true);
        setSmartMessage(res.message);
        void fetchPlanning();
      }
    } catch (err: any) {
      setSmartMessage(err?.message || 'SETU could not load the next question.');
    } finally {
      setSmartBusy(false);
    }
  };

  const explicitBook = materials.find((m) => m.documentId === selectedDocId);
  const plannedBook = materials.find((m) =>
    activePaths.some((path) => path.documentId === m.documentId)
  );
  const currentBook =
    explicitBook || (selectedDocId ? materials[0] : plannedBook || materials[0]);
  const matchingPlan = activePaths.find(
    (path) => path.documentId && path.documentId === currentBook?.documentId
  );
  const legacyPaths =
    activePaths.length > 0 && activePaths.every((path) => !path.documentId);
  const plan = matchingPlan || (legacyPaths ? activePaths[0] : undefined);
  const readyLesson = plan?.lessons?.find((lesson) => lesson.status === 'ready');
  const pace = studySummary?.pace || user?.accessibilityPreferences?.pace || null;
  const paceLabel =
    pace === 'short'
      ? 'Short sessions'
      : pace === 'long'
        ? 'Longer sessions'
        : pace === 'steady'
          ? 'Steady pace'
          : 'No pace set';
  const bookStatus = currentBook?.status || '';
  const pipelineRank = ['stored', 'extracting', 'indexing', 'awaiting_review', 'ready'].indexOf(bookStatus);
  const lessons = plan?.lessons || [];
  const readyCount = lessons.filter((lesson) => lesson.status === 'ready').length;
  const preparingCount = lessons.filter(
    (lesson) => lesson.status === 'queued' || lesson.status === 'generating'
  ).length;
  const failedCount = lessons.filter((lesson) => lesson.status === 'failed').length;

  const deskSummary = plan
    ? [
        lessons.length > 0 ? `${readyCount} of ${lessons.length} units ready` : 'No units yet',
        preparingCount > 0 ? `${preparingCount} being prepared` : null,
        failedCount > 0 ? `${failedCount} could not be prepared` : null,
      ]
        .filter(Boolean)
        .join(' · ')
    : materials.length > 0
      ? 'No learning plan for this source yet.'
      : 'Add a source to build your first learning plan.';

  const pipeline = [
    { id: 'upload', label: 'Upload the file' },
    { id: 'stored', label: 'Store the original' },
    { id: 'read', label: 'Read the pages' },
    { id: 'index', label: 'Index the passages' },
    { id: 'review', label: 'Review the plan' },
  ];
  const activePipelineIndex = isUploading
    ? typeof progressPercent === 'number'
      ? 0
      : pipelineRank >= 0
        ? pipelineRank + 1
        : 0
    : plan
      ? pipeline.length
      : pipelineRank >= 0
        ? pipelineRank + 1
        : -1;
  const showPipelineProgress = isUploading || Boolean(currentBook);

  const lessonStatusLabel = (status: string): string => {
    switch (status) {
      case 'ready':
        return 'Open →';
      case 'generating':
        return 'Being prepared now';
      case 'queued':
        return 'Waiting in the queue';
      case 'failed':
        return 'Could not be prepared';
      default:
        return `Status: ${status}`;
    }
  };

  const documentStatusLabel = (status: string): string => {
    switch (status) {
      case 'stored':
        return 'Stored, waiting for the worker';
      case 'extracting':
        return 'Reading pages';
      case 'indexing':
        return 'Indexing passages';
      case 'awaiting_review':
        return 'Ready for your review';
      case 'ready':
        return 'Plan built';
      case 'needs_ocr':
        return 'Some pages could not be read';
      case 'failed':
        return 'Processing failed';
      default:
        return status ? status.replace(/_/g, ' ') : 'Status not reported';
    }
  };

  const downloadLesson = async (lessonId: string) => {
    if (!user) return;
    setDownloadingLessonId(lessonId);
    setDownloadNotice(null);
    try {
      const pkg = await api.getLesson(lessonId);
      await saveLessonOffline(pkg, user.id);
      setDownloadNotice({ kind: 'ok', message: 'Saved for offline reading.' });
    } catch {
      setDownloadNotice({
        kind: 'error',
        message: 'Could not save this lesson. Try again when you are online.',
      });
    } finally {
      setDownloadingLessonId(null);
    }
  };

  const subjectOptions = useMemo(() => {
    if (taxonomy.subjects.length > 0) {
      return taxonomy.subjects.map((subject) => ({
        id: subject.id,
        label: subject.canonicalName || subject.name,
      }));
    }
    return (user?.subjectsInterested || []).map((value) => ({
      id: value,
      label: value.replace(/^subject-/, '').replace(/-/g, ' '),
    }));
  }, [taxonomy.subjects, user?.subjectsInterested]);

  if (!user) {
    return (
      <WelcomeHero
        openTour={openTour}
        isAuthModalOpen={isAuthModalOpen}
        onOpenAuth={() => setIsAuthModalOpen(true)}
        onCloseAuth={() => setIsAuthModalOpen(false)}
      />
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <span className={styles.heroOrb} aria-hidden="true" />
        <span className={styles.heroRing} aria-hidden="true" />
        <div className={styles.heroCopy}>
          <span className={styles.heroKicker}>Your learning desk</span>
          <h1>Hello, {user.displayName}.</h1>
          <p>
            {deskSummary}
            {pace ? ` · ${paceLabel}` : ''}
          </p>
          <div className={styles.heroStats}>
            <span>
              <BookOpen size={14} /> {materials.length} {materials.length === 1 ? 'source' : 'sources'}
            </span>
            <span>
              <Target size={14} /> {studyPlan?.taskCount ?? 0} {(studyPlan?.taskCount ?? 0) === 1 ? 'task' : 'tasks'}
            </span>
            <span>
              <Sparkles size={14} /> {readyCount} ready {readyCount === 1 ? 'unit' : 'units'}
            </span>
          </div>
        </div>
        <div className={styles.heroAside}>
          <form onSubmit={handleJoinClassroom} className={styles.joinForm}>
            <label htmlFor="join-code">Join a classroom</label>
            <div>
              <input id="join-code" maxLength={15} value={joinCode} onChange={(e) => setJoinCode(e.target.value.toUpperCase())} placeholder="6-character code" />
              <button type="submit" disabled={isJoining || !joinCode}>{isJoining ? '…' : 'Join'}</button>
            </div>
            {joinStatus ? (
              <p className={joinStatus.success ? styles.ok : styles.bad}>{joinStatus.message}</p>
            ) : (
              <p className={styles.heroHint}>Use the code your teacher shared.</p>
            )}
          </form>
        </div>
      </header>

      {errorMessage && <div className={styles.errorBanner} role="alert">{errorMessage}</div>}
      {(loadFailures.paths || loadFailures.materials) && (
        <div className={styles.errorBanner} role="alert">
          <span>
            {loadFailures.materials && loadFailures.paths
              ? 'SETU could not load your books or your learning plan.'
              : loadFailures.materials
                ? 'SETU could not load your books.'
                : 'SETU could not load your learning plan.'}{' '}
            Check your connection, then retry.
          </span>
          <button
            type="button"
            className={styles.bannerAction}
            onClick={() => void retryWorkspace()}
            disabled={isDeskLoading}
          >
            {isDeskLoading ? 'Retrying…' : 'Retry'}
          </button>
        </div>
      )}

      <section className={styles.deskGrid} aria-label="Adaptive plan and learner understanding">
        <article className={`${styles.panel} ${styles.planPanel}`}>
          <div className={styles.panelHead}>
            <h2>Your adaptive plan</h2>
            {studyPlan && (
              <span className={styles.sectionNote}>
                {studyPlan.bookCount} {studyPlan.bookCount === 1 ? 'book' : 'books'} ·{' '}
                {studyPlan.taskCount} {studyPlan.taskCount === 1 ? 'task' : 'tasks'}
              </span>
            )}
          </div>
          {studyPlan ? (
            <>
              <p className={styles.planSummary}>{studyPlan.summary}</p>
              {studyPlan.tasks.length > 0 ? (
                <ol className={styles.planList}>
                  {studyPlan.tasks.map((task) => (
                    <li
                      key={task.id}
                      data-subject={task.subjectId}
                      style={
                        {
                          '--task-hue': task.subjectId ? subjectHue(task.subjectId) : 252,
                        } as React.CSSProperties
                      }
                      className={`${styles.planTask} ${
                        task.kind === 'remediate' || task.kind === 'review'
                          ? styles.planTaskFocus
                          : task.kind === 'stretch'
                            ? styles.planTaskStretch
                            : ''
                      }`}
                    >
                      <span className={styles.planSlot}>{task.slot}</span>
                      <div className={styles.planBody}>
                        <div className={styles.planTaskHead}>
                          <strong>{task.title}</strong>
                          <span className={styles.planSubject}>{task.subjectLabel}</span>
                        </div>
                        <p>{task.reason}</p>
                        <div className={styles.planTaskFoot}>
                          <span>{task.pathTitle}</span>
                          {task.lessonId && (
                            <button
                              type="button"
                              className={styles.planAction}
                              onClick={() =>
                                navigate(`/lesson/${task.lessonId}?pathId=${task.pathId}`)
                              }
                            >
                              {task.actionLabel} →
                            </button>
                          )}
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className={styles.meta}>
                  {studyPlan.state === 'preparing'
                    ? 'Units are still being prepared. The plan fills in as soon as the first unit is ready.'
                    : 'No task is available from recorded evidence yet. Add a book or answer a question.'}
                </p>
              )}
              {studyPlan.books.length > 0 && (
                <div className={styles.bookMix} aria-label="Books in this plan">
                  {studyPlan.books.map((book) => (
                    <span
                      key={book.pathId}
                      className={styles.bookMixItem}
                      style={
                        {
                          '--task-hue': book.subjectId ? subjectHue(book.subjectId) : 252,
                        } as React.CSSProperties
                      }
                    >
                      <span className={styles.bookMixDot} aria-hidden="true" />
                      <span>{book.subjectLabel}</span>
                      {book.readyLessons}/{book.totalLessons} ready
                    </span>
                  ))}
                </div>
              )}
            </>
          ) : (
            <p className={styles.meta}>Reading your books and evidence to build one plan…</p>
          )}
        </article>

        <article className={styles.panel}>
          <div className={styles.panelHead}>
            <h2>How you learn</h2>
            {insights && (
              <span className={styles.sectionNote}>
                {insights.confidence === 'none' ? 'No evidence yet' : `${insights.confidence} confidence`}
              </span>
            )}
          </div>
          {insights ? (
            <>
              <p className={styles.insightSummary}>{insights.summary}</p>
              <div className={styles.insightGrid}>
                <div className={styles.insightTile}>
                  <span><Target size={13} /> Accuracy</span>
                  <strong>{insights.accuracy.overall === null ? '—' : `${insights.accuracy.overall}%`}</strong>
                  <small>{insights.accuracy.trend.replace(/_/g, ' ')}</small>
                </div>
                <div className={styles.insightTile}>
                  <span><Clock3 size={13} /> Best window</span>
                  <strong>{insights.routine.bestWindow?.label || '—'}</strong>
                  <small>{insights.routine.consistencyLabel}</small>
                </div>
                <div className={styles.insightTile}>
                  <span><Brain size={13} /> Pace</span>
                  <strong>
                    {insights.pace.medianAnswerSeconds === null
                      ? '—'
                      : `${insights.pace.medianAnswerSeconds}s`}
                  </strong>
                  <small>{insights.pace.label}</small>
                </div>
                <div className={styles.insightTile}>
                  <span><Sparkles size={13} /> Hint use</span>
                  <strong>{insights.hintReliance.hintRate === null ? '—' : `${insights.hintReliance.hintRate}%`}</strong>
                  <small>{insights.hintReliance.label}</small>
                </div>
              </div>
              {(insights.mastery.strengths.length > 0 || insights.mastery.focusAreas.length > 0) && (
                <div className={styles.focusRows}>
                  {insights.mastery.strengths[0] && (
                    <p>
                      <span className={styles.focusTag}>Strength</span>
                      {insights.mastery.strengths[0].label}
                      {insights.mastery.strengths[0].score !== null
                        ? ` · ${insights.mastery.strengths[0].score}%`
                        : ''}
                    </p>
                  )}
                  {insights.mastery.focusAreas[0] && (
                    <p>
                      <span className={`${styles.focusTag} ${styles.focusTagWatch}`}>Focus</span>
                      {insights.mastery.focusAreas[0].label}
                      {insights.mastery.focusAreas[0].score !== null
                        ? ` · ${insights.mastery.focusAreas[0].score}%`
                        : ''}
                    </p>
                  )}
                </div>
              )}
              {insights.habits.length > 0 && (
                <ul className={styles.habitList}>
                  {insights.habits.slice(0, 3).map((habit) => (
                    <li
                      key={habit.id}
                      className={
                        habit.tone === 'watch'
                          ? styles.habitWatch
                          : habit.tone === 'positive'
                            ? styles.habitPositive
                            : styles.habitNeutral
                      }
                    >
                      <strong>{habit.title}</strong>
                      <span>{habit.detail}</span>
                    </li>
                  ))}
                </ul>
              )}
              <p className={styles.insightEvidence}>{insights.confidenceDetail}</p>

              <div className={styles.smartCheck}>
                <div className={styles.smartHead}>
                  <strong>Smart check</strong>
                  <span>Fewest questions to find the next gap</span>
                </div>
                {smartQuestion ? (
                  <div className={styles.smartBody}>
                    <p className={styles.smartWhy}>{smartMessage || smartQuestion.why}</p>
                    <div className={styles.smartMeta}>
                      {smartQuestion.subjectLabel} · {smartQuestion.conceptLabel} ·{' '}
                      {smartQuestion.mastery.band.replace(/_/g, ' ')}
                    </div>
                    <p className={styles.smartPrompt}>{smartQuestion.prompt}</p>
                    {smartQuestion.options.length > 0 ? (
                      <div className={styles.smartOptions}>
                        {smartQuestion.options.map((option) => (
                          <button
                            key={option}
                            type="button"
                            className={
                              smartSelected === option
                                ? `${styles.smartOption} ${styles.smartOptionOn}`
                                : styles.smartOption
                            }
                            onClick={() => setSmartSelected(option)}
                            disabled={Boolean(smartResult)}
                          >
                            {option}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <input
                        className={styles.smartInput}
                        value={smartSelected}
                        onChange={(event) => setSmartSelected(event.target.value)}
                        placeholder="Type your answer"
                        disabled={Boolean(smartResult)}
                      />
                    )}
                    {smartResult ? (
                      <div
                        className={
                          smartResult.isCorrect ? styles.smartCorrect : styles.smartWrong
                        }
                        role="status"
                      >
                        <strong>{smartResult.isCorrect ? 'Correct.' : 'Not quite.'}</strong>{' '}
                        {smartResult.feedback}
                        {smartResult.coaching?.rootGap && (
                          <p>
                            Root gap: {smartResult.coaching.rootGap.label} —{' '}
                            {smartResult.coaching.rootGap.reason}
                          </p>
                        )}
                        {smartResult.coaching?.body && (
                          <p>{smartResult.coaching.body}</p>
                        )}
                        <button
                          type="button"
                          className={styles.planAction}
                          onClick={() => void advanceSmartCheck()}
                          disabled={smartBusy}
                        >
                          {smartBusy ? 'Checking…' : 'Next question →'}
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        className={styles.planAction}
                        onClick={() => void submitSmartAnswer()}
                        disabled={smartBusy || !smartSelected.trim()}
                      >
                        {smartBusy ? 'Grading…' : 'Answer and continue'}
                      </button>
                    )}
                  </div>
                ) : smartDone ? (
                  <div className={styles.smartBody}>
                    <p className={styles.smartWhy}>{smartMessage}</p>
                    <button type="button" className={styles.planAction} onClick={() => void startSmartCheck()}>
                      Run another check
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className={styles.smartStart}
                    onClick={() => void startSmartCheck()}
                    disabled={smartBusy}
                  >
                    <Play size={13} /> {smartBusy ? 'Choosing questions…' : 'Start a smart check'}
                  </button>
                )}
                {smartMessage && !smartQuestion && !smartDone && (
                  <p className={styles.meta}>{smartMessage}</p>
                )}
              </div>
            </>
          ) : (
            <p className={styles.meta}>Understanding appears after your first study event or answer.</p>
          )}
        </article>
      </section>

      <section className={styles.split}>
        <article className={styles.panel}>
          <h2>Current book</h2>
          {materials.length > 1 && (
            <div className={styles.bookChips} role="group" aria-label="Choose a source">
              {materials.map((m) => {
                const isSelected = (currentBook?.documentId === m.documentId);
                return (
                  <button
                    key={m.documentId}
                    type="button"
                    className={isSelected ? `${styles.bookChip} ${styles.bookChipActive}` : styles.bookChip}
                    aria-pressed={isSelected}
                    onClick={() => setSelectedDocId(m.documentId)}
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
                {currentBook.chunkCount ? `${currentBook.chunkCount} indexed passages · ` : ''}
                {documentStatusLabel(bookStatus)}
              </p>
              {currentBook.progressMessage && <p className={styles.meta}>{currentBook.progressMessage}</p>}
              {currentBook.errorMessage && <p className={styles.bad}>{currentBook.errorMessage}</p>}
              {uploadNotice && <p className={styles.meta}>{uploadNotice}</p>}
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
          ) : isDeskLoading ? (
            <p className={styles.meta}>Loading your desk…</p>
          ) : (
            <p className={styles.meta}>No book yet. Upload one and a plan is built from its units.</p>
          )}
        </article>

        <article className={styles.panel}>
          <div className={styles.panelHead}>
            <h2>Units</h2>
            {lessons.length > 0 && <span className={styles.sectionNote}>{readyCount}/{lessons.length} ready</span>}
          </div>
          {lessons.length > 0 ? (
            <ol className={styles.rail}>
              {lessons.map((lesson) => (
                <li
                  key={lesson.id}
                  data-status={lesson.status}
                  className={lesson.status === 'ready' ? styles.unitReady : styles.unitWait}
                >
                  <button
                    type="button"
                    className={styles.unitButton}
                    disabled={lesson.status !== 'ready'}
                    onClick={() => navigate(`/lesson/${lesson.id}?pathId=${plan?.id}`)}
                  >
                    <span>{lesson.sequence}. {lesson.title}</span>
                    <small>
                      {lessonStatusLabel(lesson.status)}
                    </small>
                  </button>
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
              <button
                type="button"
                className={styles.secondary}
                onClick={() => void downloadLesson(readyLesson.id)}
                disabled={downloadingLessonId === readyLesson.id}
              >
                {downloadingLessonId === readyLesson.id ? 'Saving…' : 'Download'}
              </button>
            </div>
          </div>
        ) : (
          <p className={styles.meta}>
            {lessons.length === 0
              ? 'No units have been created yet.'
              : preparingCount > 0
                ? `No unit is ready yet. ${preparingCount} ${preparingCount === 1 ? 'unit is' : 'units are'} still being prepared.`
                : 'No unit is ready yet.'}
          </p>
        )}
        {downloadNotice && (
          <p
            className={downloadNotice.kind === 'ok' ? styles.ok : styles.bad}
            role={downloadNotice.kind === 'error' ? 'alert' : 'status'}
          >
            {downloadNotice.message}
          </p>
        )}
      </section>

      <section className={styles.panel}>
        <div className={styles.panelHead}>
          <h2>Add a source</h2>
          {currentBook && <span className={styles.sectionNote}>Current source</span>}
        </div>
        <AddSourcePanel
          fileInputRef={fileInputRef}
          isDragging={isDragging}
          isUploading={isUploading}
          showPipelineProgress={showPipelineProgress}
          pipeline={pipeline}
          activePipelineIndex={activePipelineIndex}
          progressPercent={progressPercent}
          currentBookFilename={currentBook?.filename}
          activityPhase={activityPhase}
          activityDetail={activityDetail}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onFileChange={handleFileChange}
          onCancel={() => {
            uploadRequestRef.current?.abort();
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
            setIsUploading(false);
            setProgressPercent(undefined);
          }}
        />
      </section>

      <section className={styles.panel}>
        <h2>Study record</h2>
        <StudyRecordPanel
          studySummary={studySummary}
          suggestionErrors={suggestionErrors}
          respondingSuggestionId={respondingSuggestionId}
          onRespond={(id, decision) => void respondToSuggestion(id, decision)}
        />
      </section>

      {reviewOutline && (
        <PlanReviewDialog
          outline={reviewOutline}
          reviewError={reviewError}
          isGeneratingPath={isGeneratingPath}
          grade={pathGrade}
          subject={pathSubject}
          subjectOptions={subjectOptions}
          taxonomy={{
            loading: taxonomy.loading,
            error: taxonomy.error,
            retry: taxonomy.retry,
          }}
          dialogRef={planDialogRef}
          onGradeChange={setPathGrade}
          onSubjectChange={setPathSubject}
          onClose={() => {
            if (isGeneratingPath) return;
            setReviewOutline(null);
            setReviewError(null);
          }}
          onBuild={handleCreatePathFromOutline}
        />
      )}
    </div>
  );
};

