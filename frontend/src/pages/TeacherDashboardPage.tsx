import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  api,
  ClassroomData,
  ClassGapRow,
  EvidenceBand,
  EvidenceConceptRow,
  EvidenceMatrixRow,
  RosterMember,
  TeacherActionRow,
} from '../services/api';
import { useTaxonomy } from '../hooks/useTaxonomy';
import { GRADES, gradeLabel } from '../lib/academic';
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
  edited: 'Overridden',
  superseded: 'Superseded',
};

function conceptLabel(conceptId: string): string {
  const words = conceptId.replace(/^concept[-_]/, '').replace(/[-_]/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function displayMinutes(minutes: number | undefined): string {
  return typeof minutes === 'number' ? String(minutes) : '—';
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
  const [newClassGrade, setNewClassGrade] = useState<number | ''>('');
  const [newClassBoard, setNewClassBoard] = useState('');
  const [newClassSubject, setNewClassSubject] = useState('');
  const [isSubmittingClass, setIsSubmittingClass] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const taxonomy = useTaxonomy(true);

  const [evidenceMatrix, setEvidenceMatrix] = useState<EvidenceMatrixRow[]>([]);
  const [classGaps, setClassGaps] = useState<ClassGapRow[]>([]);
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
  const [roster, setRoster] = useState<RosterMember[]>([]);
  const [rosterError, setRosterError] = useState<string | null>(null);
  const [isLoadingRoster, setIsLoadingRoster] = useState(false);
  const [memberBusyId, setMemberBusyId] = useState<string | null>(null);
  const [rosterFeedback, setRosterFeedback] = useState<Feedback>(null);
  const [isRotatingCode, setIsRotatingCode] = useState(false);
  const [decidingActionId, setDecidingActionId] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<Feedback>(null);
  const [overrideActionId, setOverrideActionId] = useState<string | null>(null);
  const [overrideNote, setOverrideNote] = useState('');
  const [overrideError, setOverrideError] = useState<string | null>(null);

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
      setClassGaps(res.classGaps || []);
      setActions(res.actions || []);
    } catch (err: unknown) {
      setEvidenceMatrix([]);
      setClassGaps([]);
      setActions([]);
      setMatrixError(
        err instanceof Error ? err.message : 'The roster could not be loaded from SETU.'
      );
    } finally {
      setIsLoadingMatrix(false);
    }
  }, []);

  const fetchRoster = useCallback(async (classroomId: string) => {
    setIsLoadingRoster(true);
    setRosterError(null);
    try {
      const res = await api.getClassroomRoster(classroomId);
      setRoster(res.members || []);
    } catch (err: unknown) {
      setRoster([]);
      setRosterError(
        err instanceof Error ? err.message : 'The membership list could not be loaded from SETU.'
      );
    } finally {
      setIsLoadingRoster(false);
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

  useEffect(() => {
    if (!selectedClassroomId) {
      setRoster([]);
      return;
    }
    void fetchRoster(selectedClassroomId);
    const timer = window.setInterval(() => {
      void fetchRoster(selectedClassroomId);
    }, 15000);
    return () => window.clearInterval(timer);
  }, [selectedClassroomId, fetchRoster]);

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
    if (newClassGrade === '' || !newClassBoard || !newClassSubject) {
      setCreateError('Choose a class, board, and subject first.');
      return;
    }
    if (taxonomy.loading || taxonomy.error) {
      setCreateError('Reference data is not available yet. Retry in a moment.');
      return;
    }
    setIsSubmittingClass(true);
    setCreateError(null);
    try {
      const created = await api.createClassroom({
        name: newClassName.trim(),
        grade: Number(newClassGrade),
        boardId: newClassBoard,
        subjectScope: newClassSubject,
      });
      setClassrooms((prev) => [created, ...prev]);
      setSelectedClassroomId(created.id);
      setIsCreatingClassroom(false);
      setNewClassName('');
      setNewClassGrade('');
      setNewClassBoard('');
      setNewClassSubject('');
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

  const handlePlanSupport = (gap: ClassGapRow) => {
    const candidate =
      evidenceMatrix.find(
        (row) =>
          !row.profileMissing &&
          row.concepts.some(
            (concept) =>
              concept.conceptId === gap.conceptId &&
              (concept.band === 'developing' || concept.band === 'not_enough_evidence')
          )
      ) || evidenceMatrix.find((row) => !row.profileMissing);
    if (candidate) {
      setRecStudentId(candidate.studentId);
      setRecConcept(gap.conceptId);
      setRecAction('reinforce_foundations');
      setRecNote(
        `${gap.studentsNeedingSupport} of ${gap.studentsWithEvidence} students with evidence in ` +
          `${conceptLabel(gap.conceptId)} still need support. Start with the source section and one worked example.`
      );
      setRecFeedback(null);
    }
    document
      .getElementById('suggestion-panel')
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
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

  const handleRotateCode = async () => {
    if (!selected) return;
    setIsRotatingCode(true);
    setRosterFeedback(null);
    try {
      const res = await api.rotateJoinCode(selected.id);
      setClassrooms((prev) =>
        prev.map((room) => (room.id === selected.id ? { ...room, joinCode: res.joinCode } : room))
      );
      setCopied(false);
      setRosterFeedback({
        kind: 'ok',
        message: 'A new join code was issued. The previous code no longer works.',
      });
    } catch (err: unknown) {
      setRosterFeedback({
        kind: 'error',
        message:
          err instanceof Error ? err.message : 'SETU could not rotate the classroom code.',
      });
    } finally {
      setIsRotatingCode(false);
    }
  };

  const handleMemberStatus = async (member: RosterMember, status: 'active' | 'removed') => {
    if (!selected) return;
    setMemberBusyId(member.studentId);
    setRosterFeedback(null);
    try {
      await api.updateClassroomMember(selected.id, member.studentId, status);
      setRoster((prev) =>
        prev.map((row) =>
          row.studentId === member.studentId ? { ...row, status } : row
        )
      );
      if (status === 'removed' && recStudentId === member.studentId) {
        setRecStudentId('');
        setRecConcept('');
      }
      setRosterFeedback({
        kind: 'ok',
        message:
          status === 'removed'
            ? `${member.studentName} was removed. Their work stays on their own account, but they no longer appear in this classroom.`
            : `${member.studentName} was restored. They can join this classroom again with the current code.`,
      });
      void fetchEvidenceMatrix(selected.id);
    } catch (err: unknown) {
      setRosterFeedback({
        kind: 'error',
        message:
          err instanceof Error ? err.message : 'SETU could not update that membership.',
      });
    } finally {
      setMemberBusyId(null);
    }
  };

  const handleDecideAction = async (
    action: TeacherActionRow,
    decision: 'accept' | 'dismiss' | 'override',
    notes?: string
  ) => {
    setDecidingActionId(action.id);
    setActionFeedback(null);
    try {
      const res = await api.decideTeacherAction(action.id, decision, notes);
      setActions((prev) =>
        prev.map((row) =>
          row.id === action.id
            ? { ...row, status: res.status as TeacherActionRow['status'] }
            : row
        )
      );
      setActionFeedback({
        kind: 'ok',
        message:
          decision === 'override'
            ? 'Suggestion overridden. Your note is stored with it.'
            : decision === 'accept'
              ? 'Suggestion marked accepted.'
              : 'Suggestion dismissed.',
      });
      setOverrideActionId(null);
      setOverrideNote('');
      setOverrideError(null);
    } catch (err: unknown) {
      setActionFeedback({
        kind: 'error',
        message:
          err instanceof Error ? err.message : 'SETU could not update that suggestion.',
      });
    } finally {
      setDecidingActionId(null);
    }
  };

  const handleOverrideSubmit = async (action: TeacherActionRow) => {
    if (overrideNote.trim().length < 3) {
      setOverrideError('Write why you are overriding this suggestion.');
      return;
    }
    setOverrideError(null);
    await handleDecideAction(action, 'override', overrideNote.trim());
  };

  const canSend =
    Boolean(selectedClassroomId) &&
    Boolean(recStudentId) &&
    Boolean(selectedConcept) &&
    Boolean(recNote.trim()) &&
    !isSubmittingRec;

  const taxonomyReady =
    !taxonomy.loading &&
    !taxonomy.error &&
    taxonomy.boards.length > 0 &&
    taxonomy.subjects.length > 0;

  const selectedBoardName = selected
    ? taxonomy.boards.find((board) => board.id === selected.boardId)?.name
    : undefined;
  const selectedSubjectName = selected
    ? taxonomy.subjects.find((subject) => subject.id === selected.subjectScope)?.canonicalName
    : undefined;

  const canCreateClass =
    newClassName.trim().length > 0 &&
    newClassGrade !== '' &&
    Boolean(newClassBoard) &&
    Boolean(newClassSubject) &&
    taxonomyReady &&
    !isSubmittingClass;

  return (
    <div className={styles.page}>
      <header>
        <h1>Classroom</h1>
        <p className={styles.lede}>
          Members, study time, and the unit they last read. Nothing here is filled in until a
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
              <select
                value={newClassGrade}
                onChange={(e) => setNewClassGrade(e.target.value === '' ? '' : Number(e.target.value))}
              >
                <option value="">Choose a class</option>
                {GRADES.map((grade) => (
                  <option key={grade} value={grade}>
                    {gradeLabel(grade)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Board
              <select
                value={newClassBoard}
                onChange={(e) => setNewClassBoard(e.target.value)}
                disabled={taxonomy.loading || Boolean(taxonomy.error)}
              >
                <option value="">Choose a board</option>
                {taxonomy.boards.map((board) => (
                  <option key={board.id} value={board.id}>
                    {board.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Subject
              <select
                value={newClassSubject}
                onChange={(e) => setNewClassSubject(e.target.value)}
                disabled={taxonomy.loading || Boolean(taxonomy.error)}
              >
                <option value="">Choose a subject</option>
                {taxonomy.subjects.map((subject) => (
                  <option key={subject.id} value={subject.id}>
                    {subject.canonicalName}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {taxonomy.loading && (
            <p className={styles.loadingText}>Loading boards and subjects…</p>
          )}
          {taxonomy.error && (
            <div className={styles.errorBox} role="alert">
              <strong>Reference data could not be loaded.</strong> {taxonomy.error}
              <button type="button" className={styles.inlineRetry} onClick={taxonomy.retry}>
                Retry
              </button>
            </div>
          )}
          {!taxonomy.loading &&
            !taxonomy.error &&
            (taxonomy.boards.length === 0 || taxonomy.subjects.length === 0) && (
              <p className={styles.bad} role="alert">
                No boards or subjects are available. Ask an administrator to add reference data.
              </p>
            )}
          {createError && (
            <p className={styles.bad} role="alert">
              {createError}
            </p>
          )}
          <div className={styles.rowActions}>
            <button type="submit" className={styles.primary} disabled={!canCreateClass}>
              {isSubmittingClass ? 'Creating…' : 'Create classroom'}
            </button>
          </div>
        </form>
      )}

      {selected && (
        <section className={styles.panel}>
          <div className={styles.classroomHead}>
            <div>
              <h2>{selected.name}</h2>
              <p className={styles.classroomMeta}>
                {gradeLabel(selected.grade)} ·{' '}
                {selectedBoardName || selected.boardId} ·{' '}
                {selectedSubjectName || selected.subjectScope}
              </p>
            </div>
            <span className={styles.codeGroup}>
              Join code{' '}
              {selected.joinCode ? (
                <strong className={styles.code}>{selected.joinCode}</strong>
              ) : (
                <em className={styles.codeUnavailable}>Code unavailable</em>
              )}
            </span>
            <div className={styles.rowActions}>
              <button
                type="button"
                className={styles.secondary}
                onClick={copyCode}
                disabled={!selected.joinCode}
              >
                {copied ? 'Copied' : 'Copy code'}
              </button>
              <button
                type="button"
                className={styles.secondary}
                onClick={() => void handleRotateCode()}
                disabled={isRotatingCode}
              >
                {isRotatingCode ? 'Rotating…' : 'Rotate code'}
              </button>
            </div>
          </div>

          {rosterFeedback && (
            <p className={rosterFeedback.kind === 'ok' ? styles.ok : styles.bad} role="status">
              {rosterFeedback.message}
            </p>
          )}

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
            <div
              className={styles.tableWrap}
              role="region"
              aria-label="Student evidence table"
              tabIndex={0}
            >
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Student and evidenced topics</th>
                    <th>Minutes</th>
                    <th>Last read</th>
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
                                <code className={styles.conceptCode}>{concept.conceptId}</code>
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
                        <span className={styles.minutesValue}>{displayMinutes(row.minutesStudied)}</span>
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
                      <td>{row.readingTitle || 'No active reading session'}</td>
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

          {evidenceMatrix.length > 0 && (
            <p className={styles.scrollHint}>
              Scroll the table sideways to see last opened, checks, and change.
            </p>
          )}

          {!isLoadingMatrix && evidenceMatrix.length > 0 && (
            <div className={styles.gapPanel}>
              <div className={styles.gapHead}>
                <div>
                  <h3>Class gap radar</h3>
                  <p>
                    Ranked from concept evidence already recorded for this classroom. No estimated
                    or placeholder scores.
                  </p>
                </div>
                <span className={styles.gapCount}>
                  {classGaps.length} {classGaps.length === 1 ? 'topic' : 'topics'} with evidence
                </span>
              </div>
              {classGaps.length === 0 ? (
                <p className={styles.lede}>
                  Students have joined but have not recorded concept evidence yet. Gaps appear after
                  their first graded checks.
                </p>
              ) : (
                <ul className={styles.gapList}>
                  {classGaps.slice(0, 5).map((gap) => {
                    const bandTotal =
                      gap.bands.demonstrated +
                      gap.bands.approaching +
                      gap.bands.developing +
                      gap.bands.not_enough_evidence;
                    return (
                      <li key={gap.conceptId} className={styles.gapItem}>
                        <div className={styles.gapItemHead}>
                          <div>
                            <strong>{conceptLabel(gap.conceptId)}</strong>
                            <code className={styles.gapCode}>{gap.conceptId}</code>
                          </div>
                          <span
                            className={
                              gap.studentsNeedingSupport > 0
                                ? `${styles.gapNeed} ${styles.gapNeedWatch}`
                                : `${styles.gapNeed} ${styles.gapNeedOk}`
                            }
                          >
                            {gap.studentsNeedingSupport > 0
                              ? `${gap.studentsNeedingSupport} need support`
                              : 'On track'}
                          </span>
                        </div>
                        <div className={styles.gapMeta}>
                          <span>
                            {gap.studentsWithEvidence}{' '}
                            {gap.studentsWithEvidence === 1 ? 'student' : 'students'} with evidence
                          </span>
                          <span>
                            Average{' '}
                            {gap.averageScore === null ? '—' : `${Math.round(gap.averageScore)}%`}
                          </span>
                          <span>Priority {gap.priority}</span>
                        </div>
                        <div
                          className={styles.gapBands}
                          role="img"
                          aria-label={`${gap.bands.demonstrated} demonstrated, ${gap.bands.approaching} approaching, ${gap.bands.developing} developing, ${gap.bands.not_enough_evidence} not enough evidence`}
                        >
                          {bandTotal > 0 && (
                            <>
                              <i
                                className={styles.gapBandDemonstrated}
                                style={{ flexGrow: gap.bands.demonstrated }}
                                title={`${gap.bands.demonstrated} demonstrated`}
                              />
                              <i
                                className={styles.gapBandApproaching}
                                style={{ flexGrow: gap.bands.approaching }}
                                title={`${gap.bands.approaching} approaching`}
                              />
                              <i
                                className={styles.gapBandDeveloping}
                                style={{ flexGrow: gap.bands.developing }}
                                title={`${gap.bands.developing} developing`}
                              />
                              <i
                                className={styles.gapBandSparse}
                                style={{ flexGrow: gap.bands.not_enough_evidence }}
                                title={`${gap.bands.not_enough_evidence} not enough evidence`}
                              />
                            </>
                          )}
                        </div>
                        {gap.supportNames.length > 0 && (
                          <p className={styles.gapNames}>
                            Needs support: {gap.supportNames.join(', ')}
                            {gap.studentsNeedingSupport > gap.supportNames.length ? '…' : ''}
                          </p>
                        )}
                        <button
                          type="button"
                          className={styles.secondary}
                          onClick={() => handlePlanSupport(gap)}
                          disabled={
                            !evidenceMatrix.some(
                              (row) => !row.profileMissing && row.concepts.length > 0
                            )
                          }
                        >
                          Plan support
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          )}

          <div className={styles.rosterPanel}>
            <h3>Membership</h3>
            {rosterError && (
              <div className={styles.errorBox} role="alert">
                <strong>Memberships could not be loaded.</strong> {rosterError}
                <button
                  type="button"
                  className={styles.inlineRetry}
                  onClick={() => void fetchRoster(selected.id)}
                >
                  Retry
                </button>
              </div>
            )}
            {isLoadingRoster && roster.length === 0 && (
              <p className={styles.lede}>Loading memberships…</p>
            )}
            {!isLoadingRoster && !rosterError && roster.length === 0 && (
              <p className={styles.lede}>No one has joined this classroom yet.</p>
            )}
            {roster.length > 0 && (
              <ul className={styles.rosterList}>
                {roster.map((member) => (
                  <li key={member.studentId}>
                    <div>
                      <strong>{member.studentName}</strong>
                      <span
                        className={
                          member.status === 'active'
                            ? `${styles.rosterStatus} ${styles.rosterActive}`
                            : `${styles.rosterStatus} ${styles.rosterRemoved}`
                        }
                      >
                        {member.status === 'active' ? 'Active' : 'Removed'}
                      </span>
                      {member.joinedAt && (
                        <span className={styles.rosterDate}>
                          joined {new Date(member.joinedAt).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    <button
                      type="button"
                      className={styles.secondary}
                      disabled={memberBusyId === member.studentId}
                      onClick={() =>
                        void handleMemberStatus(
                          member,
                          member.status === 'active' ? 'removed' : 'active'
                        )
                      }
                    >
                      {memberBusyId === member.studentId
                        ? 'Saving…'
                        : member.status === 'active'
                          ? 'Remove'
                          : 'Restore'}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      )}

      <form id="suggestion-panel" className={styles.panel} onSubmit={handleSendRecommendation}>
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
        {actionFeedback && (
          <p className={actionFeedback.kind === 'ok' ? styles.ok : styles.bad} role="status">
            {actionFeedback.message}
          </p>
        )}
        {actions.length === 0 ? (
          <p className={styles.lede}>No suggestions sent from this classroom yet.</p>
        ) : (
          <div
            className={styles.tableWrap}
            role="region"
            aria-label="Sent suggestions table"
            tabIndex={0}
          >
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Topic</th>
                  <th>Action</th>
                  <th>Status</th>
                  <th>Date</th>
                  <th>Decision</th>
                </tr>
              </thead>
              <tbody>
                {actions.map((action) => (
                  <React.Fragment key={action.id}>
                    <tr>
                      <td>{studentNameById.get(action.studentId) || 'Not in this roster'}</td>
                      <td>
                        {action.conceptId ? (
                          <span className={styles.topicCell}>
                            <span>{conceptLabel(action.conceptId)}</span>
                            <code className={styles.conceptCode}>{action.conceptId}</code>
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>{ACTION_LABEL[action.actionType] || action.actionType}</td>
                      <td>
                        <span
                          className={`${styles.actionStatus} ${
                            styles[`status_${action.status}`] || ''
                          }`}
                        >
                          {STATUS_LABEL[action.status] || action.status}
                        </span>
                      </td>
                      <td>
                        {action.createdAt ? new Date(action.createdAt).toLocaleDateString() : '—'}
                      </td>
                      <td>
                        {action.status === 'proposed' ? (
                          <div className={styles.rowActions}>
                            <button
                              type="button"
                              className={styles.secondary}
                              disabled={decidingActionId === action.id}
                              onClick={() => void handleDecideAction(action, 'accept')}
                            >
                              Accept
                            </button>
                            <button
                              type="button"
                              className={styles.secondary}
                              disabled={decidingActionId === action.id}
                              onClick={() => void handleDecideAction(action, 'dismiss')}
                            >
                              Dismiss
                            </button>
                            <button
                              type="button"
                              className={styles.secondary}
                              disabled={decidingActionId === action.id}
                              onClick={() => {
                                setOverrideActionId(action.id);
                                setOverrideNote('');
                                setOverrideError(null);
                                setActionFeedback(null);
                              }}
                            >
                              Override
                            </button>
                          </div>
                        ) : (
                          <span className={styles.actionResolved}>
                            {action.status === 'edited'
                              ? 'Your note replaced the suggestion.'
                              : action.status === 'accepted'
                                ? action.studentResponse
                                  ? 'Accepted by the student.'
                                  : 'Visible to the student.'
                                : action.status === 'dismissed'
                                  ? 'Not sent to the student.'
                                  : 'Replaced by a newer suggestion.'}
                          </span>
                        )}
                      </td>
                    </tr>
                    {overrideActionId === action.id && action.status === 'proposed' && (
                      <tr>
                        <td colSpan={6}>
                          <div className={styles.overrideForm}>
                            <label htmlFor={`override-${action.id}`}>
                              What should the student do instead?
                            </label>
                            <textarea
                              id={`override-${action.id}`}
                              value={overrideNote}
                              maxLength={500}
                              rows={3}
                              onChange={(e) => setOverrideNote(e.target.value)}
                            />
                            {overrideError && (
                              <p className={styles.bad} role="alert">
                                {overrideError}
                              </p>
                            )}
                            <div className={styles.rowActions}>
                              <button
                                type="button"
                                className={styles.primary}
                                disabled={decidingActionId === action.id}
                                onClick={() => void handleOverrideSubmit(action)}
                              >
                                {decidingActionId === action.id ? 'Saving…' : 'Save override'}
                              </button>
                              <button
                                type="button"
                                className={styles.secondary}
                                onClick={() => {
                                  setOverrideActionId(null);
                                  setOverrideNote('');
                                  setOverrideError(null);
                                }}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {actions.length > 0 && (
          <p className={styles.scrollHint}>
            Scroll the table sideways to reach the accept, dismiss, and override buttons.
          </p>
        )}
      </section>
    </div>
  );
};
