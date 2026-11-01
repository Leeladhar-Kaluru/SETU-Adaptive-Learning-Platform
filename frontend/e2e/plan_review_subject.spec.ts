import { test, expect } from '@playwright/test';

const student = {
  id: '55555555-5555-4555-8555-555555555555',
  email: 'asha@example.com',
  role: 'student',
  displayName: 'Asha',
  grade: 10,
  boardId: 'board-cbse',
  preferredLanguage: 'en-IN',
  subjectsInterested: [],
  dailyGoalMinutes: 20,
  onboardingCompleted: true,
  tourCompleted: true,
};

const document = {
  id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  documentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  filename: 'Class 10 Social Science Textbook.pdf',
  status: 'awaiting_review',
  pageCount: 24,
  chunkCount: 40,
};

test('the plan review modal lists catalogue subjects even when onboarding has no interests', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('setu_auth_token', 'e2e-token');
    localStorage.setItem('setu_active_user_id', '55555555-5555-4555-8555-555555555555');
  });

  await page.route(/\/api\/v1\/profile$/, (route) => route.fulfill({ json: student }));
  await page.route('**/api/v1/catalogue/boards', (route) =>
    route.fulfill({ json: [{ id: 'board-cbse', code: 'CBSE', name: 'CBSE', region: 'India' }] })
  );
  await page.route('**/api/v1/catalogue/subjects', (route) =>
    route.fulfill({
      json: [
        { id: 'subject-science', code: 'SCI', canonicalName: 'Science', name: 'Science' },
        { id: 'subject-social', code: 'SOC', canonicalName: 'Social Science', name: 'Social Science' },
        { id: 'subject-math', code: 'MATH', canonicalName: 'Mathematics', name: 'Mathematics' },
      ],
    })
  );
  await page.route('**/api/v1/catalogue/languages', (route) =>
    route.fulfill({ json: [{ id: 'lang-en', bcp47Tag: 'en-IN', nativeName: 'English', script: 'Latn' }] })
  );
  await page.route('**/api/v1/documents', (route) => route.fulfill({ json: [document] }));
  await page.route('**/api/v1/documents/*/status', (route) =>
    route.fulfill({
      json: {
        documentId: document.documentId,
        status: 'awaiting_review',
        filename: document.filename,
        pageCount: document.pageCount,
        chunkCount: document.chunkCount,
        canBuildPath: true,
        chapters: [{ title: 'Chapter 1: Resources', pageStart: 1, pageEnd: 24 }],
      },
    })
  );
  await page.route('**/api/v1/learning-paths', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/v1/study/summary', (route) => route.fulfill({ status: 503, json: { detail: 'offline' } }));
  await page.route('**/api/v1/study/plan', (route) => route.fulfill({ status: 503, json: { detail: 'offline' } }));
  await page.route('**/api/v1/study/insights', (route) => route.fulfill({ status: 503, json: { detail: 'offline' } }));

  await page.goto('/');
  await page.getByText('Current book').waitFor();
  await page.getByRole('button', { name: 'Build my learning plan' }).click();

  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  const subject = dialog.getByLabel('Subject');
  await expect(subject.locator('option', { hasText: 'Science' })).toHaveCount(2);
  await expect(subject.locator('option', { hasText: 'Social Science' })).toHaveCount(1);
  await expect(subject).toHaveValue('subject-social');
  await expect(dialog.getByLabel('Class')).toHaveValue('10');
  await expect(dialog.getByRole('button', { name: 'Build my learning plan' })).toBeEnabled();

  await subject.selectOption('subject-science');
  await expect(dialog.getByRole('button', { name: 'Build my learning plan' })).toBeEnabled();

  let posted: Record<string, unknown> | null = null;
  await page.route('**/api/v1/learning-paths', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fulfill({ json: [] });
      return;
    }
    posted = route.request().postDataJSON();
    await route.fulfill({
      json: { pathId: 'path-1', firstLessonId: 'lesson-1', totalLessons: 1, status: 'generating' },
    });
  });

  await dialog.getByRole('button', { name: 'Build my learning plan' }).click();
  await expect(dialog).toBeHidden();
  expect(posted).toEqual({
    documentId: document.documentId,
    grade: 10,
    subjectId: 'subject-science',
  });
});
