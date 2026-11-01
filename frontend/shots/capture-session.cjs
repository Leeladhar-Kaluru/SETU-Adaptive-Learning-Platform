// Waits on the real SETU login page until the user signs in, then captures the
// session token from localStorage into system temp. The password is typed by
// the user into the real UI — it never reaches this script, files, or chat.
const { chromium } = require('playwright');
const fs = require('fs');
const os = require('os');
const path = require('path');

const BASE = 'http://localhost:5173';
const EXPECTED_USER = process.env.EXPECTED_USER_ID || null;
const outFile = process.env.OUT_FILE || 'setu-chotu2-session.json';

const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  log('desk open — waiting for the user to sign in (expected user id:', EXPECTED_USER || 'any', ')');

  const deadline = Date.now() + 30 * 60 * 1000;
  for (;;) {
    const state = await page.evaluate(() => ({
      token: localStorage.getItem('setu_auth_token'),
      userId: localStorage.getItem('setu_active_user_id'),
    }));
    if (state.token && state.userId) {
      if (EXPECTED_USER && state.userId !== EXPECTED_USER) {
        log('signed in as', state.userId, 'but waiting for', EXPECTED_USER, '— sign out and switch accounts');
        await page.waitForTimeout(5000);
        continue;
      }
      const dest = path.join(os.tmpdir(), outFile);
      fs.writeFileSync(dest, JSON.stringify({ token: state.token, userId: state.userId }));
      log('session captured for', state.userId, '->', dest);
      break;
    }
    if (Date.now() > deadline) throw new Error('no sign-in within 30 minutes');
    await page.waitForTimeout(2000);
  }
  await browser.close();
  log('DONE');
})().catch((err) => {
  console.error('CAPTURE FAILED:', err);
  process.exit(1);
});
