import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  ApiError,
  addProfileCard,
  deleteProfileCard,
  fetchCardProductRules,
  fetchCardProducts,
  fetchCategories,
  fetchMerchants,
  fetchProfileBenefits,
  fetchProfileCards,
  fetchProfiles,
  fetchRewardsSummary,
  getApiBaseUrl,
  recommendCards,
  resetProfile,
  updateProfileCard,
} from './client';

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

  it('fetches profile cards, benefits, and rewards summary and propagates errors', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [{ id: 10, nickname: 'Daily Cash', is_active: true }],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [{ benefit_id: 20, name: 'Monthly Dining Credit', status: 'unused' }],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          profile_id: 1,
          profile_slug: 'maya',
          currencies: [],
          estimated_total_usd_cents: 0,
          estimated_total_label: 'Estimated USD',
          excluded_unvalued_currency_codes: [],
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ title: 'Not Found', status: 404, detail: 'Profile not found' }),
      } as Response);

    const cards = await fetchProfileCards('maya/1', 'https://api.cardpilot.demo');
    expect(cards).toHaveLength(1);
    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'https://api.cardpilot.demo/api/v1/profiles/maya%2F1/cards',
      expect.objectContaining({ method: 'GET' }),
    );

    const benefits = await fetchProfileBenefits('maya', 'https://api.cardpilot.demo/api/v1/');
    expect(benefits).toHaveLength(1);
    expect(fetchSpy).toHaveBeenNthCalledWith(
      2,
      'https://api.cardpilot.demo/api/v1/profiles/maya/benefits',
      expect.objectContaining({ method: 'GET' }),
    );

    const summary = await fetchRewardsSummary('maya');
    expect(summary.profile_slug).toBe('maya');
    expect(fetchSpy).toHaveBeenNthCalledWith(
      3,
      '/api/v1/profiles/maya/rewards/summary',
      expect.objectContaining({ method: 'GET' }),
    );

    await expect(fetchRewardsSummary('missing')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      detail: 'Profile not found',
    });
  });

  it('fetches catalog products and rules, manages profile cards, handles 204, and surfaces 409/422 errors', async () => {
    const deleteJsonSpy = vi.fn(async () => {
      throw new Error('should not parse 204 body');
    });

    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [{ id: 1, name: 'Northwind Cash Everyday' }],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [{ id: 10, rule_key: 'nwcash.dining', multiplier: '3.0' }],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => ({ id: 105, nickname: 'New Cash', is_active: true }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 105, nickname: 'New Cash', is_active: false }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 204,
        json: deleteJsonSpy,
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: async () => ({
          title: 'Conflict',
          status: 409,
          detail: "Profile already holds 'New Cash' for this card product.",
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({
          title: 'Unprocessable Entity',
          status: 422,
          detail: 'Validation failed.',
          errors: [
            {
              loc: ['body', 'nickname'],
              msg: 'Value must not contain 13-19 digit card numbers.',
              type: 'value_error',
            },
          ],
        }),
      } as Response);

    const products = await fetchCardProducts('https://api.cardpilot.demo');
    expect(products).toHaveLength(1);
    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'https://api.cardpilot.demo/api/v1/card-products',
      expect.objectContaining({ method: 'GET' }),
    );

    const rules = await fetchCardProductRules(1, 'https://api.cardpilot.demo');
    expect(rules).toHaveLength(1);
    expect(fetchSpy).toHaveBeenNthCalledWith(
      2,
      'https://api.cardpilot.demo/api/v1/card-products/1/rules',
      expect.objectContaining({ method: 'GET' }),
    );

    const created = await addProfileCard(
      'maya/1',
      { card_product_id: 1, nickname: 'New Cash', opened_on: '2026-01-15', is_active: true },
      'https://api.cardpilot.demo',
    );
    expect(created.id).toBe(105);
    expect(fetchSpy).toHaveBeenNthCalledWith(
      3,
      'https://api.cardpilot.demo/api/v1/profiles/maya%2F1/cards',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          card_product_id: 1,
          nickname: 'New Cash',
          opened_on: '2026-01-15',
          is_active: true,
        }),
      }),
    );

    const updated = await updateProfileCard('maya/1', 105, { is_active: false });
    expect(updated.is_active).toBe(false);
    expect(fetchSpy).toHaveBeenNthCalledWith(
      4,
      '/api/v1/profiles/maya%2F1/cards/105',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ is_active: false }),
      }),
    );

    await expect(deleteProfileCard('maya/1', 105)).resolves.toBeUndefined();
    expect(deleteJsonSpy).not.toHaveBeenCalled();
    expect(fetchSpy).toHaveBeenNthCalledWith(
      5,
      '/api/v1/profiles/maya%2F1/cards/105',
      expect.objectContaining({ method: 'DELETE' }),
    );

    await expect(
      addProfileCard('maya', { card_product_id: 1, nickname: 'New Cash', is_active: true }),
    ).rejects.toMatchObject({
      name: 'ApiError',
      status: 409,
      detail: "Profile already holds 'New Cash' for this card product.",
    });

    await expect(
      addProfileCard('maya', { card_product_id: 1, nickname: '4111111111111111', is_active: true }),
    ).rejects.toMatchObject({
      name: 'ApiError',
      status: 422,
      errors: [
        {
          loc: ['body', 'nickname'],
          msg: 'Value must not contain 13-19 digit card numbers.',
          type: 'value_error',
        },
      ],
    });
  });

  it('fetches categories and merchants and posts recommendation requests', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [{ id: 1, code: 'dining', name: 'Dining' }],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [{ id: 5, name: 'Harbor Bistro', default_category_code: 'dining', tags: [] }],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          ranked: [],
          unranked: [],
          ineligible: [],
          global_notes: [],
          engine_version: '1.0.0',
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({
          title: 'Unprocessable Entity',
          status: 422,
          detail: 'Validation failed.',
          errors: [
            {
              loc: ['body', 'amount_cents'],
              msg: 'Input should be greater than 0',
              type: 'greater_than',
            },
          ],
        }),
      } as Response);

    const categories = await fetchCategories('https://api.cardpilot.demo');
    expect(categories).toHaveLength(1);
    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'https://api.cardpilot.demo/api/v1/categories',
      expect.objectContaining({ method: 'GET' }),
    );

    const merchants = await fetchMerchants('https://api.cardpilot.demo');
    expect(merchants).toHaveLength(1);
    expect(fetchSpy).toHaveBeenNthCalledWith(
      2,
      'https://api.cardpilot.demo/api/v1/merchants',
      expect.objectContaining({ method: 'GET' }),
    );

    const rec = await recommendCards(
      'maya/1',
      {
        amount_cents: 12500,
        category_code: 'dining',
        merchant_id: 5,
        purchase_date: '2026-11-20',
        card_ids: [101],
      },
      'https://api.cardpilot.demo',
    );
    expect(rec.engine_version).toBe('1.0.0');
    expect(fetchSpy).toHaveBeenNthCalledWith(
      3,
      'https://api.cardpilot.demo/api/v1/profiles/maya%2F1/recommendations',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          amount_cents: 12500,
          category_code: 'dining',
          merchant_id: 5,
          purchase_date: '2026-11-20',
          card_ids: [101],
        }),
      }),
    );

    await expect(
      recommendCards('maya', { amount_cents: 0, category_code: 'dining' }),
    ).rejects.toMatchObject({
      name: 'ApiError',
      status: 422,
      errors: [
        {
          loc: ['body', 'amount_cents'],
          msg: 'Input should be greater than 0',
          type: 'greater_than',
        },
      ],
    });
  });
});
