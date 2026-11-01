import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw, CheckCircle2, Clock, AlertTriangle, Ban, FileSearch } from 'lucide-react';
import { getAllDoubts, type OfflineDoubt } from '../db/indexedDB';
import { syncManager } from '../services/syncManager';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import styles from './DoubtQueuePage.module.css';

type DoubtStatus = 'answered' | 'needs_retry' | 'rejected' | 'waiting' | 'processing';

interface DoubtRow {
  clientDoubtId: string;
  questionText: string;
  status: DoubtStatus;
  submittedAt: string;
  pathId?: string | null;
  answer?: string;
  citations: Array<{ citationId?: string; sourceTitle?: string | null; pageNumber?: number; pageStart?: number; pageEnd?: number; snippet?: string; excerpt?: string }>;
  limitations?: string | null;
  retryable: boolean;
  errorMessage?: string;
}

const STATUS_LABEL: Record<DoubtStatus, string> = {
  answered: 'Answered',
  needs_retry: 'Needs retry',
  rejected: 'Rejected',
  waiting: 'Waiting to sync',
  processing: 'Being answered',
};

function toRow(local: OfflineDoubt): DoubtRow {
  let status: DoubtStatus = 'waiting';
  if (local.status === 'answered') status = 'answered';
  else if (local.status === 'rejected') status = 'rejected';
  else if (local.status === 'needs_retry' || local.status === 'failed') status = 'needs_retry';
  else if (local.status === 'syncing') status = 'processing';

  return {
    clientDoubtId: local.clientDoubtId,
    questionText: local.questionText,
    status,
    submittedAt: local.submittedAt,
    pathId: local.pathId,
    answer: local.answerPayload?.answer || undefined,
    citations: local.answerPayload?.citations || [],
    limitations: local.answerPayload?.limitations ?? null,
    retryable: status === 'needs_retry',
    errorMessage: local.lastError,
  };
}

export const DoubtQueuePage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [localDoubts, setLocalDoubts] = useState<OfflineDoubt[]>([]);
  const [serverDoubts, setServerDoubts] = useState<DoubtRow[]>([]);
  const [serverStatus, setServerStatus] = useState<{ state: 'loading' | 'ready' | 'error'; message?: string }>({
    state: 'loading',
  });
  const [isSyncing, setIsSyncing] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [retryErrors, setRetryErrors] = useState<Record<string, string>>({});
  const [localError, setLocalError] = useState<string | null>(null);
  const [isOnline, setIsOnline] = useState(
    typeof navigator !== 'undefined' ? navigator.onLine : true
  );

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const loadLocal = async () => {
    if (!user) {
      setLocalDoubts([]);
      return;
    }
    setLocalError(null);
    try {
      setLocalDoubts(await getAllDoubts(user.id));
    } catch {
      setLocalDoubts([]);
      setLocalError(
        'This browser did not allow SETU to read its local queue. Questions saved offline may not appear here.'
      );
    }
  };

  const loadServer = async () => {
    if (!user) return;
    setServerStatus({ state: 'loading' });
    try {
      const list = await api.listDoubts();
      setServerDoubts(
        list.map((doubt) => {
          const answered = doubt.status === 'answered' && Boolean(doubt.answerJson?.answer);
          const status: DoubtStatus = answered
            ? 'answered'
            : doubt.status === 'rejected'
              ? 'rejected'
              : doubt.status === 'needs_retry'
                ? 'needs_retry'
                : doubt.status === 'queued_offline' ||
                    doubt.status === 'sending' ||
                    doubt.status === 'processing'
                  ? 'processing'
                  : 'waiting';
          return {
            clientDoubtId: doubt.clientDoubtId,
            questionText: doubt.questionText,
            status,
            submittedAt: doubt.createdAt,
            pathId: doubt.pathId ?? null,
            answer: doubt.answerJson?.answer || undefined,
            citations: doubt.answerJson?.citations || [],
            limitations: doubt.answerJson?.limitations ?? null,
            retryable: status === 'needs_retry',
            errorMessage: doubt.lastErrorCode || doubt.answerJson?.message || undefined,
          };
        })
      );
      setServerStatus({ state: 'ready' });
    } catch (err: any) {
      setServerStatus({
        state: 'error',
        message: err?.message || 'Doubt history could not be loaded from SETU.',
      });
    }
  };

  useEffect(() => {
    void loadLocal();
    void loadServer();
    const unsubscribe = syncManager.subscribe((syncing) => {
      setIsSyncing(syncing);
      if (!syncing) {
        void loadLocal();
        void loadServer();
      }
    });
    return unsubscribe;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  const rows = useMemo(() => {
    const serverMap = new Map(serverDoubts.map((row) => [row.clientDoubtId, row]));
    const localRows = localDoubts.map(toRow);
    const merged = localRows.map((row) => {
      const server = serverMap.get(row.clientDoubtId);
      if (!server) return row;
      const localAnswered = row.status === 'answered';
      return localAnswered ? row : server;
    });
    for (const server of serverDoubts) {
      if (!merged.some((row) => row.clientDoubtId === server.clientDoubtId)) {
        merged.push(server);
      }
    }
    return merged.sort(
      (a, b) => new Date(b.submittedAt).getTime() - new Date(a.submittedAt).getTime()
    );
  }, [localDoubts, serverDoubts]);

  const handleManualSync = async () => {
    await syncManager.syncPendingData();
    await loadLocal();
    await loadServer();
  };

  const handleRetry = async (row: DoubtRow) => {
    if (!user) return;
    setRetryingId(row.clientDoubtId);
    setRetryErrors((prev) => ({ ...prev, [row.clientDoubtId]: '' }));
    try {
      const res = await api.askDoubt({
        clientDoubtId: row.clientDoubtId,
        questionText: row.questionText,
        pathId: row.pathId || undefined,
      });
      if (res.status !== 'answered' || !res.answerJson?.answer) {
        throw new Error(res.answerJson?.message || 'The tutor is still unavailable.');
      }
      setServerDoubts((prev) => {
        const withoutRow = prev.filter((item) => item.clientDoubtId !== row.clientDoubtId);
        return [
          {
            ...row,
            status: 'answered' as const,
            retryable: false,
            answer: res.answerJson.answer,
            citations: res.answerJson.citations || [],
            limitations: res.answerJson.limitations ?? null,
            errorMessage: undefined,
          },
          ...withoutRow,
        ];
      });
      await loadLocal();
    } catch (err: any) {
      setRetryErrors((prev) => ({
        ...prev,
        [row.clientDoubtId]: err?.message || 'The tutor could not answer this yet.',
      }));
    } finally {
      setRetryingId(null);
    }
  };

  const statusClass = (status: DoubtStatus) =>
    status === 'answered'
      ? styles.statusAnswered
      : status === 'needs_retry'
        ? styles.statusRetry
        : status === 'rejected'
          ? styles.statusRejected
          : status === 'processing'
            ? styles.statusProcessing
            : styles.statusWaiting;

  const statusIcon = (status: DoubtStatus) => {
    if (status === 'answered') return <CheckCircle2 size={13} />;
    if (status === 'needs_retry') return <AlertTriangle size={13} />;
    if (status === 'rejected') return <Ban size={13} />;
    if (status === 'processing') return <RefreshCw size={13} className={styles.spin} />;
    return <Clock size={13} />;
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <button type="button" className={styles.backLink} onClick={() => navigate('/')}>
            <ArrowLeft size={14} /> Back to Desk
          </button>
          <h1 className={styles.title}>Doubts</h1>
          <p className={styles.lede}>
            Every question you asked SETU, with its real state. Questions asked while the device was
            offline are stored here until they can be answered.
          </p>
        </div>

        <button
          type="button"
          className={styles.syncButton}
          onClick={() => void handleManualSync()}
          disabled={isSyncing}
        >
          <RefreshCw size={15} className={isSyncing ? styles.spin : ''} />
          {isSyncing ? 'Syncing…' : 'Sync now'}
        </button>
      </div>

      {localError && (
        <div className={styles.notice} role="alert">
          <strong>Local queue unavailable.</strong> {localError}
          <button type="button" className={styles.noticeRetry} onClick={() => void loadLocal()}>
            Retry
          </button>
        </div>
      )}

      {serverStatus.state === 'error' && (
        <div className={styles.notice} role="status">
          <strong>SETU could not be reached.</strong> Showing doubts stored on this device only.
          <span className={styles.noticeDetail}>{serverStatus.message}</span>
          <button type="button" className={styles.noticeRetry} onClick={() => void loadServer()}>
            Retry
          </button>
        </div>
      )}

      {serverStatus.state === 'loading' && rows.length === 0 && (
        <div className={styles.skeleton} aria-label="Loading doubts">
          <div className={styles.skeletonLine} />
          <div className={styles.skeletonLine} />
        </div>
      )}

      {serverStatus.state !== 'loading' && rows.length === 0 && (
        <div className={styles.empty}>
          <Clock size={36} className={styles.emptyIcon} aria-hidden="true" />
          <h2>No doubts yet.</h2>
          <p>
            Open a lesson and choose Ask a doubt. Answers cite the page of your uploaded material
            they came from.
          </p>
          <button type="button" className={styles.primary} onClick={() => navigate('/')}>
            Go to your desk
          </button>
        </div>
      )}

      {rows.length > 0 && (
        <ul className={styles.list}>
          {rows.map((row) => (
            <li key={row.clientDoubtId} className={styles.card}>
              <div className={styles.cardHead}>
                <div>
                  <div className={styles.meta}>
                    {new Date(row.submittedAt).toLocaleString()}
                  </div>
                  <h2 className={styles.question}>{row.questionText}</h2>
                </div>
                <span className={`${styles.status} ${statusClass(row.status)}`}>
                  {statusIcon(row.status)} {STATUS_LABEL[row.status]}
                </span>
              </div>

              {row.status === 'answered' && row.answer && (
                <div className={styles.answer}>
                  <div className={styles.answerLabel}>
                    {row.limitations === 'no_source_attached'
                      ? 'No source attached'
                      : 'Answer from your sources'}
                  </div>
                  <p className={styles.answerText}>{row.answer}</p>
                  {row.limitations === 'no_source_attached' && (
                    <button
                      type="button"
                      className={styles.primary}
                      onClick={() => navigate('/')}
                    >
                      Add a source
                    </button>
                  )}
                  {row.limitations === 'insufficient_source_evidence' && (
                    <p className={styles.limitation}>
                      Your uploaded source did not contain enough evidence for a grounded
                      answer.
                    </p>
                  )}
                  {row.citations.length > 0 && (
                    <div className={styles.citations}>
                      <FileSearch size={14} />
                      <span>
                        {row.citations[0]?.sourceTitle ? `${row.citations[0].sourceTitle} · ` : ''}
                        Source page
                        {row.citations.length > 1 ? 's' : ''}:{' '}
                        {row.citations.map((citation, index) => {
                          const start = citation.pageNumber ?? citation.pageStart;
                          const end = citation.pageEnd;
                          return (
                            <strong key={citation.citationId || index}>
                              {start}
                              {end && end !== start ? `–${end}` : ''}
                              {index < row.citations.length - 1 ? ', ' : ''}
                            </strong>
                          );
                        })}
                      </span>
                    </div>
                  )}
                </div>
              )}

              {row.status === 'needs_retry' && (
                <div className={styles.retryBox}>
                  <p>
                    The tutor could not answer this when you last asked. Your question is saved — you
                    can retry it now.
                  </p>
                  {row.errorMessage && <p className={styles.errorDetail}>{row.errorMessage}</p>}
                  {retryErrors[row.clientDoubtId] && (
                    <p className={styles.errorDetail} role="alert">
                      {retryErrors[row.clientDoubtId]}
                    </p>
                  )}
                  <button
                    type="button"
                    className={styles.retryButton}
                    onClick={() => void handleRetry(row)}
                    disabled={retryingId === row.clientDoubtId || !isOnline}
                  >
                    {retryingId === row.clientDoubtId
                      ? 'Asking SETU…'
                      : isOnline
                        ? 'Retry'
                        : 'Retry when online'}
                  </button>
                </div>
              )}

              {row.status === 'processing' && (
                <p className={styles.waitingText}>
                  SETU is answering this question now. Refresh this page to see the result.
                </p>
              )}

              {row.status === 'waiting' && (
                <p className={styles.waitingText}>
                  Saved on this device. It will be sent when SETU is reachable.
                </p>
              )}

              {row.status === 'rejected' && (
                <p className={styles.rejectedText}>
                  This question was rejected because it was empty or malformed. Ask it again from the
                  lesson.
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
