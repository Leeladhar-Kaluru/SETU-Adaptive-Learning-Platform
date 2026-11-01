import { test, expect } from '@playwright/test';

const student = {
  id: '33333333-3333-4333-8333-333333333333',
  email: 'student@example.com',
  role: 'student',
  displayName: 'Doubt Student',
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
  practice: [],
  checkpointTest: [],
};

async function signIn(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    localStorage.setItem('setu_auth_token', 'e2e-token');
    localStorage.setItem('setu_active_user_id', '33333333-3333-4333-8333-333333333333');
  });
  await page.route(/\/api\/v1\/profile$/, (route) => route.fulfill({ json: student }));
  await page.route('**/api/v1/learning-paths/lessons/**', (route) =>
    route.fulfill({ json: lessonPackage })
  );
}

async function askDoubt(page: import('@playwright/test').Page, question: string) {
  await page.getByRole('button', { name: 'Ask Doubt' }).click();
  await page
    .getByPlaceholder('e.g., Ask any question or clarification about this concept...')
    .fill(question);
  await page.getByRole('button', { name: 'Submit Doubt' }).click();
}

async function readOutbox(page: import('@playwright/test').Page) {
  return page.evaluate(async () => {
    const request = indexedDB.open('SetuDeskDB');
    const database = await new Promise<IDBDatabase>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const transaction = database.transaction('doubtOutbox', 'readonly');
    const getAll = transaction.objectStore('doubtOutbox').getAll();
    const rows = await new Promise<any[]>((resolve, reject) => {
      getAll.onsuccess = () => resolve(getAll.result);
      getAll.onerror = () => reject(getAll.error);
    });
    database.close();
    return rows;
  });
}

test('an online doubt is answered immediately and never enters the offline queue', async ({ page }) => {
  await signIn(page);
  const requests: any[] = [];
  await page.route('**/api/v1/doubts', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    requests.push(route.request().postDataJSON());
    await route.fulfill({
      json: {
        id: 'doubt-1',
        status: 'answered',
        answerJson: {
          answer: 'The cell membrane controls what enters and leaves the cell.',
          citations: [{ citationId: 'cite-1', pageNumber: 12, pageStart: 12, pageEnd: 12 }],
          limitations: null,
          answeredAt: new Date().toISOString(),
        },
      },
    });
  });

  await page.goto('/lesson/lesson-1?pathId=22222222-2222-4222-8222-222222222222');
  await askDoubt(page, 'What does the cell membrane do?');

  await expect(page.getByText('Answer from your sources')).toBeVisible();
  await expect(
    page.getByText('The cell membrane controls what enters and leaves the cell.')
  ).toBeVisible();
  await expect(page.getByText('Page 12')).toBeVisible();

  await expect.poll(() => requests.length).toBe(1);
  const rows = await readOutbox(page);
  expect(rows).toHaveLength(1);
  expect(rows[0].status).toBe('answered');
  expect(rows[0].synced).toBe(true);
});

test('a provider failure shows a retry state and the same question can be retried', async ({ page }) => {
  await signIn(page);
  let calls = 0;
  await page.route('**/api/v1/doubts', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    calls += 1;
    if (calls === 1) {
      await route.fulfill({
        json: {
          id: 'doubt-2',
          status: 'needs_retry',
          answerJson: {
            answer: null,
            citations: [],
            limitations: 'tutor_unavailable',
            retryable: true,
            message: 'The tutor is unavailable. Your question is saved; retry in a moment.',
          },
        },
      });
      return;
    }
    await route.fulfill({
      json: {
        id: 'doubt-2',
        status: 'answered',
        answerJson: {
          answer: 'Diffusion moves particles from high to low concentration.',
          citations: [],
          limitations: null,
          answeredAt: new Date().toISOString(),
        },
      },
    });
  });

  await page.goto('/lesson/lesson-1?pathId=22222222-2222-4222-8222-222222222222');
  await askDoubt(page, 'How does diffusion work?');

  await expect(page.getByText('Could not answer yet')).toBeVisible();
  await expect(page.getByText('The tutor is unavailable. Your question is saved; retry in a moment.')).toBeVisible();

  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(
    page.getByText('Diffusion moves particles from high to low concentration.')
  ).toBeVisible();
  await expect.poll(() => calls).toBe(2);
});

test('a doubt queues only when the browser is genuinely offline and syncs once', async ({ page, context }) => {
  await signIn(page);
  const syncBodies: any[] = [];
  await page.route('**/api/v1/sync/doubts', async (route) => {
    const body = route.request().postDataJSON();
    syncBodies.push(body);
    const doubt = body.doubts[0];
    await route.fulfill({
      json: {
        results: [
          {
            id: 'doubt-3',
            clientDoubtId: doubt.clientDoubtId,
            status: 'answered',
            questionText: doubt.questionText,
            answerJson: {
              answer: 'Photosynthesis happens in the chloroplast.',
              citations: [{ citationId: 'cite-2', pageNumber: 5, pageStart: 5, pageEnd: 5 }],
              limitations: null,
              answeredAt: new Date().toISOString(),
            },
          },
        ],
      },
    });
  });

  await page.goto('/lesson/lesson-1?pathId=22222222-2222-4222-8222-222222222222');
  await context.setOffline(true);
  await askDoubt(page, 'Where does photosynthesis happen?');

  await expect(page.getByText('Stored in Offline Queue')).toBeVisible();
  const queued = await readOutbox(page);
  expect(queued).toHaveLength(1);
  expect(queued[0].status).toBe('queued');
  expect(queued[0].synced).toBe(false);
  expect(queued[0].ownerId).toBe(student.id);

  await context.setOffline(false);
  await expect.poll(async () => (await readOutbox(page))[0]?.status).toBe('answered');

  await expect.poll(() => syncBodies.length).toBe(1);
  const synced = await readOutbox(page);
  expect(synced[0].synced).toBe(true);
  expect(synced[0].answerPayload.answer).toBe('Photosynthesis happens in the chloroplast.');

  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await page.waitForTimeout(300);
  expect(syncBodies).toHaveLength(1);
});

test('the doubts view states each real status and offers retry only where it is possible', async ({ page }) => {
  await signIn(page);
  await page.route('**/api/v1/doubts', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        json: [
          {
            id: 'd-answered',
            clientDoubtId: 'answered-1',
            status: 'answered',
            questionText: 'What is a cell?',
            answerJson: {
              answer: 'The basic unit of life.',
              citations: [{ citationId: 'c1', pageNumber: 3 }],
              limitations: null,
              answeredAt: new Date().toISOString(),
            },
            createdAt: '2026-10-28T09:00:00.000Z',
          },
          {
            id: 'd-retry',
            clientDoubtId: 'retry-1',
            status: 'needs_retry',
            questionText: 'Why do cells divide?',
            answerJson: { answer: null, retryable: true },
            lastErrorCode: 'tutor_unavailable',
            createdAt: '2026-10-28T09:05:00.000Z',
          },
          {
            id: 'd-rejected',
            clientDoubtId: 'rejected-1',
            status: 'rejected',
            questionText: '',
            answerJson: null,
            createdAt: '2026-10-28T09:10:00.000Z',
          },
        ],
      });
      return;
    }
    await route.fulfill({
      json: {
        id: 'd-retry',
        status: 'answered',
        answerJson: {
          answer: 'Cells divide to grow and repair tissue.',
          citations: [],
          limitations: null,
          answeredAt: new Date().toISOString(),
        },
      },
    });
  });

  await page.goto('/doubts');
  await expect(page.getByRole('heading', { name: 'Doubts' })).toBeVisible();
  await expect(page.getByText('Answered', { exact: true })).toBeVisible();
  await expect(page.getByText('Needs retry', { exact: true })).toBeVisible();
  await expect(page.getByText('Rejected', { exact: true })).toBeVisible();
  await expect(page.getByText('The basic unit of life.')).toBeVisible();

  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByText('Cells divide to grow and repair tissue.')).toBeVisible();
});

test('the doubts view says No doubts yet without inventing history', async ({ page }) => {
  await signIn(page);
  await page.route('**/api/v1/doubts', (route) =>
    route.fulfill({ json: [] })
  );

  await page.goto('/doubts');
  await expect(page.getByText('No doubts yet.')).toBeVisible();
});

test('Ask SETU answers a general question and labels it as general knowledge', async ({ page }) => {
  await signIn(page);
  await page.route('**/api/v1/doubts', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    await route.fulfill({
      json: {
        id: 'doubt-gk',
        status: 'answered',
        answerJson: {
          answer: 'Photosynthesis is how plants make food from sunlight, water and carbon dioxide.',
          citations: [],
          limitations: 'general_knowledge',
          answeredAt: new Date().toISOString(),
        },
      },
    });
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'Ask SETU a question' }).click();
  await page.getByLabel('Your question').fill('What is photosynthesis?');
  await page.getByRole('button', { name: 'Send question' }).click();

  await expect(
    page.getByText('Photosynthesis is how plants make food from sunlight, water and carbon dioxide.')
  ).toBeVisible();
  await expect(page.getByText('General knowledge', { exact: true })).toBeVisible();
  await expect(
    page.getByText('Not from your books — add a source for page-cited answers.')
  ).toBeVisible();
  await expect(page.getByText('Citations', { exact: false })).toHaveCount(0);
});

test('an Ask SETU question asked offline shows its answer in the chat thread after reconnecting', async ({ page, context }) => {
  await signIn(page);
  await page.route('**/api/v1/sync/doubts', async (route) => {
    const body = route.request().postDataJSON();
    const doubt = body.doubts[0];
    await route.fulfill({
      json: {
        results: [
          {
            id: 'doubt-off',
            clientDoubtId: doubt.clientDoubtId,
            status: 'answered',
            questionText: doubt.questionText,
            answerJson: {
              answer: 'The nucleus controls the activities of the cell.',
              citations: [],
              limitations: 'general_knowledge',
              answeredAt: new Date().toISOString(),
            },
          },
        ],
      },
    });
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'Ask SETU a question' }).click();
  await context.setOffline(true);
  await page.getByLabel('Your question').fill('What does the nucleus do?');
  await page.getByRole('button', { name: 'Send question' }).click();

  await expect(page.getByText('Saved offline', { exact: true })).toBeVisible();
  const queued = await readOutbox(page);
  expect(queued).toHaveLength(1);
  expect(queued[0].synced).toBe(false);

  await context.setOffline(false);
  await expect.poll(async () => (await readOutbox(page))[0]?.synced).toBe(true);
  await expect
    .poll(() =>
      page.getByText('The nucleus controls the activities of the cell.').isVisible()
    )
    .toBe(true);
  await expect(page.getByText('General knowledge', { exact: true })).toBeVisible();
});
