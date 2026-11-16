/**
 * Format integer cents to a standard USD currency string without binary float drift.
 * Examples:
 *   formatCentsToUsd(10000) -> "$100.00"
 *   formatCentsToUsd(95) -> "$0.95"
 *   formatCentsToUsd(0) -> "$0.00"
 */
export function formatCentsToUsd(centsInput: number | string): string {
  const cents = typeof centsInput === 'string' ? parseInt(centsInput, 10) : Math.round(centsInput);
  if (isNaN(cents)) {
    return '$0.00';
  }

  const isNegative = cents < 0;
  const absCents = Math.abs(cents);
  const dollars = Math.floor(absCents / 100);
  const remainder = absCents % 100;
  const remainderStr = remainder.toString().padStart(2, '0');

  const formattedDollars = dollars.toLocaleString('en-US');
  return `${isNegative ? '-' : ''}$${formattedDollars}.${remainderStr}`;
}

/**
 * Format reward units with currency name.
 */
export function formatRewardUnits(units: number | string, currencyName: string): string {
  const numStr = typeof units === 'number' ? units.toFixed(2) : units;
  return `${numStr} ${currencyName}`;
}
