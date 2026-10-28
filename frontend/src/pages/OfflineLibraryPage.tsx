import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { HardDrive, Trash2, BookOpen, ArrowLeft } from 'lucide-react';
import { listOfflineLessons, deleteOfflineLesson, getOfflineStorageUsage, type OfflineLesson } from '../db/indexedDB';

export const OfflineLibraryPage: React.FC = () => {
  const navigate = useNavigate();
  const [lessons, setLessons] = useState<OfflineLesson[]>([]);
  const [usage, setUsage] = useState<{ count: number; totalBytes: number }>({ count: 0, totalBytes: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadOfflineData();
  }, []);

  const loadOfflineData = async () => {
    setLoading(true);
    const offlineList = await listOfflineLessons();
    const storageUsage = await getOfflineStorageUsage();
    setLessons(offlineList);
    setUsage(storageUsage);
    setLoading(false);
  };

  const handleDelete = async (lessonId: string) => {
    await deleteOfflineLesson(lessonId);
    await loadOfflineData();
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '32px 24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <button onClick={() => navigate('/')} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#4A5873', fontSize: '13px', marginBottom: '8px', cursor: 'pointer' }}>
            <ArrowLeft size={14} /> Back to Desk
          </button>
          <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#15233B' }}>Offline Learning Library</h1>
          <p style={{ fontSize: '14px', color: '#4A5873' }}>
            Lessons and visual diagrams stored locally in your browser IndexedDB for study without internet access.
          </p>
        </div>

        {/* Quota Card */}
        <div style={{ padding: '16px 20px', background: '#FFFFFF', border: '1px solid #D9DEEA', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '16px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <HardDrive size={28} color="#4055D9" />
          <div>
            <div style={{ fontSize: '12px', fontWeight: 600, color: '#7E8B9F', textTransform: 'uppercase' }}>IndexedDB Storage</div>
            <div style={{ fontSize: '16px', fontWeight: 700, color: '#15233B' }}>
              {usage.count} package(s) • {formatBytes(usage.totalBytes)}
            </div>
          </div>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#7E8B9F' }}>Checking IndexedDB...</div>
      ) : lessons.length === 0 ? (
        <div style={{ padding: '48px', textAlign: 'center', background: '#FFFFFF', border: '1px dashed #D9DEEA', borderRadius: '12px' }}>
          <HardDrive size={40} color="#BDC8DA" style={{ marginBottom: '12px' }} />
          <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#15233B' }}>No offline lessons downloaded yet</h3>
          <p style={{ fontSize: '14px', color: '#7E8B9F', marginTop: '4px', maxWidth: '440px', margin: '4px auto 16px' }}>
            Open any lesson from your Desk and click "Save Offline" to download all explanations, worked examples, and diagrams.
          </p>
          <button
            onClick={() => navigate('/')}
            style={{ padding: '8px 16px', background: '#4055D9', color: '#FFFFFF', borderRadius: '6px', fontSize: '13px', fontWeight: 600 }}
          >
            Browse Desk
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
          {lessons.map(l => (
            <div
              key={l.lessonId}
              style={{
                background: '#FFFFFF',
                border: '1px solid #D9DEEA',
                borderRadius: '10px',
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: '#4055D9', background: '#EEF1FC', padding: '2px 8px', borderRadius: '4px' }}>
                    Class {l.grade} • {l.subjectId}
                  </span>
                  <span style={{ fontSize: '11px', color: '#7E8B9F' }}>
                    {formatBytes(l.sizeBytes)}
                  </span>
                </div>
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#15233B', marginBottom: '8px', lineHeight: 1.4 }}>
                  {l.title}
                </h3>
                <div style={{ fontSize: '12px', color: '#7E8B9F' }}>
                  Downloaded: {new Date(l.downloadedAt).toLocaleDateString()}
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '20px', paddingTop: '12px', borderTop: '1px solid #E8ECF4' }}>
                <button
                  onClick={() => navigate(`/lesson/${l.lessonId}?pathId=${l.pathId}`)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#4055D9', fontSize: '13px', fontWeight: 600 }}
                >
                  <BookOpen size={14} /> Open Offline
                </button>

                <button
                  onClick={() => handleDelete(l.lessonId)}
                  style={{ color: '#C93B2B', padding: '6px', borderRadius: '4px' }}
                  title="Remove from offline cache"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
