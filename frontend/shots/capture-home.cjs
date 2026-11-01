// Visual verification screenshots for the redesigned HomePage.
// Fixture API responses here are screenshot-only; the app itself ships no mocks.
const { chromium } = require('playwright');

const BASE = 'http://localhost:5173';

const student = {
  id: '33333333-3333-4333-8333-333333333333',
  email: 'student@example.com',
  role: 'student',
  displayName: 'Chotu',
  grade: 9,
  boardId: 'board-cbse',
  onboardingCompleted: true,
  tourCompleted: true,
};

const paths = [
  {
    id: '22222222-2222-4222-8222-222222222222',
    documentId: 'doc-1',
    subjectId: 'subject-science',
    title: 'NCERT Science',
    lessons: [
      { id: 'lesson-1', sequence: 1, title: 'Food: Where Does It Come From?', status: 'ready' },
      { id: 'lesson-2', sequence: 2, title: 'Components of Food', status: 'ready' },
      { id: 'lesson-3', sequence: 3, title: 'Fibre to Fabric', status: 'queued' },
      { id: 'lesson-4', sequence: 4, title: 'Sorting Materials', status: 'generating' },
    ],
  },
  {
    id: '33333333-3333-4333-8333-333333333333',
    documentId: 'doc-2',
    subjectId: 'subject-math',
    title: 'NCERT Mathematics',
    lessons: [
      { id: 'lesson-5', sequence: 1, title: 'Rational Numbers', status: 'ready' },
      { id: 'lesson-6', sequence: 2, title: 'Linear Equations', status: 'queued' },
    ],
  },
];

const documents = [
  {
    id: 'doc-1', documentId: 'doc-1', filename: 'NCERT Class 6 Science.pdf',
    status: 'ready', pageCount: 168, chunkCount: 402,
  },
  {
    id: 'doc-2', documentId: 'doc-2', filename: 'NCERT Class 8 Mathematics.pdf',
    status: 'awaiting_review', pageCount: 210, chunkCount: 318,
  },
];

const plan = {
  id: '33333333-3333-4333-8333-333333333333',
  state: 'ready',
  bookCount: 2,
  taskCount: 4,
  summary: 'Two books are in your plan. Science is strong; Maths needs one targeted review before the next chapter.',
  tasks: [
    {
      id: 'task-1', slot: 'Now', kind: 'remediate', subjectId: 'subject-math',
      subjectLabel: 'Mathematics', title: 'Revisit Rational Numbers',
      reason: 'Two practice answers were wrong in the last session, so this concept is still developing.',
      pathTitle: 'NCERT Mathematics', pathId: '33333333-3333-4333-8333-333333333333', lessonId: 'lesson-5',
      actionLabel: 'Practice',
    },
    {
      id: 'task-2', slot: 'Next', kind: 'continue', subjectId: 'subject-science',
      subjectLabel: 'Science', title: 'Continue Components of Food',
      reason: 'You read for 12 minutes and answered 5 of 6 checkpoint questions correctly.',
      pathTitle: 'NCERT Science', pathId: '22222222-2222-4222-8222-222222222222', lessonId: 'lesson-2',
      actionLabel: 'Continue',
    },
    {
      id: 'task-3', slot: 'Later', kind: 'review', subjectId: 'subject-science',
      subjectLabel: 'Science', title: 'Quick review of Food Sources',
      reason: 'Reviewing earlier units keeps the memory fresh before the next checkpoint.',
      pathTitle: 'NCERT Science', pathId: '22222222-2222-4222-8222-222222222222', lessonId: 'lesson-1',
      actionLabel: 'Review',
    },
    {
      id: 'task-4', slot: 'Stretch', kind: 'stretch', subjectId: 'subject-math',
      subjectLabel: 'Mathematics', title: 'Try an extension problem',
      reason: 'You finished the basics quickly; a challenge question tests how deep it goes.',
      pathTitle: 'NCERT Mathematics', pathId: '33333333-3333-4333-8333-333333333333',
      actionLabel: 'Try it',
    },
  ],
  books: [
    { pathId: '22222222-2222-4222-8222-222222222222', subjectId: 'subject-science', subjectLabel: 'Science', readyLessons: 2, totalLessons: 4 },
    { pathId: '33333333-3333-4333-8333-333333333333', subjectId: 'subject-math', subjectLabel: 'Mathematics', readyLessons: 1, totalLessons: 2 },
  ],
};

const insights = {
  confidence: 'moderate',
  confidenceDetail: 'Based on 18 answers across two units.',
  summary: 'You answer steadily and rarely ask for hints. Best results come in the evening.',
  accuracy: { overall: 78, trend: 'steady' },
  routine: { bestWindow: { label: 'Evening' }, consistencyLabel: '4 of 7 days' },
  pace: { medianAnswerSeconds: 22, label: 'Steady' },
  hintReliance: { hintRate: 12, label: 'Low hint use' },
  mastery: {
    strengths: [{ label: 'Components of Food', score: 92 }],
    focusAreas: [{ label: 'Rational Numbers', score: 55 }],
  },
  habits: [
    { id: 'h1', title: 'Consistent reader', detail: 'You opened a unit on 4 of the last 7 days.', tone: 'positive' },
    { id: 'h2', title: 'Low hint use', detail: 'You try first and ask for a hint only when stuck.', tone: 'positive' },
    { id: 'h3', title: 'Evening focus', detail: 'Most study happens between 6 and 9 pm.', tone: 'neutral' },
  ],
};

const summary = {
  minutesStudied: 34,
  readingTitle: 'Components of Food',
  checkpointCount: 2,
  accuracyRate: 0.78,
  improvement: 'improving',
  pace: 'steady',
  dailyGoalMinutes: 20,
  focus: 'Continue with Components of Food.',
  heatmap: [
    { date: '2026-10-26', seconds: 0 }, { date: '2026-10-27', seconds: 720 },
    { date: '2026-10-28', seconds: 480 }, { date: '2026-10-29', seconds: 0 },
    { date: '2026-10-30', seconds: 1200 }, { date: '2026-10-31', seconds: 300 },
    { date: '2026-11-01', seconds: 960 },
  ],
  suggestions: [
    {
      id: 'sug-1', note: 'Revise the number line examples on page 4 before Thursday’s practice.',
      actionType: 'practice', conceptId: 'concept-rational-numbers',
      explanation: 'Chotu missed both negative-number questions in the last checkpoint.',
      teacherName: 'Ms. Iyer',
    },
  ],
};

async function mockDesk(page) {
  await page.route('**/api/v1/profile', (route) => route.fulfill({ json: student }));
  await page.route('**/api/v1/documents', (route) => route.fulfill({ json: documents }));
  await page.route('**/api/v1/learning-paths', (route) => route.fulfill({ json: paths }));
  await page.route('**/api/v1/study/plan', (route) => route.fulfill({ json: plan }));
  await page.route('**/api/v1/study/insights', (route) => route.fulfill({ json: insights }));
  await page.route('**/api/v1/study/summary', (route) => route.fulfill({ json: summary }));
  await page.route('**/api/v1/catalogue/**', (route) => route.fulfill({ json: [] }));
}

(async () => {
  const browser = await chromium.launch();
  const out = 'shots';
  require('fs').mkdirSync(out, { recursive: true });

  // Welcome (signed out)
  const ctx1 = await browser.newContext({ viewport: { width: 1360, height: 900 } });
  const page1 = await ctx1.newPage();
  await page1.goto(BASE, { waitUntil: 'networkidle' });
  await page1.screenshot({ path: `${out}/home-welcome.png`, fullPage: true });
  await ctx1.close();

  // Desk (signed in)
  const ctx2 = await browser.newContext({ viewport: { width: 1360, height: 900 } });
  const page2 = await ctx2.newPage();
  await page2.addInitScript(() => {
    localStorage.setItem('setu_auth_token', 'shot-token');
    localStorage.setItem('setu_active_user_id', '33333333-3333-4333-8333-333333333333');
  });
  await mockDesk(page2);
  await page2.goto(BASE, { waitUntil: 'networkidle' });
  await page2.waitForTimeout(400);
  await page2.screenshot({ path: `${out}/home-desk.png`, fullPage: true });
  await ctx2.close();

  // Desk (mobile)
  const ctx3 = await browser.newContext({ viewport: { width: 412, height: 915 } });
  const page3 = await ctx3.newPage();
  await page3.addInitScript(() => {
    localStorage.setItem('setu_auth_token', 'shot-token');
    localStorage.setItem('setu_active_user_id', '33333333-3333-4333-8333-333333333333');
  });
  await mockDesk(page3);
  await page3.goto(BASE, { waitUntil: 'networkidle' });
  await page3.waitForTimeout(400);
  await page3.screenshot({ path: `${out}/home-desk-mobile.png`, fullPage: true });
  await ctx3.close();

  await browser.close();
  console.log('screenshots done');
})();
