import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { App } from './App';
import { BackendStatus, getHealthUrl } from './components/BackendStatus';
import { formatCentsToUsd, getTodayLocalIsoDate, parseUsdToCents } from './lib/formatters';
import { getRuleStaleness } from './lib/rules';

const MOCK_PROFILES = [
  { id: 1, slug: 'maya', display_name: 'Maya — The Optimizer', is_demo: true },
  { id: 2, slug: 'dev', display_name: 'Dev — Benefit Tracker', is_demo: true },
];

const MOCK_CARDS: Record<string, unknown[]> = {
  maya: [
    {
      id: 101,
      profile_id: 1,
      card_product_id: 1,
      nickname: 'Daily Cash',
      opened_on: '2025-02-01',
      is_active: true,
      card_product: {
        id: 1,
        issuer_name: 'Northwind Bank',
        name: 'Northwind Cash Everyday',
        annual_fee_cents: 0,
        network_label: 'Visa',
        description: 'Everyday cash back',
        reward_currency: {
          id: 1,
          code: 'NW_CASH',
          name: 'Northwind Cash',
          kind: 'cash_back',
          is_cash_equivalent: true,
        },
      },
    },
    {
      id: 102,
      profile_id: 1,
      card_product_id: 2,
      nickname: 'Skyward Explorer',
      opened_on: '2025-08-01',
      is_active: false,
      card_product: {
        id: 2,
        issuer_name: 'Skyward Financial',
        name: 'Skyward Miles Explorer',
        annual_fee_cents: 9500,
        network_label: 'Mastercard',
        description: 'Travel miles',
        reward_currency: {
          id: 3,
          code: 'SKY_MILES',
          name: 'Skyward Miles',
          kind: 'miles',
          is_cash_equivalent: false,
        },
      },
    },
  ],
  dev: [
    {
      id: 201,
      profile_id: 2,
      card_product_id: 3,
      nickname: 'Summit Points',
      opened_on: '2025-01-10',
      is_active: true,
      card_product: {
        id: 3,
        issuer_name: 'Horizon Bancorp',
        name: 'Horizon Summit Points',
        annual_fee_cents: 25000,
        network_label: 'Visa',
        description: 'Travel points',
        reward_currency: {
          id: 4,
          code: 'HORIZON_PTS',
          name: 'Horizon Points',
          kind: 'points',
          is_cash_equivalent: false,
        },
      },
    },
  ],
};

const MOCK_BENEFITS: Record<string, unknown[]> = {
  maya: [
    {
      benefit_id: 1,
      profile_card_id: 101,
      card_name: 'Daily Cash',
      card_product_id: 1,
      card_product_name: 'Northwind Cash Everyday',
      name: 'Monthly Dining Credit',
      benefit_type: 'credit',
      value_cents: 1500,
      reset_period: 'monthly',
      notes: '',
      next_reset_date: '2026-12-01',
      days_until_reset: 10,
      used_cents: 0,
      remaining_cents: 1500,
      over_used_cents: 0,
      is_over_used: false,
      usage_count: 0,
      status: 'unused',
      usages: [],
    },
    {
      benefit_id: 2,
      profile_card_id: 102,
      card_name: 'Skyward Explorer',
      card_product_id: 2,
      card_product_name: 'Skyward Miles Explorer',
      name: 'Priority Boarding Perk',
      benefit_type: 'perk',
      value_cents: null,
      reset_period: 'card_year',
      notes: '',
      next_reset_date: null,
      days_until_reset: 1,
      used_cents: null,
      remaining_cents: null,
      over_used_cents: null,
      is_over_used: false,
      usage_count: 0,
      status: 'unused',
      usages: [],
    },
    // Excluded: null days_until_reset
    {
      benefit_id: 7,
      profile_card_id: 102,
      card_name: 'Skyward Explorer',
      card_product_id: 2,
      card_product_name: 'Skyward Miles Explorer',
      name: 'Unknown Period Perk',
      benefit_type: 'perk',
      value_cents: null,
      reset_period: 'card_year',
      notes: '',
      next_reset_date: null,
      days_until_reset: null,
      used_cents: null,
      remaining_cents: null,
      over_used_cents: null,
      is_over_used: false,
      usage_count: 0,
      status: 'unused',
      usages: [],
    },
    // Excluded: already used
    {
      benefit_id: 3,
      profile_card_id: 101,
      card_name: 'Daily Cash',
      card_product_id: 1,
      card_product_name: 'Northwind Cash Everyday',
      name: 'Used Streaming Credit',
      benefit_type: 'credit',
      value_cents: 1000,
      reset_period: 'monthly',
      notes: '',
      next_reset_date: '2026-12-01',
      days_until_reset: 10,
      used_cents: 1000,
      remaining_cents: 0,
      over_used_cents: 0,
      is_over_used: false,
      usage_count: 1,
      status: 'used',
      usages: [],
    },
    // Excluded: > 30 days
    {
      benefit_id: 4,
      profile_card_id: 101,
      card_name: 'Daily Cash',
      card_product_id: 1,
      card_product_name: 'Northwind Cash Everyday',
      name: 'Far Future Credit',
      benefit_type: 'credit',
      value_cents: 5000,
      reset_period: 'calendar_year',
      notes: '',
      next_reset_date: '2027-01-01',
      days_until_reset: 42,
      used_cents: 0,
      remaining_cents: 5000,
      over_used_cents: 0,
      is_over_used: false,
      usage_count: 0,
      status: 'unused',
      usages: [],
    },
    // Excluded: negative days_until_reset
    {
      benefit_id: 5,
      profile_card_id: 101,
      card_name: 'Daily Cash',
      card_product_id: 1,
      card_product_name: 'Northwind Cash Everyday',
      name: 'Expired Credit',
      benefit_type: 'credit',
      value_cents: 2000,
      reset_period: 'monthly',
      notes: '',
      next_reset_date: '2026-11-01',
      days_until_reset: -1,
      used_cents: 0,
      remaining_cents: 2000,
      over_used_cents: 0,
      is_over_used: false,
      usage_count: 0,
      status: 'unused',
      usages: [],
    },
  ],
  dev: [
    {
      benefit_id: 6,
      profile_card_id: 201,
      card_name: 'Summit Points',
      card_product_id: 3,
      card_product_name: 'Horizon Summit Points',
      name: 'Quarterly Streaming Credit',
      benefit_type: 'credit',
      value_cents: 2500,
      reset_period: 'quarterly',
      notes: '',
      next_reset_date: '2026-12-20',
      days_until_reset: 30,
      used_cents: 0,
      remaining_cents: 2500,
      over_used_cents: 0,
      is_over_used: false,
      usage_count: 0,
      status: 'unused',
      usages: [],
    },
  ],
};

const MOCK_REWARDS: Record<string, unknown> = {
  maya: {
    profile_id: 1,
    profile_slug: 'maya',
    currencies: [
      {
        reward_currency_id: 1,
        reward_currency_code: 'NW_CASH',
        reward_currency_name: 'Northwind Cash',
        reward_currency_kind: 'cash_back',
        total_reward_units: '130.0000',
        transaction_count: 2,
        is_valued: true,
        valuation_status: 'valued',
        current_cents_per_unit: '1.0000',
        is_user_set: false,
        estimated_value_cents: 130,
        limitation_note: null,
      },
      {
        reward_currency_id: 3,
        reward_currency_code: 'SKY_MILES',
        reward_currency_name: 'Skyward Miles',
        reward_currency_kind: 'miles',
        total_reward_units: '200.0000',
        transaction_count: 1,
        is_valued: false,
        valuation_status: 'unvalued',
        current_cents_per_unit: null,
        is_user_set: null,
        estimated_value_cents: null,
        limitation_note: 'No estimated value is set for SKY_MILES.',
      },
    ],
    estimated_total_usd_cents: 130,
    estimated_total_label:
      'Estimated USD value based on current valuations (excludes unvalued currencies)',
    excluded_unvalued_currency_codes: ['SKY_MILES'],
    limitation_message: 'Excluded unvalued currencies from estimated USD total: SKY_MILES.',
  },
  dev: {
    profile_id: 2,
    profile_slug: 'dev',
    currencies: [
      {
        reward_currency_id: 4,
        reward_currency_code: 'HORIZON_PTS',
        reward_currency_name: 'Horizon Points',
        reward_currency_kind: 'points',
        total_reward_units: '500.0000',
        transaction_count: 1,
        is_valued: true,
        valuation_status: 'valued',
        current_cents_per_unit: '1.5000',
        is_user_set: true,
        estimated_value_cents: 750,
        limitation_note: null,
      },
    ],
    estimated_total_usd_cents: 750,
    estimated_total_label:
      'Estimated USD value based on current valuations (excludes unvalued currencies)',
    excluded_unvalued_currency_codes: [],
    limitation_message: null,
  },
};

function mockFetchHandlers(options?: {
  profiles?: typeof MOCK_PROFILES;
  profilesOk?: boolean;
  resetOk?: boolean;
  cardsOk?: boolean;
  benefitsOk?: boolean;
  rewardsOk?: boolean;
  emptyDashboard?: boolean;
}) {
  const profiles = options?.profiles ?? MOCK_PROFILES;
  const profilesOk = options?.profilesOk ?? true;
  const resetOk = options?.resetOk ?? true;
  const cardsOk = options?.cardsOk ?? true;
  const benefitsOk = options?.benefitsOk ?? true;
  const rewardsOk = options?.rewardsOk ?? true;
  const emptyDashboard = options?.emptyDashboard ?? false;

  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;

    if (url.endsWith('/healthz')) {
      return {
        ok: true,
        status: 200,
        json: async () => ({ status: 'ok', version: '0.1.0' }),
      } as Response;
    }

    if (url.endsWith('/profiles') && (!init?.method || init.method === 'GET')) {
      if (!profilesOk) {
        return {
          ok: false,
          status: 500,
          json: async () => ({
            title: 'Internal Server Error',
            status: 500,
            detail: 'Database unavailable',
          }),
        } as Response;
      }
      return { ok: true, status: 200, json: async () => profiles } as Response;
    }

    if (url.includes('/profiles/') && url.endsWith('/reset') && init?.method === 'POST') {
      if (!resetOk) {
        return {
          ok: false,
          status: 500,
          json: async () => ({
            title: 'Internal Server Error',
            status: 500,
            detail: 'Reset failed',
          }),
        } as Response;
      }
      const slug = url.split('/profiles/')[1].replace('/reset', '');
      const prof = profiles.find((p) => p.slug === slug) ?? profiles[0];
      return {
        ok: true,
        status: 200,
        json: async () => ({
          status: 'reset',
          profile: prof,
          cards_restored: 4,
          valuations_restored: 2,
        }),
      } as Response;
    }

    const profileMatch = url.match(/\/profiles\/([^/]+)\/(cards|benefits|rewards\/summary)$/);
    if (profileMatch) {
      const [, slug, resource] = profileMatch;
      if (resource === 'cards') {
        if (!cardsOk) {
          return {
            ok: false,
            status: 500,
            json: async () => ({ title: 'Error', status: 500, detail: 'Cards load failed' }),
          } as Response;
        }
        return {
          ok: true,
          status: 200,
          json: async () => (emptyDashboard ? [] : (MOCK_CARDS[slug] ?? [])),
        } as Response;
      }
      if (resource === 'benefits') {
        if (!benefitsOk) {
          return {
            ok: false,
            status: 500,
            json: async () => ({ title: 'Error', status: 500, detail: 'Benefits load failed' }),
          } as Response;
        }
        return {
          ok: true,
          status: 200,
          json: async () => (emptyDashboard ? [] : (MOCK_BENEFITS[slug] ?? [])),
        } as Response;
      }
      if (resource === 'rewards/summary') {
        if (!rewardsOk) {
          return {
            ok: false,
            status: 500,
            json: async () => ({ title: 'Error', status: 500, detail: 'Rewards load failed' }),
          } as Response;
        }
        return {
          ok: true,
          status: 200,
          json: async () =>
            emptyDashboard
              ? {
                  profile_id: 1,
                  profile_slug: slug,
                  currencies: [],
                  estimated_total_usd_cents: 0,
                  estimated_total_label: 'Estimated USD',
                  excluded_unvalued_currency_codes: [],
                  limitation_message: null,
                }
              : MOCK_REWARDS[slug],
        } as Response;
      }
    }

    return {
      ok: false,
      status: 404,
      json: async () => ({ title: 'Not Found', status: 404 }),
    } as Response;
  });
}

describe('formatCentsToUsd helper', () => {
  it('formats integer cents correctly without float arithmetic', () => {
    expect(formatCentsToUsd(10000)).toBe('$100.00');
    expect(formatCentsToUsd(9500)).toBe('$95.00');
    expect(formatCentsToUsd(95)).toBe('$0.95');
    expect(formatCentsToUsd(0)).toBe('$0.00');
    expect(formatCentsToUsd(-500)).toBe('-$5.00');
  });

  it('handles string input safely', () => {
    expect(formatCentsToUsd('25000')).toBe('$250.00');
    expect(formatCentsToUsd('invalid')).toBe('$0.00');
  });
});

describe('CardPilot App Shell, Dashboard, Router, and Profile Picker', () => {
  beforeEach(() => {
    mockFetchHandlers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('loads live dashboard cards, 0-30 day unused benefit alerts, and per-currency rewards', async () => {
    render(<App />);

    expect(screen.getByRole('heading', { level: 1, name: /CardPilot/i })).toBeInTheDocument();
    const banner = screen.getByRole('complementary', { name: /Demo Disclaimer/i });
    expect(
      within(banner).getByText(/Sample data only\. Not issuer terms\. Not financial advice\./i),
    ).toBeInTheDocument();

    // Cards widget
    expect(await screen.findByRole('heading', { level: 4, name: 'Daily Cash' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 4, name: 'Skyward Explorer' })).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();

    // Benefit alerts: includes unused 0..30 days (Monthly Dining Credit, Priority Boarding Perk)
    expect(screen.getByRole('heading', { level: 4, name: 'Monthly Dining Credit' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 4, name: 'Priority Boarding Perk' })).toBeInTheDocument();
    expect(screen.getByText('10 days left')).toBeInTheDocument();
    expect(screen.getByText('1 day left')).toBeInTheDocument();
    expect(screen.getByText('2 Active Alerts')).toBeInTheDocument();
    // Excludes used, > 30 days, negative days, and null days_until_reset
    expect(screen.queryByText('Used Streaming Credit')).not.toBeInTheDocument();
    expect(screen.queryByText('Far Future Credit')).not.toBeInTheDocument();
    expect(screen.queryByText('Expired Credit')).not.toBeInTheDocument();
    expect(screen.queryByText('Unknown Period Perk')).not.toBeInTheDocument();

    // Rewards snapshot: per-currency units + separate estimated USD + unvalued limitation
    expect(screen.getByText('130.0000 NW_CASH')).toBeInTheDocument();
    expect(screen.getByText('200.0000 SKY_MILES')).toBeInTheDocument();
    expect(screen.getByText('Unvalued')).toBeInTheDocument();
    expect(
      screen.getByText('Excluded unvalued currencies from estimated USD total: SKY_MILES.'),
    ).toBeInTheDocument();
  });

  it('refetches dashboard widgets on profile switch and after demo reset', async () => {
    const fetchSpy = mockFetchHandlers();
    render(<App />);

    const select = await screen.findByLabelText(/Select demo profile/i);
    fireEvent.change(select, { target: { value: 'dev' } });

    expect(
      await screen.findByRole('heading', { level: 4, name: 'Summit Points' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Quarterly Streaming Credit')).toBeInTheDocument();
    expect(screen.getByText('500.0000 HORIZON_PTS')).toBeInTheDocument();

    const callsBeforeReset = fetchSpy.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: 'Reset Demo Data' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Reset' }));

    await waitFor(() => {
      expect(screen.getByText(/4 cards, 2 valuations restored/i)).toBeInTheDocument();
    });

    await waitFor(() => {
      const newCalls = fetchSpy.mock.calls.slice(callsBeforeReset).map(([u]) => String(u));
      expect(newCalls.some((u) => u.endsWith('/profiles/dev/cards'))).toBe(true);
      expect(newCalls.some((u) => u.endsWith('/profiles/dev/benefits'))).toBe(true);
      expect(newCalls.some((u) => u.endsWith('/profiles/dev/rewards/summary'))).toBe(true);
    });
  });

  it('handles independent widget error/retry and empty states', async () => {
    vi.restoreAllMocks();
    mockFetchHandlers({ cardsOk: false, benefitsOk: false, rewardsOk: false });
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Cards load failed/i)).toBeInTheDocument();
      expect(screen.getByText(/Benefits load failed/i)).toBeInTheDocument();
      expect(screen.getByText(/Rewards load failed/i)).toBeInTheDocument();
    });

    vi.restoreAllMocks();
    mockFetchHandlers({ emptyDashboard: true });
    fireEvent.click(screen.getByRole('button', { name: 'Retry Cards' }));
    fireEvent.click(screen.getByRole('button', { name: 'Retry Benefit Alerts' }));
    fireEvent.click(screen.getByRole('button', { name: 'Retry Rewards Snapshot' }));

    await waitFor(() => {
      expect(screen.getByText('No cards added to this profile yet.')).toBeInTheDocument();
      expect(screen.getByText('No unused benefits expiring within 30 days.')).toBeInTheDocument();
      expect(
        screen.getByText('No reward activity recorded for this profile yet.'),
      ).toBeInTheDocument();
    });
  });

  it('displays error alert on failed reset without clearing selected profile', async () => {
    vi.restoreAllMocks();
    mockFetchHandlers({ resetOk: false });
    render(<App />);

    const select = await screen.findByLabelText(/Select demo profile/i);
    fireEvent.change(select, { target: { value: 'dev' } });

    fireEvent.click(screen.getByRole('button', { name: 'Reset Demo Data' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Reset' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/Reset failed/i);
    });
    expect(screen.queryByText(/valuations restored/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Select demo profile/i)).toHaveValue('dev');
  });

  it('navigates across all routes and dashboard action buttons while keeping disclaimer visible', async () => {
    render(<App />);
    await screen.findByRole('heading', { level: 4, name: 'Daily Cash' });

    fireEvent.click(screen.getByRole('button', { name: 'Manage Cards' }));
    expect(
      screen.getByRole('heading', { level: 2, name: /Add Card from Fictional Catalog/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole('link', { name: /^Dashboard$/i }));
    fireEvent.click(screen.getByRole('button', { name: 'View All Benefits' }));
    expect(screen.getByRole('heading', { level: 2, name: /Benefits View/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('link', { name: /^Dashboard$/i }));
    fireEvent.click(screen.getByRole('button', { name: 'View Full Rewards' }));
    expect(screen.getByRole('heading', { level: 2, name: /Rewards View/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('link', { name: /^Compare$/i }));
    expect(
      screen.getByRole('heading', { level: 2, name: /Compare Cards for Purchase/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole('link', { name: /^Rules$/i }));
    expect(
      screen.getByRole('heading', { level: 2, name: /Earning Rules & Source Provenance/i }),
    ).toBeInTheDocument();

    const banner = screen.getByRole('complementary', { name: /Demo Disclaimer/i });
    expect(
      within(banner).getByText(/Sample data only\. Not issuer terms\. Not financial advice\./i),
    ).toBeInTheDocument();
  });
});

describe('BackendStatus component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it('derives health URL from VITE_API_BASE_URL or falls back to /healthz', () => {
    expect(getHealthUrl(undefined)).toBe('/healthz');
    expect(getHealthUrl('')).toBe('/healthz');
    expect(getHealthUrl('   ')).toBe('/healthz');
    expect(getHealthUrl('https://cardpilot-api-dev.onrender.com/api/v1')).toBe(
      'https://cardpilot-api-dev.onrender.com/healthz',
    );
    expect(getHealthUrl('https://cardpilot-api-dev.onrender.com/api/v1/')).toBe(
      'https://cardpilot-api-dev.onrender.com/healthz',
    );
  });

  it('requests backend /healthz URL when VITE_API_BASE_URL is configured', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://cardpilot-api-dev.onrender.com/api/v1');
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'ok', version: '0.1.0' }),
    } as Response);

    render(<BackendStatus />);

    await waitFor(() => {
      expect(screen.getByText('API Connected')).toBeInTheDocument();
    });
    expect(fetchSpy).toHaveBeenCalledWith('https://cardpilot-api-dev.onrender.com/healthz');
  });

  it('displays API Offline when /healthz fetch fails or returns non-200', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error('Network error'));
    const { unmount } = render(<BackendStatus />);
    await waitFor(() => {
      expect(screen.getByText('API Offline')).toBeInTheDocument();
    });
    unmount();

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 503,
    } as Response);
    render(<BackendStatus />);
    await waitFor(() => {
      expect(screen.getByText('API Offline')).toBeInTheDocument();
    });
  });
});

const MOCK_CATALOG_PRODUCTS = [
  {
    id: 1,
    issuer_name: 'Northwind Bank',
    name: 'Northwind Cash Everyday',
    annual_fee_cents: 0,
    network_label: 'Visa',
    description: 'Everyday cash back card',
    reward_currency: {
      id: 1,
      code: 'NW_CASH',
      name: 'Northwind Cash',
      kind: 'cash_back',
      is_cash_equivalent: true,
    },
  },
  {
    id: 2,
    issuer_name: 'Skyward Financial',
    name: 'Skyward Miles Explorer',
    annual_fee_cents: 9500,
    network_label: 'Mastercard',
    description: 'Travel miles card',
    reward_currency: {
      id: 3,
      code: 'SKY_MILES',
      name: 'Skyward Miles',
      kind: 'miles',
      is_cash_equivalent: false,
    },
  },
  {
    id: 3,
    issuer_name: 'Horizon Bancorp',
    name: 'Horizon Summit Points',
    annual_fee_cents: 25000,
    network_label: 'Visa',
    description: 'Unheld by Maya catalog card',
    reward_currency: {
      id: 4,
      code: 'HORIZON_PTS',
      name: 'Horizon Points',
      kind: 'points',
      is_cash_equivalent: false,
    },
  },
];

// Reference date in tests: 2026-11-20
// 179 days before 2026-11-20 = 2026-05-25
// 180 days before 2026-11-20 = 2026-05-24
// 181 days before 2026-11-20 = 2026-05-23
const MOCK_PRODUCT_RULES: Record<number, unknown[]> = {
  1: [
    {
      id: 11,
      rule_key: 'nwcash.dining',
      version: 1,
      scope_type: 'category',
      category_code: 'DINING',
      merchant_name: null,
      multiplier: '3.0',
      priority: 10,
      rounding: 'nearest_cent',
      effective_from: '2026-01-01',
      effective_to: '2026-12-31',
      min_transaction_cents: 1000,
      min_period_spend_cents: null,
      threshold_period: null,
      post_cap_behavior: 'fallback_base',
      cap: {
        id: 1,
        cap_group_key: 'nwcash_dining_q',
        cap_amount_cents: 50000,
        period: 'quarterly',
      },
      exclusions: [
        {
          id: 1,
          exclusion_type: 'merchant_tag',
          target_category_code: null,
          target_merchant_name: null,
          target_tag: 'bakery_cafe',
          reason: 'Standalone bakeries excluded',
        },
      ],
      source: {
        id: 1,
        title: 'Northwind Sample Terms v1',
        kind: 'fictional_sample',
        url: 'https://example.invalid/northwind-terms',
        notes: 'Fictional dining rule',
        last_reviewed_on: '2026-05-24', // Exactly 180 days -> Fresh
      },
    },
    {
      id: 12,
      rule_key: 'nwcash.base',
      version: 1,
      scope_type: 'base',
      category_code: null,
      merchant_name: null,
      multiplier: '1.0',
      priority: 1,
      rounding: 'floor',
      effective_from: '2026-01-01',
      effective_to: null,
      min_transaction_cents: null,
      min_period_spend_cents: null,
      threshold_period: null,
      post_cap_behavior: 'none',
      cap: null,
      exclusions: [],
      source: {
        id: 2,
        title: 'Northwind Legacy Archive',
        kind: 'fictional_sample',
        url: null,
        notes: '',
        last_reviewed_on: '2026-05-23', // 181 days -> Stale
      },
    },
  ],
  3: [
    {
      id: 31,
      rule_key: 'horizon.travel',
      version: 2,
      scope_type: 'category',
      category_code: 'TRAVEL',
      merchant_name: null,
      multiplier: '4.0',
      priority: 20,
      rounding: 'nearest_unit',
      effective_from: '2026-07-01',
      effective_to: null,
      min_transaction_cents: null,
      min_period_spend_cents: null,
      threshold_period: null,
      post_cap_behavior: 'none',
      cap: null,
      exclusions: [],
      source: {
        id: 3,
        title: 'Horizon Travel Guide',
        kind: 'public_doc_example',
        url: null,
        notes: 'Unheld catalog product rule',
        last_reviewed_on: '2026-05-25', // 179 days -> Fresh
      },
    },
  ],
};

function mockT39Fetch(options?: {
  catalogOk?: boolean;
  emptyCatalog?: boolean;
  cardsOk?: boolean;
  rulesOk?: boolean;
  emptyRules?: boolean;
  deleteOk?: boolean;
  addStatus?: number;
}) {
  const catalogOk = options?.catalogOk ?? true;
  const emptyCatalog = options?.emptyCatalog ?? false;
  const cardsOk = options?.cardsOk ?? true;
  const rulesOk = options?.rulesOk ?? true;
  const emptyRules = options?.emptyRules ?? false;
  const deleteOk = options?.deleteOk ?? true;
  const addStatus = options?.addStatus ?? 201;

  const cardsByProfile: Record<string, Array<Record<string, unknown>>> = {
    maya: JSON.parse(JSON.stringify(MOCK_CARDS.maya)),
    dev: JSON.parse(JSON.stringify(MOCK_CARDS.dev)),
  };
  let nextCardId = 300;

  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    const method = init?.method ?? 'GET';

    if (url.endsWith('/healthz')) {
      return {
        ok: true,
        status: 200,
        json: async () => ({ status: 'ok', version: '0.1.0' }),
      } as Response;
    }

    if (url.endsWith('/profiles') && method === 'GET') {
      return { ok: true, status: 200, json: async () => MOCK_PROFILES } as Response;
    }

    if (url.endsWith('/card-products') && method === 'GET') {
      if (!catalogOk) {
        return {
          ok: false,
          status: 503,
          json: async () => ({ title: 'Service Unavailable', status: 503, detail: 'Catalog down' }),
        } as Response;
      }
      return {
        ok: true,
        status: 200,
        json: async () => (emptyCatalog ? [] : MOCK_CATALOG_PRODUCTS),
      } as Response;
    }

    const rulesMatch = url.match(/\/card-products\/(\d+)\/rules$/);
    if (rulesMatch && method === 'GET') {
      if (!rulesOk) {
        return {
          ok: false,
          status: 500,
          json: async () => ({ title: 'Internal Error', status: 500, detail: 'Rules failed' }),
        } as Response;
      }
      const productId = Number(rulesMatch[1]);
      return {
        ok: true,
        status: 200,
        json: async () => (emptyRules ? [] : (MOCK_PRODUCT_RULES[productId] ?? [])),
      } as Response;
    }

    const cardsCollectionMatch = url.match(/\/profiles\/([^/]+)\/cards$/);
    if (cardsCollectionMatch) {
      const slug = decodeURIComponent(cardsCollectionMatch[1]);
      if (method === 'GET') {
        if (!cardsOk) {
          return {
            ok: false,
            status: 500,
            json: async () => ({ title: 'Internal Error', status: 500, detail: 'Cards failed' }),
          } as Response;
        }
        return {
          ok: true,
          status: 200,
          json: async () => cardsByProfile[slug] ?? [],
        } as Response;
      }

      if (method === 'POST') {
        const body = JSON.parse(String(init?.body ?? '{}')) as {
          card_product_id: number;
          nickname: string;
          opened_on?: string | null;
          is_active: boolean;
        };
        if (addStatus === 409) {
          return {
            ok: false,
            status: 409,
            json: async () => ({
              title: 'Conflict',
              status: 409,
              detail: `Profile already holds '${body.nickname}' for this card product.`,
            }),
          } as Response;
        }
        if (addStatus === 422) {
          return {
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
          } as Response;
        }
        const product =
          MOCK_CATALOG_PRODUCTS.find((p) => p.id === body.card_product_id) ??
          MOCK_CATALOG_PRODUCTS[0];
        const created = {
          id: nextCardId++,
          profile_id: slug === 'maya' ? 1 : 2,
          card_product_id: product.id,
          nickname: body.nickname,
          opened_on: body.opened_on ?? null,
          is_active: body.is_active,
          card_product: product,
        };
        cardsByProfile[slug] = [...(cardsByProfile[slug] ?? []), created];
        return { ok: true, status: 201, json: async () => created } as Response;
      }
    }

    const cardItemMatch = url.match(/\/profiles\/([^/]+)\/cards\/(\d+)$/);
    if (cardItemMatch) {
      const slug = decodeURIComponent(cardItemMatch[1]);
      const cardId = Number(cardItemMatch[2]);
      if (method === 'PATCH') {
        const body = JSON.parse(String(init?.body ?? '{}')) as { is_active?: boolean };
        const list = cardsByProfile[slug] ?? [];
        const target = list.find((c) => c.id === cardId);
        if (!target) {
          return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
        }
        if (typeof body.is_active === 'boolean') {
          target.is_active = body.is_active;
        }
        return { ok: true, status: 200, json: async () => target } as Response;
      }
      if (method === 'DELETE') {
        if (!deleteOk) {
          return {
            ok: false,
            status: 409,
            json: async () => ({
              title: 'Conflict',
              status: 409,
              detail: 'Cannot remove card with existing transactions.',
            }),
          } as Response;
        }
        cardsByProfile[slug] = (cardsByProfile[slug] ?? []).filter((c) => c.id !== cardId);
        return { ok: true, status: 204 } as Response;
      }
    }

    return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
  });
}

describe('T39 Cards and Rules views', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('computes rule staleness deterministically at 179, 180, and 181 calendar days', () => {
    expect(getRuleStaleness('2026-05-25', '2026-11-20')).toEqual({
      ageDays: 179,
      isStale: false,
      thresholdDays: 180,
    });
    expect(getRuleStaleness('2026-05-24', '2026-11-20')).toEqual({
      ageDays: 180,
      isStale: false,
      thresholdDays: 180,
    });
    expect(getRuleStaleness('2026-05-23', '2026-11-20')).toEqual({
      ageDays: 181,
      isStale: true,
      thresholdDays: 180,
    });
  });

  it('renders catalog and held cards, adds a card, and validates blank nickname client-side', async () => {
    const fetchSpy = mockT39Fetch();
    render(<App initialEntries={['/cards']} />);

    expect(await screen.findByText('Daily Cash')).toBeInTheDocument();
    expect(screen.getByText('Status: Active')).toBeInTheDocument();
    expect(screen.getByText('Status: Inactive')).toBeInTheDocument();

    const nicknameInput = screen.getByLabelText('Card Nickname');
    expect(nicknameInput).toHaveAttribute('aria-describedby', 'card-nickname-safety-hint');
    expect(
      screen.getByText('Do not enter real card numbers or sensitive data.'),
    ).toBeInTheDocument();

    // Blank nickname -> client-side validation, no POST
    fireEvent.change(nicknameInput, { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add Card' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Nickname is required and must not be blank.',
    );
    expect(fetchSpy.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);

    // Valid add
    fireEvent.change(screen.getByLabelText('Catalog Card Product'), { target: { value: '3' } });
    fireEvent.change(nicknameInput, { target: { value: 'Weekend Travel' } });
    fireEvent.change(screen.getByLabelText('Opened Date (optional)'), {
      target: { value: '2026-02-01' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add Card' }));

    expect(await screen.findByText('Weekend Travel')).toBeInTheDocument();
    expect(screen.getByText('Opened: 2026-02-01')).toBeInTheDocument();
    expect(screen.getByText(/Added "Weekend Travel"/)).toBeInTheDocument();
  });

  it('surfaces 409 duplicate and 422 validation errors from add card', async () => {
    mockT39Fetch({ addStatus: 409 });
    const { unmount } = render(<App initialEntries={['/cards']} />);
    await screen.findByText('Daily Cash');

    fireEvent.change(screen.getByLabelText('Card Nickname'), { target: { value: 'Daily Cash' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add Card' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Profile already holds 'Daily Cash' for this card product.",
    );
    unmount();

    mockT39Fetch({ addStatus: 422 });
    render(<App initialEntries={['/cards']} />);
    await screen.findByText('Daily Cash');

    fireEvent.change(screen.getByLabelText('Card Nickname'), {
      target: { value: '4111111111111111' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add Card' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Value must not contain 13-19 digit card numbers.',
    );
  });

  it('activates/deactivates cards and handles delete confirmation, success, and failure', async () => {
    mockT39Fetch({ deleteOk: true });
    const { unmount } = render(<App initialEntries={['/cards']} />);
    await screen.findByText('Daily Cash');

    const firstCard = screen.getAllByTestId('held-card-item')[0];
    fireEvent.click(within(firstCard).getByRole('button', { name: 'Deactivate' }));
    await waitFor(() => {
      expect(within(firstCard).getByText('Status: Inactive')).toBeInTheDocument();
    });

    // Delete with confirmation
    fireEvent.click(within(firstCard).getByRole('button', { name: 'Remove' }));
    expect(
      within(firstCard).getByRole('group', { name: 'Confirm removal of Daily Cash' }),
    ).toBeInTheDocument();
    fireEvent.click(within(firstCard).getByRole('button', { name: 'Confirm Remove' }));

    await waitFor(() => {
      expect(screen.queryByText('Daily Cash')).not.toBeInTheDocument();
    });
    unmount();

    // Failed delete preserves card and shows API error
    mockT39Fetch({ deleteOk: false });
    render(<App initialEntries={['/cards']} />);
    await screen.findByText('Daily Cash');

    const cardItem = screen.getAllByTestId('held-card-item')[0];
    fireEvent.click(within(cardItem).getByRole('button', { name: 'Remove' }));
    fireEvent.click(within(cardItem).getByRole('button', { name: 'Confirm Remove' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Cannot remove card with existing transactions.',
    );
    expect(screen.getByText('Daily Cash')).toBeInTheDocument();
  });

  it('isolates profile cards and clears transient feedback when switching profiles', async () => {
    mockT39Fetch();
    render(<App initialEntries={['/cards']} />);

    await screen.findByText('Daily Cash');
    const firstCard = screen.getAllByTestId('held-card-item')[0];
    fireEvent.click(within(firstCard).getByRole('button', { name: 'Deactivate' }));
    expect(await screen.findByText('"Daily Cash" is now Inactive.')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Select demo profile'), { target: { value: 'dev' } });

    expect(await screen.findByText('Summit Points')).toBeInTheDocument();
    expect(screen.queryByText('Daily Cash')).not.toBeInTheDocument();
    expect(screen.queryByText('"Daily Cash" is now Inactive.')).not.toBeInTheDocument();
  });

  it('renders /rules with source metadata, effective dates, null fields, unheld products, and 180/181 staleness', async () => {
    mockT39Fetch();
    render(<App initialEntries={['/rules']} rulesReferenceDate="2026-11-20" />);

    // Product 1 rules (one 180-day Fresh, one 181-day Stale with null optional fields)
    expect(await screen.findByText('nwcash.dining')).toBeInTheDocument();
    expect(screen.getByText('nwcash.base')).toBeInTheDocument();

    const ruleCards = screen.getAllByTestId('earning-rule-item');
    // 180 days -> Fresh
    expect(within(ruleCards[0]).getByText('Fresh')).toBeInTheDocument();
    expect(within(ruleCards[0]).getByText('Reviewed 180 days ago')).toBeInTheDocument();
    expect(within(ruleCards[0]).getByText('Northwind Sample Terms v1')).toBeInTheDocument();
    expect(within(ruleCards[0]).getByText('2026-01-01 to 2026-12-31')).toBeInTheDocument();
    expect(within(ruleCards[0]).getByText('$500.00 per quarterly (nwcash_dining_q)')).toBeInTheDocument();

    // 181 days -> Stale, null effective_to and null url
    expect(within(ruleCards[1]).getByText('Stale')).toBeInTheDocument();
    expect(
      within(ruleCards[1]).getByText('Stale source (181 days since review; threshold 180 days)'),
    ).toBeInTheDocument();
    expect(within(ruleCards[1]).getByText('2026-01-01 to No end date')).toBeInTheDocument();
    expect(within(ruleCards[1]).queryByText(/Source URL:/)).not.toBeInTheDocument();

    // Switch to unheld catalog product 3 (Horizon Summit Points, 179 days -> Fresh)
    fireEvent.change(screen.getByLabelText('Inspect Rules for Card Product'), {
      target: { value: '3' },
    });
    expect(await screen.findByText('horizon.travel')).toBeInTheDocument();
    expect(screen.getByText('Reviewed 179 days ago')).toBeInTheDocument();
  });

  it('handles independent error/retry and empty states for catalog, held cards, and rules', async () => {
    mockT39Fetch({ catalogOk: false, cardsOk: false });
    const { unmount } = render(<App initialEntries={['/cards']} />);

    expect(await screen.findByRole('button', { name: 'Retry Catalog' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Retry Held Cards' })).toBeInTheDocument();
    unmount();

    mockT39Fetch({ rulesOk: false });
    const { unmount: unmountRulesErr } = render(
      <App initialEntries={['/rules']} rulesReferenceDate="2026-11-20" />,
    );
    expect(await screen.findByRole('button', { name: 'Retry Rules' })).toBeInTheDocument();
    unmountRulesErr();

    mockT39Fetch({ emptyRules: true });
    render(<App initialEntries={['/rules']} rulesReferenceDate="2026-11-20" />);
    expect(
      await screen.findByText('No earning rules defined for this card product.'),
    ).toBeInTheDocument();
  });

  it('handles missing/invalid dates, custom thresholds, leap-year, and year boundaries in getRuleStaleness', () => {
    expect(getRuleStaleness('', '2026-11-20')).toEqual({
      ageDays: null,
      isStale: false,
      thresholdDays: 180,
    });
    expect(getRuleStaleness('2026-02-30', '2026-11-20')).toEqual({
      ageDays: null,
      isStale: false,
      thresholdDays: 180,
    });
    expect(getRuleStaleness('not-a-date', '2026-11-20')).toEqual({
      ageDays: null,
      isStale: false,
      thresholdDays: 180,
    });
    expect(getRuleStaleness('2026-05-24', new Date('invalid'))).toEqual({
      ageDays: null,
      isStale: false,
      thresholdDays: 180,
    });

    // Custom threshold
    expect(getRuleStaleness('2026-10-21', '2026-11-20', 30)).toEqual({
      ageDays: 30,
      isStale: false,
      thresholdDays: 30,
    });
    expect(getRuleStaleness('2026-10-20', '2026-11-20', 30)).toEqual({
      ageDays: 31,
      isStale: true,
      thresholdDays: 30,
    });

    // Leap-year and month/year boundaries
    expect(getRuleStaleness('2024-02-28', '2024-03-01')).toEqual({
      ageDays: 2,
      isStale: false,
      thresholdDays: 180,
    });
    expect(getRuleStaleness('2025-02-28', '2025-03-01')).toEqual({
      ageDays: 1,
      isStale: false,
      thresholdDays: 180,
    });
    expect(getRuleStaleness('2025-12-31', '2026-01-01')).toEqual({
      ageDays: 1,
      isStale: false,
      thresholdDays: 180,
    });
  });

  it('prevents in-flight add-card mutation from leaking feedback or clearing form after profile switch', async () => {
    let resolveDeferredPost!: (res: Response) => void;
    let rejectDeferredPost!: (reason?: unknown) => void;
    let mayaCardsFetchCount = 0;

    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      const method = init?.method ?? 'GET';

      if (url.endsWith('/healthz')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ status: 'ok', version: '0.1.0' }),
        } as Response);
      }
      if (url.endsWith('/profiles') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => MOCK_PROFILES,
        } as Response);
      }
      if (url.endsWith('/card-products') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => MOCK_CATALOG_PRODUCTS,
        } as Response);
      }
      if (url.endsWith('/profiles/maya/cards') && method === 'GET') {
        mayaCardsFetchCount += 1;
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => MOCK_CARDS.maya,
        } as Response);
      }
      if (url.endsWith('/profiles/dev/cards') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => MOCK_CARDS.dev,
        } as Response);
      }
      if (url.endsWith('/profiles/maya/cards') && method === 'POST') {
        return new Promise<Response>((resolve, reject) => {
          resolveDeferredPost = resolve;
          rejectDeferredPost = reject;
        });
      }
      return Promise.resolve({
        ok: false,
        status: 404,
        json: async () => ({ title: 'Not Found' }),
      } as Response);
    });

    // Success variant
    const { unmount } = render(<App initialEntries={['/cards']} />);
    await screen.findByText('Daily Cash');
    const initialMayaFetches = mayaCardsFetchCount;

    fireEvent.change(screen.getByLabelText('Card Nickname'), { target: { value: 'Maya New Card' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add Card' }));

    // Switch to Dev while Maya's POST is in flight
    fireEvent.change(screen.getByLabelText('Select demo profile'), { target: { value: 'dev' } });
    await screen.findByText('Summit Points');
    fireEvent.change(screen.getByLabelText('Card Nickname'), { target: { value: 'Dev Draft' } });

    resolveDeferredPost({
      ok: true,
      status: 201,
      json: async () => ({
        id: 999,
        profile_id: 1,
        card_product_id: 1,
        nickname: 'Maya New Card',
        opened_on: null,
        is_active: true,
        card_product: MOCK_CATALOG_PRODUCTS[0],
      }),
    } as Response);

    await waitFor(() => {
      expect(screen.getByLabelText('Card Nickname')).toHaveValue('Dev Draft');
    });
    expect(screen.queryByText(/Added "Maya New Card"/)).not.toBeInTheDocument();

    // Switching back to Maya triggers a refetch because ['profile', 'maya'] was invalidated
    fireEvent.change(screen.getByLabelText('Select demo profile'), { target: { value: 'maya' } });
    await waitFor(() => {
      expect(mayaCardsFetchCount).toBeGreaterThan(initialMayaFetches);
    });
    unmount();

    // Failure variant
    render(<App initialEntries={['/cards']} />);
    await screen.findByText('Daily Cash');
    fireEvent.change(screen.getByLabelText('Card Nickname'), { target: { value: 'Maya Fail Card' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add Card' }));

    fireEvent.change(screen.getByLabelText('Select demo profile'), { target: { value: 'dev' } });
    await screen.findByText('Summit Points');

    rejectDeferredPost(new Error('Network timeout for Maya'));

    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
    expect(screen.getByLabelText('Card Nickname')).toHaveValue('Maya Fail Card');
  });

  it('hardens source URLs in /rules: renders https link safely and blocks unsafe schemes', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      if (url.endsWith('/healthz')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ status: 'ok', version: '0.1.0' }),
        } as Response;
      }
      if (url.endsWith('/profiles')) {
        return { ok: true, status: 200, json: async () => MOCK_PROFILES } as Response;
      }
      if (url.endsWith('/card-products')) {
        return { ok: true, status: 200, json: async () => MOCK_CATALOG_PRODUCTS } as Response;
      }
      if (url.endsWith('/card-products/1/rules')) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            MOCK_PRODUCT_RULES[1][0],
            {
              ...(MOCK_PRODUCT_RULES[1][1] as Record<string, unknown>),
              source: {
                id: 99,
                title: 'Unsafe Source Test',
                kind: 'fictional_sample',
                url: 'javascript:alert(1)',
                notes: 'Should not render as anchor',
                last_reviewed_on: '2026-10-01',
              },
            },
          ],
        } as Response;
      }
      return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
    });

    render(<App initialEntries={['/rules']} rulesReferenceDate="2026-11-20" />);

    const safeLink = await screen.findByRole('link', {
      name: 'https://example.invalid/northwind-terms',
    });
    expect(safeLink).toHaveAttribute('href', 'https://example.invalid/northwind-terms');
    expect(safeLink).toHaveAttribute('target', '_blank');
    expect(safeLink).toHaveAttribute('rel', 'noopener noreferrer');

    expect(screen.getByText('javascript:alert(1)')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'javascript:alert(1)' })).not.toBeInTheDocument();
  });

  it('preserves card and displays error alert when PATCH update fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      const method = init?.method ?? 'GET';
      if (url.endsWith('/healthz')) {
        return { ok: true, status: 200, json: async () => ({ status: 'ok' }) } as Response;
      }
      if (url.endsWith('/profiles') && method === 'GET') {
        return { ok: true, status: 200, json: async () => MOCK_PROFILES } as Response;
      }
      if (url.endsWith('/card-products') && method === 'GET') {
        return { ok: true, status: 200, json: async () => MOCK_CATALOG_PRODUCTS } as Response;
      }
      if (url.endsWith('/profiles/maya/cards') && method === 'GET') {
        return { ok: true, status: 200, json: async () => MOCK_CARDS.maya } as Response;
      }
      if (url.includes('/profiles/maya/cards/') && method === 'PATCH') {
        return {
          ok: false,
          status: 500,
          json: async () => ({
            title: 'Internal Server Error',
            status: 500,
            detail: 'Update failed on server.',
          }),
        } as Response;
      }
      return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
    });

    render(<App initialEntries={['/cards']} />);
    await screen.findByText('Daily Cash');

    const firstCard = screen.getAllByTestId('held-card-item')[0];
    fireEvent.click(within(firstCard).getByRole('button', { name: 'Deactivate' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Update failed on server.');
    expect(within(firstCard).getByText('Status: Active')).toBeInTheDocument();
  });

  it('does not issue profile-specific card queries when no profile is selected on /cards', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      if (url.endsWith('/healthz')) {
        return { ok: true, status: 200, json: async () => ({ status: 'ok' }) } as Response;
      }
      if (url.endsWith('/profiles')) {
        return { ok: true, status: 200, json: async () => [] } as Response;
      }
      if (url.endsWith('/card-products')) {
        return { ok: true, status: 200, json: async () => MOCK_CATALOG_PRODUCTS } as Response;
      }
      return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
    });

    render(<App initialEntries={['/cards']} />);

    expect(
      await screen.findByText('Select a demo profile to view and manage held cards.'),
    ).toBeInTheDocument();
    expect(await screen.findByLabelText('Catalog Card Product')).toBeDisabled();
    expect(
      fetchSpy.mock.calls.some(([input]) => String(input).includes('/profiles/') && String(input).includes('/cards')),
    ).toBe(false);
  });

  it('recovers when clicking Retry Catalog, Retry Held Cards, and Retry Rules', async () => {
    let catalogFails = true;
    let cardsFails = true;
    let rulesFails = true;

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      if (url.endsWith('/healthz')) {
        return { ok: true, status: 200, json: async () => ({ status: 'ok' }) } as Response;
      }
      if (url.endsWith('/profiles')) {
        return { ok: true, status: 200, json: async () => MOCK_PROFILES } as Response;
      }
      if (url.endsWith('/card-products')) {
        if (catalogFails) {
          return {
            ok: false,
            status: 503,
            json: async () => ({ title: 'Unavailable', detail: 'Catalog error' }),
          } as Response;
        }
        return { ok: true, status: 200, json: async () => MOCK_CATALOG_PRODUCTS } as Response;
      }
      if (url.endsWith('/profiles/maya/cards')) {
        if (cardsFails) {
          return {
            ok: false,
            status: 500,
            json: async () => ({ title: 'Error', detail: 'Held cards error' }),
          } as Response;
        }
        return { ok: true, status: 200, json: async () => MOCK_CARDS.maya } as Response;
      }
      if (url.endsWith('/card-products/1/rules')) {
        if (rulesFails) {
          return {
            ok: false,
            status: 500,
            json: async () => ({ title: 'Error', detail: 'Rules error' }),
          } as Response;
        }
        return { ok: true, status: 200, json: async () => MOCK_PRODUCT_RULES[1] } as Response;
      }
      return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
    });

    const { unmount } = render(<App initialEntries={['/cards']} />);
    const retryCatalog = await screen.findByRole('button', { name: 'Retry Catalog' });
    const retryCards = await screen.findByRole('button', { name: 'Retry Held Cards' });

    catalogFails = false;
    cardsFails = false;
    fireEvent.click(retryCatalog);
    fireEvent.click(retryCards);

    expect(await screen.findByLabelText('Catalog Card Product')).toBeInTheDocument();
    expect(await screen.findByText('Daily Cash')).toBeInTheDocument();
    unmount();

    render(<App initialEntries={['/rules']} rulesReferenceDate="2026-11-20" />);
    const retryRules = await screen.findByRole('button', { name: 'Retry Rules' });
    rulesFails = false;
    fireEvent.click(retryRules);

    expect(await screen.findByText('nwcash.dining')).toBeInTheDocument();
  });
});

const MOCK_CATEGORIES = [
  { id: 1, code: 'groceries', name: 'Groceries' },
  { id: 2, code: 'dining', name: 'Dining' },
  { id: 3, code: 'travel', name: 'Travel' },
];

const MOCK_MERCHANTS = [
  {
    id: 10,
    name: 'Harbor Bistro',
    default_category_code: 'dining',
    default_category_id: 2,
    tags: ['restaurant'],
  },
  {
    id: 11,
    name: 'FreshMart',
    default_category_code: 'groceries',
    default_category_id: 1,
    tags: ['supermarket'],
  },
];

const MOCK_RECOMMENDATION_RESPONSE = {
  engine_version: '1.0.0',
  global_notes: [
    'Annual fees and benefit credits are excluded from recommendation ranking.',
    'Tie broken deterministically by profile card id.',
  ],
  ranked: [
    {
      rank: 1,
      profile_card_id: 101,
      card_name: 'Daily Cash',
      reward_currency: 'NW_CASH',
      status: 'ranked',
      reward_units: '4.0000',
      estimated_value_cents: 400,
      reason: null,
      message: null,
      applied: [
        {
          portion_cents: 5000,
          rule_id: 11,
          rule_key: 'nwcash.dining',
          rule_version: 1,
          multiplier: '5.0',
          reward_units: '2.5000',
        },
        {
          portion_cents: 5000,
          rule_id: 12,
          rule_key: 'nwcash.base',
          rule_version: 1,
          multiplier: '1.0',
          reward_units: '0.5000',
        },
      ],
      explanation: [
        'Matched dining 5x rule up to remaining $50.00 quarterly cap.',
        'Remaining $50.00 fell back to base 1x rule.',
      ],
      warnings: ['Cap nearly exhausted: $0.00 remaining after this purchase.'],
    },
  ],
  unranked: [
    {
      rank: null,
      profile_card_id: 103,
      card_name: 'Skyward Miles Card',
      reward_currency: 'SKY_MILES',
      status: 'unranked',
      reward_units: '300.0000',
      estimated_value_cents: null,
      reason: 'no_valuation',
      message: 'No valuation configured for SKY_MILES; configure it in Settings.',
      applied: [
        {
          portion_cents: 10000,
          rule_id: 21,
          rule_key: 'skyward.dining',
          rule_version: 1,
          multiplier: '3.0',
          reward_units: '300.0000',
        },
      ],
      explanation: ['Earned 300.0000 SKY_MILES under dining 3x rule.'],
      warnings: [],
    },
  ],
  ineligible: [
    {
      rank: null,
      profile_card_id: 104,
      card_name: 'Legacy Card',
      reward_currency: 'NW_CASH',
      status: 'ineligible',
      reward_units: '0.0000',
      estimated_value_cents: null,
      reason: 'no_effective_rule',
      message: 'No earning rule is effective on the selected purchase date.',
      applied: [],
      explanation: ['All rules expired prior to 2026-11-20.'],
      warnings: ['Rule expired.'],
    },
  ],
};

function mockT40Fetch(options?: {
  profiles?: typeof MOCK_PROFILES;
  categoriesOk?: boolean;
  merchantsOk?: boolean;
  recommendOk?: boolean;
  recommendationPayload?: typeof MOCK_RECOMMENDATION_RESPONSE;
}) {
  const profiles = options?.profiles ?? MOCK_PROFILES;
  const categoriesOk = options?.categoriesOk ?? true;
  const merchantsOk = options?.merchantsOk ?? true;
  const recommendOk = options?.recommendOk ?? true;
  const recommendationPayload = options?.recommendationPayload ?? MOCK_RECOMMENDATION_RESPONSE;

  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    const method = init?.method ?? 'GET';

    if (url.endsWith('/healthz')) {
      return {
        ok: true,
        status: 200,
        json: async () => ({ status: 'ok', version: '0.1.0' }),
      } as Response;
    }
    if (url.endsWith('/profiles') && method === 'GET') {
      return { ok: true, status: 200, json: async () => profiles } as Response;
    }
    if (url.endsWith('/categories') && method === 'GET') {
      if (!categoriesOk) {
        return {
          ok: false,
          status: 500,
          json: async () => ({ title: 'Error', detail: 'Categories unavailable' }),
        } as Response;
      }
      return { ok: true, status: 200, json: async () => MOCK_CATEGORIES } as Response;
    }
    if (url.endsWith('/merchants') && method === 'GET') {
      if (!merchantsOk) {
        return {
          ok: false,
          status: 500,
          json: async () => ({ title: 'Error', detail: 'Merchants unavailable' }),
        } as Response;
      }
      return { ok: true, status: 200, json: async () => MOCK_MERCHANTS } as Response;
    }
    if (url.endsWith('/profiles/maya/cards') && method === 'GET') {
      return {
        ok: true,
        status: 200,
        json: async () => [
          ...(MOCK_CARDS.maya as Array<Record<string, unknown>>),
          {
            ...(MOCK_CARDS.maya[0] as Record<string, unknown>),
            id: 103,
            nickname: 'Skyward Miles Card',
            is_active: true,
          },
        ],
      } as Response;
    }
    if (url.endsWith('/profiles/dev/cards') && method === 'GET') {
      return { ok: true, status: 200, json: async () => MOCK_CARDS.dev } as Response;
    }
    if (url.includes('/recommendations') && method === 'POST') {
      if (!recommendOk) {
        return {
          ok: false,
          status: 422,
          json: async () => ({
            title: 'Unprocessable Entity',
            status: 422,
            detail: 'Invalid recommendation payload.',
          }),
        } as Response;
      }
      return {
        ok: true,
        status: 200,
        json: async () => recommendationPayload,
      } as Response;
    }
    return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
  });
}

describe('T40 Compare view', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('parses positive USD strings into integer cents without floats and formats local date', () => {
    expect(parseUsdToCents('125.00')).toBe(12500);
    expect(parseUsdToCents('125')).toBe(12500);
    expect(parseUsdToCents('10.5')).toBe(1050);
    expect(parseUsdToCents('.99')).toBe(99);
    expect(parseUsdToCents('0')).toBeNull();
    expect(parseUsdToCents('0.00')).toBeNull();
    expect(parseUsdToCents('-5.00')).toBeNull();
    expect(parseUsdToCents('1.234')).toBeNull();
    expect(parseUsdToCents('abc')).toBeNull();
    expect(parseUsdToCents('')).toBeNull();

    expect(getTodayLocalIsoDate(new Date(2026, 10, 5, 23, 45))).toBe('2026-11-05');
  });

  it('populates form from categories/merchants/active cards, auto-fills category, and respects manual override', async () => {
    const fetchSpy = mockT40Fetch();
    render(<App initialEntries={['/compare']} />);

    const categorySelect = await screen.findByLabelText('Category');
    const merchantSelect = await screen.findByLabelText('Merchant (optional)');
    expect(await screen.findByLabelText(/Daily Cash/)).toBeInTheDocument();
    expect(screen.getByText('1 inactive card is excluded by default.')).toBeInTheDocument();
    expect(screen.queryByLabelText(/Skyward Explorer/)).not.toBeInTheDocument();

    // Auto-fill category from merchant default_category_code
    fireEvent.change(merchantSelect, { target: { value: '10' } });
    expect(categorySelect).toHaveValue('dining');

    // Manual override is preserved when merchant changes or is cleared
    fireEvent.change(categorySelect, { target: { value: 'travel' } });
    fireEvent.change(merchantSelect, { target: { value: '11' } });
    expect(categorySelect).toHaveValue('travel');
    fireEvent.change(merchantSelect, { target: { value: '' } });
    expect(categorySelect).toHaveValue('travel');

    // All active cards selected -> card_ids: null
    fireEvent.change(screen.getByLabelText('Amount (USD)'), { target: { value: '100.00' } });
    fireEvent.click(screen.getByRole('button', { name: 'Compare Cards' }));

    await screen.findByText('Comparison Results');
    const firstPost = fetchSpy.mock.calls.find(
      ([u, init]) => String(u).includes('/recommendations') && init?.method === 'POST',
    );
    expect(JSON.parse(String(firstPost?.[1]?.body))).toMatchObject({
      amount_cents: 10000,
      category_code: 'travel',
      merchant_id: null,
      card_ids: null,
    });

    // Uncheck one card -> sends strict subset card_ids: [101]
    fireEvent.click(screen.getByLabelText(/Skyward Miles Card/));
    fireEvent.click(screen.getByRole('button', { name: 'Compare Cards' }));

    await waitFor(() => {
      const posts = fetchSpy.mock.calls.filter(
        ([u, init]) => String(u).includes('/recommendations') && init?.method === 'POST',
      );
      expect(posts).toHaveLength(2);
      expect(JSON.parse(String(posts[1]?.[1]?.body))).toMatchObject({
        card_ids: [101],
      });
    });
  });

  it('renders ranked, unranked, ineligible, applied cap-straddle, warnings, global notes, and explanation toggle', async () => {
    mockT40Fetch();
    render(<App initialEntries={['/compare']} />);

    await screen.findByLabelText('Category');
    fireEvent.click(screen.getByRole('button', { name: 'Compare Cards' }));

    expect(await screen.findByText('Engine v1.0.0')).toBeInTheDocument();
    expect(screen.getByText('Ranked Cards (1)')).toBeInTheDocument();
    expect(screen.getByText('Unranked Cards (1)')).toBeInTheDocument();
    expect(screen.getByText('Ineligible Cards (1)')).toBeInTheDocument();

    // Ranked + cap straddle + warnings + explanation toggle
    const rankedItem = screen.getByTestId('compare-ranked-item');
    expect(within(rankedItem).getByText('#1 Daily Cash')).toBeInTheDocument();
    expect(within(rankedItem).getByText('$4.00')).toBeInTheDocument();
    expect(within(rankedItem).getByText(/\$50\.00 at 5\.0× \(nwcash\.dining v1\)/)).toBeInTheDocument();
    expect(within(rankedItem).getByText(/\$50\.00 at 1\.0× \(nwcash\.base v1\)/)).toBeInTheDocument();
    expect(
      within(rankedItem).getByText(/Cap nearly exhausted: \$0\.00 remaining/),
    ).toBeInTheDocument();

    const toggleBtn = within(rankedItem).getByRole('button', { name: 'Show explanation' });
    expect(toggleBtn).toHaveAttribute('aria-expanded', 'false');
    expect(
      within(rankedItem).queryByText(/Matched dining 5x rule/),
    ).not.toBeInTheDocument();

    fireEvent.click(toggleBtn);
    expect(toggleBtn).toHaveAttribute('aria-expanded', 'true');
    expect(toggleBtn).toHaveTextContent('Hide explanation');
    expect(within(rankedItem).getByText(/Matched dining 5x rule/)).toBeInTheDocument();

    // Unranked & Ineligible
    const unrankedItem = screen.getByTestId('compare-unranked-item');
    expect(
      within(unrankedItem).getByText('No valuation configured for SKY_MILES; configure it in Settings.'),
    ).toBeInTheDocument();
    const ineligibleItem = screen.getByTestId('compare-ineligible-item');
    expect(
      within(ineligibleItem).getByText('No earning rule is effective on the selected purchase date.'),
    ).toBeInTheDocument();

    // Global notes
    expect(
      screen.getByText('Annual fees and benefit credits are excluded from recommendation ranking.'),
    ).toBeInTheDocument();
  });

  it('validates amount and empty card subset, handles API error, and recovers on retry', async () => {
    const fetchSpy = mockT40Fetch({ recommendOk: false });
    render(<App initialEntries={['/compare']} />);

    await screen.findByLabelText(/Daily Cash/);

    // Invalid amount -> no POST
    fireEvent.change(screen.getByLabelText('Amount (USD)'), { target: { value: '12.345' } });
    fireEvent.click(screen.getByRole('button', { name: 'Compare Cards' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Enter a positive USD amount with up to two decimal places',
    );
    expect(fetchSpy.mock.calls.some(([u]) => String(u).includes('/recommendations'))).toBe(false);

    // Uncheck all active cards -> no POST
    fireEvent.change(screen.getByLabelText('Amount (USD)'), { target: { value: '50.00' } });
    fireEvent.click(screen.getByLabelText(/Daily Cash/));
    fireEvent.click(screen.getByLabelText(/Skyward Miles Card/));
    fireEvent.click(screen.getByRole('button', { name: 'Compare Cards' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Select at least one active card to compare.',
    );

    // Re-check card and hit API 422 error
    fireEvent.click(screen.getByLabelText(/Daily Cash/));
    fireEvent.click(screen.getByRole('button', { name: 'Compare Cards' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid recommendation payload.');

    // Recover on resubmit
    mockT40Fetch({ recommendOk: true });
    fireEvent.click(screen.getByRole('button', { name: 'Compare Cards' }));
    expect(await screen.findByText('Comparison Results')).toBeInTheDocument();
  });

  it('clears results on profile switch and isolates in-flight recommendation responses', async () => {
    let resolveDeferredPost!: (res: Response) => void;

    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      const method = init?.method ?? 'GET';
      if (url.endsWith('/healthz')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ status: 'ok' }),
        } as Response);
      }
      if (url.endsWith('/profiles')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => MOCK_PROFILES,
        } as Response);
      }
      if (url.endsWith('/categories')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => MOCK_CATEGORIES,
        } as Response);
      }
      if (url.endsWith('/merchants')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => MOCK_MERCHANTS,
        } as Response);
      }
      if (url.endsWith('/profiles/maya/cards')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => MOCK_CARDS.maya,
        } as Response);
      }
      if (url.endsWith('/profiles/dev/cards')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => MOCK_CARDS.dev,
        } as Response);
      }
      if (url.endsWith('/profiles/maya/recommendations') && method === 'POST') {
        return new Promise<Response>((resolve) => {
          resolveDeferredPost = resolve;
        });
      }
      return Promise.resolve({
        ok: false,
        status: 404,
        json: async () => ({ title: 'Not Found' }),
      } as Response);
    });

    render(<App initialEntries={['/compare']} />);
    await screen.findByLabelText(/Daily Cash/);

    fireEvent.click(screen.getByRole('button', { name: 'Compare Cards' }));

    // Switch to Dev before Maya's recommendation settles
    fireEvent.change(screen.getByLabelText('Select demo profile'), { target: { value: 'dev' } });
    expect(await screen.findByLabelText(/Summit Points/)).toBeInTheDocument();

    resolveDeferredPost({
      ok: true,
      status: 200,
      json: async () => MOCK_RECOMMENDATION_RESPONSE,
    } as Response);

    await waitFor(() => {
      expect(screen.queryByText('Comparison Results')).not.toBeInTheDocument();
    });
  });

  it('disables comparison and issues no profile requests when no profile is selected', async () => {
    const fetchSpy = mockT40Fetch({ profiles: [] });
    render(<App initialEntries={['/compare']} />);

    expect(
      await screen.findByText('Select a demo profile to compare cards.'),
    ).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Compare Cards' })).toBeDisabled();
    expect(
      fetchSpy.mock.calls.some(([u]) => String(u).includes('/profiles/')),
    ).toBe(false);
  });
});
