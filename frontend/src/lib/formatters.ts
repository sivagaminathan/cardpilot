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

const USD_AMOUNT_PATTERN = /^\s*(?:(\d+)(?:\.(\d{1,2}))?|\.(\d{1,2}))\s*$/;

/**
 * Parse a positive USD string into integer cents without floating-point arithmetic.
 * Rejects zero, negative values, malformed strings, and more than 2 decimal places.
 */
export function parseUsdToCents(input: string): number | null {
  const match = USD_AMOUNT_PATTERN.exec(input);
  if (!match) {
    return null;
  }
  const dollarsStr = match[1] ?? '0';
  const rawCents = match[2] ?? match[3] ?? '';
  const centsStr = rawCents.padEnd(2, '0');
  const dollars = Number.parseInt(dollarsStr, 10);
  const cents = Number.parseInt(centsStr, 10);
  const totalCents = dollars * 100 + cents;
  if (!Number.isSafeInteger(totalCents) || totalCents <= 0) {
    return null;
  }
  return totalCents;
}

/**
 * Return today's local calendar date formatted as YYYY-MM-DD.
 */
export function getTodayLocalIsoDate(now: Date = new Date()): string {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}
