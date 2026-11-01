import React, { useEffect, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTaxonomy } from '../hooks/useTaxonomy';
import { GRADES, gradeLabel } from '../lib/academic';
import { UserProfileData } from '../services/api';
import styles from './OnboardingTour.module.css';

interface OnboardingTourProps {
  isOpen: boolean;
  onClose: () => void;
}

export const OnboardingTour: React.FC<OnboardingTourProps> = ({ isOpen, onClose }) => {
  const { user, signup, login, updateProfile } = useAuth();
  const [step, setStep] = useState<number>(0);

  // Unauthenticated Registration / Sign-in state
  const [authMode, setAuthMode] = useState<'register' | 'signin'>('register');
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [role, setRole] = useState<'student' | 'teacher'>('student');
  const [authError, setAuthError] = useState<string | null>(null);

  // Student Preferences state
  const [grade, setGrade] = useState<number | ''>('');
  const [boardId, setBoardId] = useState('');
  const [preferredLanguage, setPreferredLanguage] = useState('');
  const [selectedSubjects, setSelectedSubjects] = useState<string[]>([]);
  const [pace, setPace] = useState<'short' | 'steady' | 'long' | ''>('');
  const [dailyMinutes, setDailyMinutes] = useState<number | ''>('');
  const [learningGoals, setLearningGoals] = useState<string[]>([]);
  const [preferencesError, setPreferencesError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const wasOpen = useRef(false);
  const taxonomy = useTaxonomy(isOpen);

  useEffect(() => {
    if (!isOpen) {
      wasOpen.current = false;
      return;
    }
    if (wasOpen.current) return;
    wasOpen.current = true;
    setGrade(user?.grade ?? '');
    setBoardId(user?.boardId ?? '');
    setPreferredLanguage(user?.preferredLanguage ?? '');
    setSelectedSubjects(user?.subjectsInterested ?? []);
    setPace((user?.accessibilityPreferences?.pace as 'short' | 'steady' | 'long') ?? '');
    setDailyMinutes(user?.dailyGoalMinutes ?? '');
    setLearningGoals(user?.learningGoals ?? []);
    setPreferencesError(null);
  }, [isOpen, user]);

  if (!isOpen) return null;

  const taxonomyEmpty =
    !taxonomy.loading &&
    !taxonomy.error &&
    (taxonomy.boards.length === 0 ||
      taxonomy.subjects.length === 0 ||
      taxonomy.languages.length === 0);

  const toggleSubject = (id: string) => {
    if (selectedSubjects.includes(id)) {
      setSelectedSubjects(selectedSubjects.filter(s => s !== id));
    } else {
      setSelectedSubjects([...selectedSubjects, id]);
    }
  };

  const toggleGoal = (goal: string) => {
    if (learningGoals.includes(goal)) {
      setLearningGoals(learningGoals.filter(g => g !== goal));
    } else {
      setLearningGoals([...learningGoals, goal]);
    }
  };

  const handleRegisterOrLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);

    if (authMode === 'register') {
      if (!displayName.trim()) {
        setAuthError('Please enter your full name.');
        return;
      }
      if (password.length < 6) {
        setAuthError('Password must be at least 6 characters long.');
        return;
      }
      if (password !== confirmPassword) {
        setAuthError('Passwords do not match. Please verify your confirm password.');
        return;
      }
      if (role === 'student' && (grade === '' || !boardId || !preferredLanguage)) {
        setAuthError('Choose your class, board, and language first.');
        return;
      }
      if (role === 'student' && (taxonomy.error || taxonomyEmpty)) {
        setAuthError(taxonomy.error || 'Reference data is unavailable. Try again in a moment.');
        return;
      }

      setIsSubmitting(true);
      try {
        const created = await signup({
          email: email.trim(),
          password,
          displayName: displayName.trim(),
          role,
          grade: role === 'student' ? Number(grade) : undefined,
          boardId: role === 'student' ? boardId : undefined,
          preferredLanguage: role === 'student' ? preferredLanguage : undefined,
        });
        if (created.role === 'teacher') {
          await updateProfile({ onboardingCompleted: true, tourCompleted: true });
          onClose();
        } else {
          setStep(3);
        }
      } catch (err: any) {
        setAuthError(err.message || 'Registration failed. Please check your details.');
      } finally {
        setIsSubmitting(false);
      }
    } else {
      // Sign-in mode
      setIsSubmitting(true);
      try {
        await login(email.trim(), password);
        onClose();
      } catch (err: any) {
        setAuthError(err.message || 'Sign in failed. Please check your credentials.');
      } finally {
        setIsSubmitting(false);
      }
    }
  };

  const handleFinishPreferences = async () => {
    setPreferencesError(null);
    if (!user) {
      onClose();
      return;
    }
    const isStudent = user.role !== 'teacher';
    if (isStudent && (grade === '' || !boardId || !preferredLanguage)) {
      setPreferencesError('Choose your class, board, and language before finishing setup.');
      return;
    }
    setIsSubmitting(true);
    try {
      const updates: Partial<UserProfileData> = {
        onboardingCompleted: true,
        tourCompleted: true,
        learningGoals,
      };
      if (isStudent) {
        updates.grade = Number(grade);
        updates.boardId = boardId;
        updates.preferredLanguage = preferredLanguage;
        updates.subjectsInterested = selectedSubjects;
      }
      if (pace) {
        updates.accessibilityPreferences = {
          ...(user.accessibilityPreferences || {}),
          pace,
        };
      }
      if (dailyMinutes !== '') updates.dailyGoalMinutes = Number(dailyMinutes);
      await updateProfile(updates);
      onClose();
    } catch (err: unknown) {
      setPreferencesError(
        err instanceof Error ? err.message : 'SETU could not save your setup. Try again.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    onClose();
  };

  const handleAcademicContinue = () => {
    setPreferencesError(null);
    if (grade === '' || !boardId || !preferredLanguage) {
      setPreferencesError('Choose your class, board, and language before continuing.');
      return;
    }
    setStep(3);
  };

  return (
    <div className={styles.backdrop} role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
      <div className={styles.modal}>
        <div className={styles.header}>
          <span className={styles.brandBadge}>Getting Started with SETU</span>
          <button
            className={styles.closeButton}
            onClick={handleClose}
            aria-label="Close getting started"
          >
            ×
          </button>
        </div>

        <div className={styles.body}>
          {/* Step Indicator */}
          <div className={styles.stepIndicator}>
            <div className={`${styles.stepBar} ${step >= 0 ? styles.stepBarActive : ''}`} />
            <div className={`${styles.stepBar} ${step >= 1 ? styles.stepBarActive : ''}`} />
            <div className={`${styles.stepBar} ${step >= 2 ? styles.stepBarActive : ''}`} />
            <div className={`${styles.stepBar} ${step >= 3 ? styles.stepBarActive : ''}`} />
          </div>

          {/* STEP 0: Introduction */}
          {step === 0 && (
            <div>
              <h2 id="onboarding-title" className={styles.title}>
                Welcome to SETU
              </h2>
              <p className={styles.subtitle}>
                The purpose-built, source-grounded adaptive learning desk for school students. Learn concepts directly from the sources you add, ask doubts with page citations, and study offline anytime.
              </p>
              <div className={styles.featureList}>
                <div className={styles.featureCard}>
                  <div className={styles.featureIcon}>📖</div>
                  <div>
                    <div className={styles.featureTitle}>Source-Grounded Learning</div>
                    <div className={styles.featureText}>
                      Every explanation and citation is checked against the document you upload. If the source does not contain enough evidence, SETU says so instead of inventing an answer.
                    </div>
                  </div>
                </div>
                <div className={styles.featureCard}>
                  <div className={styles.featureIcon}>⚡</div>
                  <div>
                    <div className={styles.featureTitle}>Learn · Solve · Test Flow</div>
                    <div className={styles.featureText}>
                      Step through source-grounded concepts, practice with progressive hints, and prove genuine mastery through checkpoint tests.
                    </div>
                  </div>
                </div>
                <div className={styles.featureCard}>
                  <div className={styles.featureIcon}>📡</div>
                  <div>
                    <div className={styles.featureTitle}>Durable Offline Capability</div>
                    <div className={styles.featureText}>
                      Download lesson packages to IndexedDB. Queue doubts while offline, and automatically sync answers when back online.
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* STEP 1: How SETU Works */}
          {step === 1 && (
            <div>
              <h2 id="onboarding-title" className={styles.title}>
                How SETU Works
              </h2>
              <p className={styles.subtitle}>
                Built for Indian school curriculum standards.
              </p>

              <div className={styles.featureList}>
                <div className={styles.featureCard}>
                  <div className={styles.featureIcon}>1️⃣</div>
                  <div>
                    <div className={styles.featureTitle}>Ingestion & Outline Review</div>
                    <div className={styles.featureText}>
                      Upload full textbooks up to 50MB and 300–500 pages. The worker extracts text with optical character recognition for scanned pages, generates chapter outlines, and builds vector embeddings.
                    </div>
                  </div>
                </div>

                <div className={styles.featureCard}>
                  <div className={styles.featureIcon}>2️⃣</div>
                  <div>
                    <div className={styles.featureTitle}>Adaptive Difficulty & Diagnostic Evidence</div>
                    <div className={styles.featureText}>
                      Your responses generate an evidence profile. As you master concepts, SETU advances difficulty or provides targeted remediation for misconceptions.
                    </div>
                  </div>
                </div>

                <div className={styles.featureCard}>
                  <div className={styles.featureIcon}>3️⃣</div>
                  <div>
                    <div className={styles.featureTitle}>Teacher Evidence Matrix</div>
                    <div className={styles.featureText}>
                      Teachers create classrooms with unique Join Codes, monitoring real student concept demonstration bands (Developing, Approaching, Demonstrated).
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: Registration / Account Creation or Profile Details */}
          {step === 2 && !user && (
            <div>
              <h2 id="onboarding-title" className={styles.title}>
                {authMode === 'register' ? 'Create Your SETU Account' : 'Sign in to Your Account'}
              </h2>
              <p className={styles.subtitle}>
                {authMode === 'register'
                  ? 'Join SETU to start your personalized, source-grounded learning journey.'
                  : 'Enter your credentials to return to your Learning Desk.'}
              </p>

              {authError && <div className={styles.errorBanner}>{authError}</div>}

              <form onSubmit={handleRegisterOrLogin}>
                {authMode === 'register' && (
                  <>
                    <div className={styles.fieldGroup}>
                      <label className={styles.label} htmlFor="tour-reg-name">
                        Full Name
                      </label>
                      <input
                        id="tour-reg-name"
                        type="text"
                        required
                        className={styles.input}
                        value={displayName}
                        onChange={e => setDisplayName(e.target.value)}
                        placeholder="e.g. Aarav Sharma"
                      />
                    </div>

                    <div className={styles.formGrid}>
                      <div className={styles.fieldGroup}>
                        <label className={styles.label} htmlFor="tour-reg-role">
                          Role
                        </label>
                        <select
                          id="tour-reg-role"
                          className={styles.select}
                          value={role}
                          onChange={e => setRole(e.target.value as any)}
                        >
                          <option value="student">Student</option>
                          <option value="teacher">Teacher / Educator</option>
                        </select>
                      </div>

                      {role === 'student' && (
                        <div className={styles.fieldGroup}>
                          <label className={styles.label} htmlFor="tour-reg-grade">
                            Class / Grade
                          </label>
                          <select
                            id="tour-reg-grade"
                            className={styles.select}
                            required
                            value={grade}
                            onChange={e => setGrade(e.target.value === '' ? '' : Number(e.target.value))}
                          >
                            <option value="">Select class</option>
                            {GRADES.map((value) => (
                              <option key={value} value={value}>{gradeLabel(value)}</option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>

                    {role === 'student' && (
                      <>
                        {taxonomy.loading && (
                          <p className={styles.taxonomyStatus}>Loading boards, subjects, and languages…</p>
                        )}
                        {taxonomy.error && (
                          <p className={styles.taxonomyError} role="alert">
                            {taxonomy.error}{' '}
                            <button
                              type="button"
                              className={styles.inlineRetry}
                              onClick={taxonomy.retry}
                            >
                              Retry
                            </button>
                          </p>
                        )}
                        {taxonomyEmpty && (
                          <p className={styles.taxonomyError} role="alert">
                            No reference data is available. Ask an administrator to add boards,
                            subjects, and languages.
                          </p>
                        )}
                        <div className={styles.formGrid}>
                          <div className={styles.fieldGroup}>
                            <label className={styles.label} htmlFor="tour-reg-board">
                              Curriculum Board
                            </label>
                            <select
                              id="tour-reg-board"
                              className={styles.select}
                              required
                              value={boardId}
                              onChange={e => setBoardId(e.target.value)}
                              disabled={taxonomy.loading || Boolean(taxonomy.error)}
                            >
                              <option value="">Select a board</option>
                              {taxonomy.boards.map((board) => (
                                <option key={board.id} value={board.id}>
                                  {board.name}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div className={styles.fieldGroup}>
                            <label className={styles.label} htmlFor="tour-reg-lang">
                              Language
                            </label>
                            <select
                              id="tour-reg-lang"
                              className={styles.select}
                              required
                              value={preferredLanguage}
                              onChange={e => setPreferredLanguage(e.target.value)}
                              disabled={taxonomy.loading || Boolean(taxonomy.error)}
                            >
                              <option value="">Select a language</option>
                              {taxonomy.languages.map((language) => (
                                <option key={language.id} value={language.bcp47Tag}>
                                  {language.nativeName}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>
                      </>
                    )}
                  </>
                )}

                <div className={styles.fieldGroup}>
                  <label className={styles.label} htmlFor="tour-reg-email">
                    Email Address
                  </label>
                  <input
                    id="tour-reg-email"
                    type="email"
                    required
                    className={styles.input}
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="name@example.com"
                  />
                </div>

                <div className={styles.fieldGroup}>
                  <label className={styles.label} htmlFor="tour-reg-password">
                    Password {authMode === 'register' ? '(minimum 6 characters)' : ''}
                  </label>
                  <input
                    id="tour-reg-password"
                    type="password"
                    required
                    minLength={6}
                    className={styles.input}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    placeholder="••••••••"
                  />
                </div>

                {authMode === 'register' && (
                  <div className={styles.fieldGroup}>
                    <label className={styles.label} htmlFor="tour-reg-confirm-password">
                      Confirm Password
                    </label>
                    <input
                      id="tour-reg-confirm-password"
                      type="password"
                      required
                      minLength={6}
                      className={styles.input}
                      value={confirmPassword}
                      onChange={e => setConfirmPassword(e.target.value)}
                      placeholder="••••••••"
                    />
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className={styles.nextButton}
                  style={{ width: '100%', marginTop: '0.75rem', padding: '0.75rem' }}
                >
                  {isSubmitting
                    ? 'Processing...'
                    : authMode === 'register'
                    ? 'Create SETU Account'
                    : 'Sign in to Desk'}
                </button>

                <div className={styles.switchLinkRow}>
                  {authMode === 'register' ? (
                    <>
                      <span>Already have an account?</span>
                      <button
                        type="button"
                        className={styles.inlineLinkButton}
                        onClick={() => { setAuthMode('signin'); setAuthError(null); }}
                      >
                        Sign in here
                      </button>
                    </>
                  ) : (
                    <>
                      <span>Need a new account?</span>
                      <button
                        type="button"
                        className={styles.inlineLinkButton}
                        onClick={() => { setAuthMode('register'); setAuthError(null); }}
                      >
                        Register here
                      </button>
                    </>
                  )}
                </div>
              </form>
            </div>
          )}

          {/* STEP 2 for already logged-in user: Academic context */}
          {step === 2 && user && user.role !== 'teacher' && (
            <div>
              <h2 id="onboarding-title" className={styles.title}>
                Academic Context
              </h2>
              <p className={styles.subtitle}>
                Customise your Desk to your curriculum, board, and learning language.
              </p>
              {taxonomy.loading && (
                <p className={styles.taxonomyStatus}>Loading boards, subjects, and languages…</p>
              )}
              {taxonomy.error && (
                <p className={styles.taxonomyError} role="alert">
                  {taxonomy.error}{' '}
                  <button type="button" className={styles.inlineRetry} onClick={taxonomy.retry}>
                    Retry
                  </button>
                </p>
              )}
              {taxonomyEmpty && (
                <p className={styles.taxonomyError} role="alert">
                  No reference data is available. Ask an administrator to add boards, subjects,
                  and languages.
                </p>
              )}
              {preferencesError && (
                <p className={styles.errorBanner} role="alert">
                  {preferencesError}
                </p>
              )}
              <div className={styles.formGrid}>
                <div className={styles.fieldGroup}>
                  <label className={styles.label} htmlFor="grade-select">
                    Class / Grade
                  </label>
                  <select
                    id="grade-select"
                    className={styles.select}
                    required
                    value={grade}
                    onChange={e => setGrade(e.target.value === '' ? '' : Number(e.target.value))}
                  >
                    <option value="">Select class</option>
                    {GRADES.map((value) => (
                      <option key={value} value={value}>{gradeLabel(value)}</option>
                    ))}
                  </select>
                </div>

                <div className={styles.fieldGroup}>
                  <label className={styles.label} htmlFor="board-select">
                    Curriculum Board
                  </label>
                  <select
                    id="board-select"
                    className={styles.select}
                    required
                    value={boardId}
                    onChange={e => setBoardId(e.target.value)}
                    disabled={taxonomy.loading || Boolean(taxonomy.error)}
                  >
                    <option value="">Select a board</option>
                    {taxonomy.boards.map((board) => (
                      <option key={board.id} value={board.id}>
                        {board.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className={styles.fieldGroup}>
                <label className={styles.label} htmlFor="lang-select">
                  Instruction & Reading Language
                </label>
                <select
                  id="lang-select"
                  className={styles.select}
                  required
                  value={preferredLanguage}
                  onChange={e => setPreferredLanguage(e.target.value)}
                  disabled={taxonomy.loading || Boolean(taxonomy.error)}
                >
                  <option value="">Select a language</option>
                  {taxonomy.languages.map((language) => (
                    <option key={language.id} value={language.bcp47Tag}>
                      {language.nativeName}
                    </option>
                  ))}
                </select>
              </div>

              <div className={styles.fieldGroup}>
                <label className={styles.label}>Subjects You Focus On</label>
                <div className={styles.chipGroup}>
                  {taxonomy.subjects.map((subject) => (
                    <button
                      key={subject.id}
                      type="button"
                      className={`${styles.chip} ${selectedSubjects.includes(subject.id) ? styles.chipSelected : ''}`}
                      onClick={() => toggleSubject(subject.id)}
                    >
                      {selectedSubjects.includes(subject.id) ? '✓ ' : '+ '}
                      {subject.canonicalName}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {step === 2 && user && user.role === 'teacher' && (
            <div>
              <h2 id="onboarding-title" className={styles.title}>
                Ready to teach
              </h2>
              <p className={styles.subtitle}>
                Teacher accounts skip academic and study-habit setup. Finish to open your classroom
                dashboard.
              </p>
              {preferencesError && (
                <p className={styles.errorBanner} role="alert">
                  {preferencesError}
                </p>
              )}
            </div>
          )}

          {/* STEP 3: Study Habits & Enter Desk */}
          {step === 3 && (
            <div>
              <h2 id="onboarding-title" className={styles.title}>
                Study Habits & Goals
              </h2>
              <p className={styles.subtitle}>
                Set realistic daily commitments. Your learning pace adapts according to your evidence.
              </p>
              {preferencesError && (
                <p className={styles.errorBanner} role="alert">
                  {preferencesError}
                </p>
              )}

              <div className={styles.fieldGroup}>
                <label className={styles.label}>How do you want to pace your study?</label>
                <div className={styles.chipGroup}>
                  {[
                    { id: 'short' as const, label: 'Short sessions (15m)' },
                    { id: 'steady' as const, label: 'Steady pace (30m)' },
                    { id: 'long' as const, label: 'Longer sessions (45m)' },
                  ].map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      className={`${styles.chip} ${pace === option.id ? styles.chipSelected : ''}`}
                      onClick={() => setPace(pace === option.id ? '' : option.id)}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className={styles.fieldGroup}>
                <label className={styles.label}>Daily Study Commitment</label>
                <div className={styles.chipGroup}>
                  {[15, 30, 45, 60].map(mins => (
                    <button
                      key={mins}
                      type="button"
                      className={`${styles.chip} ${dailyMinutes === mins ? styles.chipSelected : ''}`}
                      onClick={() => setDailyMinutes(dailyMinutes === mins ? '' : mins)}
                    >
                      {mins} minutes / day
                    </button>
                  ))}
                </div>
              </div>

              <div className={styles.fieldGroup}>
                <label className={styles.label}>Primary Learning Goals</label>
                <div className={styles.chipGroup}>
                  {[
                    'Concept Mastery',
                    'Board Exam Preparation',
                    'NCERT Chapter Revisions',
                    'Doubt Resolution',
                    'Self-Paced Practice'
                  ].map(goal => (
                    <button
                      key={goal}
                      type="button"
                      className={`${styles.chip} ${learningGoals.includes(goal) ? styles.chipSelected : ''}`}
                      onClick={() => toggleGoal(goal)}
                    >
                      {learningGoals.includes(goal) ? '✓ ' : '+ '}
                      {goal}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer controls: Back / Continue / Skip */}
        <div className={styles.footer}>
          {user ? (
            <button className={styles.skipButton} onClick={handleClose} type="button">
              Skip for now
            </button>
          ) : (
            <div />
          )}

          <div className={styles.actionButtons}>
            {step > 0 && (
              <button
                className={styles.backButton}
                onClick={() => setStep(step - 1)}
                type="button"
              >
                Back
              </button>
            )}

            {step < 2 ? (
              <button
                className={styles.nextButton}
                onClick={() => setStep(step + 1)}
                type="button"
              >
                {step === 1 && !user ? 'Continue to Registration →' : 'Continue'}
              </button>
            ) : step === 2 && user?.role === 'teacher' ? (
              <button
                className={styles.nextButton}
                onClick={handleFinishPreferences}
                disabled={isSubmitting}
                type="button"
              >
                {isSubmitting ? 'Saving...' : 'Finish setup'}
              </button>
            ) : step === 2 && user ? (
              <button
                className={styles.nextButton}
                onClick={handleAcademicContinue}
                type="button"
              >
                Continue
              </button>
            ) : step === 3 ? (
              <button
                className={styles.nextButton}
                onClick={handleFinishPreferences}
                disabled={isSubmitting}
                type="button"
              >
                {isSubmitting ? 'Saving...' : 'Enter SETU Desk'}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
};
