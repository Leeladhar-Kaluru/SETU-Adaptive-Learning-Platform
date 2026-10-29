import { test, expect } from '@playwright/test';

test('an unknown route renders a real not-found page', async ({ page }) => {
  await page.goto('/this-route-does-not-exist');
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Back to SETU' })).toHaveAttribute('href', '/');
});

test('a guest sees only real navigation and protected routes ask for sign-in', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('link', { name: 'Dashboard' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Downloads' })).toHaveCount(0);

  await page.goto('/dashboard');
  await expect(page.getByText('Sign in to open your lessons, progress, and doubts.')).toBeVisible();
  await page.getByRole('button', { name: 'Sign in or create an account' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
});
