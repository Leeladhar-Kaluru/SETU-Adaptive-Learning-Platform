import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  api,
  StudentDashboardResponse,
  ActivityHeatmapDay,
  CatalogueBoard
} from '../services/api';
import { useAuth } from '../context/AuthContext';
import styles from './StudentDashboardPage.module.css';

const GRADES = [6, 7, 8, 9, 10];

export const StudentDashboardPage: React.FC = () => {
  const { updateProfile } = useAuth();
  const [data, setData] = useState<StudentDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDay, setSelectedDay] = useState<ActivityHeatmapDay | null>(null);
  const [boards, setBoards] = useState<CatalogueBoard[]>([]);
  const [boardError, setBoardError] = useState<string | null>(null);

  // Classroom join state
  const [joinCodeInput, setJoinCodeInput] = useState('');
  const [joinStatus, setJoinStatus] = useState<string | null>(null);
  const [isJoining, setIsJoining] = useState(false);

  // Profile Edit modal state
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editName, setEditName] = useState('');
  const [editGrade, setEditGrade] = useState<number | ''>('');
  const [editBoard, setEditBoard] = useState('');
  const [editGoal, setEditGoal] = useState<number | ''>('');
  const [editError, setEditError] = useState<string | null>(null);
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  const loadBoards = async () => {
    setBoardError(null);
    try {
      const list = await api.getBoards();
      setBoards(list);
    } catch (err: any) {
      setBoards([]);
      setBoardError(err?.message || 'Curriculum boards could not be loaded.');
    }
  };

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
    void loadBoards();
  }, []);

  const handleJoinClassroom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!joinCodeInput.trim()) return;
    setIsJoining(true);
    setJoinStatus(null);
    try {
      await api.joinClassroom(joinCodeInput.trim().toUpperCase());
      setJoinStatus('Joined classroom successfully!');
      setJoinCodeInput('');
      fetchDashboardData();
    } catch (err: any) {
      setJoinStatus(err?.message || 'Failed to join classroom. Check the code and try again.');
    } finally {
      setIsJoining(false);
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setEditError(null);
    if (editGrade === '' || !editBoard) {
      setEditError('Choose a class and board before saving.');
      return;
    }
    setIsSavingProfile(true);
    try {
      await updateProfile({
        displayName: editName.trim(),
        grade: Number(editGrade),
        boardId: editBoard,
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
        <p style={{ padding: '40px 0', color: 'var(--ink-secondary)' }}>
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
            <h2>Unable to load dashboard</h2>
            <p style={{ color: 'var(--ink-secondary)', marginTop: 8 }}>{error}</p>
          </div>
          <button type="button" className={styles.editBtn} onClick={fetchDashboardData}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const { profile, stats, activityHeatmap, conceptMastery, recentAttempts, classrooms } = data;
  const initial = profile.displayName ? profile.displayName.charAt(0).toUpperCase() : 'S';

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

  return (
    <div className={styles.container}>
      {/* 1. Profile Header Card */}
      <section className={styles.profileCard}>
        <div className={styles.profileLeft}>
          <div className={styles.avatar}>{initial}</div>
          <div className={styles.profileInfo}>
            <h1>{profile.displayName}</h1>
            {profile.email && <div className={styles.profileEmail}>{profile.email}</div>}
            <div className={styles.badgeRow}>
              {profile.grade != null && (
                <span className={`${styles.badge} ${styles.badgeBrand}`}>Class {profile.grade}</span>
              )}
              {profile.boardId && (
                <span className={`${styles.badge} ${styles.badgeBoard}`}>
                  {profile.boardId.replace('board-', '').toUpperCase()}
                </span>
              )}
              {profile.dailyGoalMinutes != null && (
                <span className={`${styles.badge} ${styles.badgeGoal}`}>
                  Goal: {profile.dailyGoalMinutes} min/day
                </span>
              )}
            </div>
            {(!profile.grade || !profile.boardId || !profile.preferredLanguage) && (
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
            Edit Academic Profile
          </button>
        </div>
      </section>

      {/* 2. Key Academic Stats */}
      <section className={styles.statsGrid}>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Current Streak</span>
          <span className={styles.statValue}>
            {stats.currentStreak} {stats.currentStreak === 1 ? 'Day' : 'Days'}
          </span>
          <span className={styles.statSub}>
            {stats.currentStreak > 0 ? 'Consistency maintained!' : 'Complete an activity today'}
          </span>
        </div>

        <div className={styles.statCard}>
          <span className={styles.statLabel}>Longest Streak</span>
          <span className={styles.statValue}>
            {stats.longestStreak} {stats.longestStreak === 1 ? 'Day' : 'Days'}
          </span>
          <span className={styles.statSub}>Personal best consistency</span>
        </div>

        <div className={styles.statCard}>
          <span className={styles.statLabel}>Total Time Studied</span>
          <span className={styles.statValue}>
            {stats.totalMinutesStudied >= 60
              ? `${(stats.totalMinutesStudied / 60).toFixed(1)} hrs`
              : `${stats.totalMinutesStudied} mins`}
          </span>
          <span className={styles.statSub}>Across {stats.totalSessions} study sessions</span>
        </div>

        <div className={styles.statCard}>
          <span className={styles.statLabel}>Checkpoint Accuracy</span>
          <span className={styles.statValue}>
            {stats.totalQuestionsAttempted === 0 ? '—' : `${stats.averageAccuracy}%`}
          </span>
          <span className={styles.statSub}>
            {stats.totalQuestionsAttempted === 0
              ? 'No checkpoint attempts yet'
              : `${stats.totalQuestionsAttempted} questions attempted`}
          </span>
        </div>
      </section>

      {/* 3. Learning Consistency Heatmap (12 Weeks / 84 Days) */}
      <section className={styles.heatmapCard}>
        <div className={styles.cardHeader}>
          <div>
            <div className={styles.cardTitle}>Learning Consistency Heatmap</div>
            <div className={styles.cardSubtitle}>
              Activity distribution over the past 12 weeks (84 days) across reading and checkpoints.
            </div>
          </div>
          <div className={styles.heatmapLegend}>
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

        <div className={styles.heatmapScroll}>
          {stats.totalSessions === 0 ? (
            <div className={styles.emptyNotice}>
              No study activity yet. Open a ready lesson to start the heatmap.
            </div>
          ) : (
            <div className={styles.heatmapContainer}>
              <div className={styles.heatmapGrid}>
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
                    <div
                      key={day.date}
                      className={`${styles.heatmapCell} ${levelClass}`}
                      onClick={() => setSelectedDay(day)}
                      title={`${day.date}: ${day.minutes} min studied (${day.count} activities)`}
                    />
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {selectedDay && (
          <div className={styles.activeDayTooltip}>
            <strong>{selectedDay.date}</strong>: {selectedDay.minutes} minutes studied across{' '}
            {selectedDay.count} interactions.
          </div>
        )}
      </section>

      {/* 4. Split Section: Concept Mastery Matrix + Recent Checkpoints */}
      <div className={styles.twoColGrid}>
        {/* Concept Mastery Matrix */}
        <section className={styles.sectionCard}>
          <div className={styles.cardTitle}>Concept Mastery Matrix</div>
          <div className={styles.cardSubtitle}>
            Evidence-backed mastery calculations across syllabus concepts.
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
                    <span className={styles.conceptName}>
                      {item.conceptId.replace(/_/g, ' ')}
                    </span>
                    <span className={`${styles.bandPill} ${getBandClass(item.band)}`}>
                      {formatBandName(item.band)}
                    </span>
                  </div>

                  <div className={styles.scoreBarTrack}>
                    <div
                      className={`${styles.scoreBarFill} ${getFillClass(item.band)}`}
                      style={{ width: `${item.score}%` }}
                    />
                  </div>

                  <div className={styles.masteryFoot}>
                    <span>
                      Score: {item.score}% ({item.evidenceCount} evidence points)
                    </span>
                    {item.needsRemediation && (
                      <div className={styles.remediationAlert}>
                        <span>Refresher Injected</span>
                        <Link to="/" className={styles.reviewBtn}>
                          Practice Now
                        </Link>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Recent Checkpoints */}
        <section className={styles.sectionCard}>
          <div className={styles.cardTitle}>Recent Practice Checkpoints</div>
          <div className={styles.cardSubtitle}>
            Detailed log of your latest questions and understanding checks.
          </div>

          {recentAttempts.length === 0 ? (
            <div className={styles.emptyNotice}>
              No checkpoint attempts yet.
            </div>
          ) : (
            <table className={styles.attemptsTable}>
              <thead>
                <tr>
                  <th>Topic</th>
                  <th>Outcome</th>
                  <th>Hints</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {recentAttempts.map((att) => (
                  <tr key={att.id}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{att.lessonTitle}</div>
                      <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>
                        {att.occurredAt ? new Date(att.occurredAt).toLocaleDateString() : ''}
                      </div>
                    </td>
                    <td>
                      <span
                        className={att.isCorrect ? styles.attemptCorrect : styles.attemptIncorrect}
                      >
                        {att.isCorrect ? 'Correct' : 'Needs Review'}
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

      {/* 5. Classrooms & Teacher Connection */}
      <section className={styles.sectionCard}>
        <div className={styles.cardTitle}>Enrolled Classrooms</div>
        <div className={styles.cardSubtitle}>
          Connect with your teachers to receive personalized recommendations and evidence-based guidance.
        </div>

        {classrooms.length === 0 ? (
          <div className={styles.emptyNotice}>You have not joined a classroom.</div>
        ) : (
          <div className={styles.classroomsList}>
            {classrooms.map((c) => (
              <div key={c.id} className={styles.classroomCard}>
                <span className={styles.classroomName}>{c.name}</span>
                <span className={styles.classroomMeta}>
                  Class {c.grade} • {c.subjectScope}
                </span>
                <span className={styles.joinCodePill}>Code: {c.joinCode}</span>
              </div>
            ))}
          </div>
        )}

        <form className={styles.joinForm} onSubmit={handleJoinClassroom}>
          <input
            type="text"
            className={styles.joinInput}
            placeholder="Enter Classroom Code (e.g. CBSE10)"
            value={joinCodeInput}
            onChange={(e) => setJoinCodeInput(e.target.value)}
            disabled={isJoining}
          />
          <button type="submit" className={styles.joinSubmitBtn} disabled={isJoining}>
            {isJoining ? 'Joining…' : 'Join Classroom'}
          </button>
        </form>
        {joinStatus && (
          <div style={{ fontSize: 13, marginTop: 8, color: 'var(--brand-primary)', fontWeight: 600 }}>
            {joinStatus}
          </div>
        )}
      </section>

      {/* Profile Edit Drawer/Modal */}
      {isEditOpen && (
        <div className={styles.modalBackdrop}>
          <div className={styles.modalCard}>
            <div className={styles.modalTitle}>Edit Academic Profile</div>
            <form onSubmit={handleSaveProfile} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className={styles.formGroup}>
                <label>Display Name</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  required
                />
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="edit-grade">Class / Grade</label>
                <select
                  id="edit-grade"
                  value={editGrade}
                  onChange={(e) => setEditGrade(e.target.value === '' ? '' : Number(e.target.value))}
                >
                  <option value="">Choose a class</option>
                  {GRADES.map((grade) => (
                    <option key={grade} value={grade}>Class {grade}</option>
                  ))}
                </select>
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="edit-board">Curriculum Board</label>
                <select
                  id="edit-board"
                  value={editBoard}
                  onChange={(e) => setEditBoard(e.target.value)}
                  disabled={Boolean(boardError)}
                >
                  <option value="">Choose a board</option>
                  {boards.map((board) => (
                    <option key={board.id} value={board.id}>
                      {board.code ? `${board.code} — ${board.name}` : board.name}
                    </option>
                  ))}
                </select>
                {boardError && (
                  <p className={styles.formError} role="alert">
                    {boardError}{' '}
                    <button type="button" className={styles.editBtn} onClick={() => void loadBoards()}>
                      Retry
                    </button>
                  </p>
                )}
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="edit-goal">Daily Learning Goal (Minutes)</label>
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
                  disabled={isSavingProfile || Boolean(boardError)}
                >
                  {isSavingProfile ? 'Saving…' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
