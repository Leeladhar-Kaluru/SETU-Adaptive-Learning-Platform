import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Navigation } from './components/Navigation';
import { HomePage } from './pages/HomePage';
import { LessonReaderPage } from './pages/LessonReaderPage';
import { OfflineLibraryPage } from './pages/OfflineLibraryPage';
import { DoubtQueuePage } from './pages/DoubtQueuePage';
import { TeacherDashboardPage } from './pages/TeacherDashboardPage';

export const App: React.FC = () => {
  return (
    <>
      <Navigation />
      <main style={{ flex: 1 }}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/lesson/:lessonId" element={<LessonReaderPage />} />
          <Route path="/library" element={<OfflineLibraryPage />} />
          <Route path="/doubts" element={<DoubtQueuePage />} />
          <Route path="/teacher" element={<TeacherDashboardPage />} />
        </Routes>
      </main>
    </>
  );
};

export default App;
