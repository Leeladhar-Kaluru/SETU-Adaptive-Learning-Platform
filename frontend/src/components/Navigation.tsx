import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { syncManager } from '../services/syncManager';
import { useAuth } from '../context/AuthContext';
import { AuthModal } from './AuthModal';
import { api } from '../services/api';
import styles from './Navigation.module.css';

export const Navigation: React.FC = () => {
  const { user, logout, openTour } = useAuth();
  const [isOnline, setIsOnline] = useState(typeof navigator !== 'undefined' ? navigator.onLine : true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [lessonHref, setLessonHref] = useState('/');

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    const unsubscribe = syncManager.subscribe((syncing, count) => {
      setIsSyncing(syncing);
      setPendingCount(count);
    });
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    void syncManager.refreshPending();
  }, [user]);

  useEffect(() => {
    if (!user || user.role === 'teacher') {
      setLessonHref('/');
      return;
    }
    let cancelled = false;
    api.getLearningPaths()
      .then((paths) => {
        if (cancelled) return;
        const path = paths[0];
        const ready = path?.lessons?.find((lesson) => lesson.status === 'ready');
        const target = ready?.id || path?.firstLessonId;
        setLessonHref(target ? `/lesson/${target}?pathId=${path.id}` : '/');
      })
      .catch(() => {
        if (!cancelled) setLessonHref('/');
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    isActive ? `${styles.navLink} ${styles.navLinkActive}` : styles.navLink;

  return (
    <>
      <aside className={styles.sidebar}>
        <NavLink to={user?.role === 'teacher' ? '/teacher' : '/'} className={styles.brand}>
          <span className={styles.brandLogo}>S</span>
          <span className={styles.brandName}>SETU</span>
        </NavLink>

        <nav className={styles.navLinks} aria-label="Primary">
          {user?.role === 'teacher' ? (
            <NavLink to="/teacher" className={linkClass}>Classroom</NavLink>
          ) : (
            <>
              <NavLink to="/" end className={linkClass}>Home</NavLink>
              <NavLink to="/dashboard" className={linkClass}>Dashboard</NavLink>
              {lessonHref !== '/' && <NavLink to={lessonHref} className={linkClass}>Lesson</NavLink>}
              <NavLink to="/doubts" className={linkClass}>
                Doubts{pendingCount > 0 ? ` (${pendingCount})` : ''}
              </NavLink>
              <NavLink to="/library" className={linkClass}>Downloads</NavLink>
            </>
          )}
        </nav>

        <div className={styles.sidebarFoot}>
          <div className={`${styles.badge} ${isOnline ? styles.badgeOnline : styles.badgeOffline}`}>
            <span className={styles.dot} />
            {isOnline ? 'Online' : 'Offline'}
          </div>
          {pendingCount > 0 && isOnline && (
            <button type="button" className={styles.syncButton} onClick={() => syncManager.syncPendingData()} disabled={isSyncing}>
              {isSyncing ? 'Syncing' : 'Sync now'}
            </button>
          )}
          <button type="button" className={styles.tourTriggerButton} onClick={openTour}>
            Get Started
          </button>
          {user ? (
            <div className={styles.userBlock}>
              <span className={styles.userName}>{user.displayName}</span>
              <span className={styles.userRoleBadge}>{user.role === 'teacher' ? 'Teacher' : 'Student'}</span>
              <button type="button" className={styles.logoutBtn} onClick={() => void logout()}>Sign out</button>
            </div>
          ) : (
            <button type="button" className={styles.loginBtn} onClick={() => setIsAuthModalOpen(true)}>
              Sign in
            </button>
          )}
        </div>
      </aside>
      <AuthModal isOpen={isAuthModalOpen} onClose={() => setIsAuthModalOpen(false)} />
    </>
  );
};
