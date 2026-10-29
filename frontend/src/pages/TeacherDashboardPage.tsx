import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  api,
  ClassroomData,
  EvidenceBand,
  EvidenceConceptRow,
  EvidenceMatrixRow,
  TeacherActionRow,
} from '../services/api';
import styles from './TeacherDashboardPage.module.css';

const BAND_LABEL: Record<EvidenceBand, string> = {
  not_enough_evidence: 'Not enough evidence',
  developing: 'Developing',
  approaching: 'Approaching',
  demonstrated: 'Demonstrated',
};

const ACTION_LABEL: Record<string, string> = {
  reinforce_foundations: 'Stay with this unit',
  advance_challenge: 'Move to the next unit',
  targeted_review: 'Review the worked example',
};

const STATUS_LABEL: Record<TeacherActionRow['status'], string> = {
  proposed: 'Proposed',
  accepted: 'Accepted',
  dismissed: 'Dismissed',
  superseded: 'Superseded',
};

function conceptLabel(conceptId: string): string {
  const words = conceptId.replace(/^concept[-_]/, '').replace(/[-_]/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function bandClass(band: EvidenceBand): string {
  if (band === 'demonstrated') return styles.bandDemonstrated;
  if (band === 'approaching') return styles.bandApproaching;
  if (band === 'developing') return styles.bandDeveloping;
  return styles.bandSparse;
}

type Feedback = { kind: 'ok' | 'error'; message: string } | null;

export const TeacherDashboardPage: React.FC = () => {
  const [classrooms, setClassrooms] = useState<ClassroomData[]>([]);
  const [selectedClassroomId, setSelectedClassroomId] = useState<string | null>(null);
  const [isLoadingClassrooms, setIsLoadingClassrooms] = useState(true);
  const [classroomError, setClassroomError] = useState<string | null>(null);
  const [isCreatingClassroom, setIsCreatingClassroom] = useState(false);
  const [newClassName, setNewClassName] = useState('');
  const [newClassGrade, setNewClassGrade] = useState<number>(9);
  const [newClassBoard, setNewClassBoard] = useState('board-cbse');
  const [newClassSubject, setNewClassSubject] = useState('SCIENCE');
  const [isSubmittingClass, setIsSubmittingClass] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [evidenceMatrix, setEvidenceMatrix] = useState<EvidenceMatrixRow[]>([]);
  const [actions, setActions] = useState<TeacherActionRow[]>([]);
  const [isLoadingMatrix, setIsLoadingMatrix] = useState(false);
  const [matrixError, setMatrixError] = useState<string | null>(null);

  const [recStudentId, setRecStudentId] = useState('');
  const [recConcept, setRecConcept] = useState('');
  const [recAction, setRecAction] = useState('reinforce_foundations');
  const [recNote, setRecNote] = useState('');
  const [isSubmittingRec, setIsSubmittingRec] = useState(false);
  const [recFeedback, setRecFeedback] = useState<Feedback>(null);
  const [copied, setCopied] = useState(false);

  const fetchClassrooms = useCallback(async () => {
    setIsLoadingClassrooms(true);
    setClassroomError(null);
    try {
      const res = await api.getClassrooms();
      const list = Array.isArray(res) ? res : (res as { classrooms?: ClassroomData[] }).classrooms || [];
      setClassrooms(list);
      setSelectedClassroomId((current) =>
        current && list.some((room) => room.id === current) ? current : list[0]?.id ?? null
      );
      if (list.length === 0) setIsCreatingClassroom(true);
    } catch (err: unknown) {
      setClassrooms([]);
      setClassroomError(
        err instanceof Error ? err.message : 'Classrooms could not be loaded from SETU.'
      );
    } finally {
      setIsLoadingClassrooms(false);
    }
  }, []);

  useEffect(() => {
    void fetchClassrooms();
  }, [fetchClassrooms]);

  const fetchEvidenceMatrix = useCallback(async (classroomId: string) => {
    setIsLoadingMatrix(true);
    setMatrixError(null);
    try {
      const res = await api.getEvidenceMatrix(classroomId);
      setEvidenceMatrix(res.matrix || []);
      setActions(res.actions || []);
    } catch (err: unknown) {
      setEvidenceMatrix([]);
      setActions([]);
      setMatrixError(
        err instanceof Error ? err.message : 'The roster could not be loaded from SETU.'
      );
    } finally {
      setIsLoadingMatrix(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedClassroomId) return;
    void fetchEvidenceMatrix(selectedClassroomId);
    const timer = window.setInterval(() => {
      void fetchEvidenceMatrix(selectedClassroomId);
    }, 15000);
    return () => window.clearInterval(timer);
  }, [selectedClassroomId, fetchEvidenceMatrix]);

  const selected = classrooms.find((room) => room.id === selectedClassroomId) || null;

  const selectedRow = evidenceMatrix.find((row) => row.studentId === recStudentId) || null;
  const selectableStudents = evidenceMatrix.filter((row) => !row.profileMissing);
  const selectedConcept: EvidenceConceptRow | null =
    selectedRow?.concepts.find((concept) => concept.conceptId === recConcept) || null;

  const studentNameById = useMemo(() => {
    const map = new Map<string, string>();
    evidenceMatrix.forEach((row) => map.set(row.studentId, row.studentName));
    return map;
  }, [evidenceMatrix]);

  useEffect(() => {
    if (!selectedRow) {
      if (recStudentId) setRecStudentId('');
      if (recConcept) setRecConcept('');
      return;
    }
    if (recConcept && !selectedRow.concepts.some((concept) => concept.conceptId === recConcept)) {
      setRecConcept('');
    }
  }, [selectedRow, recStudentId, recConcept]);

  const handleCreateClassroom = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!newClassName.trim()) {
      setCreateError('Write a classroom name first.');
      return;
    }
    setIsSubmittingClass(true);
    setCreateError(null);
    try {
      const created = await api.createClassroom({
        name: newClassName.trim(),
        grade: newClassGrade,
        boardId: newClassBoard,
        subjectScope: newClassSubject,
      });
      setClassrooms((prev) => [created, ...prev]);
      setSelectedClassroomId(created.id);
      setIsCreatingClassroom(false);
      setNewClassName('');
    } catch (err: unknown) {
      setCreateError(
        err instanceof Error ? err.message : 'SETU could not create the classroom.'
      );
    } finally {
      setIsSubmittingClass(false);
    }
  };

  const handleSelectStudent = (studentId: string) => {
    setRecStudentId(studentId);
    setRecConcept('');
    setRecFeedback(null);
  };

  const handleSendRecommendation = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedClassroomId) return;
    if (!recStudentId) {
      setRecFeedback({ kind: 'error', message: 'Choose a student first.' });
      return;
    }
    if (!selectedConcept) {
      setRecFeedback({ kind: 'error', message: 'Choose a topic that has evidence.' });
      return;
    }
    if (!recNote.trim()) {
      setRecFeedback({ kind: 'error', message: 'Write the suggestion.' });
      return;
    }
    setIsSubmittingRec(true);
    setRecFeedback(null);
    try {
      const created = await api.addRecommendation({
        classroomId: selectedClassroomId,
        studentId: recStudentId,
        conceptId: selectedConcept.conceptId,
        actionType: recAction,
        notes: recNote.trim(),
      });
      setActions((prev) => [
        {
          id: created.id,
          studentId: recStudentId,
          conceptId: selectedConcept.conceptId,
          actionType: created.actionType,
          notes: created.notes,
          status: (created.status as TeacherActionRow['status']) || 'proposed',
          createdAt: new Date().toISOString(),
        },
        ...prev,
      ]);
      setRecFeedback({ kind: 'ok', message: 'Suggestion sent to that student.' });
      setRecNote('');
    } catch (err: unknown) {
      setRecFeedback({
        kind: 'error',
        message: err instanceof Error ? err.message : 'SETU could not send the suggestion.',
      });
    } finally {
      setIsSubmittingRec(false);
    }
  };

  const copyCode = async () => {
    if (!selected?.joinCode) return;
    await navigator.clipboard.writeText(selected.joinCode);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  const canSend =
    Boolean(selectedClassroomId) &&
    Boolean(recStudentId) &&
    Boolean(selectedConcept) &&
    Boolean(recNote.trim()) &&
    !isSubmittingRec;

  return (
    <div className={styles.page}>
      <header>
        <h1>Classroom</h1>
        <p className={styles.lede}>
          Members, study time, and the unit they last opened. Nothing here is filled in until a
          student joins and studies.
        </p>
      </header>

      <div className={styles.toolbar}>
        {isLoadingClassrooms && <span className={styles.loadingText}>Loading classrooms…</span>}
        {classrooms.map((room) => (
          <button
            key={room.id}
            type="button"
            className={room.id === selectedClassroomId ? `${styles.chip} ${styles.chipOn}` : styles.chip}
            onClick={() => setSelectedClassroomId(room.id)}
          >
            {room.name}
          </button>
        ))}
        <button
          type="button"
          className={styles.secondary}
          onClick={() => setIsCreatingClassroom((open) => !open)}
        >
          New classroom
        </button>
      </div>

      {classroomError && (
        <div className={styles.errorBox} role="alert">
          <strong>SETU could not load your classrooms.</strong> {classroomError}
          <button type="button" className={styles.inlineRetry} onClick={() => void fetchClassrooms()}>
            Retry
          </button>
        </div>
      )}

      {isCreatingClassroom && (
        <form className={styles.panel} onSubmit={handleCreateClassroom}>
          <h2>Create a classroom</h2>
          <div className={styles.form}>
            <label>
              Name
              <input
                required
                value={newClassName}
                onChange={(e) => setNewClassName(e.target.value)}
                placeholder="Morning science"
              />
            </label>
            <label>
              Class
              <select value={newClassGrade} onChange={(e) => setNewClassGrade(Number(e.target.value))}>
                {[6, 7, 8, 9, 10].map((grade) => (
                  <option key={grade} value={grade}>
                    Class {grade}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Board
              <select value={newClassBoard} onChange={(e) => setNewClassBoard(e.target.value)}>
                <option value="board-cbse">CBSE</option>
                <option value="board-ncert">NCERT</option>
                <option value="board-icse">ICSE</option>
                <option value="board-state">State board</option>
              </select>
            </label>
            <label>
              Subject
              <select value={newClassSubject} onChange={(e) => setNewClassSubject(e.target.value)}>
                <option value="SCIENCE">Science</option>
                <option value="MATHEMATICS">Mathematics</option>
                <option value="SOCIAL_SCIENCE">Social science</option>
                <option value="ENGLISH">English</option>
                <option value="HINDI">Hindi</option>
              </select>
            </label>
          </div>
          {createError && (
            <p className={styles.bad} role="alert">
              {createError}
            </p>
          )}
          <div className={styles.rowActions}>
            <button type="submit" className={styles.primary} disabled={isSubmittingClass}>
              {isSubmittingClass ? 'Creating…' : 'Create classroom'}
            </button>
          </div>
        </form>
      )}

      {selected && (
        <section className={styles.panel}>
          <div className={styles.toolbar}>
            <h2>{selected.name}</h2>
            <span>
              Join code{' '}
              {selected.joinCode ? (
                <strong className={styles.code}>{selected.joinCode}</strong>
              ) : (
                <em className={styles.codeUnavailable}>Code unavailable</em>
              )}
            </span>
            <button
              type="button"
              className={styles.secondary}
              onClick={copyCode}
              disabled={!selected.joinCode}
            >
              {copied ? 'Copied' : 'Copy code'}
            </button>
          </div>

          {matrixError && (
            <div className={styles.errorBox} role="alert">
              <strong>The roster could not be loaded.</strong> {matrixError}
              <button
                type="button"
                className={styles.inlineRetry}
                onClick={() => void fetchEvidenceMatrix(selected.id)}
              >
                Retry
              </button>
            </div>
          )}

          {isLoadingMatrix ? (
            <p className={styles.lede}>Loading the roster…</p>
          ) : evidenceMatrix.length === 0 ? (
            <p className={styles.empty}>
              No students have joined. Share the code above. Their minutes and checks will show here
              after they study.
            </p>
          ) : (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Student and evidenced topics</th>
                    <th>Minutes</th>
                    <th>Last opened</th>
                    <th>Checks</th>
                    <th>Change</th>
                  </tr>
                </thead>
                <tbody>
                  {evidenceMatrix.map((row) => (
                    <tr
                      key={row.studentId}
                      className={row.studentId === recStudentId ? styles.rowSelected : undefined}
                    >
                      <td>
                        <div className={styles.studentHead}>
                          {row.profileMissing ? (
                            <span className={styles.studentName}>Account removed</span>
                          ) : (
                            <button
                              type="button"
                              className={styles.studentButton}
                              onClick={() => handleSelectStudent(row.studentId)}
                              aria-pressed={row.studentId === recStudentId}
                            >
                              {row.studentName}
                            </button>
                          )}
                          <span className={`${styles.band} ${bandClass(row.evidenceBand)}`}>
                            {BAND_LABEL[row.evidenceBand]}
                          </span>
                        </div>
                        {row.concepts.length === 0 ? (
                          <p className={styles.noConcepts}>No evidenced topics yet.</p>
                        ) : (
                          <ul className={styles.conceptList}>
                            {row.concepts.map((concept) => (
                              <li key={concept.conceptId} className={styles.conceptItem}>
                                <span className={styles.conceptName}>{conceptLabel(concept.conceptId)}</span>
                                <span className={styles.conceptMeta}>
                                  {BAND_LABEL[concept.band]} · {Math.round(concept.score)}% ·{' '}
                                  {concept.evidenceCount}{' '}
                                  {concept.evidenceCount === 1 ? 'check' : 'checks'}
                                  {concept.calculatedAt
                                    ? ` · ${new Date(concept.calculatedAt).toLocaleDateString()}`
                                    : ''}
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </td>
                      <td>
                        {row.minutesStudied ?? 0}
                        <span className={styles.bars} aria-hidden="true">
                          {(row.heatmap || []).map((day) => (
                            <i
                              key={day.date}
                              style={{
                                height: Math.max(
                                  2,
                                  Math.min(22, Math.round((day.seconds || 0) / 30))
                                ),
                                opacity: day.seconds ? 1 : 0.25,
                              }}
                              title={`${day.date}: ${Math.round(day.seconds / 60)} min`}
                            />
                          ))}
                        </span>
                      </td>
                      <td>{row.readingTitle || 'Not opened yet'}</td>
                      <td>
                        {row.accuracyKnown
                          ? `${Math.round(row.accuracyRate * 100)}%`
                          : 'No checks yet'}
                      </td>
                      <td>
                        {row.improvement === 'improving'
                          ? 'Improving'
                          : row.improvement === 'needs_support'
                            ? 'Needs support'
                            : row.improvement === 'steady'
                              ? 'Steady'
                              : 'Not enough checks'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      <form className={styles.panel} onSubmit={handleSendRecommendation}>
        <h2>Suggestion</h2>
        <p className={styles.lede}>
          This note appears on that student’s desk. It is sent only to someone who has joined this
          classroom and has real evidence for the topic.
        </p>
        {recFeedback && (
          <p className={recFeedback.kind === 'ok' ? styles.ok : styles.bad} role="status">
            {recFeedback.message}
          </p>
        )}
        <div className={styles.form}>
          <label>
            Student
            <select
              value={recStudentId}
              onChange={(e) => handleSelectStudent(e.target.value)}
              disabled={selectableStudents.length === 0}
            >
              <option value="">Choose a student</option>
              {selectableStudents.map((row) => (
                <option key={row.studentId} value={row.studentId}>
                  {row.studentName}
                </option>
              ))}
            </select>
          </label>
          <label>
            Topic
            <select
              value={recConcept}
              onChange={(e) => setRecConcept(e.target.value)}
              disabled={!selectedRow || selectedRow.concepts.length === 0}
            >
              <option value="">
                {selectedRow && selectedRow.concepts.length === 0
                  ? 'No evidenced topics yet'
                  : 'Choose an evidenced topic'}
              </option>
              {(selectedRow?.concepts || []).map((concept) => (
                <option key={concept.conceptId} value={concept.conceptId}>
                  {conceptLabel(concept.conceptId)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Action
            <select value={recAction} onChange={(e) => setRecAction(e.target.value)}>
              <option value="reinforce_foundations">Stay with this unit</option>
              <option value="advance_challenge">Move to the next unit</option>
              <option value="targeted_review">Review the worked example</option>
            </select>
          </label>
          <label>
            Note
            <textarea
              rows={3}
              value={recNote}
              onChange={(e) => setRecNote(e.target.value)}
              placeholder="Write what you want this student to do next."
            />
          </label>
        </div>
        {selectedConcept && (
          <p className={styles.evidenceNote}>
            Based on {BAND_LABEL[selectedConcept.band].toLowerCase()} evidence ·{' '}
            {selectedConcept.evidenceCount}{' '}
            {selectedConcept.evidenceCount === 1 ? 'check' : 'checks'}
            {selectedConcept.calculatedAt
              ? ` · last assessed ${new Date(selectedConcept.calculatedAt).toLocaleDateString()}`
              : ''}
          </p>
        )}
        <div className={styles.rowActions}>
          <button type="submit" className={styles.primary} disabled={!canSend}>
            {isSubmittingRec ? 'Sending…' : 'Send suggestion'}
          </button>
        </div>
      </form>

      <section className={styles.panel}>
        <h2>Sent suggestions</h2>
        {actions.length === 0 ? (
          <p className={styles.lede}>No suggestions sent from this classroom yet.</p>
        ) : (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Topic</th>
                  <th>Action</th>
                  <th>Status</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {actions.map((action) => (
                  <tr key={action.id}>
                    <td>{studentNameById.get(action.studentId) || 'Student'}</td>
                    <td>{action.conceptId ? conceptLabel(action.conceptId) : '—'}</td>
                    <td>{ACTION_LABEL[action.actionType] || action.actionType}</td>
                    <td>
                      <span className={`${styles.actionStatus} ${styles[`status_${action.status}`] || ''}`}>
                        {STATUS_LABEL[action.status] || action.status}
                      </span>
                    </td>
                    <td>
                      {action.createdAt ? new Date(action.createdAt).toLocaleDateString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};
