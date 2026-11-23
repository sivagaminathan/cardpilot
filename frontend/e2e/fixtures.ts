import { test as base, expect, type APIRequestContext } from '@playwright/test';
import type { ProfileResetResponse } from '../src/api/client';

export const DEMO_PROFILE_KEYS = ['maya', 'dev'] as const;

export function getPlaywrightApiBaseUrl(
  configuredUrl: string | undefined = process.env.PLAYWRIGHT_API_BASE_URL,
): string {
  const raw = configuredUrl?.trim() || 'http://localhost:8000';
  const normalized = raw.replace(/\/+$/, '');
  return normalized.endsWith('/api/v1') ? normalized : `${normalized}/api/v1`;
}

export async function resetDemoProfile(
  request: APIRequestContext,
  profileKey: string,
): Promise<ProfileResetResponse> {
  const apiBase = getPlaywrightApiBaseUrl();
  const url = `${apiBase}/profiles/${encodeURIComponent(profileKey)}/reset`;
  const response = await request.post(url);
  if (!response.ok()) {
    const bodyText = await response.text().catch(() => '');
    throw new Error(
      `Failed to reset demo profile "${profileKey}" (${response.status()} ${response.statusText()}): ${bodyText}`,
    );
  }
  const data = (await response.json()) as ProfileResetResponse;
  if (data.status !== 'reset' || data.profile?.slug !== profileKey) {
    throw new Error(
      `Unexpected reset response for "${profileKey}": ${JSON.stringify(data)}`,
    );
  }
  return data;
}

export async function resetAllDemoProfiles(request: APIRequestContext): Promise<void> {
  for (const profileKey of DEMO_PROFILE_KEYS) {
    await resetDemoProfile(request, profileKey);
  }
}

export const test = base.extend<{ resetProfiles: void }>({
  resetProfiles: [
    async ({ request }, use) => {
      await resetAllDemoProfiles(request);
      await use();
    },
    { auto: true },
  ],
});

export { expect };
