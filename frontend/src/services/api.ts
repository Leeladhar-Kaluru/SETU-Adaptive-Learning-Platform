// SETU API Service Client - Typed contracts connecting frontend to backend

const API_BASE = '/api/v1';

export interface UserProfileData {
  id: string;
  email: string | null;
  role: 'student' | 'teacher';
  displayName: string;
  grade?: number | null;
  boardId?: string | null;
  preferredLanguage?: string | null;
  subjectsInterested?: string[];
  learningGoals?: string[];
  dailyGoalMinutes?: number | null;
  canTeach?: boolean;
  academicContextComplete?: boolean;
  accessibilityPreferences?: {
    font_size?: string;
    reduced_motion?: boolean;
    high_contrast?: boolean;
    pace?: 'short' | 'steady' | 'long';
  };
  onboardingCompleted?: boolean;
  tourCompleted?: boolean;
}

export interface CatalogueBoard {
  id: string;
  code: string;
  name: string;
  region?: string | null;
  officialUrl?: string | null;
}

export interface CatalogueSubject {
  id: string;
  code: string;
  canonicalName: string;
  name: string;
}

export interface CatalogueLanguage {
  id: string;
  bcp47Tag: string;
  nativeName: string;
  script: string;
}

export interface AuthResponse {
  accessToken: string;
  user: UserProfileData;
}

export interface CatalogueResource {
  id: string;
  title: string;
  description?: string;
  boardId: string;
  board: string;
  grade: number;
  subjectId: string;
  subject: string;
  medium?: string;
  edition?: string;
  externalUrl?: string;
  totalPages?: number;
  rights?: {
    licenseName: string;
    canLink: boolean;
    canDownload: boolean;
    canStore: boolean;
    canProcess: boolean;
    canOfflineCache: boolean;
  };
}

export interface IngestionStatus {
  documentId: string;
  status: 'selected' | 'uploading' | 'stored' | 'extracting' | 'extracted' | 'indexing' | 'indexed' | 'analysing' | 'awaiting_review' | 'generating' | 'ready' | 'failed' | 'needs_ocr';
  filename: string;
  pageCount?: number;
  chunkCount?: number;
  pagesRead?: number;
  pagesNeedingOcr?: number;
  errorMessage?: string;
  progressMessage?: string;
  deduplicated?: boolean;
  canBuildPath?: boolean;
  outlineMessage?: string;
  chapters?: Array<{ title: string; pageStart: number; pageEnd: number }>;
}

export interface UserDocument {
  id: string;
  documentId: string;
  filename: string;
  status: string;
  pageCount?: number;
  chunkCount?: number;
  pagesRead?: number;
  pagesNeedingOcr?: number;
  sizeBytes?: number;
  errorMessage?: string;
  progressMessage?: string;
  deduplicated?: boolean;
  createdAt?: string;
  chapters?: Array<{ title: string; pageStart: number; pageEnd: number }>;
}

export interface LearningPathItem {
  id: string;
  documentId?: string | null;
  title: string;
  grade: number;
  subjectId: string;
  status: string;
  progressPercent: number;
  totalLessons: number;
  readyLessons: number;
  sourceTitle?: string;
  firstLessonId?: string;
  lessons?: Array<{ id: string; title: string; status: string; sequence: number }>;
}

export interface ClassroomData {
  id: string;
  name: string;
  grade: number;
  boardId: string;
  subjectScope: string;
  joinCode: string | null;
  memberCount: number;
  createdAt: string;
}

export type EvidenceBand =
  | 'not_enough_evidence'
  | 'developing'
  | 'approaching'
  | 'demonstrated';

export interface EvidenceConceptRow {
  conceptId: string;
  band: EvidenceBand;
  score: number;
  evidenceCount: number;
  calculatedAt: string | null;
}

export interface EvidenceMatrixRow {
  studentId: string;
  studentName: string;
  profileMissing?: boolean;
  concepts: EvidenceConceptRow[];
  conceptsDemonstrated: number;
  totalConcepts: number;
  accuracyRate: number;
  accuracyKnown?: boolean;
  recentAttemptsCount: number;
  evidenceBand: EvidenceBand;
  lastActive: string;
  minutesStudied?: number;
  readingTitle?: string | null;
  improvement?: string;
  heatmap?: Array<{ date: string; seconds: number }>;
  focus?: string;
}

export interface TeacherActionRow {
  id: string;
  studentId: string;
  conceptId: string;
  actionType: string;
  notes: string;
  status: 'proposed' | 'accepted' | 'dismissed' | 'edited' | 'superseded';
  studentResponse?: { decision: string; note?: string; respondedAt?: string } | null;
  createdAt: string;
}

export interface RosterMember {
  studentId: string;
  studentName: string;
  profileMissing: boolean;
  status: 'active' | 'removed';
  joinedAt: string | null;
}

export interface EvidenceMatrixResponse {
  classroomId: string;
  name?: string;
  grade?: number;
  subjectScope?: string;
  joinCode?: string | null;
  totalStudents: number;
  matrix: EvidenceMatrixRow[];
  actions: TeacherActionRow[];
  classGaps?: ClassGapRow[];
}

export interface ClassGapRow {
  conceptId: string;
  studentsWithEvidence: number;
  averageScore: number | null;
  bands: Record<EvidenceBand, number>;
  studentsNeedingSupport: number;
  supportNames: string[];
  priority: number;
}

export interface DashboardStats {
  currentStreak: number;
  longestStreak: number;
  totalMinutesStudied: number;
  totalSessions: number;
  averageAccuracy: number;
  totalQuestionsAttempted: number;
}

export interface ActivityHeatmapDay {
  date: string;
  seconds: number;
  minutes: number;
  count: number;
  level: 0 | 1 | 2 | 3 | 4;
}

export interface ConceptMasteryItem {
  conceptId: string;
  band: 'demonstrated' | 'approaching' | 'developing' | 'not_enough_evidence';
  score: number;
  evidenceCount: number;
  calculatedAt: string | null;
  needsRemediation: boolean;
}

export interface RecentAttemptItem {
  id: string;
  lessonTitle: string;
  score: number;
  isCorrect: boolean;
  hintsUsed: number;
  elapsedSeconds: number;
  occurredAt: string | null;
}

export interface LearnerEvidenceItem {
  conceptId: string;
  label: string;
  band: EvidenceBand;
  score: number | null;
  evidenceCount: number;
  calculatedAt?: string | null;
}

export interface LearnerInsightBlock {
  state: 'measured' | 'no_evidence';
  detail: string;
}

export interface LearnerAccuracy extends LearnerInsightBlock {
  overall: number | null;
  lastSevenDays: number | null;
  previousSevenDays: number | null;
  trend: 'improving' | 'needs_support' | 'steady' | 'starting' | 'no_evidence';
  practiceAccuracy?: number | null;
  checkpointAccuracy?: number | null;
}

export interface LearnerPace extends LearnerInsightBlock {
  medianAnswerSeconds: number | null;
  medianSessionMinutes: number | null;
  dailyGoalMinutes: number | null;
  goalProgress: number | null;
  label: string;
}

export interface LearnerHints extends LearnerInsightBlock {
  hintedAttempts: number;
  totalAttempts: number;
  hintRate: number | null;
  averageHints: number | null;
  accuracyWithHints: number | null;
  accuracyWithoutHints: number | null;
  label: string;
}

export interface LearnerRoutineWindow {
  id: string;
  label: string;
  minutes: number;
  sessions: number;
  attempts: number;
  correct: number;
  accuracy: number | null;
}

export interface LearnerRoutine extends LearnerInsightBlock {
  windows: LearnerRoutineWindow[];
  bestWindow: LearnerRoutineWindow | null;
  currentStreak: number;
  longestStreak: number;
  activeDays: number;
  consistencyScore: number;
  consistencyLabel: string;
  weekdayMinutes: number;
  weekendMinutes: number;
  timezoneNote?: string;
}

export interface LearnerMastery extends LearnerInsightBlock {
  concepts: LearnerEvidenceItem[];
  strengths: LearnerEvidenceItem[];
  focusAreas: LearnerEvidenceItem[];
  bands: {
    demonstrated: number;
    approaching: number;
    developing: number;
    notEnoughEvidence: number;
  };
}

export interface LearnerHabit {
  id: string;
  tone: 'positive' | 'neutral' | 'watch';
  title: string;
  detail: string;
}

export interface LearnerInsights {
  generatedAt: string;
  state: 'measured' | 'no_evidence';
  confidence: 'none' | 'low' | 'medium' | 'high';
  confidenceDetail: string;
  summary: string;
  library: { activePaths: number; readyLessons: number };
  evidence: {
    studyEvents: number;
    gradedAttempts: number;
    practiceAttempts: number;
    checkpointAttempts: number;
    conceptEvidence: number;
    activeDays: number;
    totalMinutes: number;
  };
  accuracy: LearnerAccuracy;
  pace: LearnerPace;
  hintReliance: LearnerHints;
  routine: LearnerRoutine;
  mastery: LearnerMastery;
  habits: LearnerHabit[];
}

export interface StudyPlanTask {
  id: string;
  kind: 'remediate' | 'review' | 'continue' | 'next_lesson' | 'practice' | 'stretch';
  priority: number;
  slot: string;
  title: string;
  reason: string;
  actionLabel: string;
  pathId: string;
  pathTitle: string;
  subjectId: string;
  subjectLabel: string;
  lessonId: string | null;
  lessonTitle: string | null;
  conceptId: string | null;
  conceptLabel: string | null;
  evidence: Record<string, unknown>;
}

export interface StudyPlanBook {
  pathId: string;
  title: string;
  documentTitle: string | null;
  grade: number;
  subjectId: string;
  subjectLabel: string;
  status: string;
  totalLessons: number;
  readyLessons: number;
  completedLessons: number;
  mastery: {
    demonstrated: number;
    approaching: number;
    developing: number;
    notEnoughEvidence: number;
  };
  strongestConcept: LearnerEvidenceItem | null;
  focusConcept: LearnerEvidenceItem | null;
  inProgressLesson: { lessonId: string; title: string } | null;
  nextLesson: { lessonId: string; title: string } | null;
}

export interface StudyPlan {
  generatedAt: string;
  state: 'active' | 'preparing' | 'empty';
  summary: string;
  subjectMix: string[];
  bookCount: number;
  taskCount: number;
  tasks: StudyPlanTask[];
  books: StudyPlanBook[];
  roadmap: Array<{
    pathId: string;
    title: string;
    subjectLabel: string;
    lessons: Array<{
      lessonId: string;
      title: string;
      sequence: number;
      status: string;
      attempts: number;
      readingMinutes: number;
    }>;
  }>;
  counts: {
    completedLessons: number;
    readyLessons: number;
    totalLessons: number;
    waitingBooks: number;
  };
}

export interface CoachRootGap {
  conceptId: string;
  label: string;
  band: EvidenceBand;
  score: number | null;
  evidenceCount: number;
  lessonTitle: string;
  sequence: number;
  distance: number;
  reason: string;
}

export interface CoachCard {
  id: string;
  scope: 'attempt' | 'lesson';
  tone?: 'celebrate' | 'retry';
  headline?: string;
  body: string;
  conceptId?: string | null;
  conceptLabel?: string | null;
  rootGap?: CoachRootGap | null;
  mastery?: { band?: string; score?: number; evidenceCount?: number };
  nextStep?: { title?: string; reason?: string; action?: string };
  keyPoint?: { title: string; body: string } | null;
  source?: { page: number; title: string; excerpt: string } | null;
  studyTip?: { title: string; body: string } | null;
  evidence?: Record<string, unknown>;
}

export interface LessonCoachMoment {
  id: string;
  kind: 'key_point' | 'source_spotlight' | 'fun_fact' | 'study_tip' | 'challenge';
  title: string;
  body: string;
  evidence?: string;
  source?: { page: number; title: string };
}

export interface LessonCoaching {
  lessonId: string;
  lessonTitle: string;
  state: 'ready' | 'no_source_material';
  intro: string;
  difficulty: 'standard' | 'challenge';
  challengeCount: number;
  concepts: string[];
  developingConcepts: string[];
  moments: LessonCoachMoment[];
  autoShowId: string | null;
  generatedAt: string;
}

export interface SmartCheckQuestion {
  questionKey: string;
  lessonVersionId: string;
  lessonId: string;
  pathId: string;
  lessonTitle: string;
  pathTitle: string;
  subjectId: string;
  subjectLabel: string;
  conceptId: string;
  conceptLabel: string;
  prompt: string;
  type: string;
  options: string[];
  difficulty: string;
  why: string;
  mastery: { band: EvidenceBand; score: number | null; evidenceCount: number };
}

export interface SmartCheckResponse {
  state: 'ready' | 'no_questions';
  message: string;
  questions: SmartCheckQuestion[];
  maxQuestions: number;
  coverage?: {
    availableConcepts: number;
    measuredConcepts: number;
    unknownConcepts: number;
  };
}

export interface SmartCheckNextResponse {
  state: 'question' | 'complete';
  stopReason: 'max_questions' | 'enough_evidence' | 'no_more_questions' | null;
  message: string;
  question: SmartCheckQuestion | null;
  answeredCount: number;
  remaining?: number;
}

export interface StudentDashboardResponse {
  profile: UserProfileData;
  stats: DashboardStats;
  activityHeatmap: ActivityHeatmapDay[];
  conceptMastery: ConceptMasteryItem[];
  recentAttempts: RecentAttemptItem[];
  classrooms: Array<{
    id: string;
    name: string;
    grade: number;
    subjectScope: string;
    joinCode: string;
    joinedAt: string;
  }>;
  understanding?: LearnerInsights;
  teaching?: { canTeach: boolean; ownedClassrooms: number };
}

export interface AttemptSubmission {
  lessonVersionId: string;
  questionKey: string;
  response: unknown;
  hintLevel?: number;
  hintsUsed?: string[];
  elapsedSeconds?: number;
  attemptKind?: 'practice' | 'checkpoint';
  syncIdempotencyKey?: string;
}

export interface AttemptResult {
  attemptId: string;
  isCorrect: boolean;
  score: number;
  correctAnswer?: unknown;
  feedback: string;
  mastery: { band: string; score: number; evidenceCount: number; explanation: string };
  nextAction: {
    action: string;
    title: string;
    reason: string;
    canAdvance: boolean;
    remediationInjected?: boolean;
    remediationLessonId?: string;
  };
  coaching?: CoachCard | null;
  alreadyRecorded: boolean;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('setu_auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const REQUEST_TIMEOUT_MS = 8000;
const RETRYABLE_STATUSES = new Set([502, 503, 504]);

async function fetchOnce(endpoint: string, options: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      signal: controller.signal
    });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = {
    'Content-Type': 'application/json',
    ...authHeaders(),
    ...(options.headers || {})
  };

  let response: Response;
  try {
    response = await fetchOnce(endpoint, { ...options, headers });
  } catch (firstError) {
    try {
      response = await fetchOnce(endpoint, { ...options, headers });
    } catch {
      throw firstError;
    }
  }

  if (!response.ok && RETRYABLE_STATUSES.has(response.status)) {
    const retried = await fetchOnce(endpoint, { ...options, headers });
    if (retried.ok) return retried.json();
    response = retried;
  }

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || JSON.stringify(errJson);
    } catch {
      // ignore
    }
    throw new ApiError(errorDetail || `Request failed with status ${response.status}`, response.status);
  }

  return response.json();
}

export const api = {
  // Auth
  async signup(data: { email: string; password: string; displayName: string; role?: string; grade?: number; boardId?: string; preferredLanguage?: string }): Promise<AuthResponse> {
    return request<AuthResponse>('/auth/signup', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },

  async login(data: { email: string; password: string }): Promise<AuthResponse> {
    return request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },

  async getMe(): Promise<{ user: UserProfileData }> {
    return request<{ user: UserProfileData }>('/auth/me');
  },

  // Profile
  async getProfile(): Promise<UserProfileData> {
    return request<UserProfileData>('/profile');
  },

  async updateProfile(updates: Partial<UserProfileData>): Promise<{ profile: UserProfileData }> {
    return request<{ profile: UserProfileData }>('/profile', {
      method: 'PUT',
      body: JSON.stringify(updates)
    });
  },

  // Catalogue
  async getBoards(): Promise<CatalogueBoard[]> {
    return request<CatalogueBoard[]>('/catalogue/boards');
  },

  async getSubjects(): Promise<CatalogueSubject[]> {
    return request<CatalogueSubject[]>('/catalogue/subjects');
  },

  async getLanguages(): Promise<CatalogueLanguage[]> {
    return request<CatalogueLanguage[]>('/catalogue/languages');
  },

  async getCatalogue(params?: { query?: string; grade?: number; subjectId?: string; boardId?: string }): Promise<CatalogueResource[]> {
    const q = new URLSearchParams();
    if (params?.query) q.append('search', params.query);
    if (params?.grade) q.append('grade', String(params.grade));
    if (params?.subjectId) q.append('subject_id', params.subjectId);
    if (params?.boardId) q.append('board_id', params.boardId);
    const queryString = q.toString() ? `?${q.toString()}` : '';
    const res = await request<any>(`/catalogue/resources${queryString}`);
    return Array.isArray(res) ? res : res.resources || [];
  },

  // Documents
  uploadDocument(
    file: File,
    onProgress?: (percent: number) => void,
    requestRef?: { current: XMLHttpRequest | null }
  ): Promise<{ documentId: string; filename: string; pageCount: number; chunkCount: number; status: string; errorMessage?: string; progressMessage?: string; deduplicated?: boolean }> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      if (requestRef) requestRef.current = xhr;
      xhr.open('POST', `${API_BASE}/documents/upload`);
      const token = localStorage.getItem('setu_auth_token');
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      };
      xhr.onload = () => {
        let body: any = {};
        try {
          body = JSON.parse(xhr.responseText || '{}');
        } catch {
          body = {};
        }
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(body);
          return;
        }
        const detail = body.detail || xhr.statusText || 'Upload failed.';
        reject(new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)));
      };
      xhr.onerror = () => reject(new TypeError('Upload failed before the server stored the file.'));
      xhr.onabort = () => reject(new Error('Upload cancelled.'));
      const formData = new FormData();
      formData.append('file', file);
      xhr.send(formData);
    });
  },

  async listDocuments(): Promise<UserDocument[]> {
    const res = await request<UserDocument[] | { documents: UserDocument[] }>('/documents');
    return Array.isArray(res) ? res : res.documents || [];
  },

  async retryDocument(documentId: string): Promise<UserDocument> {
    return request<UserDocument>(`/documents/${documentId}/retry`, { method: 'POST' });
  },

  async getDocumentStatus(documentId: string): Promise<IngestionStatus> {
    return request<IngestionStatus>(`/documents/${documentId}/status`);
  },

  async deleteDocument(documentId: string): Promise<{ success: boolean; documentId: string }> {
    return request<{ success: boolean; documentId: string }>(`/documents/${documentId}`, {
      method: 'DELETE'
    });
  },

  // Learning Paths
  async getLearningPaths(): Promise<LearningPathItem[]> {
    const res = await request<LearningPathItem[] | { paths: LearningPathItem[] }>('/learning-paths');
    return Array.isArray(res) ? res : res.paths || [];
  },

  async createLearningPath(data: { documentId: string; grade: number; subjectId: string }): Promise<any> {
    return request<any>('/learning-paths', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },

  async getLesson(lessonId: string): Promise<any> {
    return request<any>(`/learning-paths/lessons/${lessonId}`);
  },

  async submitAttempt(data: AttemptSubmission): Promise<AttemptResult> {
    return request<AttemptResult>('/attempts', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },

  // Doubts (Real online submission & history)
  async askDoubt(data: {
    questionText: string;
    pathId?: string;
    lessonVersionId?: string;
    blockId?: string;
    sourcePage?: number;
    clientDoubtId?: string;
  }): Promise<{ id: string; status: string; answerJson?: any }> {
    return request<{ id: string; status: string; answerJson?: any }>('/doubts', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },

  async listDoubts(): Promise<Array<{
    id: string;
    clientDoubtId: string;
    status: string;
    questionText: string;
    answerJson?: any;
    lastErrorCode?: string | null;
    pathId?: string | null;
    lessonVersionId?: string | null;
    sourcePage?: number;
    blockId?: string;
    createdAt: string;
  }>> {
    const res = await request<any>('/doubts');
    return Array.isArray(res) ? res : res.doubts || [];
  },

  // Teacher & Classrooms
  async getClassrooms(): Promise<ClassroomData[]> {
    const res = await request<any>('/teacher/classrooms');
    return Array.isArray(res) ? res : res.classrooms || [];
  },

  async createClassroom(data: { name: string; grade: number; boardId: string; subjectScope: string }): Promise<ClassroomData> {
    return request<ClassroomData>('/teacher/classrooms', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },

  async joinClassroom(joinCode: string): Promise<{ success: boolean; classroom: any; membership: any }> {
    return request<{ success: boolean; classroom: any; membership: any }>('/teacher/join', {
      method: 'POST',
      body: JSON.stringify({ joinCode })
    });
  },

  async getEvidenceMatrix(classroomId: string): Promise<EvidenceMatrixResponse> {
    return request<EvidenceMatrixResponse>(`/teacher/classrooms/${classroomId}/evidence-matrix`);
  },

  async getClassroomRoster(classroomId: string): Promise<{
    classroomId: string;
    joinCode: string | null;
    members: RosterMember[];
  }> {
    return request(`/teacher/classrooms/${classroomId}/roster`);
  },

  async rotateJoinCode(classroomId: string): Promise<{ classroomId: string; joinCode: string }> {
    return request(`/teacher/classrooms/${classroomId}/rotate-join-code`, { method: 'POST' });
  },

  async updateClassroomMember(
    classroomId: string,
    studentId: string,
    status: 'active' | 'removed'
  ): Promise<{ classroomId: string; studentId: string; status: string }> {
    return request(`/teacher/classrooms/${classroomId}/members/${studentId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  },

  async decideTeacherAction(
    actionId: string,
    decision: 'accept' | 'dismiss' | 'override',
    notes?: string
  ): Promise<{ id: string; status: string; decision: string; notes: string }> {
    return request(`/teacher/actions/${actionId}`, {
      method: 'PATCH',
      body: JSON.stringify({ decision, notes }),
    });
  },

  async addRecommendation(data: { classroomId: string; studentId: string; conceptId: string; actionType: string; notes: string }): Promise<{
    id: string;
    status: string;
    actionType: string;
    conceptId: string;
    notes: string;
    reason: {
      evidence?: EvidenceConceptRow;
      [key: string]: unknown;
    };
  }> {
    return request('/teacher/recommendations', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },

  async respondToRecommendation(actionId: string, decision: 'accept' | 'dismiss'): Promise<{ id: string; status: string }> {
    return request(`/study/recommendations/${actionId}/respond`, {
      method: 'POST',
      body: JSON.stringify({ decision }),
    });
  },

  async getStudySummary(): Promise<{
    minutesStudied: number;
    readingTitle?: string | null;
    checkpointCount: number;
    accuracyRate: number | null;
    improvement: string;
    pace: string | null;
    dailyGoalMinutes: number | null;
    focus: string;
    heatmap: Array<{ date: string; seconds: number }>;
    suggestions: Array<{
      id: string;
      note: string;
      actionType: string;
      conceptId?: string | null;
      status?: string;
      explanation?: string | null;
      teacherName?: string | null;
      createdAt?: string | null;
    }>;
  }> {
    return request('/study/summary');
  },

  async getLearnerInsights(): Promise<LearnerInsights> {
    return request<LearnerInsights>('/study/insights');
  },

  async getStudyPlan(): Promise<StudyPlan> {
    return request<StudyPlan>('/study/plan');
  },

  async getLessonCoaching(lessonId: string): Promise<LessonCoaching> {
    return request<LessonCoaching>(`/study/coach/${lessonId}`);
  },

  async getSmartCheck(): Promise<SmartCheckResponse> {
    return request<SmartCheckResponse>('/study/smart-check');
  },

  async getNextSmartQuestion(answeredQuestionKeys: string[]): Promise<SmartCheckNextResponse> {
    return request<SmartCheckNextResponse>('/study/smart-check/next', {
      method: 'POST',
      body: JSON.stringify({ answeredQuestionKeys }),
    });
  },

  async getStudentDashboard(): Promise<StudentDashboardResponse> {
    return request<StudentDashboardResponse>('/profile/dashboard');
  },

  async recordStudy(data: {
    eventType: 'reading' | 'checkpoint';
    pathId?: string;
    lessonId?: string;
    lessonTitle?: string;
    seconds?: number;
    score?: number;
  }): Promise<{ id: string }> {
    return request('/study/events', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }
};
