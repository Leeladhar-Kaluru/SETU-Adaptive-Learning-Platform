import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw, CheckCircle, Clock, FileSearch } from 'lucide-react';
import { getAllDoubts, type OfflineDoubt } from '../db/indexedDB';
import { syncManager } from '../services/syncManager';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const DoubtQueuePage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [doubts, setDoubts] = useState<OfflineDoubt[]>([]);
  const [isSyncing, setIsSyncing] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void loadDoubts();
    const unsubscribe = syncManager.subscribe((syncing) => {
      setIsSyncing(syncing);
      if (!syncing) {
        void loadDoubts();
      }
    });
    return unsubscribe;
  }, [user?.id]);

  const loadDoubts = async () => {
    setLoading(true);
    if (!user) {
      setDoubts([]);
      setLoading(false);
      return;
    }
    const localList = await getAllDoubts(user.id);
    try {
      const serverList = await api.listDoubts();
      const serverMap = new Set(serverList.map((s) => s.clientDoubtId));

      const serverFormatted: OfflineDoubt[] = serverList.map((s) => ({
        clientDoubtId: s.clientDoubtId,
        ownerId: user.id,
        pathId: '',
        questionText: s.questionText,
        status: (s.status === 'answered' ? 'answered' : s.status === 'failed' ? 'failed' : 'queued') as any,
        synced: true,
        submittedAt: s.createdAt,
        answerPayload: s.answerJson
          ? {
              answer: s.answerJson.answer || '',
              citations: s.answerJson.citations || [],
              answeredAt: s.answerJson.answeredAt || s.createdAt,
            }
          : undefined,
      }));

      // Combine server records with local un-synced outbox
      const localOnly = localList.filter((l) => !serverMap.has(l.clientDoubtId));
      const combined = [...serverFormatted, ...localOnly].sort(
        (a, b) => new Date(b.submittedAt).getTime() - new Date(a.submittedAt).getTime()
      );
      setDoubts(combined);
    } catch {
      setDoubts(localList);
    } finally {
      setLoading(false);
    }
  };

  const handleManualSync = async () => {
    await syncManager.syncPendingData();
    await loadDoubts();
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '32px 24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <button onClick={() => navigate('/')} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#4A5873', fontSize: '13px', marginBottom: '8px', cursor: 'pointer' }}>
            <ArrowLeft size={14} /> Back to Desk
          </button>
          <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#15233B' }}>Doubt Sync Queue</h1>
          <p style={{ fontSize: '14px', color: '#4A5873' }}>
            Questions asked during offline study are persisted locally in IndexedDB and resolved idempotently once connected.
          </p>
        </div>

        <button
          onClick={handleManualSync}
          disabled={isSyncing}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 18px',
            background: '#4055D9',
            color: '#FFFFFF',
            borderRadius: '6px',
            fontSize: '13px',
            fontWeight: 600,
            cursor: isSyncing ? 'not-allowed' : 'pointer'
          }}
        >
          <RefreshCw size={15} className={isSyncing ? 'spin' : ''} />
          {isSyncing ? 'Syncing...' : 'Sync Queue Now'}
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#7E8B9F' }}>Checking queue...</div>
      ) : doubts.length === 0 ? (
        <div style={{ padding: '48px', textAlign: 'center', background: '#FFFFFF', border: '1px dashed #D9DEEA', borderRadius: '12px' }}>
          <Clock size={40} color="#BDC8DA" style={{ marginBottom: '12px' }} />
          <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#15233B' }}>Doubt queue is empty</h3>
          <p style={{ fontSize: '14px', color: '#7E8B9F', marginTop: '4px', maxWidth: '440px', margin: '4px auto 16px' }}>
            When studying any lesson offline or online, use "Ask Doubt" or click "Ask Tutor" under any section to log questions.
          </p>
          <button
            onClick={() => navigate('/')}
            style={{ padding: '8px 16px', background: '#4055D9', color: '#FFFFFF', borderRadius: '6px', fontSize: '13px', fontWeight: 600 }}
          >
            Go to Desk
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {doubts.map(d => (
            <div
              key={d.clientDoubtId}
              style={{
                background: '#FFFFFF',
                border: '1px solid #D9DEEA',
                borderRadius: '10px',
                padding: '20px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: '#7E8B9F', textTransform: 'uppercase' }}>
                    Client ID: {d.clientDoubtId} • Submitted: {new Date(d.submittedAt).toLocaleTimeString()}
                  </span>
                  <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#15233B', marginTop: '4px' }}>
                    "{d.questionText}"
                  </h3>
                </div>

                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '4px 10px',
                    borderRadius: '9999px',
                    fontSize: '12px',
                    fontWeight: 600,
                    background: d.status === 'answered' ? '#E8F5F0' : '#FDF5EB',
                    color: d.status === 'answered' ? '#23795B' : '#A65B12',
                    border: `1px solid ${d.status === 'answered' ? '#A3D9C4' : '#F1CE9C'}`
                  }}
                >
                  {d.status === 'answered' ? <CheckCircle size={13} /> : <Clock size={13} />}
                  {d.status === 'answered' ? 'Answered' : 'Queued (Offline)'}
                </span>
              </div>

              {d.answerPayload && (
                <div style={{ padding: '16px', background: '#FAFAF8', borderRadius: '8px', border: '1px solid #D9DEEA' }}>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: '#4055D9', marginBottom: '6px' }}>
                    VERIFIED TEXTBOOK ANSWER
                  </div>
                  <div style={{ fontSize: '14px', lineHeight: 1.6, color: '#15233B' }}>
                    {d.answerPayload.answer}
                  </div>

                  {d.answerPayload.citations?.length > 0 && (
                    <div style={{ marginTop: '12px', paddingTop: '8px', borderTop: '1px solid #D9DEEA', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#23795B' }}>
                      <FileSearch size={14} />
                      <span>
                        Verified in source:{' '}
                        {d.answerPayload.citations.map((c: any, i: number) => (
                          <strong key={i} style={{ marginRight: '6px' }}>
                            Page {c.pageNumber || c.pageStart}{c.pageEnd && c.pageEnd !== (c.pageNumber || c.pageStart) ? `–${c.pageEnd}` : ''}
                          </strong>
                        ))}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

