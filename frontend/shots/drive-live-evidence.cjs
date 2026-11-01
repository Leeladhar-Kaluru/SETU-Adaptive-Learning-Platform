// Live-evidence driver: generates REAL attempt evidence on the freshly built
// NCERT plans as the signed-in user, then records how the adaptive plan changed.
// - Science 6 Ch1: correct practice + a correct checkpoint pass -> demonstrated
// - Maths 8 Ch1: deliberate wrong practice answers -> developing
// - A real ~2.5 minute reading session on Maths Ch1 (real UI timer)
// - Maths 8 Ch2: one wrong answer through the REAL UI -> root-gap coach card
// Everything goes through the real API/UI; answer keys are read server-side only
// via scripts/dump_questions.py (the client never receives them).
// The session token is never read from or written to disk: the script opens the
// visible desk, the user signs in, and the token stays in this process memory.
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = 'C:/projects/setu - V2';
const API = 'http://127.0.0.1:8000';
const BASE = 'http://localhost:5173';
const shotDir = path.join(ROOT, 'context/demo-evidence');
fs.mkdirSync(shotDir, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

let auth = null;

async function apiGet(pathname) {
  const res = await fetch(`${API}${pathname}`, {
    headers: { Authorization: `Bearer ${auth.token}` },
  });
  if (!res.ok) throw new Error(`${res.status} ${(await res.text()).slice(0, 300)}`);
  return res.json();
}

async function apiPost(pathname, body) {
  const res = await fetch(`${API}${pathname}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${auth.token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${(await res.text()).slice(0, 300)}`);
  return res.json();
}

function save(name, data) {
  const file = path.join(shotDir, name);
  fs.writeFileSync(file, JSON.stringify(data, null, 2));
  log('saved', file);
}

function dumpAnswers(lessonVersionId) {
  const out = execFileSync(
    path.join(ROOT, 'backend/.venv/Scripts/python.exe'),
    ['scripts/dump_questions.py', lessonVersionId],
    { cwd: path.join(ROOT, 'backend'), encoding: 'utf8' }
  );
  const list = JSON.parse(out);
  const map = new Map();
  for (const q of list) map.set(q.questionKey, q);
  return map;
}

function answerFor(dumpMap, question) {
  const row = dumpMap.get(question.questionId);
  if (!row) throw new Error(`no answer key for ${question.questionId}`);
  return row.answerKey?.answer;
}

function conceptOf(question) {
  return (question.conceptIds || [])[0] || null;
}

async function findPaths() {
  const paths = await apiGet('/api/v1/learning-paths');
  return {
    science: paths.find((p) => p.grade === 6 && p.subjectId === 'subject-science'),
    maths: paths.find((p) => p.grade === 8 && p.subjectId === 'subject-math'),
  };
}

async function getPackage(lessonId, pathId) {
  return apiGet(`/api/v1/learning-paths/lessons/${lessonId}?pathId=${pathId}`);
}

function wrongResponse(question, correctAnswer) {
  if (question.type === 'multiple_choice') {
    const options = question.options || [];
    const wrong = options.find((o) => String(o).trim() !== String(correctAnswer).trim());
    if (wrong !== undefined) return wrong;
    return String(correctAnswer).trim() + ' (definitely not this)';
  }
  if (question.type === 'numeric') {
    const n = parseFloat(correctAnswer);
    return String(Number.isFinite(n) ? n + 7 : 12345);
  }
  return 'not the recorded answer';
}

function mostCommonConcept(questions) {
  const counts = new Map();
  for (const q of questions) {
    for (const c of q.conceptIds || []) {
      counts.set(c, (counts.get(c) || 0) + 1);
    }
  }
  let best = null;
  let bestCount = 0;
  for (const [c, n] of counts) {
    if (n > bestCount) {
      best = c;
      bestCount = n;
    }
  }
  return best;
}

async function submitAttempt({ lessonVersionId, questionKey, response, attemptKind, keySuffix }) {
  return apiPost('/api/v1/attempts', {
    lessonVersionId,
    questionKey,
    response,
    hintLevel: 0,
    hintsUsed: [],
    elapsedSeconds: 30,
    attemptKind,
    syncIdempotencyKey: `${attemptKind}-${lessonVersionId}-${questionKey}-${keySuffix}`,
  });
}

async function waitForReadyLessons(mathsNeeded) {
  const deadline = Date.now() + 45 * 60 * 1000;
  for (;;) {
    const { science, maths } = await findPaths();
    const readyCount = (p) => (p?.lessons || []).filter((l) => l.status === 'ready').length;
    const sc = readyCount(science);
    const mc = readyCount(maths);
    log(`ready lessons: science=${sc} maths=${mc} (need maths>=${mathsNeeded})`);
    if (science && maths && sc >= 1 && mc >= mathsNeeded) return { science, maths };
    if (Date.now() > deadline) throw new Error('timed out waiting for ready lessons');
    await sleep(20000);
  }
}

function summarizeTasks(tasks) {
  return (tasks || []).map((t) => ({
    slot: t.slot,
    kind: t.kind,
    title: t.title,
    pathTitle: t.pathTitle,
    reason: t.reason,
  }));
}

(async () => {
  const signInBrowser = await chromium.launch({ headless: false });
  const signInContext = await signInBrowser.newContext({ viewport: { width: 1280, height: 900 } });
  const signInPage = await signInContext.newPage();
  await signInPage.goto(BASE, { waitUntil: 'domcontentloaded' });
  log('desk open — please sign in as the demo student in the opened window');
  const signInDeadline = Date.now() + 30 * 60 * 1000;
  while (Date.now() < signInDeadline) {
    const state = await signInPage.evaluate(() => ({
      token: localStorage.getItem('setu_auth_token'),
      userId: localStorage.getItem('setu_active_user_id'),
    }));
    if (state.token && state.userId) {
      auth = state;
      break;
    }
    await sleep(2000);
  }
  if (!auth) throw new Error('no sign-in within 30 minutes');
  log('signed in as', auth.userId);
  await signInBrowser.close();

  const { science, maths } = await waitForReadyLessons(2);
  log(`science path ${science.id} (${science.title})`, `maths path ${maths.id} (${maths.title})`);

  const baseline = {
    capturedAt: new Date().toISOString(),
    plan: await apiGet('/api/v1/study/plan'),
    insights: await apiGet('/api/v1/study/insights'),
    summary: await apiGet('/api/v1/study/summary'),
  };
  save('baseline.json', baseline);
  log('baseline tasks:', baseline.plan.tasks.map((t) => `${t.kind}:${t.title}`).join(' | '));

  const scienceL1 = science.lessons.find((l) => l.sequence === 1 && l.status === 'ready');
  const sciPkg = await getPackage(scienceL1.id, science.id);
  const sciDump = dumpAnswers(sciPkg.lessonVersionId);
  const sciAll = [...(sciPkg.practice || []), ...(sciPkg.checkpointTest || [])];
  const sciConcept = mostCommonConcept(sciAll) || conceptOf(sciAll[0]);
  const sciPractice = (sciPkg.practice || [])
    .filter((q) => (q.conceptIds || []).includes(sciConcept))
    .slice(0, 2);
  const sciCheckpoint = (sciPkg.checkpointTest || []).slice(0, 6);

  const sciOutcomes = [];
  for (const [i, q] of sciPractice.entries()) {
    const r = await submitAttempt({
      lessonVersionId: sciPkg.lessonVersionId,
      questionKey: q.questionId,
      response: answerFor(sciDump, q),
      attemptKind: 'practice',
      keySuffix: `demo-correct-${i}`,
    });
    sciOutcomes.push({ step: `science-practice-correct-${i}`, questionKey: q.questionId, isCorrect: r.isCorrect, mastery: r.mastery });
    log(`science practice correct ${i + 1}:`, r.isCorrect, r.mastery?.band);
  }
  for (const [i, q] of sciCheckpoint.entries()) {
    const r = await submitAttempt({
      lessonVersionId: sciPkg.lessonVersionId,
      questionKey: q.questionId,
      response: answerFor(sciDump, q),
      attemptKind: 'checkpoint',
      keySuffix: `demo-pass-${i}`,
    });
    sciOutcomes.push({ step: `science-checkpoint-correct-${i}`, questionKey: q.questionId, isCorrect: r.isCorrect, mastery: r.mastery });
    log(`science checkpoint correct ${i + 1}:`, r.isCorrect, r.mastery?.band);
  }

  const mathsL1 = maths.lessons.find((l) => l.sequence === 1 && l.status === 'ready');
  const mathsPkg = await getPackage(mathsL1.id, maths.id);
  const mathsDump = dumpAnswers(mathsPkg.lessonVersionId);
  const mathsAll = [...(mathsPkg.practice || []), ...(mathsPkg.checkpointTest || [])];
  const mathsConcept = mostCommonConcept(mathsAll) || conceptOf(mathsAll[0]);
  const mathsWrongQ = (mathsPkg.practice || [])
    .filter((q) => (q.conceptIds || []).includes(mathsConcept))
    .slice(0, 3);

  const mathsOutcomes = [];
  for (const [i, q] of mathsWrongQ.entries()) {
    const response = wrongResponse(q, answerFor(mathsDump, q));
    const r = await submitAttempt({
      lessonVersionId: mathsPkg.lessonVersionId,
      questionKey: q.questionId,
      response,
      attemptKind: 'practice',
      keySuffix: `demo-wrong-${i}`,
    });
    mathsOutcomes.push({ step: `maths-practice-wrong-${i}`, questionKey: q.questionId, response, isCorrect: r.isCorrect, mastery: r.mastery });
    log(`maths practice wrong ${i + 1}:`, r.isCorrect, r.mastery?.band);
  }
  save('attempt-evidence.json', { science: sciOutcomes, maths: mathsOutcomes, mathsConcept, sciConcept });

  // Real reading session on Maths Ch1 via the real UI timer (headless).
  log('opening maths lesson for a real reading session (~2.5 min)');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await context.addInitScript(
    ({ token, userId }) => {
      localStorage.setItem('setu_auth_token', token);
      localStorage.setItem('setu_active_user_id', userId);
    },
    { token: auth.token, userId: auth.userId }
  );
  const page = await context.newPage();
  await page.goto(`${BASE}/lesson/${mathsL1.id}?pathId=${maths.id}`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: /2\. Solve/ }).waitFor({ timeout: 60000 });
  await sleep(150000);
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await sleep(4000);
  await browser.close();
  log('reading session ended');

  const summaryAfterReading = await apiGet('/api/v1/study/summary');
  log('summary after reading:', {
    minutesStudied: summaryAfterReading.minutesStudied,
    readingTitle: summaryAfterReading.readingTitle,
  });

  const after = {
    capturedAt: new Date().toISOString(),
    plan: await apiGet('/api/v1/study/plan'),
    insights: await apiGet('/api/v1/study/insights'),
    summary: summaryAfterReading,
  };
  save('after-evidence.json', after);
  log('after tasks:', after.plan.tasks.map((t) => `${t.kind}:${t.title}`).join(' | '));

  const diff = {
    baselineTasks: summarizeTasks(baseline.plan.tasks),
    afterTasks: summarizeTasks(after.plan.tasks),
    baselineAccuracy: baseline.summary.accuracyRate,
    afterAccuracy: after.summary.accuracyRate,
    baselineMinutes: baseline.summary.minutesStudied,
    afterMinutes: after.summary.minutesStudied,
    baselineSummary: baseline.plan.summary,
    afterSummary: after.plan.summary,
  };
  save('plan-diff.json', diff);

  // Root-gap demo: one wrong answer on Maths Ch2 through the REAL UI.
  const mathsL2 = maths.lessons.find((l) => l.sequence === 2 && l.status === 'ready');
  if (!mathsL2) {
    log('maths lesson 2 not ready yet — skipping root-gap UI demo');
  } else {
    const l2Pkg = await getPackage(mathsL2.id, maths.id);
    const l2Dump = dumpAnswers(l2Pkg.lessonVersionId);
    const practiceQ = (l2Pkg.practice || []).find((q) => (q.options || []).length > 0) || (l2Pkg.practice || [])[0];
    const correctAnswer = answerFor(l2Dump, practiceQ);
    const options = practiceQ.options || [];
    const wrongIdx = options.findIndex((o) => String(o).trim() !== String(correctAnswer).trim());
    const clickIdx = wrongIdx >= 0 ? wrongIdx : 0;
    const letter = String.fromCharCode(65 + clickIdx);

    const browser2 = await chromium.launch({ headless: true });
    const ctx2 = await browser2.newContext({ viewport: { width: 1280, height: 1200 } });
    await ctx2.addInitScript(
      ({ token, userId }) => {
        localStorage.setItem('setu_auth_token', token);
        localStorage.setItem('setu_active_user_id', userId);
      },
      { token: auth.token, userId: auth.userId }
    );
    const p2 = await ctx2.newPage();
    const responseBody = await (async () => {
      let captured = null;
      p2.on('response', async (resp) => {
        if (resp.url().includes('/api/v1/attempts') && resp.request().method() === 'POST') {
          try { captured = await resp.json(); } catch {}
        }
      });
      await p2.goto(`${BASE}/lesson/${mathsL2.id}?pathId=${maths.id}`, { waitUntil: 'domcontentloaded' });
      await p2.getByRole('button', { name: /2\. Solve/ }).waitFor({ timeout: 60000 });
      await p2.getByRole('button', { name: /2\. Solve/ }).click();
      if (options.length > 0) {
        await p2.getByRole('button', { name: new RegExp(`^${letter}\\. `) }).first().click();
      } else {
        await p2.locator('input[type=text]').first().fill(wrongResponse(practiceQ, correctAnswer));
      }
      await p2.getByRole('button', { name: 'Check Answer' }).click();
      await sleep(3000);
      await p2.screenshot({ path: path.join(shotDir, 'root-gap-coach.png'), fullPage: true });
      return captured;
    })();
    await browser2.close();
    if (responseBody) {
      save('root-gap-attempt.json', responseBody);
      log('rootGap:', JSON.stringify(responseBody.coaching?.rootGap, null, 2).slice(0, 600));
    } else {
      log('attempt response not captured via UI');
    }
  }

  log('DONE — evidence complete');
})().catch((err) => {
  console.error('EVIDENCE DRIVER FAILED:', err);
  process.exit(1);
});
