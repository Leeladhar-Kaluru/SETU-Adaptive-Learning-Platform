import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  AlertTriangle,
  BookOpen,
  Download,
  GraduationCap,
  Home,
  LayoutDashboard,
  MessageCircleQuestion,
  Sparkles,
} from 'lucide-react';
import { syncManager } from '../services/syncManager';
import { useAuth } from '../context/AuthContext';
import { AuthModal } from './AuthModal';
import { api } from '../services/api';
import styles from './Navigation.module.css';

const initialsFor = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'S';

export const Navigation: React.FC = () => {
  const { user, logout, openTour } = useAuth();
  const [isOnline, setIsOnline] = useState(typeof navigator !== 'undefined' ? navigator.onLine : true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [lastSyncError, setLastSyncError] = useState<string | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [lessonHref, setLessonHref] = useState('/');

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    const unsubscribe = syncManager.subscribe((syncing, count, lastError) => {
      setIsSyncing(syncing);
      setPendingCount(count);
      setLastSyncError(lastError);
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
        <NavLink to={user?.role === 'teacher' ? '/teacher' : '/'} className={styles.brand} title="SETU home">
          <span className={styles.brandMark} aria-hidden="true">
            <img src="/setu-logo.svg" alt="" width={34} height={34} />
          </span>
          <span className={styles.brandText}>
            <span className={styles.brandName}>SETU</span>
            <span className={styles.brandTag}>Learning desk</span>
          </span>
        </NavLink>

        <nav className={styles.navLinks} aria-label="Primary">
          <span className={styles.navLabel} aria-hidden="true">Your desk</span>
          {!user ? (
            <NavLink to="/" end className={linkClass}>
              <Home size={16} aria-hidden="true" /> Home
            </NavLink>
          ) : user.role === 'teacher' ? (
            <NavLink to="/teacher" className={linkClass}>
              <GraduationCap size={16} aria-hidden="true" /> Classroom
            </NavLink>
          ) : (
            <>
              <NavLink to="/" end className={linkClass}>
                <Home size={16} aria-hidden="true" /> Home
              </NavLink>
              <NavLink to="/dashboard" className={linkClass}>
                <LayoutDashboard size={16} aria-hidden="true" /> Dashboard
              </NavLink>
              {lessonHref !== '/' && (
                <NavLink to={lessonHref} className={linkClass}>
                  <BookOpen size={16} aria-hidden="true" /> Lesson
                </NavLink>
              )}
              {user.canTeach && (
                <NavLink to="/teacher" className={linkClass}>
                  <GraduationCap size={16} aria-hidden="true" /> Classroom
                </NavLink>
              )}
              <NavLink to="/doubts" className={linkClass}>
                <MessageCircleQuestion size={16} aria-hidden="true" /> Doubts
                {pendingCount > 0 ? <span className={styles.countBadge}>{pendingCount}</span> : null}
              </NavLink>
              <NavLink to="/library" className={linkClass}>
                <Download size={16} aria-hidden="true" /> Downloads
              </NavLink>
            </>
          )}
        </nav>

        <div className={styles.sidebarFoot}>
          <div
            className={`${styles.badge} ${isOnline ? styles.badgeOnline : styles.badgeOffline}`}
            title={
              isOnline
                ? 'Connected'
                : 'Offline. Work is saved on this device and syncs when you reconnect.'
            }
          >
            <span className={styles.dot} />
            {isOnline ? 'Online' : 'Offline'}
          </div>
          {pendingCount > 0 && isOnline && (
            <button
              type="button"
              className={`${styles.syncButton} ${lastSyncError ? styles.syncButtonError : ''}`}
              onClick={() => void syncManager.syncPendingData()}
              disabled={isSyncing}
            >
              {lastSyncError ? <AlertTriangle size={14} aria-hidden="true" /> : null}
              {isSyncing ? 'Syncing…' : lastSyncError ? 'Last sync failed — Retry' : 'Sync now'}
            </button>
          )}
          <button type="button" className={styles.tourTriggerButton} onClick={openTour}>
            <Sparkles size={14} aria-hidden="true" />
            {user ? 'How SETU works' : 'Get started'}
          </button>
          {user ? (
            <div className={styles.userBlock}>
              <span className={styles.avatar} aria-hidden="true">{initialsFor(user.displayName)}</span>
              <span className={styles.userCopy}>
                <span className={styles.userName}>{user.displayName}</span>
                <span className={styles.userRoleBadge}>{user.role === 'teacher' ? 'Teacher' : 'Student'}</span>
              </span>
              <button type="button" className={styles.logoutBtn} onClick={() => void logout()}>
                Sign out
              </button>
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
