import { test, expect } from '@playwright/test';

const profile = {
  id: '33333333-3333-4333-8333-333333333333',
  email: 'student@example.com',
  role: 'student',
  displayName: 'Test Student',
  grade: 9,
  boardId: 'board-cbse',
  onboardingCompleted: true,
  tourCompleted: true,
};

const lessonPackage = {
  lessonId: 'lesson-1',
  lessonVersionId: '11111111-1111-4111-8111-111111111111',
  pathId: '22222222-2222-4222-8222-222222222222',
  title: 'Cell Structure',
  grade: 9,
  subjectId: 'subject-science',
  objectives: [],
  blocks: [],
  visuals: [],
  workedExamples: [],
  takeaways: [],
  practice: [{
    questionId: 'q1',
    type: 'multiple_choice',
    prompt: 'Which is the basic unit of life?',
    options: ['Cell', 'Tissue', 'Organ', 'Organism'],
    conceptIds: ['concept-cell'],
    hints: ['Read the first block.'],
    feedback: 'The cell is the basic unit.',
  }],
  checkpointTest: [{
    questionId: 't1',
    type: 'multiple_choice',
    prompt: 'Which statement is independent evidence?',
    options: ['A', 'B', 'C', 'D'],
    conceptIds: ['concept-cell'],
    hints: [],
    feedback: 'B is correct.',
  }],
};

async function signIn(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    localStorage.setItem('setu_auth_token', 'e2e-token');
    localStorage.setItem('setu_active_user_id', '33333333-3333-4333-8333-333333333333');
  });
  await page.route(/\/api\/v1\/profile$/, (route) => route.fulfill({ json: profile }));
  await page.route('**/api/v1/learning-paths/lessons/**', (route) => route.fulfill({ json: lessonPackage }));
}

test('practice is graded by the server and never trusts client correctness', async ({ page }) => {
  await signIn(page);
  let body: any = null;
  await page.route('**/api/v1/attempts', async (route) => {
    body = route.request().postDataJSON();
    await route.fulfill({
      json: {
        attemptId: 'att-1', isCorrect: false, score: 0,
        correctAnswer: 'Cell', feedback: 'Not quite. Re-read the first block.',
        mastery: { band: 'developing', score: 0, evidenceCount: 1, explanation: 'One incorrect response.' },
        nextAction: { action: 'review_prerequisite', title: 'Review Prerequisite Concepts', reason: 'Review the source.', canAdvance: true },
        alreadyRecorded: false,
      },
    });
  });

  await page.goto('/lesson/lesson-1?pathId=22222222-2222-4222-8222-222222222222');
  await page.getByRole('button', { name: /2\. Solve/ }).click();
  await page.getByRole('button', { name: 'B. Tissue' }).click();
  await page.getByRole('button', { name: 'Check Answer' }).click();

  await expect(page.getByText('Not quite. Re-read the first block.')).toBeVisible();
  expect(body.isCorrect).toBeUndefined();
  expect(body.score).toBeUndefined();
  expect(body.questionKey).toBe('q1');
  expect(body.lessonVersionId).toBe(lessonPackage.lessonVersionId);
  expect(body.attemptKind).toBe('practice');
});

test('checkpoint shows server mastery and no teacher-only link', async ({ page }) => {
  await signIn(page);
  const bodies: any[] = [];
  await page.route('**/api/v1/attempts', async (route) => {
    bodies.push(route.request().postDataJSON());
    await route.fulfill({
      json: {
        attemptId: `att-${bodies.length}`, isCorrect: true, score: 1,
        correctAnswer: 'B', feedback: 'B is correct.',
        mastery: { band: 'demonstrated', score: 1, evidenceCount: 3, explanation: 'Three independent correct observations.' },
        nextAction: { action: 'move_forward', title: 'Advance to Next Lesson', reason: 'Mastery demonstrated.', canAdvance: true },
        alreadyRecorded: false,
      },
    });
  });

  await page.goto('/lesson/lesson-1?pathId=22222222-2222-4222-8222-222222222222');
  await page.getByRole('button', { name: /3\. Test/ }).click();
  await page.getByRole('button', { name: 'B. B' }).click();
  await page.getByRole('button', { name: 'Submit Checkpoint Test' }).click();

  await expect(page.getByText(/Mastery: demonstrated/i)).toBeVisible();
  await expect(page.getByRole('button', { name: /Teacher Evidence Matrix/ })).toHaveCount(0);
  expect(bodies).toHaveLength(1);
  expect(bodies[0].attemptKind).toBe('checkpoint');
  expect(bodies[0].isCorrect).toBeUndefined();
});
