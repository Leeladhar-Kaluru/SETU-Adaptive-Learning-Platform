import Dexie, { type Table } from 'dexie';

export interface OfflineLesson {
  lessonId: string;
  ownerId: string;
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
  ownerId: string;
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
  syncError?: string;
}

export interface OfflineDoubt {
  clientDoubtId: string;
  ownerId: string;
  pathId: string;
  lessonVersionId?: string;
  blockId?: string;
  sourcePage?: number;
  questionText: string;
  status: 'queued' | 'syncing' | 'answered' | 'failed' | 'needs_retry' | 'rejected';
  synced: boolean;
  submittedAt: string;
  lastError?: string;
  answerPayload?: {
    answer: string;
    citations: Array<{ citationId: string; pageNumber: number; snippet: string }>;
    answeredAt: string;
    limitations?: string | null;
  };
}

export interface CachedAnswer {
  clientDoubtId: string;
  ownerId: string;
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
    // Version 2 attributes every cached row to the signed-in account. Legacy
    // rows have no owner and cannot be attributed safely, so they are cleared.
    this.version(2).stores({
      lessons: 'lessonId, ownerId, pathId, grade, subjectId, downloadedAt, lastAccessedAt',
      offlineVisuals: 'visualId, lessonId, type',
      offlineAttempts: 'clientAttemptId, ownerId, lessonId, questionKey, synced, submittedAt',
      doubtOutbox: 'clientDoubtId, ownerId, pathId, status, synced, submittedAt',
      cachedAnswers: 'clientDoubtId, ownerId, doubtId, cachedAt',
      syncEvents: 'eventId, eventType, synced, timestamp'
    }).upgrade(async (tx) => {
      await tx.table('lessons').clear();
      await tx.table('offlineVisuals').clear();
      await tx.table('offlineAttempts').clear();
      await tx.table('doubtOutbox').clear();
      await tx.table('cachedAnswers').clear();
      await tx.table('syncEvents').clear();
    });
  }
}

export const db = new SetuDatabase();

function requireOwnerId(ownerId: string): string {
  if (!ownerId) throw new Error('Sign in before using offline data.');
  return ownerId;
}

// Offline Lesson Helpers
export async function saveLessonOffline(lessonPackage: any, ownerId: string): Promise<void> {
  requireOwnerId(ownerId);
  if (
    !lessonPackage?.lessonId ||
    !lessonPackage?.pathId ||
    !lessonPackage?.grade ||
    !lessonPackage?.subjectId
  ) {
    throw new Error('This lesson package is incomplete and cannot be saved offline.');
  }
  const size = new Blob([JSON.stringify(lessonPackage)]).size;
  const now = new Date().toISOString();

  await db.transaction('rw', db.lessons, db.offlineVisuals, async () => {
    await db.lessons.put({
      lessonId: lessonPackage.lessonId,
      ownerId,
      pathId: lessonPackage.pathId,
      grade: lessonPackage.grade,
      subjectId: lessonPackage.subjectId,
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

export async function getOfflineLesson(
  ownerId: string,
  lessonId: string
): Promise<OfflineLesson | undefined> {
  const lesson = await db.lessons.get(lessonId);
  if (!lesson || lesson.ownerId !== ownerId) return undefined;
  await db.lessons.update(lessonId, { lastAccessedAt: new Date().toISOString() });
  return lesson;
}

export async function listOfflineLessons(ownerId: string): Promise<OfflineLesson[]> {
  const lessons = await db.lessons.where('ownerId').equals(ownerId).toArray();
  return lessons.sort((a, b) => b.downloadedAt.localeCompare(a.downloadedAt));
}

export async function deleteOfflineLesson(ownerId: string, lessonId: string): Promise<void> {
  const lesson = await db.lessons.get(lessonId);
  if (!lesson || lesson.ownerId !== ownerId) return;
  await db.transaction('rw', db.lessons, db.offlineVisuals, async () => {
    await db.lessons.delete(lessonId);
    await db.offlineVisuals.where('lessonId').equals(lessonId).delete();
  });
}

export async function getOfflineStorageUsage(
  ownerId: string
): Promise<{ count: number; totalBytes: number }> {
  const lessons = await db.lessons.where('ownerId').equals(ownerId).toArray();
  return {
    count: lessons.length,
    totalBytes: lessons.reduce((sum, lesson) => sum + (lesson.sizeBytes || 0), 0)
  };
}

export async function clearOfflineData(): Promise<void> {
  await db.transaction(
    'rw',
    [db.lessons, db.offlineVisuals, db.offlineAttempts, db.doubtOutbox, db.cachedAnswers, db.syncEvents],
    async () => {
      await Promise.all([
        db.lessons.clear(),
        db.offlineVisuals.clear(),
        db.offlineAttempts.clear(),
        db.doubtOutbox.clear(),
        db.cachedAnswers.clear(),
        db.syncEvents.clear(),
      ]);
    }
  );
}

// Offline Doubt Outbox Helpers
export async function queueDoubtOffline(params: {
  clientDoubtId: string;
  ownerId: string;
  pathId: string;
  lessonVersionId?: string;
  blockId?: string;
  sourcePage?: number;
  questionText: string;
}): Promise<OfflineDoubt> {
  requireOwnerId(params.ownerId);
  const doubtRecord: OfflineDoubt = {
    clientDoubtId: params.clientDoubtId,
    ownerId: params.ownerId,
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

export async function listPendingDoubts(ownerId: string): Promise<OfflineDoubt[]> {
  return db.doubtOutbox
    .where('ownerId')
    .equals(ownerId)
    .and(doubt => !doubt.synced)
    .toArray();
}

export async function getAllDoubts(ownerId: string): Promise<OfflineDoubt[]> {
  const doubts = await db.doubtOutbox.where('ownerId').equals(ownerId).toArray();
  return doubts.sort((a, b) => b.submittedAt.localeCompare(a.submittedAt));
}

// Offline Attempt Helpers
export async function queueAttemptOffline(params: {
  clientAttemptId: string;
  ownerId: string;
  lessonId: string;
  lessonVersionId: string;
  questionKey: string;
  response: unknown;
  hintLevel: number;
  hintsUsed: string[];
  attemptKind: 'practice' | 'checkpoint';
  elapsedSeconds: number;
}): Promise<void> {
  requireOwnerId(params.ownerId);
  const attemptRecord: OfflineAttempt = {
    ...params,
    synced: false,
    submittedAt: new Date().toISOString()
  };
  await db.offlineAttempts.put(attemptRecord);
}
