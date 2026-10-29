import { test, expect } from '@playwright/test';

test('teacher sees scoped evidence and sends an explained recommendation', async ({ page }) => {
  const teacher = {
    id: '66666666-6666-4666-8666-666666666666',
    email: 'teacher@example.com',
    role: 'teacher',
    displayName: 'Teacher Rao',
    onboardingCompleted: true,
    tourCompleted: true,
  };
  const room = {
    id: '77777777-7777-4777-8777-777777777777',
    name: 'Morning Science',
    grade: 9,
    boardId: 'board-cbse',
    subjectScope: 'subject-science',
    joinCode: 'ABC123',
    memberCount: 1,
    createdAt: '2026-10-01T00:00:00',
  };
  const row = {
    studentId: '55555555-5555-4555-8555-555555555555',
    studentName: 'Asha',
    concepts: [
      {
        conceptId: 'concept-cell',
        band: 'approaching',
        score: 64,
        evidenceCount: 2,
        calculatedAt: '2026-10-27T10:00:00',
      },
    ],
    conceptsDemonstrated: 0,
    totalConcepts: 1,
    accuracyRate: 0.5,
    accuracyKnown: true,
    recentAttemptsCount: 2,
    evidenceBand: 'approaching',
    lastActive: '2026-10-27',
    minutesStudied: 12,
    readingTitle: 'Cells',
    improvement: 'steady',
    heatmap: [],
    focus: 'Review cells.',
  };
  const sent: any[] = [];

  await page.addInitScript(() => localStorage.setItem('setu_auth_token', 'e2e-token'));
  await page.route(/\/api\/v1\/profile$/, (route) => route.fulfill({ json: teacher }));
  await page.route('**/api/v1/teacher/classrooms', (route) => route.fulfill({ json: [room] }));
  await page.route(`**/api/v1/teacher/classrooms/${room.id}/evidence-matrix`, (route) => {
    return route.fulfill({
      json: {
        classroomId: room.id,
        totalStudents: 1,
        matrix: [row],
        actions: [],
      },
    });
  });
  await page.route('**/api/v1/teacher/recommendations', async (route) => {
    sent.push(route.request().postDataJSON());
    await route.fulfill({
      json: {
        id: '88888888-8888-4888-8888-888888888888',
        status: 'proposed',
        actionType: 'targeted_review',
        conceptId: 'concept-cell',
        notes: 'Review the worked example.',
        reason: { evidence: row.concepts[0] },
      },
    });
  });
  await page.route('**/api/v1/learning-paths', (route) => route.fulfill({ json: [] }));

  await page.goto('/teacher');
  await expect(page.getByText('Morning Science').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Asha' })).toBeVisible();
  await expect(page.getByText('Approaching', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: /Asha/ }).click();
  await page.getByLabel('Topic').selectOption('concept-cell');
  await expect(page.getByText(/Based on approaching evidence/)).toBeVisible();
  await page.getByLabel('Note').fill('Review the worked example.');
  await page.getByRole('button', { name: /Send suggestion/ }).click();

  await expect.poll(() => sent.length).toBe(1);
  expect(sent[0].conceptId).toBe('concept-cell');
  expect(sent[0].notes).toBe('Review the worked example.');
  await expect(page.getByText('Suggestion sent to that student.')).toBeVisible();
  await expect(page.getByText('Proposed', { exact: true })).toBeVisible();
});

test('a teacher cannot send a suggestion without an evidenced topic', async ({ page }) => {
  const teacher = {
    id: '66666666-6666-4666-8666-666666666666',
    email: 'teacher@example.com',
    role: 'teacher',
    displayName: 'Teacher Rao',
    onboardingCompleted: true,
    tourCompleted: true,
  };
  const room = {
    id: '77777777-7777-4777-8777-777777777777',
    name: 'Morning Science',
    grade: 9,
    boardId: 'board-cbse',
    subjectScope: 'subject-science',
    joinCode: 'ABC123',
    memberCount: 1,
    createdAt: '2026-10-01T00:00:00',
  };
  const row = {
    studentId: '55555555-5555-4555-8555-555555555555',
    studentName: 'Asha',
    concepts: [],
    conceptsDemonstrated: 0,
    totalConcepts: 0,
    accuracyRate: 0,
    accuracyKnown: false,
    recentAttemptsCount: 0,
    evidenceBand: 'not_enough_evidence',
    lastActive: '',
    minutesStudied: 0,
    readingTitle: null,
    improvement: 'not_enough',
    heatmap: [],
  };

  await page.addInitScript(() => localStorage.setItem('setu_auth_token', 'e2e-token'));
  await page.route(/\/api\/v1\/profile$/, (route) => route.fulfill({ json: teacher }));
  await page.route('**/api/v1/teacher/classrooms', (route) => route.fulfill({ json: [room] }));
  await page.route(`**/api/v1/teacher/classrooms/${room.id}/evidence-matrix`, (route) =>
    route.fulfill({ json: { classroomId: room.id, totalStudents: 1, matrix: [row], actions: [] } })
  );
  await page.route('**/api/v1/learning-paths', (route) => route.fulfill({ json: [] }));

  await page.goto('/teacher');
  await expect(page.getByText('Not enough evidence').first()).toBeVisible();
  await expect(page.getByText('No evidenced topics yet.').first()).toBeVisible();

  await page.getByRole('button', { name: /Asha/ }).click();
  await expect(page.getByLabel('Topic')).toBeDisabled();
  await page.getByLabel('Note').fill('Read another unit first.');
  await expect(page.getByRole('button', { name: /Send suggestion/ })).toBeDisabled();
});
