import { test, expect } from './fixtures';

test('logs $10.00 usage against Monthly Dining Credit on /benefits and updates remaining balance', async ({
  page,
}) => {
  await page.goto('/benefits');

  await expect(page.getByLabel('Select demo profile')).toHaveValue('maya');

  const diningBenefitCard = page.locator('article.benefit-card', {
    hasText: 'Monthly Dining Credit',
  });
  await expect(diningBenefitCard).toBeVisible();
  await expect(diningBenefitCard).toContainText('$15.00');

  await diningBenefitCard.getByLabel('Usage Amount (USD)').fill('10.00');
  await diningBenefitCard.getByLabel('Note (optional)').fill('Team lunch');
  await diningBenefitCard.getByRole('button', { name: 'Log Usage' }).click();

  await expect(diningBenefitCard.getByRole('status')).toContainText('Logged $10.00 usage');
  await expect(diningBenefitCard).toContainText('Status: Partially used');
  await expect(diningBenefitCard).toContainText('$10.00');
  await expect(diningBenefitCard).toContainText('$5.00');
  await expect(
    diningBenefitCard.getByRole('heading', { level: 4, name: 'Logged Usages (1)' }),
  ).toBeVisible();
  await expect(diningBenefitCard).toContainText('Team lunch');
});
