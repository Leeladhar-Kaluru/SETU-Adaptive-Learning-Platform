import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, CheckCircle2, AlertCircle, ArrowRight, BookOpen } from 'lucide-react';
import styles from './HomePage.module.css';

interface ExtractionOutline {
  documentId: string;
  versionId: string;
  filename: string;
  pageCount: number;
  chunkCount: number;
  extractedTitle: string;
}

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [extractedOutline, setExtractedOutline] = useState<ExtractionOutline | null>(null);
  const [generatingPath, setGeneratingPath] = useState(false);
  const [catalogueItems, setCatalogueItems] = useState<any[]>([]);

  useEffect(() => {
    // Fetch catalogue
    fetch('/api/v1/catalogue/resources')
      .then(res => res.ok ? res.json() : [])
      .then(data => setCatalogueItems(data))
      .catch(err => console.warn('Could not load catalogue:', err));
  }, []);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileUpload(e.target.files[0]);
    }
  };

  const handleFileUpload = async (file: File) => {
    // Validate size (50MB)
    const MAX_SIZE = 50 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      setErrorMessage(`File exceeds the 50MB size limit (${(file.size / (1024 * 1024)).toFixed(1)}MB).`);
      return;
    }

    setErrorMessage(null);
    setIsUploading(true);
    setUploadProgress(15);
    setStatusMessage(`Uploading ${file.name} to private storage...`);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('grade', '9');
    formData.append('subject', 'SCIENCE');

    try {
      setUploadProgress(40);
      setStatusMessage('Extracting pages, text, and structure...');

      const res = await fetch('/api/v1/documents/upload', {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Upload failed with HTTP ${res.status}`);
      }

      setUploadProgress(80);
      setStatusMessage('Generating 768d vector embeddings & full-text index...');

      const data = await res.json();
      setUploadProgress(100);
      setStatusMessage('Extraction complete! Source outline ready.');

      setExtractedOutline({
        documentId: data.documentId,
        versionId: data.versionId,
        filename: file.name,
        pageCount: data.pageCount || 1,
        chunkCount: data.chunkCount || 1,
        extractedTitle: data.title || file.name.replace(/\.[^/.]+$/, '')
      });
    } catch (err: any) {
      setErrorMessage(err.message || 'An error occurred during extraction.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleCreatePath = async () => {
    if (!extractedOutline) return;
    setGeneratingPath(true);
    setErrorMessage(null);

    try {
      const res = await fetch('/api/v1/learning-paths/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          documentVersionId: extractedOutline.versionId,
          title: extractedOutline.extractedTitle,
          grade: 9,
          subject: 'SCIENCE'
        })
      });

      if (!res.ok) {
        throw new Error('Failed to generate initial learning path');
      }

      const data = await res.json();
      // Navigate to reader for the first lesson
      if (data.firstLessonId) {
        navigate(`/lesson/${data.firstLessonId}?pathId=${data.pathId}`);
      } else {
        navigate(`/lesson/default-01?pathId=${data.pathId}`);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Could not construct learning path.');
      setGeneratingPath(false);
    }
  };

  return (
    <div className={styles.container}>
      <section className={styles.hero}>
        <h1 className={styles.heroTitle}>SETU Academic Desk</h1>
        <p className={styles.heroSubtitle}>
          Source-first adaptive learning desk for Classes 6–10. Upload any syllabus document, textbook chapter, or teacher notes to create a verified, citation-grounded learning path with offline capability.
        </p>
      </section>

      <div className={styles.grid}>
        {/* Document Ingestion Card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>Upload Source Document</h2>
            <p className={styles.cardDescription}>
              Page-aware extraction with grounded citations. Up to 50MB.
            </p>
          </div>

          <input
            type="file"
            ref={fileInputRef}
            style={{ display: 'none' }}
            accept=".pdf,.docx,.pptx,.txt,.md,.png,.jpg,.jpeg"
            onChange={handleFileChange}
          />

          <div
            className={`${styles.dropzone} ${isDragging ? styles.dropzoneDragging : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className={styles.dropzoneIcon} />
            <div className={styles.dropzoneText}>
              Click to select file or drag & drop here
            </div>

            <div className={styles.formatTags}>
              <span className={styles.formatTag}>PDF</span>
              <span className={styles.formatTag}>DOCX</span>
              <span className={styles.formatTag}>PPTX</span>
              <span className={styles.formatTag}>TXT</span>
              <span className={styles.formatTag}>MD</span>
              <span className={styles.formatTag}>Images</span>
              <span className={styles.sizeBadge}>Up to 50MB</span>
            </div>
          </div>

          {isUploading && (
            <div className={styles.statusBox}>
              <div className={styles.statusHeader}>
                <span>Extracting Document</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className={styles.progressBar}>
                <div className={styles.progressFill} style={{ width: `${uploadProgress}%` }} />
              </div>
              <div className={styles.statusMessage}>{statusMessage}</div>
            </div>
          )}

          {errorMessage && (
            <div style={{ marginTop: '16px', padding: '12px', background: '#FDEEED', border: '1px solid #F3BCB8', borderRadius: '6px', color: '#C93B2B', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertCircle size={16} />
              <span>{errorMessage}</span>
            </div>
          )}

          {extractedOutline && (
            <div className={styles.outlineCard}>
              <div className={styles.outlineTitle}>
                <CheckCircle2 size={16} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'text-bottom' }} />
                Source Extracted & Indexed
              </div>
              <div className={styles.outlineMeta}>
                <strong>{extractedOutline.filename}</strong> • {extractedOutline.pageCount} page(s) • {extractedOutline.chunkCount} vector chunk(s) (768d)
              </div>
              <button
                className={styles.primaryButton}
                onClick={handleCreatePath}
                disabled={generatingPath}
              >
                {generatingPath ? 'Generating First 3 Lessons...' : 'Start Learning Path'}
                <ArrowRight size={16} />
              </button>
            </div>
          )}
        </div>

        {/* Standard Curriculum Resources */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>Standard Curriculum Catalogue</h2>
            <p className={styles.cardDescription}>
              Approved Class 6–10 textbook units ready for instant adaptive study.
            </p>
          </div>

          <div className={styles.catalogueList}>
            {catalogueItems.length > 0 ? (
              catalogueItems.map((cat: any) => (
                <div key={cat.id} className={styles.catalogueItem}>
                  <div className={styles.catInfo}>
                    <span className={styles.catTitle}>{cat.title}</span>
                    <span className={styles.catMeta}>
                      Class {cat.grade} • {cat.subject} • {cat.board || 'CBSE'}
                    </span>
                  </div>
                  <button
                    className={styles.studyButton}
                    onClick={() => navigate(`/lesson/${cat.id}?catalogue=true`)}
                  >
                    Open Unit
                  </button>
                </div>
              ))
            ) : (
              // Default core items if remote catalogue table has no custom rows yet
              [
                { id: 'sci-9-cell', title: 'The Fundamental Unit of Life (Cell & Membrane)', grade: 9, subject: 'Science', board: 'CBSE' },
                { id: 'math-8-rat', title: 'Rational Numbers & Number Lines', grade: 8, subject: 'Mathematics', board: 'CBSE' },
                { id: 'sci-10-chem', title: 'Chemical Reactions and Equations', grade: 10, subject: 'Science', board: 'CBSE' },
                { id: 'math-9-poly', title: 'Polynomials & Geometric Factoring', grade: 9, subject: 'Mathematics', board: 'NCERT' }
              ].map((item) => (
                <div key={item.id} className={styles.catalogueItem}>
                  <div className={styles.catInfo}>
                    <span className={styles.catTitle}>{item.title}</span>
                    <span className={styles.catMeta}>
                      Class {item.grade} • {item.subject} • {item.board}
                    </span>
                  </div>
                  <button
                    className={styles.studyButton}
                    onClick={() => navigate(`/lesson/${item.id}?subject=${item.subject}&grade=${item.grade}&title=${encodeURIComponent(item.title)}`)}
                  >
                    <BookOpen size={13} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'text-bottom' }} />
                    Study
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
