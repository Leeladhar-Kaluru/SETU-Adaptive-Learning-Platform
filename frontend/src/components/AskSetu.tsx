import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  BookOpen,
  FileSearch,
  Loader2,
  MessageCircleQuestion,
  Send,
  Sparkles,
  WifiOff,
  X,
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { db, getAllDoubts, queueDoubtOffline, type OfflineDoubt } from '../db/indexedDB';
import { syncManager } from '../services/syncManager';
import { useDialogFocus } from '../hooks/useDialogFocus';
import { AuthModal } from './AuthModal';
import styles from './AskSetu.module.css';

export function openAskSetu(): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('open-ask-setu'));
  }
}

type Citation = {
  citationId?: string;
  sourceTitle?: string | null;
  pageStart?: number;
  pageEnd?: number;
  excerpt?: string;
};

type ChatEntry = {
  id: string;
  question: string;
  answer: string;
  citations: Citation[];
  limitations?: string | null;
  queued?: boolean;
  syncStatus?: string;
};

const makeId = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? `doubt_${crypto.randomUUID()}`
    : `doubt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

const toEntry = (row: OfflineDoubt): ChatEntry => {
  const payload = row.answerPayload;
  const queued = !row.synced;
  let answer: string;
  if (payload?.answer) {
    answer = payload.answer;
  } else if (row.status === 'syncing') {
    answer = 'Sending your question to SETU…';
  } else if (queued) {
    answer =
      'Saved on this device. Your question will be sent automatically when you are back online, and the answer will appear here.';
  } else {
    answer = row.lastError || 'SETU could not answer that yet.';
  }
  return {
    id: row.clientDoubtId,
    question: row.questionText,
    answer,
    citations: (payload?.citations || []) as Citation[],
    limitations: payload?.limitations ?? null,
    queued,
    syncStatus: row.synced ? 'answered' : row.status,
  };
};

export const AskSetu: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [question, setQuestion] = useState('');
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOnline, setIsOnline] = useState(
    typeof navigator !== 'undefined' ? navigator.onLine : true
  );
  const dialogRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const threadEndRef = useRef<HTMLDivElement>(null);
  const wasSyncingRef = useRef(false);

  const pathId = new URLSearchParams(location.search).get('pathId') || undefined;
  const [activePath, setActivePath] = useState<{ id: string; title: string; sourceTitle?: string } | null>(null);

  useEffect(() => {
    if (!user) return;
    let isMounted = true;
    api.getLearningPaths()
      .then((paths) => {
        if (!isMounted || !paths || paths.length === 0) return;
        const matched = pathId ? paths.find((p) => p.id === pathId) : paths[0];
        if (matched) {
          setActivePath({
            id: matched.id,
            title: matched.title,
            sourceTitle: matched.sourceTitle || matched.title,
          });
        }
      })
      .catch(() => {});
    return () => {
      isMounted = false;
    };
  }, [user, pathId]);

  useDialogFocus(dialogRef, isOpen, () => setIsOpen(false));

  useEffect(() => {
    const online = () => setIsOnline(true);
    const offline = () => setIsOnline(false);
    window.addEventListener('online', online);
    window.addEventListener('offline', offline);
    return () => {
      window.removeEventListener('online', online);
      window.removeEventListener('offline', offline);
    };
  }, []);

  const loadThread = useCallback(async () => {
    if (!user) return;
    const rows = await getAllDoubts(user.id);
    setEntries(rows.slice().reverse().map(toEntry));
  }, [user]);

  useEffect(() => {
    if (isOpen) {
      void loadThread();
      window.setTimeout(() => inputRef.current?.focus(), 80);
    }
  }, [isOpen, loadThread]);

  // After every sync pass, re-read the outbox so offline questions that just
  // got answered by the server appear in the thread.
  useEffect(() => {
    if (!user) return;
    return syncManager.subscribe((isSyncing) => {
      if (wasSyncingRef.current && !isSyncing) {
        void loadThread();
      }
      wasSyncingRef.current = isSyncing;
    });
  }, [user, loadThread]);

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [entries, busy]);

  useEffect(() => {
    const handleOpen = () => {
      if (!user) {
        setIsAuthModalOpen(true);
      } else {
        setIsOpen(true);
      }
    };
    window.addEventListener('open-ask-setu', handleOpen);
    return () => window.removeEventListener('open-ask-setu', handleOpen);
  }, [user]);

  if (user?.role === 'teacher') return null;

  const submit = async (overrideText?: string) => {
    if (!user) {
      setIsAuthModalOpen(true);
      return;
    }
    const text = (overrideText !== undefined ? overrideText : question).trim();
    if (text.length < 1 || busy) return;
    const clientDoubtId = makeId();
    const effectivePathId = pathId || activePath?.id;
    setBusy(true);
    setError(null);
    setQuestion('');

    // Safety watchdog: ensure busy never stays permanently stuck
    const safetyTimer = window.setTimeout(() => {
      setBusy(false);
    }, 20000);

    if (!navigator.onLine) {
      try {
        await queueDoubtOffline({
          clientDoubtId,
          ownerId: user.id,
          pathId: effectivePathId || '',
          questionText: text,
        });
        await syncManager.refreshPending();
        setEntries((prev) => [
          ...prev,
          {
            id: clientDoubtId,
            question: text,
            answer:
              'Saved on this device. Your question will be sent automatically when you are back online, and the answer will appear here.',
            citations: [],
            limitations: null,
            queued: true,
            syncStatus: 'queued',
          },
        ]);
      } catch {
        setError('This browser could not store the question offline. Try again when you reconnect.');
        setQuestion(text);
      } finally {
        setBusy(false);
      }
      return;
    }

    try {
      const result = await api.askDoubt({
        clientDoubtId,
        questionText: text,
        ...(effectivePathId ? { pathId: effectivePathId } : {}),
      });
      const payload = result.answerJson || {};
      if (result.status === 'answered' && payload.answer) {
        await queueDoubtOffline({
          clientDoubtId,
          ownerId: user.id,
          pathId: effectivePathId || '',
          questionText: text,
        });
        await db.doubtOutbox.update(clientDoubtId, {
          status: 'answered',
          synced: true,
          answerPayload: {
            answer: payload.answer,
            citations: payload.citations || [],
            answeredAt: payload.answeredAt || new Date().toISOString(),
            limitations: payload.limitations ?? null,
          },
        });
        setEntries((prev) => [
          ...prev,
          {
            id: clientDoubtId,
            question: text,
            answer: payload.answer,
            citations: payload.citations || [],
            limitations: payload.limitations ?? null,
          },
        ]);
      } else {
        setError(payload.message || 'SETU could not answer that yet. Please try again.');
        setQuestion(text);
      }
    } catch (err: unknown) {
      if (err instanceof TypeError) {
        setError('Could not reach SETU. Your question was not sent — try again when you reconnect.');
      } else {
        setError(err instanceof Error ? err.message : 'SETU could not answer that yet.');
      }
      setQuestion(text);
    } finally {
      window.clearTimeout(safetyTimer);
      setBusy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        className={styles.launcher}
        onClick={() => {
          if (!user) {
            setIsAuthModalOpen(true);
          } else {
            setIsOpen(true);
          }
        }}
        aria-label="Ask SETU a question"
      >
        <span className={styles.launcherGlow} aria-hidden="true" />
        <MessageCircleQuestion size={19} />
        <span>Ask SETU</span>
      </button>

      {isAuthModalOpen && (
        <AuthModal isOpen={isAuthModalOpen} onClose={() => setIsAuthModalOpen(false)} />
      )}

      {isOpen && (
        <div className={styles.overlay} onMouseDown={(event) => {
          if (event.target === event.currentTarget) setIsOpen(false);
        }}>
          <div
            className={styles.drawer}
            role="dialog"
            aria-modal="true"
            aria-labelledby="ask-setu-title"
            ref={dialogRef}
          >
            <header className={styles.header}>
              <div className={styles.headerCopy}>
                <span className={styles.kicker}>
                  <Sparkles size={12} /> Your study companion
                </span>
                <h2 id="ask-setu-title">Ask SETU</h2>
                <p>
                  Answers from your books show the exact page. General questions are
                  answered honestly and labeled.
                </p>
                {activePath && (
                  <div style={{ marginTop: '0.45rem', display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem', background: 'rgba(255, 255, 255, 0.18)', padding: '0.2rem 0.55rem', borderRadius: '4px', maxWidth: '100%', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    <BookOpen size={13} style={{ flexShrink: 0 }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>Studying: <strong>{activePath.sourceTitle || activePath.title}</strong></span>
                  </div>
                )}
              </div>
              <button
                type="button"
                className={styles.close}
                onClick={() => setIsOpen(false)}
                aria-label="Close Ask SETU"
              >
                <X size={18} />
              </button>
              <span className={styles.headerSun} aria-hidden="true" />
              <span className={styles.headerRing} aria-hidden="true" />
            </header>

            <div className={styles.thread} aria-live="polite">
              {entries.length === 0 && !busy && (
                <div className={styles.empty}>
                  <span className={styles.emptyIcon}>
                    <BookOpen size={22} />
                  </span>
                  <h3>Stuck on something?</h3>
                  <p>
                    Ask about any topic in your books — answers cite the exact page.
                    Questions beyond your books are answered from general knowledge
                    and labeled honestly.
                  </p>
                  <div className={styles.prompts}>
                    {['Explain this topic simply', 'Why does this happen?', 'Give me an example'].map(
                      (prompt) => (
                        <button
                          key={prompt}
                          type="button"
                          className={styles.promptChip}
                          onClick={() => setQuestion(prompt)}
                        >
                          {prompt}
                        </button>
                      )
                    )}
                  </div>
                </div>
              )}

              {entries.map((entry) => (
                <article key={entry.id} className={styles.exchange}>
                  <p className={styles.question}>{entry.question}</p>
                  <div
                    className={`${styles.answer} ${
                      entry.limitations === 'no_source_attached' ? styles.answerNotice : ''
                    } ${entry.limitations === 'general_knowledge' ? styles.answerGeneral : ''} ${
                      entry.queued ? styles.answerQueued : ''
                    }`}
                  >
                    {entry.syncStatus === 'syncing' && (
                      <span className={styles.answerTag}>
                        <Loader2 size={12} className={styles.spin} /> Sending…
                      </span>
                    )}
                    {entry.queued && entry.syncStatus !== 'syncing' && (
                      <span className={styles.answerTag}>
                        <WifiOff size={12} /> Saved offline
                      </span>
                    )}
                    {entry.limitations === 'general_knowledge' && (
                      <span className={`${styles.answerTag} ${styles.answerTagGeneral}`}>
                        <Sparkles size={12} /> General knowledge
                      </span>
                    )}
                    {entry.limitations === 'no_source_attached' && (
                      <span className={styles.answerTag}>
                        <BookOpen size={12} /> No source attached
                      </span>
                    )}
                    <p>{entry.answer}</p>
                    {entry.limitations === 'general_knowledge' && (
                      <p className={styles.generalNote}>
                        Not from your books — add a source for page-cited answers.
                      </p>
                    )}
                    {entry.limitations === 'no_source_attached' && (
                      <button
                        type="button"
                        className={styles.inlineAction}
                        onClick={() => {
                          setIsOpen(false);
                          navigate('/');
                        }}
                      >
                        Add your first source <ArrowRight size={14} />
                      </button>
                    )}
                    {entry.citations.length > 0 && (
                      <div className={styles.citations}>
                        <FileSearch size={13} />
                        <span>
                          {entry.citations.map((citation, index) => (
                            <span key={citation.citationId || index} className={styles.citation}>
                              {citation.sourceTitle
                                ? `${citation.sourceTitle} · page ${citation.pageStart ?? ''}`
                                : `Page ${citation.pageStart ?? ''}`}
                            </span>
                          ))}
                        </span>
                      </div>
                    )}
                  </div>
                </article>
              ))}

              {busy && (
                <div className={styles.thinking}>
                  <Loader2 size={15} className={styles.spin} />
                  Reading your sources…
                </div>
              )}

              {error && (
                <p className={styles.error} role="alert">
                  {error}
                </p>
              )}
              <div ref={threadEndRef} />
            </div>

            <form
              className={styles.composer}
              onSubmit={(event) => {
                event.preventDefault();
                void submit();
              }}
            >
              <textarea
                ref={inputRef}
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    void submit();
                  }
                }}
                rows={2}
                maxLength={2000}
                placeholder={
                  isOnline
                    ? 'Ask about your books — or anything you are curious about.'
                    : 'You are offline — ask now and it will sync later.'
                }
                aria-label="Your question"
              />
              <button
                type="submit"
                className={styles.send}
                disabled={busy || question.trim().length === 0}
                aria-label="Send question"
              >
                {busy ? <Loader2 size={17} className={styles.spin} /> : <Send size={17} />}
              </button>
            </form>

            <footer className={styles.footer}>
              <span>
                <span className={isOnline ? styles.dotOnline : styles.dotOffline} />
                {isOnline ? 'Online' : 'Offline — questions queue safely'}
              </span>
              <button type="button" onClick={() => navigate('/doubts')}>
                All doubts <ArrowRight size={13} />
              </button>
            </footer>
          </div>
        </div>
      )}
    </>
  );
};
