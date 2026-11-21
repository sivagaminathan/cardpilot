export const DEFAULT_RULE_STALENESS_DAYS = 180;

const MS_PER_UTC_DAY = 86_400_000;
const ISO_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

function parseIsoDateToUtcDay(isoDate: string): number | null {
  const match = ISO_DATE_PATTERN.exec(isoDate.trim());
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const utcMs = Date.UTC(year, month - 1, day);
  const check = new Date(utcMs);
  if (
    check.getUTCFullYear() !== year ||
    check.getUTCMonth() !== month - 1 ||
    check.getUTCDate() !== day
  ) {
    return null;
  }
  return Math.floor(utcMs / MS_PER_UTC_DAY);
}

function toUtcDay(referenceDate: Date | string): number | null {
  if (typeof referenceDate === 'string') {
    return parseIsoDateToUtcDay(referenceDate);
  }
  if (Number.isNaN(referenceDate.getTime())) {
    return null;
  }
  return Math.floor(
    Date.UTC(referenceDate.getFullYear(), referenceDate.getMonth(), referenceDate.getDate()) /
      MS_PER_UTC_DAY,
  );
}

export interface RuleStalenessResult {
  ageDays: number | null;
  isStale: boolean;
  thresholdDays: number;
}

/**
 * Determine whether a rule's last_reviewed_on date is strictly older than thresholdDays
 * calendar days relative to referenceDate. Exactly thresholdDays old is not stale.
 */
export function getRuleStaleness(
  lastReviewedOn: string,
  referenceDate: Date | string = new Date(),
  thresholdDays: number = DEFAULT_RULE_STALENESS_DAYS,
): RuleStalenessResult {
  const reviewedDay = parseIsoDateToUtcDay(lastReviewedOn);
  const refDay = toUtcDay(referenceDate);
  if (reviewedDay === null || refDay === null) {
    return { ageDays: null, isStale: false, thresholdDays };
  }
  const ageDays = refDay - reviewedDay;
  return {
    ageDays,
    isStale: ageDays > thresholdDays,
    thresholdDays,
  };
}
