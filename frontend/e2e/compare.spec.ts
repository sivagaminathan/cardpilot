import { test, expect } from './fixtures';

test('compares cards on /compare showing ranked cards, unranked Skyward Explorer, and explanation toggle', async ({
  page,
}) => {
  await page.goto('/compare');

  await expect(page.getByLabel('Select demo profile')).toHaveValue('maya');

  const categorySelect = page.getByLabel('Category');
  await expect(categorySelect.locator('option[value="dining"]')).toBeAttached();
  await categorySelect.selectOption('dining');

  await page.getByLabel('Amount (USD)').fill('100.00');
  await page.getByRole('button', { name: 'Compare Cards' }).click();

  await expect(page.getByRole('heading', { level: 3, name: 'Comparison Results' })).toBeVisible();

  const rankedItems = page.getByTestId('compare-ranked-item');
  await expect(rankedItems.first()).toBeVisible();
  await expect(rankedItems.first()).toContainText('Est. Value:');

  const unrankedCard = page.getByTestId('compare-unranked-item').filter({
    hasText: 'Skyward Explorer',
  });
  await expect(unrankedCard).toBeVisible();
  await expect(unrankedCard).toContainText('SKY_MILES');

  const firstToggle = rankedItems.first().getByRole('button', { name: 'Show explanation' });
  await expect(firstToggle).toHaveAttribute('aria-expanded', 'false');
  await firstToggle.click();
  await expect(
    rankedItems.first().getByRole('button', { name: 'Hide explanation' }),
  ).toHaveAttribute('aria-expanded', 'true');
  await expect(rankedItems.first().locator('ol li').first()).toBeVisible();
});
