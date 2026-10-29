import { test, expect } from '@playwright/test';

const student = {
  id: '55555555-5555-4555-8555-555555555555',
  email: 'asha@example.com',
  role: 'student',
  displayName: 'Asha',
  grade: null,
  boardId: null,
  preferredLanguage: null,
  dailyGoalMinutes: null,
  onboardingCompleted: true,
  tourCompleted: true,
};

const heatmap = Array.from({ length: 84 }, (_, index) => ({
  date: `2026-08-${String((index % 28) + 1).padStart(2, '0')}`,
  seconds: 0,
  minutes: 0,
  count: 0,
  level: 0,
}));

test('a fresh student sees empty states, not invented class or goal values', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('setu_auth_token', 'e2e-token');
    localStorage.setItem('setu_active_user_id', '55555555-5555-4555-8555-555555555555');
  });
  await page.route(/\/api\/v1\/profile$/, (route) => route.fulfill({ json: student }));
  await page.route('**/api/v1/profile/dashboard', (route) =>
    route.fulfill({
      json: {
        profile: student,
        stats: {
          currentStreak: 0,
          longestStreak: 0,
          totalMinutesStudied: 0,
          totalSessions: 0,
          averageAccuracy: 0,
          totalQuestionsAttempted: 0,
        },
        activityHeatmap: heatmap,
        conceptMastery: [],
        recentAttempts: [],
        classrooms: [],
      },
    })
  );
  await page.route('**/api/v1/catalogue/boards', (route) =>
    route.fulfill({
      json: [{ id: 'board-cbse', code: 'CBSE', name: 'Central Board of Secondary Education' }],
    })
  );

  await page.goto('/dashboard');
  await expect(page.getByText('Add your class, board, and language')).toBeVisible();
  await expect(page.getByText('No study activity yet.')).toBeVisible();
  await expect(page.getByText('No concept mastery evidence yet.')).toBeVisible();
  await expect(page.getByText('No checkpoint attempts yet', { exact: true })).toBeVisible();
  await expect(page.getByText('No checkpoint attempts yet.', { exact: true })).toBeVisible();
  await expect(page.getByText('Registered Student')).toHaveCount(0);
  await expect(page.getByText(/Class 10/)).toHaveCount(0);
  await expect(page.getByText(/25 min\/day/)).toHaveCount(0);
});

test('the board list comes from the API and a failed load disables saving', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('setu_auth_token', 'e2e-token');
    localStorage.setItem('setu_active_user_id', '55555555-5555-4555-8555-555555555555');
  });
  await page.route(/\/api\/v1\/profile$/, (route) => route.fulfill({ json: student }));
  await page.route('**/api/v1/profile/dashboard', (route) =>
    route.fulfill({
      json: {
        profile: student,
        stats: {
          currentStreak: 0,
          longestStreak: 0,
          totalMinutesStudied: 0,
          totalSessions: 0,
          averageAccuracy: 0,
          totalQuestionsAttempted: 0,
        },
        activityHeatmap: heatmap,
        conceptMastery: [],
        recentAttempts: [],
        classrooms: [],
      },
    })
  );
  await page.route('**/api/v1/catalogue/boards', (route) =>
    route.fulfill({ status: 503, json: { detail: 'Catalogue unavailable.' } })
  );

  await page.goto('/dashboard');
  await page.getByRole('button', { name: 'Edit Academic Profile' }).click();
  await expect(page.getByText('Catalogue unavailable.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save Changes' })).toBeDisabled();
  await expect(page.getByRole('option', { name: /CBSE/ })).toHaveCount(0);
});
