import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  api,
  StudentDashboardResponse,
  ActivityHeatmapDay
} from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useTaxonomy } from '../hooks/useTaxonomy';
import { useDialogFocus } from '../hooks/useDialogFocus';
import { GRADES, gradeLabel } from '../lib/academic';
import styles from './StudentDashboardPage.module.css';

export const StudentDashboardPage: React.FC = () => {
  const { updateProfile } = useAuth();
  const [data, setData] = useState<StudentDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDay, setSelectedDay] = useState<ActivityHeatmapDay | null>(null);
  const [heatmapAsTable, setHeatmapAsTable] = useState(false);

  // Classroom join state
  const [joinCodeInput, setJoinCodeInput] = useState('');
  const [joinStatus, setJoinStatus] = useState<{ kind: 'ok' | 'error'; message: string } | null>(null);
  const [isJoining, setIsJoining] = useState(false);

  // Profile Edit modal state
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editName, setEditName] = useState('');
  const [editGrade, setEditGrade] = useState<number | ''>('');
  const [editBoard, setEditBoard] = useState('');
  const [editLanguage, setEditLanguage] = useState('');
  const [editGoal, setEditGoal] = useState<number | ''>('');
  const [editError, setEditError] = useState<string | null>(null);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const taxonomy = useTaxonomy(true);
  const editDialogRef = useRef<HTMLDivElement>(null);
  useDialogFocus(editDialogRef, isEditOpen, () => setIsEditOpen(false));

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getStudentDashboard();
      setData(res);
      if (res.profile) {
        setEditName(res.profile.displayName || '');
        setEditGrade(res.profile.grade ?? '');
        setEditBoard(res.profile.boardId ?? '');
        setEditLanguage(res.profile.preferredLanguage ?? '');
        setEditGoal(res.profile.dailyGoalMinutes ?? '');
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load student dashboard.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchDashboardData();
  }, []);

  const handleJoinClassroom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!joinCodeInput.trim()) return;
    setIsJoining(true);
    setJoinStatus(null);
    try {
      await api.joinClassroom(joinCodeInput.trim().toUpperCase());
      setJoinStatus({ kind: 'ok', message: 'Joined the classroom.' });
      setJoinCodeInput('');
      fetchDashboardData();
    } catch (err: any) {
      setJoinStatus({
        kind: 'error',
        message: err?.message || 'Could not join. Check the code with your teacher and try again.',
      });
    } finally {
      setIsJoining(false);
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setEditError(null);
    if (editGrade === '' || !editBoard || !editLanguage) {
      setEditError('Choose a class, board, and language before saving.');
      return;
    }
    if (!editName.trim()) {
      setEditError('Enter the name your teacher will see.');
      return;
    }
    setIsSavingProfile(true);
    try {
      await updateProfile({
        displayName: editName.trim(),
        grade: Number(editGrade),
        boardId: editBoard,
        preferredLanguage: editLanguage,
        dailyGoalMinutes: editGoal === '' ? undefined : Number(editGoal)
      });
      setIsEditOpen(false);
      fetchDashboardData();
    } catch (err: any) {
      setEditError(err?.message || 'Failed to save profile.');
    } finally {
      setIsSavingProfile(false);
    }
  };

  if (loading) {
    return (
      <div className={styles.container}>
        <p className={styles.loadNote} role="status">
          Loading your learning progress and activity heatmap…
        </p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className={styles.container}>
        <div className={styles.profileCard}>
          <div>
            <h1 className={styles.stateTitle}>Unable to load dashboard</h1>
            <p className={styles.errorText}>
              {error || 'The dashboard response was empty.'}
            </p>
          </div>
          <button type="button" className={styles.editBtn} onClick={fetchDashboardData}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const { profile, stats, activityHeatmap, conceptMastery, recentAttempts, classrooms } = data;
  const understanding = data.understanding;
  const initial = profile.displayName ? profile.displayName.charAt(0).toUpperCase() : 'S';
  const boardName = taxonomy.boards.find((board) => board.id === profile.boardId)?.name;
  const languageName = taxonomy.languages.find(
    (language) => language.bcp47Tag === profile.preferredLanguage
  )?.nativeName;
  const subjectName = (subjectId: string) =>
    taxonomy.subjects.find((subject) => subject.id === subjectId)?.canonicalName || subjectId;
  const conceptLabel = (conceptId: string) =>
    conceptId.replace(/^concept[-_]/, '').replace(/[-_]/g, ' ');

  const profileIncomplete =
    profile.grade == null || !profile.boardId || !profile.preferredLanguage;

  const formatBandName = (band: string) => {
    switch (band) {
      case 'demonstrated':
        return 'Demonstrated';
      case 'approaching':
        return 'Approaching';
      case 'developing':
        return 'Developing';
      default:
        return 'Not enough evidence';
    }
  };

  const getBandClass = (band: string) => {
    switch (band) {
      case 'demonstrated':
        return styles.bandDemonstrated;
      case 'approaching':
        return styles.bandApproaching;
      case 'developing':
        return styles.bandDeveloping;
      default:
        return styles.bandSparse;
    }
  };

  const getFillClass = (band: string) => {
    switch (band) {
      case 'demonstrated':
        return styles.fillDemonstrated;
      case 'approaching':
        return styles.fillApproaching;
      default:
        return styles.fillDeveloping;
    }
  };

  const recordedDays = activityHeatmap.filter((day) => day.count > 0 || day.seconds > 0);

  return (
    <div className={styles.container}>
      {/* 1. Profile header */}
      <section className={styles.profileCard} aria-label="Student record">
        <div className={styles.profileLeft}>
          <div className={styles.avatar} aria-hidden="true">{initial}</div>
          <div className={styles.profileInfo}>
            <span className={styles.eyebrow}>Student record</span>
            <h1>{profile.displayName}</h1>
            {profile.email && <div className={styles.profileEmail}>{profile.email}</div>}
            <div className={styles.badgeRow}>
              {profile.grade != null && (
                <span className={`${styles.badge} ${styles.badgeBrand}`}>{gradeLabel(profile.grade)}</span>
              )}
              {profile.boardId && (
                <span
                  className={`${styles.badge} ${boardName ? styles.badgeBoard : styles.badgeCode}`}
                  title={boardName ? undefined : `Stored board id: ${profile.boardId}`}
                >
                  {boardName || profile.boardId}
                </span>
              )}
              {languageName && (
                <span className={`${styles.badge} ${styles.badgeBoard}`}>{languageName}</span>
              )}
              {profile.dailyGoalMinutes != null && (
                <span className={`${styles.badge} ${styles.badgeGoal}`}>
                  Goal: {profile.dailyGoalMinutes} min/day
                </span>
              )}
            </div>
            {profileIncomplete && (
              <div className={styles.emptyNotice}>
                Add your class, board, and language to finish setting up your desk.
                <button
                  type="button"
                  className={styles.editBtn}
                  onClick={() => setIsEditOpen(true)}
                >
                  Add academic details
                </button>
              </div>
            )}
          </div>
        </div>
        <div className={styles.profileRight}>
          <button type="button" className={styles.editBtn} onClick={() => setIsEditOpen(true)}>
            Edit academic profile
          </button>
        </div>
      </section>

      {/* 2. Study summary */}
      <section aria-labelledby="study-summary-title">
        <h2 id="study-summary-title" className={styles.sectionHeading}>
          Study summary
        </h2>
        <dl className={styles.statsRow}>
          <div className={styles.summaryItem}>
            <dt className={styles.statLabel}>Current streak</dt>
            <dd className={styles.statValue}>
              {stats.currentStreak} {stats.currentStreak === 1 ? 'day' : 'days'}
            </dd>
            <span className={styles.statSub}>
              {stats.currentStreak > 0
                ? 'Recorded activity includes today.'
                : 'No activity recorded today.'}
            </span>
          </div>

          <div className={styles.summaryItem}>
            <dt className={styles.statLabel}>Longest streak</dt>
            <dd className={styles.statValue}>
              {stats.longestStreak} {stats.longestStreak === 1 ? 'day' : 'days'}
            </dd>
            <span className={styles.statSub}>Personal best from recorded days.</span>
          </div>

          <div className={styles.summaryItem}>
            <dt className={styles.statLabel}>Time studied</dt>
            <dd className={styles.statValue}>
              {stats.totalMinutesStudied >= 60
                ? `${(stats.totalMinutesStudied / 60).toFixed(1)} hrs`
                : `${stats.totalMinutesStudied} mins`}
            </dd>
            <span className={styles.statSub}>
              Across {stats.totalSessions} {stats.totalSessions === 1 ? 'study session' : 'study sessions'}.
            </span>
          </div>

          <div className={styles.summaryItem}>
            <dt className={styles.statLabel}>Answer accuracy</dt>
            <dd className={styles.statValue}>
              {stats.totalQuestionsAttempted === 0 ? '—' : `${stats.averageAccuracy}%`}
            </dd>
            <span className={styles.statSub}>
              {stats.totalQuestionsAttempted === 0
                ? 'No checkpoint attempts yet'
                : `${stats.totalQuestionsAttempted} ${stats.totalQuestionsAttempted === 1 ? 'question' : 'questions'} attempted`}
            </span>
          </div>
        </dl>
      </section>

      {/* 3. How you learn */}
      {understanding && (
        <section className={styles.understandingCard} aria-labelledby="understanding-title">
          <div className={styles.cardHeader}>
            <div>
              <h2 id="understanding-title" className={styles.cardTitle}>How you learn</h2>
              <div className={styles.cardSubtitle}>
                Derived only from your recorded sessions, answers, hints and timing.
              </div>
            </div>
            <span className={styles.confidenceBadge}>
              {understanding.confidence === 'none'
                ? 'No evidence yet'
                : `${understanding.confidence} confidence`}
            </span>
          </div>

          <p className={styles.understandingSummary}>{understanding.summary}</p>

          <dl className={styles.understandingGrid}>
            <div>
              <dt>Accuracy trend</dt>
              <dd>{understanding.accuracy.overall === null ? '—' : `${understanding.accuracy.overall}%`}</dd>
              <span>{understanding.accuracy.detail}</span>
            </div>
            <div>
              <dt>Best study window</dt>
              <dd>{understanding.routine.bestWindow?.label || 'No routine yet'}</dd>
              <span>{understanding.routine.detail}</span>
            </div>
            <div>
              <dt>Working pace</dt>
              <dd>
                {understanding.pace.medianAnswerSeconds === null
                  ? 'No timed answers'
                  : `${understanding.pace.medianAnswerSeconds}s median`}
              </dd>
              <span>{understanding.pace.detail}</span>
            </div>
            <div>
              <dt>Hint reliance</dt>
              <dd>{understanding.hintReliance.hintRate === null ? '—' : `${understanding.hintReliance.hintRate}%`}</dd>
              <span>{understanding.hintReliance.detail}</span>
            </div>
          </dl>

          {understanding.habits.length > 0 && (
            <ul className={styles.habitList}>
              {understanding.habits.map((habit) => (
                <li
                  key={habit.id}
                  className={
                    habit.tone === 'watch'
                      ? styles.habitWatch
                      : habit.tone === 'positive'
                        ? styles.habitPositive
                        : styles.habitNeutral
                  }
                >
                  <strong>{habit.title}</strong>
                  <span>{habit.detail}</span>
                </li>
              ))}
            </ul>
          )}

          <div className={styles.evidenceFoot}>
            <span>{understanding.confidenceDetail}</span>
            <span>
              {understanding.evidence.activeDays} active{' '}
              {understanding.evidence.activeDays === 1 ? 'day' : 'days'} ·{' '}
              {understanding.evidence.totalMinutes} minutes ·{' '}
              {understanding.evidence.gradedAttempts} graded answers
            </span>
          </div>
        </section>
      )}

      {/* 4. Activity heatmap */}
      <section className={styles.heatmapCard} aria-labelledby="heatmap-title">
        <div className={styles.cardHeader}>
          <div>
            <h2 id="heatmap-title" className={styles.cardTitle}>Learning consistency</h2>
            <div className={styles.cardSubtitle}>
              Recorded activity over the last 84 days. Empty days had no study events.
            </div>
          </div>
          <div className={styles.heatmapLegend} aria-hidden="true">
            <span>Less</span>
            <div className={styles.legendCells}>
              <span className={`${styles.legendBox} ${styles.level0}`} />
              <span className={`${styles.legendBox} ${styles.level1}`} />
              <span className={`${styles.legendBox} ${styles.level2}`} />
              <span className={`${styles.legendBox} ${styles.level3}`} />
              <span className={`${styles.legendBox} ${styles.level4}`} />
            </div>
            <span>More</span>
          </div>
        </div>

        {recordedDays.length === 0 ? (
          <div className={styles.emptyNotice}>
            No study activity yet. Open a ready lesson to start the heatmap.
          </div>
        ) : (
          <>
            <div className={styles.heatmapToolbar}>
              <button
                type="button"
                className={styles.heatmapToggle}
                aria-pressed={heatmapAsTable}
                onClick={() => setHeatmapAsTable((value) => !value)}
                disabled={recordedDays.length === 0}
              >
                {heatmapAsTable ? 'Show as grid' : 'Show as table'}
              </button>
              <span className={styles.heatmapCount}>
                {recordedDays.length} {recordedDays.length === 1 ? 'day' : 'days'} with recorded activity
              </span>
            </div>

            {heatmapAsTable ? (
              <table className={styles.heatmapTable}>
                <caption className={styles.srOnly}>
                  Days with recorded study activity in the last 84 days
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col">Minutes</th>
                    <th scope="col">Activities</th>
                    <th scope="col">Level</th>
                  </tr>
                </thead>
                <tbody>
                  {recordedDays.map((day) => (
                    <tr key={day.date}>
                      <th scope="row">{day.date}</th>
                      <td>{day.minutes}</td>
                      <td>{day.count}</td>
                      <td>{day.level} of 4</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className={styles.heatmapContainer}>
                <div className={styles.heatmapGrid} role="group" aria-label="Daily study activity">
                  {activityHeatmap.map((day) => {
                    const levelClass =
                      day.level === 4
                        ? styles.level4
                        : day.level === 3
                        ? styles.level3
                        : day.level === 2
                        ? styles.level2
                        : day.level === 1
                        ? styles.level1
                        : styles.level0;

                    return (
                      <button
                        key={day.date}
                        type="button"
                        className={`${styles.heatmapCell} ${levelClass}`}
                        aria-pressed={selectedDay?.date === day.date}
                        aria-label={`${day.date}: ${day.minutes} minutes across ${day.count} ${
                          day.count === 1 ? 'activity' : 'activities'
                        }`}
                        onClick={() => setSelectedDay(day)}
                        title={`${day.date}: ${day.minutes} min studied (${day.count} activities)`}
                      />
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}

        <div className={styles.activeDayTooltip} role="status" aria-live="polite">
          {selectedDay ? (
            <>
              <strong>{selectedDay.date}</strong>: {selectedDay.minutes} minutes studied across{' '}
              {selectedDay.count} {selectedDay.count === 1 ? 'activity' : 'activities'}.
            </>
          ) : (
            'Select a day to see its recorded activity.'
          )}
        </div>
      </section>

      {/* 5. Concept evidence and recent attempts */}
      <div className={styles.twoColGrid}>
        <section className={styles.sectionCard} aria-labelledby="mastery-title">
          <h2 id="mastery-title" className={styles.cardTitle}>Concept mastery</h2>
          <div className={styles.cardSubtitle}>
            Bands are calculated from your recorded checkpoint evidence.
          </div>

          {conceptMastery.length === 0 ? (
            <div className={styles.emptyNotice}>
              No concept mastery evidence yet. Answer a checkpoint to build evidence.
            </div>
          ) : (
            <div className={styles.masteryList}>
              {conceptMastery.map((item) => (
                <div
                  key={item.conceptId}
                  className={`${styles.masteryItem} ${
                    item.needsRemediation ? styles.masteryItemAlert : ''
                  }`}
                >
                  <div className={styles.masteryTop}>
                    <div className={styles.conceptBlock}>
                      <span className={styles.conceptName}>{conceptLabel(item.conceptId)}</span>
                      <code className={styles.conceptCode}>{item.conceptId}</code>
                    </div>
                    <span className={`${styles.bandPill} ${getBandClass(item.band)}`}>
                      {formatBandName(item.band)}
                    </span>
                  </div>

                  <div className={styles.scoreBarTrack}>
                    <div
                      className={`${styles.scoreBarFill} ${getFillClass(item.band)}`}
                      style={{ width: `${Math.max(0, Math.min(100, item.score))}%` }}
                    />
                  </div>

                  <div className={styles.masteryFoot}>
                    <span>
                      {item.score}% from {item.evidenceCount}{' '}
                      {item.evidenceCount === 1 ? 'evidence point' : 'evidence points'}
                    </span>
                    {item.needsRemediation && (
                      <span className={styles.remediationAlert}>
                        Needs review
                        <Link to="/" className={styles.reviewBtn}>
                          Open desk
                        </Link>
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className={styles.sectionCard} aria-labelledby="attempts-title">
          <h2 id="attempts-title" className={styles.cardTitle}>Recent answers</h2>
          <div className={styles.cardSubtitle}>
            Your latest recorded answers and how long they took.
          </div>

          {recentAttempts.length === 0 ? (
            <div className={styles.emptyNotice}>No checkpoint attempts yet.</div>
          ) : (
            <table className={styles.attemptsTable}>
              <thead>
                <tr>
                  <th scope="col">Lesson</th>
                  <th scope="col">Outcome</th>
                  <th scope="col">Hints</th>
                  <th scope="col">Time</th>
                </tr>
              </thead>
              <tbody>
                {recentAttempts.map((att) => (
                  <tr key={att.id}>
                    <th scope="row" className={styles.attemptTopic}>
                      <span>{att.lessonTitle}</span>
                      <span className={styles.attemptDate}>
                        {att.occurredAt ? new Date(att.occurredAt).toLocaleDateString() : ''}
                      </span>
                    </th>
                    <td>
                      <span
                        className={att.isCorrect ? styles.attemptCorrect : styles.attemptIncorrect}
                      >
                        {att.isCorrect ? 'Correct' : 'Incorrect'}
                      </span>
                    </td>
                    <td>{att.hintsUsed}</td>
                    <td>{att.elapsedSeconds > 0 ? `${att.elapsedSeconds}s` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      {/* 5. Classrooms */}
      <section className={styles.sectionCard} aria-labelledby="classrooms-title">
        <h2 id="classrooms-title" className={styles.cardTitle}>Classrooms</h2>
        <div className={styles.cardSubtitle}>
          Classrooms you joined with a teacher's code. Your teachers see evidence from your
          recorded attempts.
        </div>

        {classrooms.length === 0 ? (
          <div className={styles.emptyNotice}>You have not joined a classroom.</div>
        ) : (
          <div className={styles.classroomsList}>
            {classrooms.map((c) => (
              <div key={c.id} className={styles.classroomCard}>
                <span className={styles.classroomName}>{c.name}</span>
                <span className={styles.classroomMeta}>
                  {gradeLabel(c.grade)} · {subjectName(c.subjectScope)}
                </span>
                {c.joinCode && (
                  <span className={styles.joinCodePill}>Code: {c.joinCode}</span>
                )}
              </div>
            ))}
          </div>
        )}

        <form className={styles.joinForm} onSubmit={handleJoinClassroom}>
          <label className={styles.joinLabel} htmlFor="join-code">
            Classroom code
          </label>
          <div className={styles.joinRow}>
            <input
              id="join-code"
              type="text"
              className={styles.joinInput}
              placeholder="Enter the code from your teacher"
              value={joinCodeInput}
              onChange={(e) => setJoinCodeInput(e.target.value)}
              disabled={isJoining}
              autoComplete="off"
            />
            <button
              type="submit"
              className={styles.joinSubmitBtn}
              disabled={isJoining || !joinCodeInput.trim()}
            >
              {isJoining ? 'Joining…' : 'Join classroom'}
            </button>
          </div>
        </form>
        {joinStatus && (
          <p
            className={joinStatus.kind === 'ok' ? styles.joinOk : styles.joinBad}
            role={joinStatus.kind === 'ok' ? 'status' : 'alert'}
          >
            {joinStatus.message}
          </p>
        )}
      </section>

      {/* 6. Profile editor */}
      {isEditOpen && (
        <div className={styles.modalBackdrop}>
          <div
            className={styles.modalCard}
            ref={editDialogRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-profile-title"
          >
            <div className={styles.modalHeader}>
              <h2 id="edit-profile-title" className={styles.modalTitle}>
                Edit academic profile
              </h2>
              <button
                type="button"
                className={styles.cancelBtn}
                onClick={() => setIsEditOpen(false)}
                disabled={isSavingProfile}
              >
                Close
              </button>
            </div>
            <form className={styles.editForm} onSubmit={handleSaveProfile}>
              <div className={styles.formGroup}>
                <label htmlFor="edit-name">Display name</label>
                <input
                  id="edit-name"
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  required
                  autoComplete="name"
                />
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="edit-grade">Class / grade</label>
                <select
                  id="edit-grade"
                  value={editGrade}
                  onChange={(e) => setEditGrade(e.target.value === '' ? '' : Number(e.target.value))}
                >
                  <option value="">Choose a class</option>
                  {GRADES.map((grade) => (
                    <option key={grade} value={grade}>{gradeLabel(grade)}</option>
                  ))}
                </select>
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="edit-board">Curriculum board</label>
                <select
                  id="edit-board"
                  value={editBoard}
                  onChange={(e) => setEditBoard(e.target.value)}
                  disabled={taxonomy.loading || Boolean(taxonomy.error)}
                >
                  <option value="">Choose a board</option>
                  {taxonomy.boards.map((board) => (
                    <option key={board.id} value={board.id}>
                      {board.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="edit-language">Learning language</label>
                <select
                  id="edit-language"
                  value={editLanguage}
                  onChange={(e) => setEditLanguage(e.target.value)}
                  disabled={taxonomy.loading || Boolean(taxonomy.error)}
                >
                  <option value="">Choose a language</option>
                  {taxonomy.languages.map((language) => (
                    <option key={language.id} value={language.bcp47Tag}>
                      {language.nativeName}
                    </option>
                  ))}
                </select>
              </div>

              {taxonomy.loading && (
                <p className={styles.formHint}>Loading boards, subjects, and languages…</p>
              )}
              {taxonomy.error && (
                <p className={styles.formError} role="alert">
                  {taxonomy.error}{' '}
                  <button type="button" className={styles.editBtn} onClick={taxonomy.retry}>
                    Retry
                  </button>
                </p>
              )}
              {!taxonomy.loading && !taxonomy.error && (taxonomy.boards.length === 0 || taxonomy.languages.length === 0) && (
                <p className={styles.formError} role="alert">
                  No reference data is available. Ask an administrator to add boards and languages.
                </p>
              )}

              <div className={styles.formGroup}>
                <label htmlFor="edit-goal">Daily learning goal (minutes)</label>
                <input
                  id="edit-goal"
                  type="number"
                  min={10}
                  max={120}
                  placeholder="Not set"
                  value={editGoal}
                  onChange={(e) => setEditGoal(e.target.value === '' ? '' : Number(e.target.value))}
                />
              </div>

              {editError && (
                <p className={styles.formError} role="alert">
                  {editError}
                </p>
              )}

              <div className={styles.modalActions}>
                <button
                  type="button"
                  className={styles.cancelBtn}
                  onClick={() => setIsEditOpen(false)}
                  disabled={isSavingProfile}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.saveBtn}
                  disabled={
                    isSavingProfile ||
                    taxonomy.loading ||
                    Boolean(taxonomy.error) ||
                    taxonomy.boards.length === 0 ||
                    taxonomy.languages.length === 0
                  }
                >
                  {isSavingProfile ? 'Saving…' : 'Save changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
