import { db } from '../db/indexedDB';
import { authHeaders } from './api';
import { getActiveUserId } from './session';

export type SyncStatusListener = (
  isSyncing: boolean,
  pendingCount: number,
  lastError: string | null,
) => void;

class SyncManager {
  private isSyncing = false;
  private lastSyncError: string | null = null;
  private listeners: Set<SyncStatusListener> = new Set();

  constructor() {
    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => {
        void this.syncPendingData();
      });

      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible' && navigator.onLine) {
          void this.syncPendingData();
        }
      });
    }
  }

  public subscribe(listener: SyncStatusListener): () => void {
    this.listeners.add(listener);
    void this.notify();
    return () => this.listeners.delete(listener);
  }

  public async refreshPending(): Promise<void> {
    await this.notify();
  }

  private async notify() {
    const ownerId = getActiveUserId();
    if (!ownerId) {
      for (const listener of this.listeners) listener(this.isSyncing, 0, this.lastSyncError);
      return;
    }
    const pendingDoubts = await db.doubtOutbox
      .where('ownerId')
      .equals(ownerId)
      .and(doubt => !doubt.synced)
      .count();
    const pendingAttempts = await db.offlineAttempts
      .where('ownerId')
      .equals(ownerId)
      .and(attempt => !attempt.synced)
      .count();
    const totalPending = pendingDoubts + pendingAttempts;
    for (const listener of this.listeners) {
      listener(this.isSyncing, totalPending, this.lastSyncError);
    }
  }

  public async syncPendingData(): Promise<{ syncedDoubts: number; syncedAttempts: number }> {
    const ownerId = getActiveUserId();
    if (!ownerId || this.isSyncing || !navigator.onLine) {
      return { syncedDoubts: 0, syncedAttempts: 0 };
    }

    this.isSyncing = true;
    await this.notify();

    let syncedDoubts = 0;
    let syncedAttempts = 0;
    let syncFailed = false;
    const headers = { 'Content-Type': 'application/json', ...authHeaders() };

    try {
      // 1. Sync doubts for this account.
      const pendingDoubts = await db.doubtOutbox
        .where('ownerId')
        .equals(ownerId)
        .and(doubt => !doubt.synced)
        .toArray();
      if (pendingDoubts.length > 0) {
        const doubtIds = pendingDoubts.map(doubt => doubt.clientDoubtId);
        await db.doubtOutbox.bulkUpdate(
          doubtIds.map(id => ({
            key: id,
            changes: { status: 'syncing' as const, lastError: undefined },
          })),
        );
        await this.notify();
        try {
          const res = await fetch('/api/v1/sync/doubts', {
            method: 'POST',
            headers,
            body: JSON.stringify({
              doubts: pendingDoubts.map(doubt => ({
                clientDoubtId: doubt.clientDoubtId,
                pathId: doubt.pathId,
                lessonVersionId: doubt.lessonVersionId,
                blockId: doubt.blockId,
                sourcePage: doubt.sourcePage,
                questionText: doubt.questionText,
                submittedAt: doubt.submittedAt,
              })),
            }),
          });

          if (res.ok) {
            const data = await res.json();
            const results: any[] = data.results || [];
            for (const result of results) {
              const matching = pendingDoubts.find(
                doubt => doubt.clientDoubtId === result.clientDoubtId
              );
              if (!matching) continue;

              const answer = result.answerJson?.answer;
              if (result.status === 'answered' && answer) {
                const answeredAt =
                  result.answerJson?.answeredAt || new Date().toISOString();
                await db.doubtOutbox.update(matching.clientDoubtId, {
                  synced: true,
                  status: 'answered',
                  lastError: undefined,
                  answerPayload: {
                    answer,
                    citations: result.answerJson?.citations || [],
                    answeredAt,
                    limitations: result.answerJson?.limitations ?? null,
                  },
                });
                syncedDoubts += 1;
              } else {
                await db.doubtOutbox.update(matching.clientDoubtId, {
                  synced: false,
                  status: result.status === 'rejected' ? 'rejected' : 'needs_retry',
                  lastError:
                    result.answerJson?.message ||
                    result.error ||
                    'The tutor is unavailable. Try again.',
                });
              }
            }
          } else {
            throw new Error(`Sync endpoint returned ${res.status}`);
          }
        } catch (err) {
          syncFailed = true;
          const message = 'The tutor could not be reached. Your question is saved and will retry.';
          await db.doubtOutbox.bulkUpdate(
            doubtIds.map(id => ({
              key: id,
              changes: {
                synced: false,
                status: 'queued' as const,
                lastError: message,
              },
            })),
          );
          console.warn('[SETU SyncManager] Doubt sync error:', err);
        }
      }

      // 2. Sync attempts one at a time so each idempotency key is applied once.
      const pendingAttempts = await db.offlineAttempts
        .where('ownerId')
        .equals(ownerId)
        .and(attempt => !attempt.synced)
        .toArray();
      for (const attempt of pendingAttempts) {
        try {
          const response = await fetch('/api/v1/attempts', {
            method: 'POST',
            headers,
            body: JSON.stringify({
              lessonVersionId: attempt.lessonVersionId,
              questionKey: attempt.questionKey,
              response: attempt.response,
              hintLevel: attempt.hintLevel,
              hintsUsed: attempt.hintsUsed,
              elapsedSeconds: attempt.elapsedSeconds,
              attemptKind: attempt.attemptKind,
              syncIdempotencyKey: attempt.clientAttemptId,
            }),
          });

          if (response.ok) {
            await db.offlineAttempts.update(attempt.clientAttemptId, {
              synced: true,
              syncError: undefined,
            });
            syncedAttempts += 1;
          } else if (
            response.status >= 400 &&
            response.status < 500 &&
            ![401, 429].includes(response.status)
          ) {
            const detail = await response.json().catch(() => ({}));
            await db.offlineAttempts.update(attempt.clientAttemptId, {
              syncError:
                typeof detail.detail === 'string'
                  ? detail.detail
                  : `Rejected (${response.status})`,
            });
          }
        } catch (err) {
          syncFailed = true;
          await db.offlineAttempts.update(attempt.clientAttemptId, {
            syncError: 'Network error — will retry on the next sync.',
          });
          console.warn('[SETU SyncManager] Attempt sync error:', err);
        }
      }
    } finally {
      this.lastSyncError = syncFailed
        ? 'Last sync failed — your offline work is safe and will retry.'
        : null;
      this.isSyncing = false;
      await this.notify();
    }

    return { syncedDoubts, syncedAttempts };
  }
}

export const syncManager = new SyncManager();
