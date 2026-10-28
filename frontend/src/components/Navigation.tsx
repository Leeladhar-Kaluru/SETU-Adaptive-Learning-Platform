import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { syncManager } from '../services/syncManager';
import styles from './Navigation.module.css';

export const Navigation: React.FC = () => {
  const [isOnline, setIsOnline] = useState(typeof navigator !== 'undefined' ? navigator.onLine : true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

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

  const handleManualSync = () => {
    syncManager.syncPendingData();
  };

  return (
    <header className={styles.navBar}>
      <div className={styles.leftSection}>
        <NavLink to="/" className={styles.brand}>
          <div className={styles.brandLogo}>S</div>
          <span className={styles.brandName}>SETU</span>
        </NavLink>

        <nav className={styles.navLinks}>
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              isActive ? `${styles.navLink} ${styles.navLinkActive}` : styles.navLink
            }
          >
            Desk
          </NavLink>
          <NavLink
            to="/library"
            className={({ isActive }) =>
              isActive ? `${styles.navLink} ${styles.navLinkActive}` : styles.navLink
            }
          >
            Offline Library
          </NavLink>
          <NavLink
            to="/doubts"
            className={({ isActive }) =>
              isActive ? `${styles.navLink} ${styles.navLinkActive}` : styles.navLink
            }
          >
            Doubt Queue {pendingCount > 0 && `(${pendingCount})`}
          </NavLink>
          <NavLink
            to="/teacher"
            className={({ isActive }) =>
              isActive ? `${styles.navLink} ${styles.navLinkActive}` : styles.navLink
            }
          >
            Teacher Desk
          </NavLink>
        </nav>
      </div>

      <div className={styles.rightSection}>
        {pendingCount > 0 && isOnline && (
          <button
            onClick={handleManualSync}
            disabled={isSyncing}
            className={styles.syncButton}
            title="Click to sync pending attempts and doubts now"
          >
            {isSyncing ? 'Syncing...' : `Sync Queue (${pendingCount})`}
          </button>
        )}

        <div className={`${styles.badge} ${isOnline ? styles.badgeOnline : styles.badgeOffline}`}>
          <span className={styles.dot} />
          {isOnline ? 'Online' : 'Offline Ready'}
        </div>
      </div>
    </header>
  );
};
