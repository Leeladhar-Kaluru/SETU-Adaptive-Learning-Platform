import { test, expect } from '@playwright/test';

const student = {
  id: '33333333-3333-4333-8333-333333333333',
  email: 'student@example.com',
  role: 'student',
  displayName: 'Offline Student',
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
  checkpointTest: [],
  practice: [{
    questionId: 'q1',
    type: 'multiple_choice',
    prompt: 'Which is the basic unit of life?',
    options: ['Cell', 'Tissue'],
    conceptIds: ['concept-cell'],
    hints: [],
    feedback: 'The cell is the basic unit.',
  }],
};

async function signIn(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    localStorage.setItem('setu_auth_token', 'e2e-token');
    localStorage.setItem('setu_active_user_id', '33333333-3333-4333-8333-333333333333');
  });
  await page.route(/\/api\/v1\/profile$/, (route) => route.fulfill({ json: student }));
  await page.route('**/api/v1/learning-paths/lessons/**', (route) => route.fulfill({ json: lessonPackage }));
}

async function readAttempts(page: import('@playwright/test').Page) {
  return page.evaluate(async () => {
    const request = indexedDB.open('SetuDeskDB');
    const database = await new Promise<IDBDatabase>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const transaction = database.transaction('offlineAttempts', 'readonly');
    const getAll = transaction.objectStore('offlineAttempts').getAll();
    const rows = await new Promise<any[]>((resolve, reject) => {
      getAll.onsuccess = () => resolve(getAll.result);
      getAll.onerror = () => reject(getAll.error);
    });
    database.close();
    return rows;
  });
}

test('offline attempt is owned by the user and syncs once with auth', async ({ page, context }) => {
  await signIn(page);
  let allowSync = false;
  const requests: Array<{ authorization: string | null; body: any }> = [];
  await page.route('**/api/v1/attempts', async (route) => {
    if (!allowSync) return route.abort('internetdisconnected');
    const request = route.request();
    requests.push({
      authorization: request.headers()['authorization'] || null,
      body: request.postDataJSON(),
    });
    await route.fulfill({
      json: {
        attemptId: 'att-1', isCorrect: true, score: 1, correctAnswer: 'Cell', feedback: 'Correct.',
        mastery: { band: 'not_enough_evidence', score: 1, evidenceCount: 1, explanation: 'One observation.' },
        nextAction: { action: 'practice_more', title: 'Practice more', reason: 'One observation is not enough.', canAdvance: true },
        alreadyRecorded: false,
      },
    });
  });

  await page.goto('/lesson/lesson-1?pathId=22222222-2222-4222-8222-222222222222');
  await context.setOffline(true);
  await page.getByRole('button', { name: /2\. Solve/ }).click();
  await page.getByRole('button', { name: 'A. Cell' }).click();
  await page.getByRole('button', { name: 'Check Answer' }).click();
  await expect(page.getByText(/Saved offline/)).toBeVisible();

  const queued = await readAttempts(page);
  expect(queued).toHaveLength(1);
  expect(queued[0].ownerId).toBe(student.id);
  expect(queued[0].lessonVersionId).toBe(lessonPackage.lessonVersionId);
  expect(queued[0].questionKey).toBe('q1');
  expect(queued[0].synced).toBe(false);

  allowSync = true;
  await context.setOffline(false);
  const syncButton = page.getByRole('button', { name: 'Sync now' });
  await syncButton.click({ timeout: 5000 }).catch(() => undefined);
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].authorization).toBe('Bearer e2e-token');
  expect(requests[0].body.syncIdempotencyKey).toBe(queued[0].clientAttemptId);
  expect(requests[0].body.isCorrect).toBeUndefined();

  await expect.poll(async () => (await readAttempts(page))[0]?.synced).toBe(true);
  await page.waitForTimeout(300);
  expect(requests).toHaveLength(1);
});

test('switching accounts clears the previous offline cache', async ({ page }) => {
  await signIn(page);
  await page.goto('/lesson/lesson-1?pathId=22222222-2222-4222-8222-222222222222');
  await page.getByRole('button', { name: /Save Offline/ }).click();
  await expect(page.getByRole('button', { name: /Saved Offline/ })).toBeVisible();

  await page.evaluate(() => {
    localStorage.setItem('setu_auth_token', 'e2e-token-b');
    localStorage.setItem('setu_active_user_id', '44444444-4444-4444-8444-444444444444');
  });
  await page.unroute(/\/api\/v1\/profile$/);
  await page.route(/\/api\/v1\/profile$/, (route) => route.fulfill({
    json: { ...student, id: '44444444-4444-4444-8444-444444444444', displayName: 'Second Student' },
  }));
  await page.goto('/library');
  await expect(page.getByText('No offline lessons downloaded yet')).toBeVisible();
});
