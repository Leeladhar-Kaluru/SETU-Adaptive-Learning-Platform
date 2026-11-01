import { test, expect } from '@playwright/test';

const boards = [{ id: 'board-test', code: 'TEST', name: 'Test Board Alpha' }];
const subjects = [
  { id: 'subject-test', code: 'TEST', canonicalName: 'Test Subject', name: 'Test Subject' },
];
const languages = [
  { id: 'lang-test', bcp47Tag: 'en-TEST', nativeName: 'Test Language', script: 'Latn' },
];

async function openRegistration(page: import('@playwright/test').Page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Get Started', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Continue' }).click();
  await dialog.getByRole('button', { name: 'Continue to Registration →' }).click();
  return dialog;
}

test('onboarding loads reference data and starts with no academic selection', async ({ page }) => {
  await page.route('**/api/v1/catalogue/boards', (route) => route.fulfill({ json: boards }));
  await page.route('**/api/v1/catalogue/subjects', (route) => route.fulfill({ json: subjects }));
  await page.route('**/api/v1/catalogue/languages', (route) => route.fulfill({ json: languages }));

  const dialog = await openRegistration(page);

  await expect(dialog.locator('select#tour-reg-grade')).toHaveValue('');
  await expect(dialog.locator('select#tour-reg-board')).toHaveValue('');
  await expect(dialog.locator('select#tour-reg-lang')).toHaveValue('');
  await expect(dialog.locator('select#tour-reg-board option')).toHaveText([
    'Select a board',
    'Test Board Alpha',
  ]);
  await expect(dialog.locator('select#tour-reg-lang option')).toHaveText([
    'Select a language',
    'Test Language',
  ]);
  await expect(dialog.locator('select#tour-reg-board option', { hasText: 'CBSE' })).toHaveCount(0);
  await expect(dialog.locator('select#tour-reg-lang option', { hasText: 'English (India)' })).toHaveCount(0);
});

test('a failed taxonomy load shows an error, disables selects, and retries', async ({ page }) => {
  let languageAttempts = 0;
  await page.route('**/api/v1/catalogue/boards', (route) => route.fulfill({ json: boards }));
  await page.route('**/api/v1/catalogue/subjects', (route) => route.fulfill({ json: subjects }));
  await page.route('**/api/v1/catalogue/languages', (route) => {
    languageAttempts += 1;
    if (languageAttempts === 1) {
      return route.fulfill({ status: 503, json: { detail: 'Catalogue offline.' } });
    }
    return route.fulfill({ json: languages });
  });

  const dialog = await openRegistration(page);

  await expect(dialog.getByText('Could not load boards, subjects, and languages.')).toBeVisible();
  await expect(dialog.locator('select#tour-reg-board')).toBeDisabled();
  await expect(dialog.locator('select#tour-reg-lang')).toBeDisabled();

  await dialog.getByRole('button', { name: 'Retry' }).click();
  await expect(dialog.getByText('Could not load boards, subjects, and languages.')).toHaveCount(0);
  await expect(dialog.locator('select#tour-reg-lang option', { hasText: 'Test Language' })).toHaveCount(1);
  expect(languageAttempts).toBe(2);
});
