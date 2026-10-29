import React, { ReactNode } from 'react';
import { Navigate, Routes, Route } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navigation } from './components/Navigation';
import { OnboardingTour } from './components/OnboardingTour';
import { AuthGate } from './components/AuthGate';
import { HomePage } from './pages/HomePage';
import { LessonReaderPage } from './pages/LessonReaderPage';
import { OfflineLibraryPage } from './pages/OfflineLibraryPage';
import { DoubtQueuePage } from './pages/DoubtQueuePage';
import { TeacherDashboardPage } from './pages/TeacherDashboardPage';
import { StudentDashboardPage } from './pages/StudentDashboardPage';
import { NotFoundPage } from './pages/NotFoundPage';
import styles from './App.module.css';

const StudentOnly: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { user, isLoading } = useAuth();
  if (isLoading) return null;
  if (user?.role === 'teacher') return <Navigate to="/teacher" replace />;
  return <>{children}</>;
};

const AppContent: React.FC = () => {
  const { isTourOpen, closeTour, isLoading } = useAuth();

  return (
    <div className={styles.shell}>
      <Navigation />
      <main className={styles.main}>
        {isLoading ? (
          <p style={{ padding: 32 }}>Loading SETU…</p>
        ) : (
          <Routes>
            <Route path="/" element={<StudentOnly><HomePage /></StudentOnly>} />
            <Route
              path="/dashboard"
              element={
                <AuthGate>
                  <StudentOnly><StudentDashboardPage /></StudentOnly>
                </AuthGate>
              }
            />
            <Route
              path="/lesson/:lessonId"
              element={
                <AuthGate>
                  <StudentOnly><LessonReaderPage /></StudentOnly>
                </AuthGate>
              }
            />
            <Route
              path="/library"
              element={
                <AuthGate>
                  <StudentOnly><OfflineLibraryPage /></StudentOnly>
                </AuthGate>
              }
            />
            <Route
              path="/doubts"
              element={
                <AuthGate>
                  <StudentOnly><DoubtQueuePage /></StudentOnly>
                </AuthGate>
              }
            />
            <Route
              path="/teacher"
              element={
                <AuthGate teacherOnly>
                  <TeacherDashboardPage />
                </AuthGate>
              }
            />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        )}
      </main>
      <OnboardingTour isOpen={isTourOpen} onClose={closeTour} />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;
