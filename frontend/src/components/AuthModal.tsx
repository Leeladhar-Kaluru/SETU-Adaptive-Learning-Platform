import React, { useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTaxonomy } from '../hooks/useTaxonomy';
import { useDialogFocus } from '../hooks/useDialogFocus';
import { GRADES, gradeLabel } from '../lib/academic';
import styles from './AuthModal.module.css';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const { login, signup } = useAuth();
  const [tab, setTab] = useState<'login' | 'signup'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState<'student' | 'teacher'>('student');
  const [grade, setGrade] = useState<number | ''>('');
  const [boardId, setBoardId] = useState('');
  const [preferredLanguage, setPreferredLanguage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const taxonomy = useTaxonomy(isOpen && tab === 'signup' && role === 'student');
  const modalRef = useRef<HTMLDivElement>(null);
  useDialogFocus(modalRef, isOpen, onClose);

  if (!isOpen) return null;

  const taxonomyEmpty =
    role === 'student' &&
    !taxonomy.loading &&
    !taxonomy.error &&
    (taxonomy.boards.length === 0 || taxonomy.languages.length === 0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (tab === 'signup') {
      if (password.length < 6) {
        setError('Password must be at least 6 characters long.');
        return;
      }
      if (password !== confirmPassword) {
        setError('Passwords do not match. Please check and try again.');
        return;
      }
      if (role === 'student' && (grade === '' || !boardId || !preferredLanguage)) {
        setError('Choose your class, board, and language first.');
        return;
      }
      if (role === 'student' && (taxonomy.error || taxonomyEmpty)) {
        setError(taxonomy.error || 'Reference data is unavailable. Try again in a moment.');
        return;
      }
    }

    setIsSubmitting(true);

    try {
      if (tab === 'login') {
        await login(email, password);
      } else {
        await signup({
          email,
          password,
          displayName,
          role,
          grade: role === 'student' ? Number(grade) : undefined,
          boardId: role === 'student' ? boardId : undefined,
          preferredLanguage: role === 'student' ? preferredLanguage : undefined,
        });
      }
      onClose();
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please check credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className={styles.backdrop} role="dialog" aria-modal="true" aria-labelledby="auth-modal-title">
      <div className={styles.modal} ref={modalRef} tabIndex={-1}>
        <div className={styles.header}>
          <h2 id="auth-modal-title" className={styles.title}>
            {tab === 'login' ? 'Sign in to SETU' : 'Create SETU Account'}
          </h2>
          <button type="button" className={styles.closeButton} onClick={onClose} aria-label="Close dialog">
            ×
          </button>
        </div>

        <div className={styles.body}>
          <div className={styles.tabGroup}>
            <button
              type="button"
              className={`${styles.tab} ${tab === 'login' ? styles.tabActive : ''}`}
              onClick={() => { setTab('login'); setError(null); }}
            >
              Sign In
            </button>
            <button
              type="button"
              className={`${styles.tab} ${tab === 'signup' ? styles.tabActive : ''}`}
              onClick={() => { setTab('signup'); setError(null); }}
            >
              Register
            </button>
          </div>

          {error && <div className={styles.errorBanner}>{error}</div>}

          <form onSubmit={handleSubmit}>
            {tab === 'signup' && (
              <>
                <div className={styles.fieldGroup}>
                  <label className={styles.label} htmlFor="auth-name">
                    Full Name
                  </label>
                  <input
                    id="auth-name"
                    type="text"
                    required
                    className={styles.input}
                    value={displayName}
                    onChange={e => setDisplayName(e.target.value)}
                    placeholder="e.g. Aarav Sharma"
                  />
                </div>

                <div className={styles.fieldGroup}>
                  <label className={styles.label} htmlFor="auth-role">
                    Role
                  </label>
                  <select
                    id="auth-role"
                    className={styles.select}
                    value={role}
                    onChange={e => setRole(e.target.value as any)}
                  >
                    <option value="student">Student</option>
                    <option value="teacher">Teacher / Educator</option>
                  </select>
                </div>

                {role === 'student' && (
                  <>
                    {taxonomy.loading && (
                      <p className={styles.taxonomyStatus}>Loading boards and languages…</p>
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
                        No boards are available. Ask an administrator to add reference data.
                      </p>
                    )}
                    <div className={styles.fieldGroup}>
                      <label className={styles.label} htmlFor="auth-grade">
                        Class / Grade
                      </label>
                      <select
                        id="auth-grade"
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
                      <label className={styles.label} htmlFor="auth-board">
                        Board
                      </label>
                      <select
                        id="auth-board"
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
                      <label className={styles.label} htmlFor="auth-language">
                        Language
                      </label>
                      <select
                        id="auth-language"
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
                  </>
                )}
              </>
            )}

            <div className={styles.fieldGroup}>
              <label className={styles.label} htmlFor="auth-email">
                Email Address
              </label>
              <input
                id="auth-email"
                type="email"
                required
                className={styles.input}
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="name@example.com"
              />
            </div>

            <div className={styles.fieldGroup}>
              <label className={styles.label} htmlFor="auth-password">
                Password
              </label>
              <input
                id="auth-password"
                type="password"
                required
                minLength={6}
                className={styles.input}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>

            {tab === 'signup' && (
              <div className={styles.fieldGroup}>
                <label className={styles.label} htmlFor="auth-confirm-password">
                  Confirm Password
                </label>
                <input
                  id="auth-confirm-password"
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
              className={styles.submitButton}
            >
              {isSubmitting
                ? 'Processing...'
                : tab === 'login'
                ? 'Sign In to Desk'
                : 'Create Account & Continue'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
