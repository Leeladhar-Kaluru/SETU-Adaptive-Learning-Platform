import { db } from '../db/indexedDB';

export type SyncStatusListener = (isSyncing: boolean, pendingCount: number) => void;

class SyncManager {
  private isSyncing = false;
  private listeners: Set<SyncStatusListener> = new Set();

  constructor() {
    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => {
        console.log('[SETU SyncManager] Network online detected, triggering sync...');
        this.syncPendingData();
      });

      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible' && navigator.onLine) {
          this.syncPendingData();
        }
      });
    }
  }

  public subscribe(listener: SyncStatusListener): () => void {
    this.listeners.add(listener);
    this.notify();
    return () => this.listeners.delete(listener);
  }

  private async notify() {
    const pendingDoubts = await db.doubtOutbox.filter(d => !d.synced).count();
    const pendingAttempts = await db.offlineAttempts.filter(a => !a.synced).count();
    const totalPending = pendingDoubts + pendingAttempts;
    for (const listener of this.listeners) {
      listener(this.isSyncing, totalPending);
    }
  }

  public async syncPendingData(): Promise<{ syncedDoubts: number; syncedAttempts: number }> {
    if (this.isSyncing || !navigator.onLine) {
      return { syncedDoubts: 0, syncedAttempts: 0 };
    }

    this.isSyncing = true;
    this.notify();

    let syncedDoubts = 0;
    let syncedAttempts = 0;

    try {
      // 1. Sync Doubts
      const pendingDoubts = await db.doubtOutbox.filter(d => !d.synced).toArray();
      if (pendingDoubts.length > 0) {
        const doubtsPayload = pendingDoubts.map(d => ({
          clientDoubtId: d.clientDoubtId,
          pathId: d.pathId,
          lessonVersionId: d.lessonVersionId,
          blockId: d.blockId,
          sourcePage: d.sourcePage,
          questionText: d.questionText,
          submittedAt: d.submittedAt
        }));

        try {
          const res = await fetch('/api/v1/sync/doubts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ doubts: doubtsPayload })
          });

          if (res.ok) {
            const data = await res.json();
            const results: any[] = data.results || [];
            
            for (const r of results) {
              const matching = pendingDoubts.find(d => d.clientDoubtId === r.clientDoubtId);
              if (matching) {
                const answerPayload = r.answer ? {
                  answer: r.answer,
                  citations: r.citations || [],
                  answeredAt: r.answeredAt || new Date().toISOString()
                } : undefined;

                await db.doubtOutbox.update(matching.clientDoubtId, {
                  synced: true,
                  status: r.status === 'answered' ? 'answered' : 'queued',
                  answerPayload
                });

                if (answerPayload) {
                  await db.cachedAnswers.put({
                    clientDoubtId: matching.clientDoubtId,
                    doubtId: r.id,
                    questionText: matching.questionText,
                    answer: answerPayload.answer,
                    citations: answerPayload.citations,
                    cachedAt: answerPayload.answeredAt
                  });
                }
                syncedDoubts++;
              }
            }
          }
        } catch (err) {
          console.warn('[SETU SyncManager] Doubt sync error:', err);
        }
      }

      // 2. Sync Quiz Attempts
      const pendingAttempts = await db.offlineAttempts.filter(a => !a.synced).toArray();
      if (pendingAttempts.length > 0) {
        const eventsPayload = pendingAttempts.map(a => ({
          eventId: a.clientAttemptId,
          eventType: 'quiz_attempt',
          payload: {
            lessonId: a.lessonId,
            lessonVersionId: a.lessonVersionId,
            questionKey: a.questionKey,
            response: a.response,
            hintLevel: a.hintLevel,
            hintsUsed: a.hintsUsed,
            attemptKind: a.attemptKind,
            elapsedSeconds: a.elapsedSeconds
          },
          timestamp: a.submittedAt
        }));

        try {
          const res = await fetch('/api/v1/sync/events', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ events: eventsPayload })
          });

          if (res.ok) {
            for (const a of pendingAttempts) {
              await db.offlineAttempts.update(a.clientAttemptId, { synced: true });
              syncedAttempts++;
            }
          }
        } catch (err) {
          console.warn('[SETU SyncManager] Attempt sync error:', err);
        }
      }
    } finally {
      this.isSyncing = false;
      this.notify();
    }

    return { syncedDoubts, syncedAttempts };
  }
}

export const syncManager = new SyncManager();
