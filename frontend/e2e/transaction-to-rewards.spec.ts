import { test, expect } from './fixtures';

test('records a transaction on /transactions and verifies per-currency and estimated USD on /rewards', async ({
  page,
}) => {
  await page.goto('/transactions');

  await expect(page.getByLabel('Select demo profile')).toHaveValue('maya');

  const cardSelect = page.getByLabel('Active Card');
  await expect(cardSelect).toBeVisible();
  await cardSelect.selectOption({ label: 'Dining & Travel (Northwind Dining & Travel)' });

  await page.getByLabel('Amount (USD)').fill('100.00');
  await page.getByLabel('Category').selectOption('dining');
  await page.getByLabel('Note (optional)').fill('E2E dinner');
  await page.getByRole('button', { name: 'Record Transaction' }).click();

  const snapshotBanner = page.getByTestId('tx-created-snapshot');
  await expect(snapshotBanner).toBeVisible();
  await expect(snapshotBanner).toContainText('NWT_PTS');

  const txItem = page.getByTestId('tx-list-item').filter({ hasText: 'Dining & Travel' });
  await expect(txItem).toBeVisible();
  await expect(txItem).toContainText('$100.00');
  await expect(txItem).toContainText('E2E dinner');

  await page.getByRole('link', { name: 'Rewards' }).click();

  const table = page.getByRole('table', { name: /Earned Rewards by Currency/i });
  await expect(table).toBeVisible();

  const nwtRow = table.getByTestId('rewards-row-NWT_PTS');
  await expect(nwtRow).toBeVisible();
  await expect(nwtRow).toContainText('1');

  await expect(
    page.getByRole('heading', { level: 2, name: /Estimated USD Value/i }),
  ).toBeVisible();
  const nwtEstimate = page.getByTestId('rewards-estimate-NWT_PTS');
  await expect(nwtEstimate).toBeVisible();
  await expect(nwtEstimate).toContainText('$');
});
