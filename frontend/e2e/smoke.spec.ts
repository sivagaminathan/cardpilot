import { test, expect } from './fixtures';

test('loads application shell with disclaimer and seeded Maya profile', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { level: 1, name: 'CardPilot' })).toBeVisible();

  const disclaimer = page.getByRole('complementary', { name: 'Demo Disclaimer' });
  await expect(disclaimer).toBeVisible();
  await expect(disclaimer).toContainText(
    'Sample data only. Not issuer terms. Not financial advice.',
  );

  const profileSelect = page.getByLabel('Select demo profile');
  await expect(profileSelect).toBeVisible();
  await expect(profileSelect.locator('option[value="maya"]')).toHaveText(
    'Maya — The Optimizer',
  );
});
