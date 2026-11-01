// Live-data driver: uploads the 3 NCERT PDFs through the REAL UI. The session
// token is never read from or written to disk — the script opens the visible
// desk, the user signs in with their own password, and the token stays inside
// the browser (in memory of this process only). No API mocks, no fixtures.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ROOT = 'C:/projects/setu - V2';
const BASE = 'http://localhost:5173';
const API = 'http://127.0.0.1:8000';

const books = [
  { file: path.join(ROOT, 'context/ncert/full/class-6-science-full.pdf'), grade: '6', subject: 'Science', tag: 'ncert-6-science-full' },
  { file: path.join(ROOT, 'context/ncert/full/class-8-mathematics-full.pdf'), grade: '8', subject: 'Mathematics', tag: 'ncert-8-maths-full' },
  { file: path.join(ROOT, 'context/ncert/full/class-10-social-economics-full.pdf'), grade: '10', subject: 'Social Science', tag: 'ncert-10-social-full' },
];

const shotDir = path.join(ROOT, 'context/demo-evidence');
fs.mkdirSync(shotDir, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

let auth = null;

async function apiGet(pathname) {
  let lastErr = null;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    const res = await fetch(`${API}${pathname}`, {
      headers: { Authorization: `Bearer ${auth.token}` },
    });
    if (res.ok) return res.json();
    lastErr = new Error(`${res.status} ${(await res.text()).slice(0, 300)}`);
    if (![500, 502, 503, 504].includes(res.status)) throw lastErr;
    await sleep(5000 * attempt);
  }
  throw lastErr;
}

async function waitForDocument(filename) {
  let last = null;
  for (let i = 0; i < 240; i += 1) {
    const docs = await apiGet('/api/v1/documents');
    const doc = docs.find((d) => d.filename === filename);
    if (doc) {
      if (doc.status !== last) log(`  ${filename}: ${doc.status}`);
      last = doc.status;
      if (['awaiting_review', 'ready', 'failed', 'needs_ocr'].includes(doc.status)) {
        return doc;
      }
    }
    await sleep(5000);
  }
  throw new Error(`document ${filename} did not reach review within 20 min`);
}

async function selectSubject(dialog, book) {
  const select = dialog.getByLabel('Subject');
  try {
    await select.selectOption({ label: book.subject });
    return;
  } catch {
    const opt = select.locator('option', { hasText: book.subject }).first();
    const value = await opt.getAttribute('value');
    if (value) await select.selectOption(value);
  }
}

async function expect_enabled(page, locator) {
  for (let i = 0; i < 60; i += 1) {
    if (await locator.isEnabled()) return;
    await sleep(1000);
  }
  throw new Error('build button never became enabled');
}

async function buildFromDialog(page, dialog, book) {
  await dialog.getByLabel('Class').selectOption(book.grade);
  await selectSubject(dialog, book);
  const buildBtn = dialog.getByRole('button', { name: 'Build my learning plan' });
  await buildBtn.waitFor({ state: 'visible', timeout: 30000 });
  await expect_enabled(page, buildBtn);
  await buildBtn.click();
  try {
    await dialog.waitFor({ state: 'hidden', timeout: 30000 });
  } catch {
    log('note: dialog still visible after build click for', book.tag);
  }
  log('plan build submitted for', book.tag);
}

async function openReviewDialogForBook(page, book) {
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.getByText('Current book').waitFor({ timeout: 30000 });
  const chip = page.getByRole('button', { name: path.basename(book.file) });
  await chip.waitFor({ state: 'visible', timeout: 30000 });
  await chip.click();
  const deskBuild = page.getByRole('button', { name: 'Build my learning plan' }).first();
  await deskBuild.waitFor({ state: 'visible', timeout: 30000 });
  await deskBuild.click();
  const dialog = page.getByRole('dialog');
  await dialog.waitFor({ state: 'visible', timeout: 30000 });
  await sleep(2500);
  return dialog;
}

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
  const page = await context.newPage();
  page.setDefaultTimeout(60000);
  page.on('pageerror', (e) => log('[pageerror]', e.message));
  page.on('console', (m) => {
    if (m.type() === 'error') log('[console.error]', m.text().slice(0, 200));
  });

  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  log('desk open — please sign in as the demo student in the opened window');

  const deadline = Date.now() + 30 * 60 * 1000;
  while (Date.now() < deadline) {
    const state = await page.evaluate(() => ({
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

  await page.getByText('Current book').waitFor({ timeout: 30000 });
  log('desk loaded');

  for (let i = 0; i < books.length; i += 1) {
    const book = books[i];
    log('uploading', path.basename(book.file));
    await page.locator('input[type=file]').setInputFiles(book.file);
    const doc = await waitForDocument(path.basename(book.file));
    if (doc.status !== 'awaiting_review' && doc.status !== 'ready') {
      throw new Error(`${book.tag} ended in status ${doc.status}: ${doc.errorMessage || ''}`);
    }
    log('processing complete for', book.tag, '— opening review dialog');
    const dialog = await openReviewDialogForBook(page, book);
    if (i === 0) {
      await page.screenshot({ path: path.join(shotDir, `${book.tag}-review-dialog.png`) });
    }
    await buildFromDialog(page, dialog, book);
    await sleep(5000);
  }
  log('all three plans submitted — polling for first ready lessons');

  const pollDeadline = Date.now() + 25 * 60 * 1000;
  let lastState = null;
  while (Date.now() < pollDeadline) {
    const paths = await apiGet('/api/v1/learning-paths');
    const fresh = (paths || []).filter((p) => p.documentId && p.status === 'active');
    for (const p of fresh) {
      const readyCount = (p.lessons || []).filter((l) => l.status === 'ready').length;
      log(
        `path ${String(p.id).slice(0, 8)} grade=${p.grade} subj=${p.subjectId} lessons=${(p.lessons || []).length} ready=${readyCount}`
      );
    }
    const readyPaths = fresh.filter((p) => (p.lessons || []).some((l) => l.status === 'ready'));
    lastState = {
      capturedAt: new Date().toISOString(),
      paths: fresh.map((p) => ({
        id: p.id,
        documentId: p.documentId,
        title: p.title,
        grade: p.grade,
        subjectId: p.subjectId,
        status: p.status,
        totalLessons: p.totalLessons,
        readyLessons: p.readyLessons,
        firstLessonId: p.firstLessonId,
        lessons: p.lessons,
      })),
    };
    if (fresh.length >= 4 && readyPaths.length >= 4) {
      log('all paths have at least one ready lesson');
      break;
    }
    await sleep(20000);
  }

  fs.writeFileSync(path.join(shotDir, 'paths-after-build.json'), JSON.stringify(lastState, null, 2));

  for (const b of books) {
    try {
      await page.goto(BASE, { waitUntil: 'domcontentloaded' });
      await page.getByText('Current book').waitFor({ timeout: 30000 });
      const chip = page.getByRole('button', { name: path.basename(b.file) });
      await chip.waitFor({ state: 'visible', timeout: 30000 });
      await chip.click();
      await sleep(2500);
      await page.screenshot({ path: path.join(shotDir, `desk-${b.tag}.png`) });
      log('screenshot saved for', b.tag);
    } catch (err) {
      log('screenshot failed for', b.tag, ':', err.message);
    }
  }

  await browser.close();
  log('DONE — evidence in', shotDir);
})().catch((err) => {
  console.error('DRIVER FAILED:', err);
  process.exit(1);
});
