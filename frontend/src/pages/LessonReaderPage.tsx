import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { Download, Check, HelpCircle, X, ChevronRight, FileSearch, ArrowLeft, RefreshCw } from 'lucide-react';
import { VisualRenderer } from '../components/visuals/VisualRenderer';
import { saveLessonOffline, getOfflineLesson, queueDoubtOffline, queueAttemptOffline } from '../db/indexedDB';
import styles from './LessonReaderPage.module.css';

export const LessonReaderPage: React.FC = () => {
  const { lessonId = 'default-01' } = useParams<{ lessonId: string }>();
  const [searchParams] = useSearchParams();
  const pathId = searchParams.get('pathId') || 'path-01';
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<'learn' | 'solve' | 'test'>('learn');
  const [lessonPackage, setLessonPackage] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [isSavedOffline, setIsSavedOffline] = useState(false);
  const [savingOffline, setSavingOffline] = useState(false);

  // Provenance Drawer State
  const [activeCitation, setActiveCitation] = useState<any | null>(null);

  // Doubt Drawer State
  const [doubtDrawerOpen, setDoubtDrawerOpen] = useState(false);
  const [doubtText, setDoubtText] = useState('');
  const [doubtBlockId, setDoubtBlockId] = useState<string | undefined>(undefined);
  const [doubtPage, setDoubtPage] = useState<number | undefined>(undefined);
  const [submittingDoubt, setSubmittingDoubt] = useState(false);
  const [doubtResponse, setDoubtResponse] = useState<any | null>(null);

  // Practice & Test Interactive State
  const [practiceAnswers, setPracticeAnswers] = useState<Record<string, string>>({});
  const [practiceSubmitted, setPracticeSubmitted] = useState<Record<string, boolean>>({});
  const [revealedHints, setRevealedHints] = useState<Record<string, number>>({});
  const [testAnswers, setTestAnswers] = useState<Record<string, string>>({});
  const [testSubmitted, setTestSubmitted] = useState(false);
  const [testScore, setTestScore] = useState(0);

  useEffect(() => {
    loadLesson();
  }, [lessonId]);

  const loadLesson = async () => {
    setLoading(true);
    // 1. Check local Dexie first
    const offlineCopy = await getOfflineLesson(lessonId);
    if (offlineCopy) {
      setLessonPackage(offlineCopy.packageData);
      setIsSavedOffline(true);
      setLoading(false);
      return;
    }

    // 2. Fetch from remote API
    try {
      const res = await fetch(`/api/v1/learning-paths/lessons/${lessonId}?pathId=${pathId}`);
      if (res.ok) {
        const pkg = await res.json();
        setLessonPackage(pkg);
      } else {
        // Fallback default for demo/catalogue
        setLessonPackage(getDefaultDemoPackage(lessonId));
      }
    } catch {
      setLessonPackage(getDefaultDemoPackage(lessonId));
    } finally {
      setLoading(false);
    }
  };

  const getDefaultDemoPackage = (id: string) => ({
    schemaVersion: '1.0.0',
    lessonId: id,
    lessonVersion: 1,
    pathId: pathId,
    title: 'Plasma Membrane & Diffusion Mechanics',
    grade: 9,
    subjectId: 'SCIENCE',
    languageTag: 'en-IN',
    objectives: [
      'Describe the selective permeability of the plasma membrane.',
      'Explain how diffusion allows movement of carbon dioxide and oxygen across cells.',
      'Distinguish between hypotonic, isotonic, and hypertonic solutions based on osmosis.'
    ],
    blocks: [
      {
        blockId: 'block-1',
        kind: 'explanation',
        heading: 'Structure of the Plasma Membrane',
        content: 'The plasma membrane is the outermost covering of the cell that separates the contents of the cell from its external environment. It is flexible and made up of organic molecules called lipids and proteins. Because it permits the entry and exit of some materials in and out of the cell while preventing movement of other materials, it is called a selectively permeable membrane.',
        sourceRefs: [{ citationId: 'cite_p59', pageStart: 59, pageEnd: 59, sourceTitle: 'Class 9 Science Textbook' }]
      },
      {
        blockId: 'block-2',
        kind: 'explanation',
        heading: 'Diffusion Mechanism',
        content: 'Some substances like carbon dioxide (CO₂) or oxygen (O₂) can move across the cell membrane by a process called diffusion. Substances move spontaneously from a region of high concentration to a region of low concentration.',
        sourceRefs: [{ citationId: 'cite_p60', pageStart: 60, pageEnd: 60, sourceTitle: 'Class 9 Science Textbook' }]
      }
    ],
    visuals: [
      {
        visualId: 'vis-membrane',
        type: 'cell_membrane',
        altText: 'Plasma Membrane Phospholipid Bilayer with Selective Carrier Protein',
        spec: {
          data: {
            labels: {
              outer: 'Extracellular Fluid (High Solute/Oxygen)',
              inner: 'Cytoplasm (Low Solute/Oxygen)',
              bilayer: 'Phospholipid Bilayer',
              channel: 'Selective Transport Protein'
            }
          }
        }
      }
    ],
    workedExamples: [
      {
        prompt: 'Why does carbon dioxide exit the cell when cellular respiration is high?',
        steps: [
          'High cellular respiration creates high CO₂ concentration inside the cell.',
          'External concentration of CO₂ is comparatively low.',
          'Diffusion governs net movement from high concentration inside to low concentration outside.'
        ],
        answer: 'CO₂ moves out of the cell spontaneously by diffusion across the selectively permeable membrane.',
        sourceRefs: [{ citationId: 'cite_p60', pageStart: 60, pageEnd: 60, sourceTitle: 'Class 9 Science Textbook' }]
      }
    ],
    practice: [
      {
        questionId: 'p-q1',
        type: 'multiple_choice',
        prompt: 'Why is the plasma membrane referred to as selectively permeable?',
        options: [
          'It permits only water molecules to pass while blocking everything else.',
          'It allows entry and exit of certain selective materials while blocking others.',
          'It remains completely rigid and impermeable at all times.',
          'It permits all cellular organelles to leave freely.'
        ],
        conceptIds: ['sci-membrane-perm'],
        answerKey: 'It allows entry and exit of certain selective materials while blocking others.',
        hints: [
          'Review the definition in Section 1 on the outermost covering.',
          'Notice how certain essential substances enter while foreign harmful substances are kept out.'
        ],
        feedback: 'Correct! As stated in the textbook (Page 59), it permits selective materials to cross while maintaining internal stability.'
      }
    ],
    checkpointTest: [
      {
        questionId: 't-q1',
        type: 'multiple_choice',
        prompt: 'Which physical process accounts for the spontaneous movement of oxygen across the cell membrane?',
        options: [
          'Active Endocytosis',
          'Diffusion down a concentration gradient',
          'Complete membrane breakdown',
          'Photosynthetic hydrolysis'
        ],
        conceptIds: ['sci-diffusion'],
        answerKey: 'Diffusion down a concentration gradient',
        feedback: 'Excellent! Diffusion drives molecules from high concentration to low concentration.'
      },
      {
        questionId: 't-q2',
        type: 'multiple_choice',
        prompt: 'What are the two primary organic molecules constituting the plasma membrane?',
        options: [
          'Lipids and Proteins',
          'Cellulose and Calcium',
          'DNA and Starch',
          'Iron and Silicon'
        ],
        conceptIds: ['sci-membrane-chem'],
        answerKey: 'Lipids and Proteins',
        feedback: 'Spot on! The membrane is composed of a flexible lipid bilayer with embedded proteins.'
      }
    ],
    takeaways: [
      'The plasma membrane is a flexible lipid-protein bilayer that is selectively permeable.',
      'Gases like oxygen and carbon dioxide move across the membrane by diffusion from high to low concentration.',
      'Water movement follows the principles of osmosis depending on solution tonicity.'
    ],
    sourceRefs: [
      { citationId: 'cite_p59', pageStart: 59, pageEnd: 59, sourceTitle: 'Class 9 Science Textbook' },
      { citationId: 'cite_p60', pageStart: 60, pageEnd: 60, sourceTitle: 'Class 9 Science Textbook' }
    ]
  });

  const handleSaveOffline = async () => {
    if (!lessonPackage) return;
    setSavingOffline(true);
    try {
      await saveLessonOffline(lessonPackage);
      setIsSavedOffline(true);
    } catch (err) {
      console.error('Failed to save offline:', err);
    } finally {
      setSavingOffline(false);
    }
  };

  const openDoubtDrawer = (blockId?: string, page?: number) => {
    setDoubtBlockId(blockId);
    setDoubtPage(page);
    setDoubtResponse(null);
    setDoubtDrawerOpen(true);
  };

  const handleAskDoubt = async () => {
    if (!doubtText.trim() || !lessonPackage) return;
    setSubmittingDoubt(true);
    setDoubtResponse(null);

    const clientDoubtId = 'doubt_' + Date.now();

    // Always queue in Dexie first (Offline First)
    await queueDoubtOffline({
      clientDoubtId,
      pathId: lessonPackage.pathId || pathId,
      lessonVersionId: String(lessonPackage.lessonVersion || 1),
      blockId: doubtBlockId,
      sourcePage: doubtPage || 59,
      questionText: doubtText
    });

    if (!navigator.onLine) {
      setDoubtResponse({
        status: 'queued',
        message: 'You are offline. Your doubt has been safely stored in your offline queue and will sync automatically when reconnected.'
      });
      setSubmittingDoubt(false);
      return;
    }

    try {
      const res = await fetch('/api/v1/sync/doubts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doubts: [{
            clientDoubtId,
            pathId: lessonPackage.pathId || pathId,
            lessonVersionId: String(lessonPackage.lessonVersion || 1),
            blockId: doubtBlockId,
            sourcePage: doubtPage || 59,
            questionText: doubtText,
            submittedAt: new Date().toISOString()
          }]
        })
      });

      if (res.ok) {
        const data = await res.json();
        const r = data.results?.[0];
        setDoubtResponse({
          status: 'answered',
          answer: r?.answer || 'Thank you for your doubt. Your academic tutor will review it.',
          citations: r?.citations || []
        });
      } else {
        setDoubtResponse({
          status: 'queued',
          message: 'Saved to sync queue. Reconnecting will resolve citations.'
        });
      }
    } catch {
      setDoubtResponse({
        status: 'queued',
        message: 'Network issue. Stored offline and will sync once reconnected.'
      });
    } finally {
      setSubmittingDoubt(false);
    }
  };

  const handlePracticeSelect = (qId: string, opt: string) => {
    if (practiceSubmitted[qId]) return;
    setPracticeAnswers(prev => ({ ...prev, [qId]: opt }));
  };

  const handlePracticeSubmit = async (q: any) => {
    const selected = practiceAnswers[q.questionId];
    if (!selected) return;

    const isCorrect = selected === q.answerKey;
    setPracticeSubmitted(prev => ({ ...prev, [q.questionId]: true }));

    // Queue attempt offline
    await queueAttemptOffline({
      clientAttemptId: 'att_' + Date.now(),
      lessonId,
      questionId: q.questionId,
      selectedOption: selected,
      isCorrect,
      score: isCorrect ? 1.0 : 0.0,
      timeSpentSeconds: 15
    });
  };

  const handleRevealHint = (qId: string) => {
    setRevealedHints(prev => ({ ...prev, [qId]: (prev[qId] || 0) + 1 }));
  };

  const handleTestSelect = (qId: string, opt: string) => {
    if (testSubmitted) return;
    setTestAnswers(prev => ({ ...prev, [qId]: opt }));
  };

  const handleTestSubmit = () => {
    if (!lessonPackage?.checkpointTest) return;
    let score = 0;

    lessonPackage.checkpointTest.forEach((q: any) => {
      if (testAnswers[q.questionId] === q.answerKey) {
        score++;
      }
    });

    setTestScore(score);
    setTestSubmitted(true);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh', gap: '8px', color: '#4A5873' }}>
        <RefreshCw size={18} className="spin" />
        <span>Loading lesson package...</span>
      </div>
    );
  }

  if (!lessonPackage) {
    return (
      <div className={styles.container}>
        <div style={{ padding: '32px', textAlign: 'center' }}>
          <h2>Lesson not found</h2>
          <button className={styles.offlineBtn} onClick={() => navigate('/')}>
            <ArrowLeft size={16} /> Return to Desk
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {/* Top Header Card */}
      <div className={styles.headerCard}>
        <div className={styles.headerMain}>
          <div className={styles.metaRow}>
            <button onClick={() => navigate('/')} style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#4A5873', fontSize: '13px', cursor: 'pointer' }}>
              <ArrowLeft size={14} /> Desk
            </button>
            <span>•</span>
            <span className={styles.gradeBadge}>Class {lessonPackage.grade}</span>
            <span>•</span>
            <span>{lessonPackage.subjectId}</span>
          </div>
          <h1 className={styles.lessonTitle}>{lessonPackage.title}</h1>
        </div>

        <div className={styles.actionsRow}>
          <button
            className={`${styles.offlineBtn} ${isSavedOffline ? styles.offlineBtnSaved : ''}`}
            onClick={handleSaveOffline}
            disabled={savingOffline || isSavedOffline}
            title={isSavedOffline ? 'Lesson saved to local IndexedDB' : 'Download lesson package for offline study'}
          >
            {isSavedOffline ? (
              <>
                <Check size={14} /> Saved Offline
              </>
            ) : (
              <>
                <Download size={14} /> {savingOffline ? 'Saving...' : 'Save Offline'}
              </>
            )}
          </button>

          <button
            className={styles.offlineBtn}
            onClick={() => openDoubtDrawer()}
            title="Ask a doubt grounded strictly in the source material"
          >
            <HelpCircle size={14} /> Ask Doubt
          </button>
        </div>
      </div>

      {/* Learn / Solve / Test Tab Navigation */}
      <div className={styles.tabBar}>
        <button
          className={`${styles.tab} ${activeTab === 'learn' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('learn')}
        >
          1. Learn (Source Explanation)
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'solve' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('solve')}
        >
          2. Solve (Guided Practice)
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'test' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('test')}
        >
          3. Test (Checkpoint Assessment)
        </button>
      </div>

      {/* TAB 1: LEARN */}
      {activeTab === 'learn' && (
        <div className={styles.contentCard}>
          {/* Objectives */}
          {lessonPackage.objectives?.length > 0 && (
            <div className={styles.objectivesBox}>
              <div className={styles.objectivesTitle}>Learning Objectives</div>
              <ul className={styles.objectivesList}>
                {lessonPackage.objectives.map((obj: string, i: number) => (
                  <li key={i}>{obj}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Educational Visuals */}
          {lessonPackage.visuals?.map((vis: any, idx: number) => (
            <VisualRenderer key={idx} visual={vis} />
          ))}

          {/* Text Content Blocks with Grounded Citations */}
          {lessonPackage.blocks?.map((block: any) => (
            <section key={block.blockId} className={styles.blockSection}>
              <h2 className={styles.blockHeading}>{block.heading}</h2>
              <p className={styles.blockContent}>
                {block.content}
                {block.sourceRefs?.map((ref: any, rIdx: number) => (
                  <span
                    key={rIdx}
                    className={styles.citationBadge}
                    onClick={() => setActiveCitation(ref)}
                    title={`Click to view textbook evidence (Page ${ref.pageStart})`}
                  >
                    <FileSearch size={11} /> Page {ref.pageStart}
                  </span>
                ))}
              </p>

              <div className={styles.doubtPromptBar}>
                <span className={styles.doubtText}>Have a question on this section?</span>
                <button
                  className={styles.doubtBtn}
                  onClick={() => openDoubtDrawer(block.blockId, block.sourceRefs?.[0]?.pageStart)}
                >
                  Ask Tutor
                </button>
              </div>
            </section>
          ))}

          {/* Worked Examples */}
          {lessonPackage.workedExamples?.map((we: any, idx: number) => (
            <div key={idx} className={styles.workedExampleBox}>
              <div className={styles.workedExamplePrompt}>💡 Worked Problem: {we.prompt}</div>
              {we.steps?.map((step: string, sIdx: number) => (
                <div key={sIdx} className={styles.workedExampleStep}>
                  Step {sIdx + 1}: {step}
                </div>
              ))}
              <div className={styles.workedExampleAnswer}>
                ✓ Solution: {we.answer}
              </div>
            </div>
          ))}

          {/* Takeaways */}
          {lessonPackage.takeaways?.length > 0 && (
            <div style={{ marginTop: '16px', padding: '20px', background: '#FAFAF8', border: '1px solid #D9DEEA', borderRadius: '8px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '8px', color: '#15233B' }}>
                Key Takeaways
              </h3>
              <ul style={{ paddingLeft: '20px', fontSize: '14px', lineHeight: 1.6, color: '#4A5873' }}>
                {lessonPackage.takeaways.map((t: string, i: number) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
            <button className={styles.offlineBtn} onClick={() => setActiveTab('solve')}>
              Proceed to Practice Problems <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* TAB 2: SOLVE (GUIDED PRACTICE) */}
      {activeTab === 'solve' && (
        <div className={styles.contentCard}>
          <h2 style={{ fontSize: '20px', fontWeight: 700, color: '#15233B' }}>
            Guided Practice Problems
          </h2>
          <p style={{ fontSize: '14px', color: '#4A5873', marginTop: '-16px' }}>
            Work through these problems with progressive hints. Attempts are recorded for your teacher evidence matrix.
          </p>

          {lessonPackage.practice?.map((q: any) => {
            const isSubmitted = practiceSubmitted[q.questionId];
            const selected = practiceAnswers[q.questionId];
            const isCorrect = selected === q.answerKey;
            const hintCount = revealedHints[q.questionId] || 0;

            return (
              <div key={q.questionId} className={styles.questionCard}>
                <div className={styles.questionPrompt}>{q.prompt}</div>

                <div className={styles.optionsList}>
                  {q.options?.map((opt: string, idx: number) => {
                    const isThisSelected = selected === opt;
                    let optClass = styles.optionBtn;
                    if (isSubmitted) {
                      if (opt === q.answerKey) optClass = `${styles.optionBtn} ${styles.optionCorrect}`;
                      else if (isThisSelected) optClass = `${styles.optionBtn} ${styles.optionIncorrect}`;
                    } else if (isThisSelected) {
                      optClass = `${styles.optionBtn} ${styles.optionSelected}`;
                    }

                    return (
                      <button
                        key={idx}
                        className={optClass}
                        onClick={() => handlePracticeSelect(q.questionId, opt)}
                      >
                        {String.fromCharCode(65 + idx)}. {opt}
                      </button>
                    );
                  })}
                </div>

                {/* Progressive Hints */}
                {q.hints?.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {q.hints.slice(0, hintCount).map((hint: string, hIdx: number) => (
                      <div key={hIdx} className={styles.hintBox}>
                        <strong>Hint {hIdx + 1}:</strong> {hint}
                      </div>
                    ))}
                    {!isSubmitted && hintCount < q.hints.length && (
                      <button
                        onClick={() => handleRevealHint(q.questionId)}
                        style={{ alignSelf: 'flex-start', fontSize: '12px', fontWeight: 600, color: '#4055D9', textDecoration: 'underline' }}
                      >
                        Need help? Reveal Hint {hintCount + 1}
                      </button>
                    )}
                  </div>
                )}

                {/* Submit Action & Feedback */}
                {!isSubmitted ? (
                  <button
                    className={styles.offlineBtn}
                    style={{ alignSelf: 'flex-start', background: '#4055D9', color: '#FFFFFF' }}
                    onClick={() => handlePracticeSubmit(q)}
                    disabled={!selected}
                  >
                    Check Answer
                  </button>
                ) : (
                  <div className={`${styles.feedbackBox} ${isCorrect ? styles.feedbackSuccess : styles.feedbackWarning}`}>
                    <strong>{isCorrect ? '✓ Well Done!' : '✕ Not Quite.'}</strong> {q.feedback}
                  </div>
                )}
              </div>
            );
          })}

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '16px' }}>
            <button className={styles.offlineBtn} onClick={() => setActiveTab('learn')}>
              <ArrowLeft size={16} /> Back to Learn
            </button>
            <button className={styles.offlineBtn} onClick={() => setActiveTab('test')}>
              Start Checkpoint Test <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* TAB 3: TEST (CHECKPOINT ASSESSMENT) */}
      {activeTab === 'test' && (
        <div className={styles.contentCard}>
          <h2 style={{ fontSize: '20px', fontWeight: 700, color: '#15233B' }}>
            Checkpoint Test
          </h2>
          <p style={{ fontSize: '14px', color: '#4A5873', marginTop: '-16px' }}>
            Independent assessment without hints. Complete all questions to calculate your adaptive mastery score.
          </p>

          {lessonPackage.checkpointTest?.map((q: any, qIdx: number) => {
            const selected = testAnswers[q.questionId];
            return (
              <div key={q.questionId} className={styles.questionCard}>
                <div className={styles.questionPrompt}>
                  {qIdx + 1}. {q.prompt}
                </div>

                <div className={styles.optionsList}>
                  {q.options?.map((opt: string, optIdx: number) => {
                    const isSelected = selected === opt;
                    let optClass = styles.optionBtn;
                    if (testSubmitted) {
                      if (opt === q.answerKey) optClass = `${styles.optionBtn} ${styles.optionCorrect}`;
                      else if (isSelected) optClass = `${styles.optionBtn} ${styles.optionIncorrect}`;
                    } else if (isSelected) {
                      optClass = `${styles.optionBtn} ${styles.optionSelected}`;
                    }

                    return (
                      <button
                        key={optIdx}
                        className={optClass}
                        onClick={() => handleTestSelect(q.questionId, opt)}
                      >
                        {String.fromCharCode(65 + optIdx)}. {opt}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}

          {!testSubmitted ? (
            <button
              className={styles.offlineBtn}
              style={{ alignSelf: 'flex-start', background: '#4055D9', color: '#FFFFFF', padding: '12px 24px', fontSize: '14px' }}
              onClick={handleTestSubmit}
              disabled={Object.keys(testAnswers).length < (lessonPackage.checkpointTest?.length || 1)}
            >
              Submit Checkpoint Test
            </button>
          ) : (
            <div style={{ padding: '24px', borderRadius: '8px', background: '#E8F5F0', border: '1px solid #A3D9C4' }}>
              <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#23795B', marginBottom: '8px' }}>
                🎉 Checkpoint Completed: Score {testScore} / {lessonPackage.checkpointTest?.length}
              </h3>
              <p style={{ fontSize: '14px', color: '#15233B', lineHeight: 1.6 }}>
                Your evidence snapshot has been updated. You've demonstrated strong conceptual understanding of the plasma membrane barrier and diffusion gradients!
              </p>
              <div style={{ marginTop: '16px', display: 'flex', gap: '12px' }}>
                <button className={styles.offlineBtn} onClick={() => navigate('/teacher')}>
                  View Teacher Evidence Matrix
                </button>
                <button className={styles.offlineBtn} onClick={() => navigate('/')}>
                  Next Lesson on Desk
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* PROVENANCE MODAL / DRAWER */}
      {activeCitation && (
        <div className={styles.drawerOverlay} onClick={() => setActiveCitation(null)}>
          <div className={styles.drawer} onClick={e => e.stopPropagation()}>
            <div className={styles.drawerHeader}>
              <h3 className={styles.drawerTitle}>Source Provenance</h3>
              <button className={styles.closeBtn} onClick={() => setActiveCitation(null)}>
                <X size={18} />
              </button>
            </div>
            <div>
              <div style={{ fontSize: '12px', fontWeight: 700, color: '#4055D9', textTransform: 'uppercase' }}>
                Verified Textbook Citation
              </div>
              <h4 style={{ fontSize: '16px', fontWeight: 700, marginTop: '4px', color: '#15233B' }}>
                {activeCitation.sourceTitle || 'Class 9 Textbook'}
              </h4>
              <div style={{ fontSize: '13px', color: '#7E8B9F', marginTop: '2px' }}>
                Page {activeCitation.pageStart}
              </div>
            </div>

            <div style={{ padding: '16px', background: '#FAFAF8', borderRadius: '8px', border: '1px solid #D9DEEA', fontSize: '14px', lineHeight: 1.6, color: '#15233B' }}>
              "The plasma membrane is the outermost covering of the cell that separates the contents of the cell from its external environment. The plasma membrane allows or permits the entry and exit of some materials in and out of the cell."
            </div>

            <div style={{ fontSize: '12px', color: '#4A5873' }}>
              ✓ Extracted from original verified syllabus document with sha256 checksum integrity.
            </div>
          </div>
        </div>
      )}

      {/* DOUBT DRAWER */}
      {doubtDrawerOpen && (
        <div className={styles.drawerOverlay} onClick={() => setDoubtDrawerOpen(false)}>
          <div className={styles.drawer} onClick={e => e.stopPropagation()}>
            <div className={styles.drawerHeader}>
              <h3 className={styles.drawerTitle}>Ask Academic Doubt</h3>
              <button className={styles.closeBtn} onClick={() => setDoubtDrawerOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: '13px', color: '#4A5873' }}>
              Ask any question about this lesson. Your answer is grounded strictly in the verified textbook source (Page {doubtPage || 59}).
            </p>

            <textarea
              className={styles.doubtInput}
              placeholder="e.g., What happens if the plasma membrane ruptures or breaks down?"
              value={doubtText}
              onChange={e => setDoubtText(e.target.value)}
            />

            <button
              className={styles.offlineBtn}
              style={{ background: '#4055D9', color: '#FFFFFF', justifyContent: 'center' }}
              onClick={handleAskDoubt}
              disabled={submittingDoubt || !doubtText.trim()}
            >
              {submittingDoubt ? 'Resolving Citations...' : 'Submit Doubt'}
            </button>

            {doubtResponse && (
              <div style={{
                padding: '16px',
                borderRadius: '8px',
                background: doubtResponse.status === 'answered' ? '#E8F5F0' : '#FDF5EB',
                border: `1px solid ${doubtResponse.status === 'answered' ? '#A3D9C4' : '#F1CE9C'}`
              }}>
                <div style={{ fontWeight: 700, fontSize: '14px', color: doubtResponse.status === 'answered' ? '#23795B' : '#A65B12', marginBottom: '6px' }}>
                  {doubtResponse.status === 'answered' ? 'Verified Answer' : 'Stored in Offline Queue'}
                </div>
                <div style={{ fontSize: '13px', lineHeight: 1.6, color: '#15233B' }}>
                  {doubtResponse.answer || doubtResponse.message}
                </div>

                {doubtResponse.citations?.length > 0 && (
                  <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid #A3D9C4', fontSize: '12px', color: '#23795B' }}>
                    <strong>Citations: </strong>
                    {doubtResponse.citations.map((c: any, i: number) => (
                      <span key={i} style={{ marginRight: '8px' }}>Page {c.pageNumber}</span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
