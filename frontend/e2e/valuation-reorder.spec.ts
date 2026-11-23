import { test, expect } from './fixtures';

test('updates NW_CASH valuation in /settings and reorders #1 ranked card on /compare', async ({
  page,
}) => {
  await page.goto('/compare');

  await expect(page.getByLabel('Select demo profile')).toHaveValue('maya');
  const categorySelect = page.getByLabel('Category');
  await expect(categorySelect.locator('option[value="dining"]')).toBeAttached();
  await categorySelect.selectOption('dining');
  await page.getByLabel('Amount (USD)').fill('100.00');
  await page.getByRole('button', { name: 'Compare Cards' }).click();

  const rankedBefore = page.getByTestId('compare-ranked-item');
  await expect(rankedBefore.first()).toContainText('#1 Dining & Travel');

  await page.getByRole('link', { name: 'Settings' }).click();

  const cashRow = page.getByTestId('valuation-row-NW_CASH');
  await expect(cashRow).toBeVisible();
  await cashRow.getByLabel(/Estimated cents per Northwind Cash Back unit/i).fill('5.0000');
  await cashRow.getByRole('button', { name: 'Save' }).click();

  await expect(cashRow.getByRole('status')).toContainText('Saved 5.0000¢');
  await expect(cashRow).toContainText('User-configured');

  await page.getByRole('link', { name: 'Compare' }).click();
  await expect(page.getByLabel('Category').locator('option[value="dining"]')).toBeAttached();
  await page.getByLabel('Category').selectOption('dining');
  await page.getByLabel('Amount (USD)').fill('100.00');
  await page.getByRole('button', { name: 'Compare Cards' }).click();

  const rankedAfter = page.getByTestId('compare-ranked-item');
  await expect(rankedAfter.first()).toContainText(/#1 (Daily Cash|Grocery 5x)/);
  await expect(rankedAfter.filter({ hasText: 'Dining & Travel' })).toContainText(
    /#[23] Dining & Travel/,
  );
});
