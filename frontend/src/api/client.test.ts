import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, fetchProfiles, getApiBaseUrl, resetProfile } from './client';

describe('API client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('resolves API base URL from bare origins and /api/v1 URLs without duplication', () => {
    expect(getApiBaseUrl(undefined)).toBe('/api/v1');
    expect(getApiBaseUrl('')).toBe('/api/v1');
    expect(getApiBaseUrl('   ')).toBe('/api/v1');
    expect(getApiBaseUrl('https://api.cardpilot.demo')).toBe('https://api.cardpilot.demo/api/v1');
    expect(getApiBaseUrl('https://api.cardpilot.demo/')).toBe('https://api.cardpilot.demo/api/v1');
    expect(getApiBaseUrl('https://api.cardpilot.demo/api/v1')).toBe(
      'https://api.cardpilot.demo/api/v1',
    );
    expect(getApiBaseUrl('https://api.cardpilot.demo/api/v1/')).toBe(
      'https://api.cardpilot.demo/api/v1',
    );
  });

  it('fetches profiles and resets a profile using typed endpoints', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [
          { id: 1, slug: 'maya', display_name: 'Maya — The Optimizer', is_demo: true },
        ],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          status: 'reset',
          profile: { id: 1, slug: 'maya', display_name: 'Maya — The Optimizer', is_demo: true },
          cards_restored: 4,
          valuations_restored: 2,
        }),
      } as Response);

    const profiles = await fetchProfiles('https://api.cardpilot.demo/api/v1');
    expect(profiles).toHaveLength(1);
    expect(profiles[0].slug).toBe('maya');
    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'https://api.cardpilot.demo/api/v1/profiles',
      expect.objectContaining({ method: 'GET' }),
    );

    const reset = await resetProfile('maya', 'https://api.cardpilot.demo/api/v1');
    expect(reset.cards_restored).toBe(4);
    expect(fetchSpy).toHaveBeenNthCalledWith(
      2,
      'https://api.cardpilot.demo/api/v1/profiles/maya/reset',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('parses RFC 9457 Problem Details into ApiError', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({
        type: 'https://cardpilot.demo/errors/validation-error',
        title: 'Unprocessable Entity',
        status: 422,
        detail: 'Request validation failed.',
        instance: '/api/v1/profiles/maya/transactions',
        errors: [{ loc: ['body', 'amount_cents'], msg: 'Input should be > 0', type: 'greater_than' }],
      }),
    } as Response);

    await expect(fetchProfiles()).rejects.toMatchObject({
      name: 'ApiError',
      status: 422,
      title: 'Unprocessable Entity',
      detail: 'Request validation failed.',
      type: 'https://cardpilot.demo/errors/validation-error',
      instance: '/api/v1/profiles/maya/transactions',
      errors: [{ loc: ['body', 'amount_cents'], msg: 'Input should be > 0', type: 'greater_than' }],
    });

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: async () => {
        throw new Error('not json');
      },
    } as unknown as Response);

    try {
      await fetchProfiles();
      expect.unreachable('Expected ApiError');
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(503);
      expect((err as ApiError).title).toBe('HTTP 503');
    }
  });
});
