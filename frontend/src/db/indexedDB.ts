import Dexie, { type Table } from 'dexie';

export interface OfflineLesson {
  lessonId: string;
  pathId: string;
  grade: number;
  subjectId: string;
  title: string;
  packageData: any; // Full conforming lesson package
  downloadedAt: string;
  lastAccessedAt: string;
  sizeBytes: number;
}

export interface OfflineVisual {
  visualId: string;
  lessonId: string;
  type: string;
  spec: any;
}

export interface OfflineAttempt {
  clientAttemptId: string;
  lessonId: string;
  lessonVersionId: string;
  questionKey: string;
  response: unknown;
  hintLevel: number;
  hintsUsed: string[];
  attemptKind: 'practice' | 'checkpoint';
  elapsedSeconds: number;
  synced: boolean;
  submittedAt: string;
}

export interface OfflineDoubt {
  clientDoubtId: string;
  pathId: string;
  lessonVersionId?: string;
  blockId?: string;
  sourcePage?: number;
  questionText: string;
  status: 'queued' | 'syncing' | 'answered' | 'failed';
  synced: boolean;
  submittedAt: string;
  answerPayload?: {
    answer: string;
    citations: Array<{ citationId: string; pageNumber: number; snippet: string }>;
    answeredAt: string;
  };
}

export interface CachedAnswer {
  clientDoubtId: string;
  doubtId?: string;
  questionText: string;
  answer: string;
  citations: Array<{ citationId: string; pageNumber: number; snippet: string }>;
  cachedAt: string;
}

export interface OfflineSyncEvent {
  eventId: string;
  eventType: 'quiz_completed' | 'lesson_read' | 'doubt_asked';
  payload: any;
  timestamp: string;
  synced: boolean;
}

export class SetuDatabase extends Dexie {
  lessons!: Table<OfflineLesson, string>;
  offlineVisuals!: Table<OfflineVisual, string>;
  offlineAttempts!: Table<OfflineAttempt, string>;
  doubtOutbox!: Table<OfflineDoubt, string>;
  cachedAnswers!: Table<CachedAnswer, string>;
  syncEvents!: Table<OfflineSyncEvent, string>;

  constructor() {
    super('SetuDeskDB');
    this.version(1).stores({
      lessons: 'lessonId, pathId, grade, subjectId, downloadedAt, lastAccessedAt',
      offlineVisuals: 'visualId, lessonId, type',
      offlineAttempts: 'clientAttemptId, lessonId, questionId, synced, submittedAt',
      doubtOutbox: 'clientDoubtId, pathId, status, synced, submittedAt',
      cachedAnswers: 'clientDoubtId, doubtId, cachedAt',
      syncEvents: 'eventId, eventType, synced, timestamp'
    });
  }
}

export const db = new SetuDatabase();

// Offline Lesson Helpers
export async function saveLessonOffline(lessonPackage: any): Promise<void> {
  const size = new Blob([JSON.stringify(lessonPackage)]).size;
  const now = new Date().toISOString();

  await db.transaction('rw', db.lessons, db.offlineVisuals, async () => {
    await db.lessons.put({
      lessonId: lessonPackage.lessonId,
      pathId: lessonPackage.pathId || 'default-path',
      grade: lessonPackage.grade || 8,
      subjectId: lessonPackage.subjectId || 'GENERAL',
      title: lessonPackage.title,
      packageData: lessonPackage,
      downloadedAt: now,
      lastAccessedAt: now,
      sizeBytes: size
    });

    if (Array.isArray(lessonPackage.visuals)) {
      for (const vis of lessonPackage.visuals) {
        if (vis.visualId && vis.spec) {
          await db.offlineVisuals.put({
            visualId: vis.visualId,
            lessonId: lessonPackage.lessonId,
            type: vis.type || 'unknown',
            spec: vis.spec
          });
        }
      }
    }
  });
}

export async function getOfflineLesson(lessonId: string): Promise<OfflineLesson | undefined> {
  const lesson = await db.lessons.get(lessonId);
  if (lesson) {
    // Update lastAccessedAt
    await db.lessons.update(lessonId, { lastAccessedAt: new Date().toISOString() });
  }
  return lesson;
}

export async function listOfflineLessons(): Promise<OfflineLesson[]> {
  return await db.lessons.orderBy('downloadedAt').reverse().toArray();
}

export async function deleteOfflineLesson(lessonId: string): Promise<void> {
  await db.transaction('rw', db.lessons, db.offlineVisuals, async () => {
    await db.lessons.delete(lessonId);
    await db.offlineVisuals.where('lessonId').equals(lessonId).delete();
  });
}

export async function getOfflineStorageUsage(): Promise<{ count: number; totalBytes: number }> {
  const allLessons = await db.lessons.toArray();
  const totalBytes = allLessons.reduce((acc, l) => acc + (l.sizeBytes || 0), 0);
  return {
    count: allLessons.length,
    totalBytes
  };
}

// Offline Doubt Outbox Helpers
export async function queueDoubtOffline(params: {
  clientDoubtId: string;
  pathId: string;
  lessonVersionId?: string;
  blockId?: string;
  sourcePage?: number;
  questionText: string;
}): Promise<OfflineDoubt> {
  const doubtRecord: OfflineDoubt = {
    clientDoubtId: params.clientDoubtId,
    pathId: params.pathId,
    lessonVersionId: params.lessonVersionId,
    blockId: params.blockId,
    sourcePage: params.sourcePage,
    questionText: params.questionText,
    status: 'queued',
    synced: false,
    submittedAt: new Date().toISOString()
  };
  await db.doubtOutbox.put(doubtRecord);
  return doubtRecord;
}

export async function listPendingDoubts(): Promise<OfflineDoubt[]> {
  return await db.doubtOutbox.where('synced').equals(0).toArray(); // Dexie boolean false is stored as 0 or boolean
}

export async function getAllDoubts(): Promise<OfflineDoubt[]> {
  return await db.doubtOutbox.orderBy('submittedAt').reverse().toArray();
}

// Offline Attempt Helpers
export async function queueAttemptOffline(params: {
  clientAttemptId: string;
  lessonId: string;
  lessonVersionId: string;
  questionKey: string;
  response: unknown;
  hintLevel: number;
  hintsUsed: string[];
  attemptKind: 'practice' | 'checkpoint';
  elapsedSeconds: number;
}): Promise<void> {
  const attemptRecord: OfflineAttempt = {
    ...params,
    synced: false,
    submittedAt: new Date().toISOString()
  };
  await db.offlineAttempts.put(attemptRecord);
}

