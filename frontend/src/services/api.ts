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
  errorMessage?: string;
  chapters?: Array<{ title: string; pageStart: number; pageEnd: number }>;
}

export interface UserDocument {
  id: string;
  documentId: string;
  filename: string;
  status: string;
  pageCount?: number;
  chunkCount?: number;
  sizeBytes?: number;
  errorMessage?: string;
  createdAt?: string;
  chapters?: Array<{ title: string; pageStart: number; pageEnd: number }>;
}

export interface LearningPathItem {
  id: string;
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
  joinCode: string;
  memberCount: number;
  createdAt: string;
}

export interface EvidenceMatrixRow {
  studentId: string;
  studentName: string;
  conceptsDemonstrated: number;
  totalConcepts: number;
  accuracyRate: number;
  accuracyKnown?: boolean;
  recentAttemptsCount: number;
  evidenceBand: 'sparse' | 'developing' | 'approaching' | 'demonstrated';
  lastActive: string;
  minutesStudied?: number;
  readingTitle?: string | null;
  improvement?: string;
  heatmap?: Array<{ date: string; seconds: number }>;
  focus?: string;
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
  alreadyRecorded: boolean;
}

export function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('setu_auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = {
    'Content-Type': 'application/json',
    ...authHeaders(),
    ...(options.headers || {})
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || JSON.stringify(errJson);
    } catch {
      // ignore
    }
    throw new Error(errorDetail || `Request failed with status ${response.status}`);
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
  ): Promise<{ documentId: string; filename: string; pageCount: number; chunkCount: number; status: string; errorMessage?: string }> {
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

  async getEvidenceMatrix(classroomId: string): Promise<{ classroomId: string; totalStudents: number; matrix: EvidenceMatrixRow[] }> {
    return request<{ classroomId: string; totalStudents: number; matrix: EvidenceMatrixRow[] }>(`/teacher/classrooms/${classroomId}/evidence-matrix`);
  },

  async addRecommendation(data: { classroomId: string; studentId: string; conceptId: string; actionType: string; notes: string }): Promise<any> {
    return request<any>('/teacher/recommendations', {
      method: 'POST',
      body: JSON.stringify(data)
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
    }>;
  }> {
    return request('/study/summary');
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
