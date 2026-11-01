import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { HardDrive, Trash2, BookOpen, ArrowLeft, RefreshCw } from 'lucide-react';
import { listOfflineLessons, deleteOfflineLesson, getOfflineStorageUsage, type OfflineLesson } from '../db/indexedDB';
import { useAuth } from '../context/AuthContext';
import { gradeLabel } from '../lib/academic';
import styles from './OfflineLibraryPage.module.css';

export const OfflineLibraryPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [lessons, setLessons] = useState<OfflineLesson[]>([]);
  const [usage, setUsage] = useState<{ count: number; totalBytes: number }>({ count: 0, totalBytes: 0 });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadOfflineData = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    if (!user) {
      setLessons([]);
      setUsage({ count: 0, totalBytes: 0 });
      setLoading(false);
      return;
    }
    try {
      const offlineList = await listOfflineLessons(user.id);
      const storageUsage = await getOfflineStorageUsage(user.id);
      setLessons(offlineList);
      setUsage(storageUsage);
    } catch {
      setLessons([]);
      setUsage({ count: 0, totalBytes: 0 });
      setLoadError(
        'This browser did not allow SETU to read its local storage. Downloads may be unavailable or blocked by private browsing.'
      );
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void loadOfflineData();
  }, [loadOfflineData]);

  const handleDelete = async (lessonId: string) => {
    if (!user) return;
    setDeletingId(lessonId);
    setDeleteError(null);
    try {
      await deleteOfflineLesson(user.id, lessonId);
      setConfirmDeleteId(null);
      await loadOfflineData();
    } catch {
      setDeleteError(
        'This download could not be removed from local storage. Close other SETU tabs and try again.'
      );
    } finally {
      setDeletingId(null);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  const subjectLabel = (subjectId: string) =>
    subjectId.replace(/^subject[-_]/, '').replace(/[-_]/g, ' ');

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <button type="button" className={styles.backButton} onClick={() => navigate('/')}>
            <ArrowLeft size={14} /> Back to desk
          </button>
          <span className={styles.eyebrow}>On this device</span>
          <h1>Offline downloads</h1>
          <p className={styles.lede}>
            Lessons stored in this browser's IndexedDB. They open from the saved copy even when
            the network is unavailable.
          </p>
        </div>

        <div className={styles.quotaCard} aria-label="Local storage use">
          <HardDrive size={22} aria-hidden="true" />
          <div>
            <div className={styles.quotaLabel}>IndexedDB storage</div>
            <div className={styles.quotaValue}>
              {usage.count} {usage.count === 1 ? 'lesson' : 'lessons'} · {formatBytes(usage.totalBytes)}
            </div>
          </div>
        </div>
      </header>

      {loadError && (
        <div className={styles.errorBanner} role="alert">
          <span>{loadError}</span>
          <button type="button" className={styles.retryButton} onClick={() => void loadOfflineData()}>
            <RefreshCw size={13} /> Retry
          </button>
        </div>
      )}

      {deleteError && (
        <div className={styles.errorBanner} role="alert">
          <span>{deleteError}</span>
          <button type="button" className={styles.retryButton} onClick={() => setDeleteError(null)}>
            Dismiss
          </button>
        </div>
      )}

      {loading ? (
        <p className={styles.loadNote} role="status">Checking this browser's local storage…</p>
      ) : lessons.length === 0 && !loadError ? (
        <section className={styles.emptyState}>
          <HardDrive size={32} aria-hidden="true" />
          <h2>No offline lessons downloaded yet</h2>
          <p>
            Open a ready lesson and choose <strong>Save Offline</strong>. The saved copy includes
            its explanations, worked examples, and visuals.
          </p>
          <button type="button" className={styles.primary} onClick={() => navigate('/')}>
            Browse the desk
          </button>
        </section>
      ) : lessons.length > 0 ? (
        <ul className={styles.grid}>
          {lessons.map((lesson) => {
            const isConfirming = confirmDeleteId === lesson.lessonId;
            const isDeleting = deletingId === lesson.lessonId;
            return (
              <li key={lesson.lessonId} className={styles.card}>
                <div className={styles.cardTop}>
                  <span className={styles.metaLine}>
                    {gradeLabel(lesson.grade)} · {subjectLabel(lesson.subjectId)}
                  </span>
                  <span className={styles.size}>{formatBytes(lesson.sizeBytes)}</span>
                </div>
                <h2 className={styles.cardTitle}>{lesson.title}</h2>
                <div className={styles.cardMeta}>
                  Saved {new Date(lesson.downloadedAt).toLocaleDateString()}
                  <span aria-hidden="true"> · </span>
                  Last opened {new Date(lesson.lastAccessedAt).toLocaleDateString()}
                </div>

                <div className={styles.cardActions}>
                  <button
                    type="button"
                    className={styles.openButton}
                    onClick={() => navigate(`/lesson/${lesson.lessonId}?pathId=${lesson.pathId}`)}
                  >
                    <BookOpen size={14} /> Open saved copy
                  </button>

                  {isConfirming ? (
                    <div className={styles.confirmRow}>
                      <span className={styles.confirmText}>Remove this download?</span>
                      <button
                        type="button"
                        className={styles.dangerButton}
                        onClick={() => void handleDelete(lesson.lessonId)}
                        disabled={isDeleting}
                      >
                        {isDeleting ? 'Removing…' : 'Remove'}
                      </button>
                      <button
                        type="button"
                        className={styles.secondary}
                        onClick={() => setConfirmDeleteId(null)}
                        disabled={isDeleting}
                      >
                        Keep
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className={styles.deleteButton}
                      onClick={() => {
                        setConfirmDeleteId(lesson.lessonId);
                        setDeleteError(null);
                      }}
                      aria-label={`Remove ${lesson.title} from this device`}
                    >
                      <Trash2 size={15} />
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
};
