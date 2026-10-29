import React, { ReactNode, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { AuthModal } from './AuthModal';
import styles from './AuthGate.module.css';

interface AuthGateProps {
  children: ReactNode;
  teacherOnly?: boolean;
}

export const AuthGate: React.FC<AuthGateProps> = ({ children, teacherOnly = false }) => {
  const { user, isLoading } = useAuth();
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  if (isLoading) return <p className={styles.loading}>Loading SETU…</p>;

  if (!user) {
    return (
      <section className={styles.page}>
        <h1>Your learning desk</h1>
        <p className={styles.lede}>Sign in to open your lessons, progress, and doubts.</p>
        <button type="button" className={styles.primary} onClick={() => setIsAuthOpen(true)}>
          Sign in or create an account
        </button>
        <AuthModal isOpen={isAuthOpen} onClose={() => setIsAuthOpen(false)} />
      </section>
    );
  }

  if (teacherOnly && user.role !== 'teacher') {
    return (
      <section className={styles.page}>
        <h1>Teacher account required</h1>
        <p className={styles.lede}>
          This page shows classroom evidence. Sign in with a teacher account to continue.
        </p>
      </section>
    );
  }

  return <>{children}</>;
};
