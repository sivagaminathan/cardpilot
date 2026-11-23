import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { App } from './App';
import { BackendStatus, getHealthUrl } from './components/BackendStatus';
import {
  formatCentsToUsd,
  getTodayLocalIsoDate,
  parseUsdToCents,
  parseValuationInput,
} from './lib/formatters';
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
    expect(
      screen.getByRole('heading', { level: 2, name: /Card Benefits & Usage Tracking/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole('link', { name: /^Dashboard$/i }));
    fireEvent.click(screen.getByRole('button', { name: 'View Full Rewards' }));
    expect(
      screen.getByRole('heading', { level: 2, name: /Earned Rewards by Currency/i }),
    ).toBeInTheDocument();

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

const MOCK_REWARD_CURRENCIES = [
  {
    id: 1,
    code: 'NW_CASH',
    name: 'Northwind Cash',
    kind: 'cash_back',
    is_cash_equivalent: true,
    default_cents_per_unit: '1.0000',
  },
  {
    id: 2,
    code: 'HORIZON_PTS',
    name: 'Horizon Points',
    kind: 'points',
    is_cash_equivalent: false,
    default_cents_per_unit: '1.5000',
  },
  {
    id: 3,
    code: 'SKY_MILES',
    name: 'Skyward Miles',
    kind: 'miles',
    is_cash_equivalent: false,
    default_cents_per_unit: '1.2000',
  },
];

function mockT41Fetch(options?: {
  profiles?: typeof MOCK_PROFILES;
  currenciesOk?: boolean;
  valuationsOk?: boolean;
  putStatus?: number;
}) {
  const profiles = options?.profiles ?? MOCK_PROFILES;
  const currenciesOk = options?.currenciesOk ?? true;
  const valuationsOk = options?.valuationsOk ?? true;
  const putStatus = options?.putStatus ?? 200;

  const valuationsByProfile: Record<string, Array<Record<string, unknown>>> = {
    maya: [
      {
        profile_id: 1,
        reward_currency_id: 1,
        reward_currency: MOCK_REWARD_CURRENCIES[0],
        cents_per_unit: '1.0000',
        is_user_set: false,
        updated_at: '2026-11-20T00:00:00Z',
      },
      {
        profile_id: 1,
        reward_currency_id: 2,
        reward_currency: MOCK_REWARD_CURRENCIES[1],
        cents_per_unit: '1.8000',
        is_user_set: true,
        updated_at: '2026-11-20T00:00:00Z',
      },
    ],
    dev: [
      {
        profile_id: 2,
        reward_currency_id: 2,
        reward_currency: MOCK_REWARD_CURRENCIES[1],
        cents_per_unit: '1.5000',
        is_user_set: false,
        updated_at: '2026-11-20T00:00:00Z',
      },
    ],
  };

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
    if (url.endsWith('/reward-currencies') && method === 'GET') {
      if (!currenciesOk) {
        return {
          ok: false,
          status: 503,
          json: async () => ({ title: 'Unavailable', detail: 'Currencies unavailable' }),
        } as Response;
      }
      return { ok: true, status: 200, json: async () => MOCK_REWARD_CURRENCIES } as Response;
    }

    const valListMatch = url.match(/\/profiles\/([^/]+)\/valuations$/);
    if (valListMatch && method === 'GET') {
      if (!valuationsOk) {
        return {
          ok: false,
          status: 500,
          json: async () => ({ title: 'Error', detail: 'Valuations failed' }),
        } as Response;
      }
      const slug = decodeURIComponent(valListMatch[1]);
      return {
        ok: true,
        status: 200,
        json: async () => valuationsByProfile[slug] ?? [],
      } as Response;
    }

    const valPutMatch = url.match(/\/profiles\/([^/]+)\/valuations\/([^/]+)$/);
    if (valPutMatch && method === 'PUT') {
      if (putStatus !== 200) {
        return {
          ok: false,
          status: putStatus,
          json: async () => ({
            title: 'Unprocessable Entity',
            status: putStatus,
            detail: 'Validation failed.',
            errors: [
              {
                loc: ['body', 'cents_per_unit'],
                msg: 'Value rejected by server.',
                type: 'value_error',
              },
            ],
          }),
        } as Response;
      }
      const slug = decodeURIComponent(valPutMatch[1]);
      const code = decodeURIComponent(valPutMatch[2]);
      const body = JSON.parse(String(init?.body ?? '{}')) as { cents_per_unit: string };
      const currency =
        MOCK_REWARD_CURRENCIES.find((c) => c.code === code) ?? MOCK_REWARD_CURRENCIES[0];
      const updated = {
        profile_id: slug === 'maya' ? 1 : 2,
        reward_currency_id: currency.id,
        reward_currency: currency,
        cents_per_unit: body.cents_per_unit,
        is_user_set: true,
        updated_at: '2026-11-22T18:00:00Z',
      };
      const existingList = valuationsByProfile[slug] ?? [];
      const filtered = existingList.filter((v) => v.reward_currency_id !== currency.id);
      valuationsByProfile[slug] = [...filtered, updated];
      return { ok: true, status: 200, json: async () => updated } as Response;
    }

    return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
  });
}

describe('T41 Settings / Valuations view', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('validates decimal valuation boundaries and rejects invalid inputs without floats', () => {
    expect(parseValuationInput('0.0001')).toBe('0.0001');
    expect(parseValuationInput('10')).toBe('10.0000');
    expect(parseValuationInput('10.0000')).toBe('10.0000');
    expect(parseValuationInput('1.5')).toBe('1.5000');
    expect(parseValuationInput('001.25')).toBe('1.2500');
    expect(parseValuationInput('.5')).toBe('0.5000');
    expect(parseValuationInput('10.0001')).toBeNull();
    expect(parseValuationInput('0')).toBeNull();
    expect(parseValuationInput('0.0000')).toBeNull();
    expect(parseValuationInput('-1')).toBeNull();
    expect(parseValuationInput('1.12345')).toBeNull();
    expect(parseValuationInput('1.')).toBeNull();
    expect(parseValuationInput('abc')).toBeNull();
    expect(parseValuationInput('')).toBeNull();
  });

  it('renders Illustrative default, User-configured, and Not configured states with reference hint', async () => {
    mockT41Fetch();
    render(<App initialEntries={['/settings']} />);

    await screen.findByLabelText('Select demo profile');
    expect(await screen.findByText('Illustrative default')).toBeInTheDocument();
    const cashRow = screen.getByTestId('valuation-row-NW_CASH');
    expect(within(cashRow).getByText('Illustrative default')).toBeInTheDocument();
    expect(within(cashRow).getByLabelText(/Estimated cents per Northwind Cash unit/i)).toHaveValue(
      '1.0000',
    );

    const pointsRow = screen.getByTestId('valuation-row-HORIZON_PTS');
    expect(within(pointsRow).getByText('User-configured')).toBeInTheDocument();
    expect(within(pointsRow).getByLabelText(/Estimated cents per Horizon Points unit/i)).toHaveValue(
      '1.8000',
    );

    const milesRow = screen.getByTestId('valuation-row-SKY_MILES');
    expect(
      within(milesRow).getByText('Not configured (unranked in Compare)'),
    ).toBeInTheDocument();
    expect(within(milesRow).getByLabelText(/Estimated cents per Skyward Miles unit/i)).toHaveValue(
      '',
    );
    expect(
      within(milesRow).getByText(/Illustrative default reference: 1\.2000¢ \(not yet configured/),
    ).toBeInTheDocument();
  });

  it('validates client-side range/precision, saves valuation to User-configured, and surfaces 422 errors', async () => {
    const fetchSpy = mockT41Fetch();
    render(<App initialEntries={['/settings']} />);

    await screen.findByLabelText('Select demo profile');
    await screen.findByText('Illustrative default');
    const milesRow = screen.getByTestId('valuation-row-SKY_MILES');
    const milesInput = within(milesRow).getByLabelText(/Estimated cents per Skyward Miles unit/i);

    // Client-side invalid range (>10) -> no PUT
    fireEvent.change(milesInput, { target: { value: '10.0001' } });
    fireEvent.click(within(milesRow).getByRole('button', { name: 'Save' }));
    expect(await within(milesRow).findByRole('alert')).toHaveTextContent(
      'Enter a positive valuation greater than 0 and up to 10 cents per unit (max 4 decimal places).',
    );
    expect(fetchSpy.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(false);

    // Valid save -> PUT + status flips to User-configured + profile invalidated
    const initialValuationsFetches = fetchSpy.mock.calls.filter(
      ([u, init]) => String(u).includes('/profiles/maya/valuations') && (!init?.method || init.method === 'GET'),
    ).length;

    fireEvent.change(milesInput, { target: { value: '1.75' } });
    fireEvent.click(within(milesRow).getByRole('button', { name: 'Save' }));

    expect(await within(milesRow).findByRole('status')).toHaveTextContent(
      'Saved 1.7500¢ per Skyward Miles unit.',
    );
    expect(within(milesRow).getByText('User-configured')).toBeInTheDocument();

    await waitFor(() => {
      const valFetches = fetchSpy.mock.calls.filter(
        ([u, init]) => String(u).includes('/profiles/maya/valuations') && (!init?.method || init.method === 'GET'),
      ).length;
      expect(valFetches).toBeGreaterThan(initialValuationsFetches);
    });

    // Server 422 error
    mockT41Fetch({ putStatus: 422 });
    fireEvent.change(milesInput, { target: { value: '2.0000' } });
    fireEvent.click(within(milesRow).getByRole('button', { name: 'Save' }));
    expect(await within(milesRow).findByRole('alert')).toHaveTextContent(
      'Value rejected by server.',
    );
  });

  it('clears drafts/feedback on profile switch and isolates in-flight PUT responses', async () => {
    let resolveDeferredPut!: (res: Response) => void;
    let mayaValFetches = 0;

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
      if (url.endsWith('/reward-currencies')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => MOCK_REWARD_CURRENCIES,
        } as Response);
      }
      if (url.endsWith('/profiles/maya/valuations') && method === 'GET') {
        mayaValFetches += 1;
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => [
            {
              profile_id: 1,
              reward_currency_id: 1,
              reward_currency: MOCK_REWARD_CURRENCIES[0],
              cents_per_unit: '1.0000',
              is_user_set: false,
              updated_at: '2026-11-20T00:00:00Z',
            },
          ],
        } as Response);
      }
      if (url.endsWith('/profiles/dev/valuations') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => [],
        } as Response);
      }
      if (url.endsWith('/profiles/maya/valuations/NW_CASH') && method === 'PUT') {
        return new Promise<Response>((resolve) => {
          resolveDeferredPut = resolve;
        });
      }
      return Promise.resolve({
        ok: false,
        status: 404,
        json: async () => ({ title: 'Not Found' }),
      } as Response);
    });

    render(<App initialEntries={['/settings']} />);
    await screen.findByLabelText('Select demo profile');
    await screen.findByText('Illustrative default');
    const cashRow = screen.getByTestId('valuation-row-NW_CASH');
    const cashInput = within(cashRow).getByLabelText(/Estimated cents per Northwind Cash unit/i);

    fireEvent.change(cashInput, { target: { value: '1.25' } });
    fireEvent.click(within(cashRow).getByRole('button', { name: 'Save' }));
    const initialMayaFetches = mayaValFetches;

    // Switch to Dev while Maya's PUT is in flight
    fireEvent.change(screen.getByLabelText('Select demo profile'), { target: { value: 'dev' } });
    await waitFor(() => {
      expect(
        within(screen.getByTestId('valuation-row-NW_CASH')).getByText(
          'Not configured (unranked in Compare)',
        ),
      ).toBeInTheDocument();
    });

    const devCashInput = within(screen.getByTestId('valuation-row-NW_CASH')).getByLabelText(
      /Estimated cents per Northwind Cash unit/i,
    );
    fireEvent.change(devCashInput, { target: { value: '1.90' } });

    resolveDeferredPut({
      ok: true,
      status: 200,
      json: async () => ({
        profile_id: 1,
        reward_currency_id: 1,
        reward_currency: MOCK_REWARD_CURRENCIES[0],
        cents_per_unit: '1.2500',
        is_user_set: true,
        updated_at: '2026-11-22T18:00:00Z',
      }),
    } as Response);

    await waitFor(() => {
      expect(devCashInput).toHaveValue('1.90');
    });
    expect(screen.queryByText(/Saved 1\.2500¢/)).not.toBeInTheDocument();

    // Switching back to Maya triggers refetch due to ['profile', 'maya'] invalidation
    fireEvent.change(screen.getByLabelText('Select demo profile'), { target: { value: 'maya' } });
    await waitFor(() => {
      expect(mayaValFetches).toBeGreaterThan(initialMayaFetches);
    });
  });

  it('handles empty profile list without profile requests and recovers on currency/valuation retry', async () => {
    const emptyFetchSpy = mockT41Fetch({ profiles: [] });
    const { unmount } = render(<App initialEntries={['/settings']} />);

    expect(
      await screen.findByText('Select a demo profile to view and edit currency valuations.'),
    ).toBeInTheDocument();
    const cashRow = await screen.findByTestId('valuation-row-NW_CASH');
    expect(
      within(cashRow).getByLabelText(/Estimated cents per Northwind Cash unit/i),
    ).toBeDisabled();
    expect(within(cashRow).getByRole('button', { name: 'Save' })).toBeDisabled();
    expect(
      emptyFetchSpy.mock.calls.some(([u]) => String(u).includes('/profiles/')),
    ).toBe(false);
    unmount();

    // Error & Retry recovery for currencies and valuations
    let failCurrencies = true;
    let failValuations = true;
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      if (url.endsWith('/healthz')) {
        return { ok: true, status: 200, json: async () => ({ status: 'ok' }) } as Response;
      }
      if (url.endsWith('/profiles')) {
        return { ok: true, status: 200, json: async () => MOCK_PROFILES } as Response;
      }
      if (url.endsWith('/reward-currencies')) {
        if (failCurrencies) {
          return {
            ok: false,
            status: 503,
            json: async () => ({ title: 'Unavailable', detail: 'Currencies error' }),
          } as Response;
        }
        return { ok: true, status: 200, json: async () => MOCK_REWARD_CURRENCIES } as Response;
      }
      if (url.endsWith('/profiles/maya/valuations')) {
        if (failValuations) {
          return {
            ok: false,
            status: 500,
            json: async () => ({ title: 'Error', detail: 'Valuations error' }),
          } as Response;
        }
        return { ok: true, status: 200, json: async () => [] } as Response;
      }
      return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
    });

    render(<App initialEntries={['/settings']} />);
    const retryCurrenciesBtn = await screen.findByRole('button', { name: 'Retry Currencies' });
    failCurrencies = false;
    fireEvent.click(retryCurrenciesBtn);

    const retryValuationsBtn = await screen.findByRole('button', { name: 'Retry Valuations' });
    failValuations = false;
    fireEvent.click(retryValuationsBtn);

    expect(await screen.findByTestId('valuation-row-NW_CASH')).toBeInTheDocument();
  });
});

const MOCK_TRANSACTIONS_MAYA = [
  {
    id: 501,
    profile_id: 1,
    profile_card_id: 101,
    card_name: 'Daily Cash',
    amount_cents: 5000,
    category_code: 'dining',
    category_name: 'Dining',
    merchant_id: 10,
    merchant_name: 'Harbor Bistro',
    merchant_text: null,
    occurred_on: '2026-11-15',
    note: 'Dinner with team',
    created_at: '2026-11-15T12:00:00Z',
    reward_calc: {
      id: 901,
      engine_version: '1.0.0',
      reward_currency: 'NW_CASH',
      reward_units: '1.5000',
      valuation_cents_per_unit_used: '1.0000',
      estimated_value_cents: 150,
      applied_rule_ids: [11],
      trace: {
        status: 'ranked',
        applied_portions: [
          {
            portion_cents: 5000,
            rule_id: 11,
            rule_key: 'nwcash.dining',
            rule_version: 1,
            multiplier: '3.0',
            reward_units: '1.5000',
          },
        ],
        explanation: ['Matched dining 3x rule.'],
        warnings: ['Cap 50% used.'],
      },
      created_at: '2026-11-15T12:00:00Z',
    },
  },
];

const MOCK_TRANSACTIONS_DEV = [
  {
    id: 601,
    profile_id: 2,
    profile_card_id: 201,
    card_name: 'Summit Points',
    amount_cents: 12000,
    category_code: 'travel',
    category_name: 'Travel',
    merchant_id: null,
    merchant_name: null,
    merchant_text: 'Rail Express',
    occurred_on: '2026-11-18',
    note: '',
    created_at: '2026-11-18T12:00:00Z',
    reward_calc: {
      id: 902,
      engine_version: '1.0.0',
      reward_currency: 'HORIZON_PTS',
      reward_units: '480.0000',
      valuation_cents_per_unit_used: null,
      estimated_value_cents: null,
      applied_rule_ids: [31],
      trace: {
        status: 'unranked',
        applied_portions: [],
        explanation: ['Earned 480.0000 HORIZON_PTS under travel 4x rule.'],
        warnings: [],
      },
      created_at: '2026-11-18T12:00:00Z',
    },
  },
];

function mockT42Fetch(options?: {
  profiles?: typeof MOCK_PROFILES;
  txOk?: boolean;
  deleteOk?: boolean;
  createStatus?: number;
}) {
  const profiles = options?.profiles ?? MOCK_PROFILES;
  const txOk = options?.txOk ?? true;
  const deleteOk = options?.deleteOk ?? true;
  const createStatus = options?.createStatus ?? 201;

  const txByProfile: Record<string, Array<Record<string, unknown>>> = {
    maya: JSON.parse(JSON.stringify(MOCK_TRANSACTIONS_MAYA)),
    dev: JSON.parse(JSON.stringify(MOCK_TRANSACTIONS_DEV)),
  };
  let nextTxId = 700;

  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    const method = init?.method ?? 'GET';

    if (url.endsWith('/healthz')) {
      return { ok: true, status: 200, json: async () => ({ status: 'ok' }) } as Response;
    }
    if (url.endsWith('/profiles') && method === 'GET') {
      return { ok: true, status: 200, json: async () => profiles } as Response;
    }
    if (url.endsWith('/categories') && method === 'GET') {
      return { ok: true, status: 200, json: async () => MOCK_CATEGORIES } as Response;
    }
    if (url.endsWith('/merchants') && method === 'GET') {
      return { ok: true, status: 200, json: async () => MOCK_MERCHANTS } as Response;
    }
    if (url.endsWith('/profiles/maya/cards') && method === 'GET') {
      return { ok: true, status: 200, json: async () => MOCK_CARDS.maya } as Response;
    }
    if (url.endsWith('/profiles/dev/cards') && method === 'GET') {
      return { ok: true, status: 200, json: async () => MOCK_CARDS.dev } as Response;
    }

    const txCollectionMatch = url.match(/\/profiles\/([^/]+)\/transactions(?:\?(.*))?$/);
    if (txCollectionMatch) {
      const slug = decodeURIComponent(txCollectionMatch[1]);
      if (method === 'GET') {
        if (!txOk) {
          return {
            ok: false,
            status: 500,
            json: async () => ({ title: 'Error', detail: 'Transactions failed' }),
          } as Response;
        }
        const query = new URLSearchParams(txCollectionMatch[2] ?? '');
        let list = txByProfile[slug] ?? [];
        const cardFilter = query.get('profile_card_id');
        if (cardFilter) {
          list = list.filter((t) => String(t.profile_card_id) === cardFilter);
        }
        const catFilter = query.get('category_code');
        if (catFilter) {
          list = list.filter((t) => t.category_code === catFilter);
        }
        const df = query.get('date_from');
        if (df) {
          list = list.filter((t) => String(t.occurred_on) >= df);
        }
        const dt = query.get('date_to');
        if (dt) {
          list = list.filter((t) => String(t.occurred_on) <= dt);
        }
        return { ok: true, status: 200, json: async () => list } as Response;
      }

      if (method === 'POST') {
        if (createStatus !== 201) {
          return {
            ok: false,
            status: createStatus,
            json: async () => ({
              title: 'Unprocessable Entity',
              status: createStatus,
              detail: 'Validation failed.',
              errors: [
                {
                  loc: ['body', 'note'],
                  msg: 'Value must not contain 13-19 digit card numbers.',
                  type: 'value_error',
                },
              ],
            }),
          } as Response;
        }
        const body = JSON.parse(String(init?.body ?? '{}')) as {
          profile_card_id: number;
          amount_cents: number;
          category_code: string;
          merchant_id?: number | null;
          merchant_text?: string | null;
          occurred_on: string;
          note?: string;
        };
        const created = {
          id: nextTxId++,
          profile_id: slug === 'maya' ? 1 : 2,
          profile_card_id: body.profile_card_id,
          card_name: slug === 'maya' ? 'Daily Cash' : 'Summit Points',
          amount_cents: body.amount_cents,
          category_code: body.category_code,
          category_name:
            MOCK_CATEGORIES.find((c) => c.code === body.category_code)?.name ?? body.category_code,
          merchant_id: body.merchant_id ?? null,
          merchant_name:
            body.merchant_id != null
              ? (MOCK_MERCHANTS.find((m) => m.id === body.merchant_id)?.name ?? null)
              : null,
          merchant_text: body.merchant_text ?? null,
          occurred_on: body.occurred_on,
          note: body.note ?? '',
          created_at: '2026-11-22T18:00:00Z',
          reward_calc: {
            id: nextTxId + 1000,
            engine_version: '1.0.0',
            reward_currency: 'NW_CASH',
            reward_units: '2.0000',
            valuation_cents_per_unit_used: '1.0000',
            estimated_value_cents: 200,
            applied_rule_ids: [11],
            trace: {
              status: 'ranked',
              applied_portions: [],
              explanation: ['Calculated 2.0000 NW_CASH snapshot.'],
              warnings: [],
            },
            created_at: '2026-11-22T18:00:00Z',
          },
        };
        txByProfile[slug] = [created, ...(txByProfile[slug] ?? [])];
        return { ok: true, status: 201, json: async () => created } as Response;
      }
    }

    const txDeleteMatch = url.match(/\/profiles\/([^/]+)\/transactions\/(\d+)$/);
    if (txDeleteMatch && method === 'DELETE') {
      const slug = decodeURIComponent(txDeleteMatch[1]);
      const txId = Number(txDeleteMatch[2]);
      if (!deleteOk) {
        return {
          ok: false,
          status: 500,
          json: async () => ({ title: 'Error', detail: 'Delete failed on server.' }),
        } as Response;
      }
      txByProfile[slug] = (txByProfile[slug] ?? []).filter((t) => t.id !== txId);
      return { ok: true, status: 204 } as Response;
    }

    return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
  });
}

describe('T42 Transactions view', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('creates transactions with seeded or custom merchant (mutually exclusive), validates USD, and shows snapshot', async () => {
    const fetchSpy = mockT42Fetch();
    render(<App initialEntries={['/transactions']} />);

    await screen.findByLabelText('Active Card');
    expect(screen.getByText('1 inactive card is excluded.')).toBeInTheDocument();

    // Note safety hint
    const noteInput = screen.getByLabelText('Note (optional)');
    expect(noteInput).toHaveAttribute('aria-describedby', 'tx-note-safety-hint');
    expect(
      screen.getByText('Do not enter real card numbers or sensitive data.'),
    ).toBeInTheDocument();

    // Invalid USD amount -> no POST
    fireEvent.change(screen.getByLabelText('Amount (USD)'), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record Transaction' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Enter a positive USD amount with up to two decimal places',
    );
    expect(fetchSpy.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);

    // Seeded merchant creation
    fireEvent.change(screen.getByLabelText('Amount (USD)'), { target: { value: '25.00' } });
    fireEvent.change(screen.getByLabelText('Seeded Merchant (optional)'), {
      target: { value: '10' },
    });
    fireEvent.change(noteInput, { target: { value: 'Coffee' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record Transaction' }));

    const snapshotBanner = await screen.findByTestId('tx-created-snapshot');
    expect(snapshotBanner).toHaveTextContent(/Earned 2\.0000 NW_CASH/);
    expect(within(snapshotBanner).getByText(/Calculated 2\.0000 NW_CASH snapshot/)).toBeInTheDocument();

    const firstPost = fetchSpy.mock.calls.find(
      ([u, init]) => String(u).includes('/transactions') && init?.method === 'POST',
    );
    const firstPayload = JSON.parse(String(firstPost?.[1]?.body)) as Record<string, unknown>;
    expect(firstPayload.merchant_id).toBe(10);
    expect('merchant_text' in firstPayload).toBe(false);

    // Custom merchant mode creation
    fireEvent.change(screen.getByLabelText('Merchant Input Type'), { target: { value: 'custom' } });
    const customInput = screen.getByLabelText('Custom Merchant (optional)');
    expect(customInput).toHaveAttribute('aria-describedby', 'tx-merchant-safety-hint');
    fireEvent.change(customInput, { target: { value: 'Corner Bakery' } });
    fireEvent.change(screen.getByLabelText('Amount (USD)'), { target: { value: '15.00' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record Transaction' }));

    await waitFor(() => {
      const posts = fetchSpy.mock.calls.filter(
        ([u, init]) => String(u).includes('/transactions') && init?.method === 'POST',
      );
      expect(posts).toHaveLength(2);
      const secondPayload = JSON.parse(String(posts[1]?.[1]?.body)) as Record<string, unknown>;
      expect(secondPayload.merchant_text).toBe('Corner Bakery');
      expect('merchant_id' in secondPayload).toBe(false);
    });
  });

  it('surfaces 422 sensitive-data error without storing transaction', async () => {
    mockT42Fetch({ createStatus: 422 });
    render(<App initialEntries={['/transactions']} />);

    await screen.findByLabelText('Active Card');
    fireEvent.change(screen.getByLabelText('Amount (USD)'), { target: { value: '30.00' } });
    fireEvent.change(screen.getByLabelText('Note (optional)'), {
      target: { value: '4111111111111111' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Record Transaction' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Value must not contain 13-19 digit card numbers.',
    );
    expect(screen.queryByTestId('tx-created-snapshot')).not.toBeInTheDocument();
  });

  it('filters transactions, blocks invalid date ranges, clears filters, and toggles trace details', async () => {
    const fetchSpy = mockT42Fetch();
    render(<App initialEntries={['/transactions']} />);

    expect(await screen.findByText('$50.00 at Harbor Bistro')).toBeInTheDocument();

    // Trace expand/collapse
    const txItem = screen.getByTestId('tx-list-item');
    const traceBtn = within(txItem).getByRole('button', { name: 'Show trace' });
    expect(traceBtn).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(traceBtn);
    expect(traceBtn).toHaveAttribute('aria-expanded', 'true');
    expect(within(txItem).getByText('Matched dining 3x rule.')).toBeInTheDocument();
    expect(within(txItem).getByText(/Cap 50% used/)).toBeInTheDocument();

    // Filter by category with no matching result
    fireEvent.change(screen.getByLabelText('Filter by Category'), { target: { value: 'travel' } });
    expect(
      await screen.findByText('No transactions recorded for the selected filters.'),
    ).toBeInTheDocument();

    // Invalid date range blocks API request
    fireEvent.change(screen.getByLabelText('Date From'), { target: { value: '2026-11-20' } });
    const callsBeforeInvalidRange = fetchSpy.mock.calls.length;
    fireEvent.change(screen.getByLabelText('Date To'), { target: { value: '2026-11-10' } });
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Date From must not be after Date To.',
    );
    expect(fetchSpy.mock.calls.length).toBe(callsBeforeInvalidRange);

    // Clear Filters restores full list
    fireEvent.click(screen.getByRole('button', { name: 'Clear Filters' }));
    expect(await screen.findByText('$50.00 at Harbor Bistro')).toBeInTheDocument();
  });

  it('handles delete cancellation, success, and failure', async () => {
    mockT42Fetch({ deleteOk: true });
    const { unmount } = render(<App initialEntries={['/transactions']} />);

    await screen.findByText('$50.00 at Harbor Bistro');
    const txItem = screen.getByTestId('tx-list-item');

    // Cancel confirmation
    fireEvent.click(within(txItem).getByRole('button', { name: 'Remove' }));
    expect(
      within(txItem).getByRole('group', { name: /Confirm removal of transaction 501/i }),
    ).toBeInTheDocument();
    fireEvent.click(within(txItem).getByRole('button', { name: 'Cancel' }));
    expect(screen.getByText('$50.00 at Harbor Bistro')).toBeInTheDocument();

    // Confirm delete
    fireEvent.click(within(txItem).getByRole('button', { name: 'Remove' }));
    fireEvent.click(within(txItem).getByRole('button', { name: 'Confirm Remove' }));
    await waitFor(() => {
      expect(screen.queryByText('$50.00 at Harbor Bistro')).not.toBeInTheDocument();
    });
    unmount();

    // Delete failure preserves transaction
    mockT42Fetch({ deleteOk: false });
    render(<App initialEntries={['/transactions']} />);
    await screen.findByText('$50.00 at Harbor Bistro');

    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Remove' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Delete failed on server.');
    expect(screen.getByText('$50.00 at Harbor Bistro')).toBeInTheDocument();
  });

  it('isolates profile switch during deferred POST, handles empty profiles, and recovers on retry', async () => {
    let resolveDeferredPost!: (res: Response) => void;
    let mayaTxFetches = 0;

    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      const method = init?.method ?? 'GET';
      if (url.endsWith('/healthz')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ status: 'ok' }) } as Response);
      }
      if (url.endsWith('/profiles')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => MOCK_PROFILES } as Response);
      }
      if (url.endsWith('/categories')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => MOCK_CATEGORIES } as Response);
      }
      if (url.endsWith('/merchants')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => MOCK_MERCHANTS } as Response);
      }
      if (url.endsWith('/profiles/maya/cards')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => MOCK_CARDS.maya } as Response);
      }
      if (url.endsWith('/profiles/dev/cards')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => MOCK_CARDS.dev } as Response);
      }
      if (url.includes('/profiles/maya/transactions') && method === 'GET') {
        mayaTxFetches += 1;
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => MOCK_TRANSACTIONS_MAYA,
        } as Response);
      }
      if (url.includes('/profiles/dev/transactions') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => MOCK_TRANSACTIONS_DEV,
        } as Response);
      }
      if (url.endsWith('/profiles/maya/transactions') && method === 'POST') {
        return new Promise<Response>((resolve) => {
          resolveDeferredPost = resolve;
        });
      }
      return Promise.resolve({ ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response);
    });

    const { unmount } = render(<App initialEntries={['/transactions']} />);
    await screen.findByText('$50.00 at Harbor Bistro');
    const initialMayaFetches = mayaTxFetches;

    fireEvent.change(screen.getByLabelText('Amount (USD)'), { target: { value: '20.00' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record Transaction' }));

    // Switch to Dev before Maya POST resolves
    fireEvent.change(screen.getByLabelText('Select demo profile'), { target: { value: 'dev' } });
    expect(await screen.findByText('$120.00 at Rail Express')).toBeInTheDocument();

    resolveDeferredPost({
      ok: true,
      status: 201,
      json: async () => MOCK_TRANSACTIONS_MAYA[0],
    } as Response);

    await waitFor(() => {
      expect(screen.queryByTestId('tx-created-snapshot')).not.toBeInTheDocument();
    });
    expect(screen.queryByText(/Recorded \$50\.00/)).not.toBeInTheDocument();

    // Switching back to Maya refetches due to ['profile', 'maya'] invalidation
    fireEvent.change(screen.getByLabelText('Select demo profile'), { target: { value: 'maya' } });
    await waitFor(() => {
      expect(mayaTxFetches).toBeGreaterThan(initialMayaFetches);
    });
    unmount();

    // Empty profiles -> no profile requests
    const emptyFetchSpy = mockT42Fetch({ profiles: [] });
    emptyFetchSpy.mockClear();
    const { unmount: unmountEmpty } = render(<App initialEntries={['/transactions']} />);
    expect(
      await screen.findByText('Select a demo profile to record and view transactions.'),
    ).toBeInTheDocument();
    expect(
      emptyFetchSpy.mock.calls.some(([u]) => String(u).includes('/profiles/')),
    ).toBe(false);
    unmountEmpty();

    // Retry recovery on transactions error
    let failTx = true;
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      if (url.endsWith('/healthz')) {
        return { ok: true, status: 200, json: async () => ({ status: 'ok' }) } as Response;
      }
      if (url.endsWith('/profiles')) {
        return { ok: true, status: 200, json: async () => MOCK_PROFILES } as Response;
      }
      if (url.endsWith('/categories')) {
        return { ok: true, status: 200, json: async () => MOCK_CATEGORIES } as Response;
      }
      if (url.endsWith('/merchants')) {
        return { ok: true, status: 200, json: async () => MOCK_MERCHANTS } as Response;
      }
      if (url.endsWith('/profiles/maya/cards')) {
        return { ok: true, status: 200, json: async () => MOCK_CARDS.maya } as Response;
      }
      if (url.includes('/profiles/maya/transactions')) {
        if (failTx) {
          return {
            ok: false,
            status: 500,
            json: async () => ({ title: 'Error', detail: 'Tx fetch failed' }),
          } as Response;
        }
        return { ok: true, status: 200, json: async () => MOCK_TRANSACTIONS_MAYA } as Response;
      }
      return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
    });

    render(<App initialEntries={['/transactions']} />);
    const retryTxBtn = await screen.findByRole('button', { name: 'Retry Transactions' });
    failTx = false;
    fireEvent.click(retryTxBtn);
    expect(await screen.findByText('$50.00 at Harbor Bistro')).toBeInTheDocument();
  });
});

const MOCK_T43_BENEFITS_MAYA = [
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
    notes: 'Eligible dining purchases',
    period_start: '2026-11-01',
    period_end: '2026-11-30',
    next_reset_date: '2026-12-01',
    days_until_reset: 10,
    used_cents: 500,
    remaining_cents: 1000,
    over_used_cents: 0,
    is_over_used: false,
    usage_count: 1,
    status: 'partially_used',
    usages: [
      {
        id: 801,
        profile_card_id: 101,
        benefit_definition_id: 1,
        amount_cents: 500,
        used_on: '2026-11-10',
        note: 'Cafe lunch',
      },
    ],
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
    notes: 'Annual airline perk',
    period_start: null,
    period_end: null,
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
  {
    benefit_id: 3,
    profile_card_id: 101,
    card_name: 'Daily Cash',
    card_product_id: 1,
    card_product_name: 'Northwind Cash Everyday',
    name: 'Streaming Credit',
    benefit_type: 'credit',
    value_cents: 1000,
    reset_period: 'monthly',
    notes: 'Monthly streaming',
    period_start: '2026-11-01',
    period_end: '2026-11-30',
    next_reset_date: '2026-12-01',
    days_until_reset: 1,
    used_cents: 1200,
    remaining_cents: -200,
    over_used_cents: 200,
    is_over_used: true,
    usage_count: 1,
    status: 'over_used',
    usages: [
      {
        id: 802,
        profile_card_id: 101,
        benefit_definition_id: 3,
        amount_cents: 1200,
        used_on: '2026-11-05',
        note: 'Streaming bundle',
      },
    ],
  },
];

const MOCK_T43_BENEFITS_DEV = [
  {
    benefit_id: 4,
    profile_card_id: 201,
    card_name: 'Summit Points',
    card_product_id: 3,
    card_product_name: 'Horizon Summit Points',
    name: 'Travel Credit',
    benefit_type: 'credit',
    value_cents: 25000,
    reset_period: 'calendar_year',
    notes: 'Annual travel credit',
    period_start: '2026-01-01',
    period_end: '2026-12-31',
    next_reset_date: '2027-01-01',
    days_until_reset: 40,
    used_cents: 0,
    remaining_cents: 25000,
    over_used_cents: 0,
    is_over_used: false,
    usage_count: 0,
    status: 'unused',
    usages: [],
  },
];

function mockT43Fetch(options?: {
  profiles?: typeof MOCK_PROFILES;
  benefitsOk?: boolean;
  emptyBenefits?: boolean;
  logStatus?: number;
  deleteOk?: boolean;
}) {
  const profiles = options?.profiles ?? MOCK_PROFILES;
  const benefitsOk = options?.benefitsOk ?? true;
  const emptyBenefits = options?.emptyBenefits ?? false;
  const logStatus = options?.logStatus ?? 201;
  const deleteOk = options?.deleteOk ?? true;

  const benefitsByProfile: Record<string, Array<Record<string, unknown>>> = {
    maya: JSON.parse(JSON.stringify(MOCK_T43_BENEFITS_MAYA)),
    dev: JSON.parse(JSON.stringify(MOCK_T43_BENEFITS_DEV)),
  };
  let nextUsageId = 900;

  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    const method = init?.method ?? 'GET';

    if (url.endsWith('/healthz')) {
      return { ok: true, status: 200, json: async () => ({ status: 'ok' }) } as Response;
    }
    if (url.endsWith('/profiles') && method === 'GET') {
      return { ok: true, status: 200, json: async () => profiles } as Response;
    }

    const listMatch = url.match(/\/profiles\/([^/]+)\/benefits$/);
    if (listMatch && method === 'GET') {
      if (!benefitsOk) {
        return {
          ok: false,
          status: 500,
          json: async () => ({ title: 'Error', detail: 'Benefits failed' }),
        } as Response;
      }
      const slug = decodeURIComponent(listMatch[1]);
      return {
        ok: true,
        status: 200,
        json: async () => (emptyBenefits ? [] : (benefitsByProfile[slug] ?? [])),
      } as Response;
    }

    const postMatch = url.match(/\/profiles\/([^/]+)\/benefits\/(\d+)\/usages$/);
    if (postMatch && method === 'POST') {
      if (logStatus !== 201) {
        return {
          ok: false,
          status: logStatus,
          json: async () => ({
            title: 'Unprocessable Entity',
            status: logStatus,
            detail: 'Validation failed.',
            errors: [
              {
                loc: ['body', 'note'],
                msg: 'Value must not contain 13-19 digit card numbers.',
                type: 'value_error',
              },
            ],
          }),
        } as Response;
      }
      const slug = decodeURIComponent(postMatch[1]);
      const benefitId = Number(postMatch[2]);
      const body = JSON.parse(String(init?.body ?? '{}')) as {
        profile_card_id: number;
        amount_cents: number | null;
        used_on: string;
        note?: string;
      };
      const created = {
        id: nextUsageId++,
        profile_card_id: body.profile_card_id,
        benefit_definition_id: benefitId,
        amount_cents: body.amount_cents,
        used_on: body.used_on,
        note: body.note ?? '',
      };
      const target = (benefitsByProfile[slug] ?? []).find(
        (b) => b.benefit_id === benefitId && b.profile_card_id === body.profile_card_id,
      );
      if (target) {
        target.usages = [...(target.usages as unknown[]), created];
      }
      return { ok: true, status: 201, json: async () => created } as Response;
    }

    const deleteMatch = url.match(/\/profiles\/([^/]+)\/benefits\/(\d+)\/usages\/(\d+)$/);
    if (deleteMatch && method === 'DELETE') {
      if (!deleteOk) {
        return {
          ok: false,
          status: 500,
          json: async () => ({ title: 'Error', detail: 'Delete usage failed.' }),
        } as Response;
      }
      const slug = decodeURIComponent(deleteMatch[1]);
      const usageId = Number(deleteMatch[3]);
      for (const b of benefitsByProfile[slug] ?? []) {
        b.usages = (b.usages as Array<{ id: number }>).filter((u) => u.id !== usageId);
      }
      return { ok: true, status: 204 } as Response;
    }

    return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
  });
}

describe('T43 Benefits view', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders statuses, overused/negative remaining, null reset dates, and singular/plural day counts', async () => {
    mockT43Fetch();
    render(<App initialEntries={['/benefits']} />);

    const diningCard = await screen.findByTestId('benefit-card-101-1');
    expect(within(diningCard).getByText('Status: Partially used')).toBeInTheDocument();
    expect(within(diningCard).getByText('2026-12-01 (10 days left)')).toBeInTheDocument();
    expect(within(diningCard).getByTestId('benefit-usage-item-801')).toHaveTextContent(
      /2026-11-10 — \$5\.00 \(Cafe lunch\)/,
    );

    const perkCard = screen.getByTestId('benefit-card-102-2');
    expect(within(perkCard).getByText('Status: Unused')).toBeInTheDocument();
    expect(within(perkCard).getByText('Period unavailable')).toBeInTheDocument();
    expect(within(perkCard).getByText('Reset date unavailable')).toBeInTheDocument();

    const overusedCard = screen.getByTestId('benefit-card-101-3');
    expect(within(overusedCard).getByText('Status: Overused')).toBeInTheDocument();
    expect(within(overusedCard).getByText('-$2.00')).toBeInTheDocument();
    expect(within(overusedCard).getByText('Overused by $2.00')).toBeInTheDocument();
    expect(within(overusedCard).getByText('2026-12-01 (1 day left)')).toBeInTheDocument();
  });

  it('logs monetary and non-monetary perk usages, validates USD, and surfaces 422 sensitive-data errors', async () => {
    const fetchSpy = mockT43Fetch();
    render(<App initialEntries={['/benefits']} />);

    const diningCard = await screen.findByTestId('benefit-card-101-1');
    const noteInput = within(diningCard).getByLabelText('Note (optional)');
    expect(noteInput).toHaveAttribute('aria-describedby', 'benefit-note-hint-101:1');
    expect(
      within(diningCard).getByText('Do not enter real card numbers or sensitive data.'),
    ).toBeInTheDocument();

    // Invalid USD -> no POST
    fireEvent.change(within(diningCard).getByLabelText('Usage Amount (USD)'), {
      target: { value: '0' },
    });
    fireEvent.click(within(diningCard).getByRole('button', { name: 'Log Usage' }));
    expect(await within(diningCard).findByRole('alert')).toHaveTextContent(
      'Enter a positive USD amount with up to two decimal places',
    );
    expect(fetchSpy.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);

    // Valid monetary log
    fireEvent.change(within(diningCard).getByLabelText('Usage Amount (USD)'), {
      target: { value: '10.00' },
    });
    fireEvent.change(noteInput, { target: { value: 'Bistro' } });
    fireEvent.click(within(diningCard).getByRole('button', { name: 'Log Usage' }));
    expect(await within(diningCard).findByRole('status')).toHaveTextContent(
      /Logged \$10\.00 usage/,
    );

    // Non-monetary perk log -> sends amount_cents: null
    const perkCard = screen.getByTestId('benefit-card-102-2');
    expect(within(perkCard).queryByLabelText('Usage Amount (USD)')).not.toBeInTheDocument();
    fireEvent.click(within(perkCard).getByRole('button', { name: 'Log Usage' }));
    expect(await within(perkCard).findByRole('status')).toHaveTextContent(/Logged perk usage/);

    const posts = fetchSpy.mock.calls.filter(([, init]) => init?.method === 'POST');
    expect(posts).toHaveLength(2);
    expect(JSON.parse(String(posts[1]?.[1]?.body))).toMatchObject({
      profile_card_id: 102,
      amount_cents: null,
    });

    // Server 422 sensitive-data error
    mockT43Fetch({ logStatus: 422 });
    fireEvent.change(within(diningCard).getByLabelText('Usage Amount (USD)'), {
      target: { value: '5.00' },
    });
    fireEvent.change(noteInput, { target: { value: '4111111111111111' } });
    fireEvent.click(within(diningCard).getByRole('button', { name: 'Log Usage' }));
    expect(await within(diningCard).findByRole('alert')).toHaveTextContent(
      'Value must not contain 13-19 digit card numbers.',
    );
  });

  it('handles usage deletion confirmation, cancellation, success, and failure', async () => {
    mockT43Fetch({ deleteOk: true });
    const { unmount } = render(<App initialEntries={['/benefits']} />);

    const usageRow = await screen.findByTestId('benefit-usage-item-801');
    fireEvent.click(within(usageRow).getByRole('button', { name: 'Remove' }));
    expect(
      within(usageRow).getByRole('group', { name: 'Confirm removal of usage 801' }),
    ).toBeInTheDocument();
    fireEvent.click(within(usageRow).getByRole('button', { name: 'Cancel' }));
    expect(screen.getByTestId('benefit-usage-item-801')).toBeInTheDocument();

    fireEvent.click(within(usageRow).getByRole('button', { name: 'Remove' }));
    fireEvent.click(within(usageRow).getByRole('button', { name: 'Confirm Remove' }));
    await waitFor(() => {
      expect(screen.queryByTestId('benefit-usage-item-801')).not.toBeInTheDocument();
    });
    expect(screen.getByText('Removed benefit usage entry.')).toBeInTheDocument();
    unmount();

    mockT43Fetch({ deleteOk: false });
    render(<App initialEntries={['/benefits']} />);
    const failUsageRow = await screen.findByTestId('benefit-usage-item-801');
    fireEvent.click(within(failUsageRow).getByRole('button', { name: 'Remove' }));
    fireEvent.click(within(failUsageRow).getByRole('button', { name: 'Confirm Remove' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Delete usage failed.');
    expect(screen.getByTestId('benefit-usage-item-801')).toBeInTheDocument();
  });

  it('isolates deferred log and delete mutations across profile switches', async () => {
    let resolveDeferredPost!: (res: Response) => void;
    let resolveDeferredDelete!: (res: Response) => void;
    let mayaBenefitFetches = 0;

    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      const method = init?.method ?? 'GET';
      if (url.endsWith('/healthz')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ status: 'ok' }) } as Response);
      }
      if (url.endsWith('/profiles')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => MOCK_PROFILES } as Response);
      }
      if (url.endsWith('/profiles/maya/benefits') && method === 'GET') {
        mayaBenefitFetches += 1;
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => MOCK_T43_BENEFITS_MAYA,
        } as Response);
      }
      if (url.endsWith('/profiles/dev/benefits') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => MOCK_T43_BENEFITS_DEV,
        } as Response);
      }
      if (url.includes('/profiles/maya/benefits/') && method === 'POST') {
        return new Promise<Response>((resolve) => {
          resolveDeferredPost = resolve;
        });
      }
      if (url.includes('/profiles/maya/benefits/') && method === 'DELETE') {
        return new Promise<Response>((resolve) => {
          resolveDeferredDelete = resolve;
        });
      }
      return Promise.resolve({ ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response);
    });

    // Deferred log mutation across profile switch
    const { unmount } = render(<App initialEntries={['/benefits']} />);
    const diningCard = await screen.findByTestId('benefit-card-101-1');
    const initialMayaFetches = mayaBenefitFetches;

    fireEvent.change(within(diningCard).getByLabelText('Usage Amount (USD)'), {
      target: { value: '10.00' },
    });
    fireEvent.click(within(diningCard).getByRole('button', { name: 'Log Usage' }));

    fireEvent.change(screen.getByLabelText('Select demo profile'), { target: { value: 'dev' } });
    expect(await screen.findByTestId('benefit-card-201-4')).toBeInTheDocument();

    resolveDeferredPost({
      ok: true,
      status: 201,
      json: async () => ({
        id: 950,
        profile_card_id: 101,
        benefit_definition_id: 1,
        amount_cents: 1000,
        used_on: '2026-11-22',
        note: '',
      }),
    } as Response);

    await waitFor(() => {
      expect(screen.queryByText(/Logged \$10\.00 usage/)).not.toBeInTheDocument();
    });
    fireEvent.change(screen.getByLabelText('Select demo profile'), { target: { value: 'maya' } });
    await waitFor(() => {
      expect(mayaBenefitFetches).toBeGreaterThan(initialMayaFetches);
    });
    unmount();

    // Deferred delete mutation across profile switch
    mayaBenefitFetches = 0;
    render(<App initialEntries={['/benefits']} />);
    const usageRow = await screen.findByTestId('benefit-usage-item-801');
    const fetchesBeforeDelete = mayaBenefitFetches;

    fireEvent.click(within(usageRow).getByRole('button', { name: 'Remove' }));
    fireEvent.click(within(usageRow).getByRole('button', { name: 'Confirm Remove' }));

    fireEvent.change(screen.getByLabelText('Select demo profile'), { target: { value: 'dev' } });
    expect(await screen.findByTestId('benefit-card-201-4')).toBeInTheDocument();

    resolveDeferredDelete({ ok: true, status: 204 } as Response);

    await waitFor(() => {
      expect(screen.queryByText('Removed benefit usage entry.')).not.toBeInTheDocument();
    });
    fireEvent.change(screen.getByLabelText('Select demo profile'), { target: { value: 'maya' } });
    await waitFor(() => {
      expect(mayaBenefitFetches).toBeGreaterThan(fetchesBeforeDelete);
    });
  });

  it('handles empty profiles, empty benefits, and error/retry recovery', async () => {
    const emptyFetchSpy = mockT43Fetch({ profiles: [] });
    const { unmount } = render(<App initialEntries={['/benefits']} />);
    expect(
      await screen.findByText('Select a demo profile to view and log card benefits.'),
    ).toBeInTheDocument();
    expect(
      emptyFetchSpy.mock.calls.some(([u]) => String(u).includes('/profiles/')),
    ).toBe(false);
    unmount();

    mockT43Fetch({ emptyBenefits: true });
    const { unmount: unmountEmptyBenefits } = render(<App initialEntries={['/benefits']} />);
    expect(
      await screen.findByText("No benefits defined for this profile's active cards."),
    ).toBeInTheDocument();
    unmountEmptyBenefits();

    let failBenefits = true;
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      if (url.endsWith('/healthz')) {
        return { ok: true, status: 200, json: async () => ({ status: 'ok' }) } as Response;
      }
      if (url.endsWith('/profiles')) {
        return { ok: true, status: 200, json: async () => MOCK_PROFILES } as Response;
      }
      if (url.endsWith('/profiles/maya/benefits')) {
        if (failBenefits) {
          return {
            ok: false,
            status: 500,
            json: async () => ({ title: 'Error', detail: 'Benefits fetch failed' }),
          } as Response;
        }
        return { ok: true, status: 200, json: async () => MOCK_T43_BENEFITS_MAYA } as Response;
      }
      return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
    });

    render(<App initialEntries={['/benefits']} />);
    const retryBtn = await screen.findByRole('button', { name: 'Retry Benefits' });
    failBenefits = false;
    fireEvent.click(retryBtn);
    expect(await screen.findByTestId('benefit-card-101-1')).toBeInTheDocument();
  });
});

const MOCK_T44_SUMMARY_MAYA = {
  profile_id: 1,
  profile_slug: 'maya',
  currencies: [
    {
      reward_currency_id: 1,
      reward_currency_code: 'NW_CASH',
      reward_currency_name: 'Northwind Cash',
      reward_currency_kind: 'cash_back',
      total_reward_units: '1.3000',
      transaction_count: 2,
      is_valued: true,
      valuation_status: 'valued',
      current_cents_per_unit: '1.0000',
      is_user_set: false,
      estimated_value_cents: 130,
      limitation_note: null,
    },
    {
      reward_currency_id: 2,
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
    {
      reward_currency_id: 3,
      reward_currency_code: 'SKY_MILES',
      reward_currency_name: 'Skyward Miles',
      reward_currency_kind: 'miles',
      total_reward_units: '400.0000',
      transaction_count: 1,
      is_valued: false,
      valuation_status: 'unvalued',
      current_cents_per_unit: null,
      is_user_set: null,
      estimated_value_cents: null,
      limitation_note: 'No valuation configured for Skyward Miles.',
    },
  ],
  estimated_total_usd_cents: 880,
  estimated_total_label:
    'Estimated USD value based on current valuations (excludes unvalued currencies)',
  excluded_unvalued_currency_codes: ['SKY_MILES'],
  limitation_message: 'Excluded unvalued currencies from estimated USD total: SKY_MILES.',
};

const MOCK_T44_SUMMARY_NONE_VALUED = {
  profile_id: 1,
  profile_slug: 'maya',
  currencies: [
    {
      reward_currency_id: 3,
      reward_currency_code: 'SKY_MILES',
      reward_currency_name: 'Skyward Miles',
      reward_currency_kind: 'miles',
      total_reward_units: '400.0000',
      transaction_count: 1,
      is_valued: false,
      valuation_status: 'unvalued',
      current_cents_per_unit: null,
      is_user_set: null,
      estimated_value_cents: null,
      limitation_note: 'No valuation configured for Skyward Miles.',
    },
  ],
  estimated_total_usd_cents: 0,
  estimated_total_label:
    'Estimated USD value based on current valuations (excludes unvalued currencies)',
  excluded_unvalued_currency_codes: ['SKY_MILES'],
  limitation_message: 'Excluded unvalued currencies from estimated USD total: SKY_MILES.',
};

const MOCK_T44_SUMMARY_DEV = {
  profile_id: 2,
  profile_slug: 'dev',
  currencies: [
    {
      reward_currency_id: 4,
      reward_currency_code: 'DEV_PTS',
      reward_currency_name: 'Dev Points',
      reward_currency_kind: 'points',
      total_reward_units: '250.0000',
      transaction_count: 1,
      is_valued: true,
      valuation_status: 'valued',
      current_cents_per_unit: '2.0000',
      is_user_set: true,
      estimated_value_cents: 500,
      limitation_note: null,
    },
  ],
  estimated_total_usd_cents: 500,
  estimated_total_label:
    'Estimated USD value based on current valuations (excludes unvalued currencies)',
  excluded_unvalued_currency_codes: [],
  limitation_message: null,
};

function mockT44Fetch(options?: {
  profiles?: typeof MOCK_PROFILES;
  summaryOk?: boolean;
  mayaSummary?: typeof MOCK_T44_SUMMARY_MAYA | typeof MOCK_T44_SUMMARY_NONE_VALUED;
  emptySummary?: boolean;
}) {
  const profiles = options?.profiles ?? MOCK_PROFILES;
  const summaryOk = options?.summaryOk ?? true;
  const mayaSummary = options?.mayaSummary ?? MOCK_T44_SUMMARY_MAYA;
  const emptySummary = options?.emptySummary ?? false;

  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url.endsWith('/healthz')) {
      return { ok: true, status: 200, json: async () => ({ status: 'ok' }) } as Response;
    }
    if (url.endsWith('/profiles')) {
      return { ok: true, status: 200, json: async () => profiles } as Response;
    }
    const match = url.match(/\/profiles\/([^/]+)\/rewards\/summary$/);
    if (match) {
      if (!summaryOk) {
        return {
          ok: false,
          status: 500,
          json: async () => ({ title: 'Error', detail: 'Summary failed' }),
        } as Response;
      }
      const slug = decodeURIComponent(match[1]);
      if (emptySummary) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            profile_id: slug === 'maya' ? 1 : 2,
            profile_slug: slug,
            currencies: [],
            estimated_total_usd_cents: 0,
            estimated_total_label: 'Estimated USD value',
            excluded_unvalued_currency_codes: [],
            limitation_message: null,
          }),
        } as Response;
      }
      return {
        ok: true,
        status: 200,
        json: async () => (slug === 'dev' ? MOCK_T44_SUMMARY_DEV : mayaSummary),
      } as Response;
    }
    return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
  });
}

describe('T44 Rewards view', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders separate per-currency table and estimated USD section with valued and unvalued currencies', async () => {
    mockT44Fetch();
    render(<App initialEntries={['/rewards']} />);

    const table = await screen.findByRole('table', { name: /Earned Rewards by Currency/i });
    expect(within(table).getByTestId('rewards-row-NW_CASH')).toHaveTextContent(
      'Illustrative default (1.0000¢/unit)',
    );
    expect(within(table).getByTestId('rewards-row-HORIZON_PTS')).toHaveTextContent(
      'User-configured (1.5000¢/unit)',
    );
    expect(within(table).getByTestId('rewards-row-SKY_MILES')).toHaveTextContent('Unvalued');
    expect(
      screen.getByText(/Raw reward units are grouped strictly by currency and are never combined/),
    ).toBeInTheDocument();

    // Separate Estimated USD Value section
    expect(
      screen.getByRole('heading', { level: 2, name: /Estimated USD Value/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId('rewards-estimate-NW_CASH')).toHaveTextContent('$1.30');
    expect(screen.getByTestId('rewards-estimate-HORIZON_PTS')).toHaveTextContent('$7.50');

    const unvaluedEstimate = screen.getByTestId('rewards-estimate-SKY_MILES');
    expect(unvaluedEstimate).toHaveTextContent('Unvalued — excluded from estimate');
    expect(unvaluedEstimate).toHaveTextContent('No valuation configured for Skyward Miles.');
    expect(unvaluedEstimate).not.toHaveTextContent('$0.00');

    expect(screen.getByText('$8.80')).toBeInTheDocument();
    expect(
      screen.getByText('Excluded unvalued currencies from estimated USD total: SKY_MILES.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Excluded unvalued currencies: SKY_MILES')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Manage Valuations' })).toHaveAttribute(
      'href',
      '/settings',
    );
    expect(screen.getByRole('link', { name: 'View Transactions' })).toHaveAttribute(
      'href',
      '/transactions',
    );
  });

  it('does not misleadingly display $0.00 when no currencies have a valuation', async () => {
    mockT44Fetch({ mayaSummary: MOCK_T44_SUMMARY_NONE_VALUED });
    render(<App initialEntries={['/rewards']} />);

    expect(
      await screen.findByText('Estimated total unavailable — no currencies have a valuation.'),
    ).toBeInTheDocument();
    expect(screen.queryByText('$0.00')).not.toBeInTheDocument();
  });

  it('handles empty rewards summary, no-profile state, error/retry recovery, and profile-switch isolation', async () => {
    mockT44Fetch({ emptySummary: true });
    const { unmount } = render(<App initialEntries={['/rewards']} />);
    expect(
      await screen.findByText(/No rewards earned yet for this profile/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { level: 2, name: /Estimated USD Value/i }),
    ).not.toBeInTheDocument();
    unmount();

    // No-profile state -> zero profile requests
    const emptyFetchSpy = mockT44Fetch({ profiles: [] });
    emptyFetchSpy.mockClear();
    const { unmount: unmountNoProfile } = render(<App initialEntries={['/rewards']} />);
    expect(
      await screen.findByText('Select a demo profile to view earned rewards.'),
    ).toBeInTheDocument();
    expect(
      emptyFetchSpy.mock.calls.some(([u]) => String(u).includes('/profiles/')),
    ).toBe(false);
    unmountNoProfile();

    // Error & Retry recovery + profile switch
    let failSummary = true;
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      if (url.endsWith('/healthz')) {
        return { ok: true, status: 200, json: async () => ({ status: 'ok' }) } as Response;
      }
      if (url.endsWith('/profiles')) {
        return { ok: true, status: 200, json: async () => MOCK_PROFILES } as Response;
      }
      if (url.endsWith('/profiles/maya/rewards/summary')) {
        if (failSummary) {
          return {
            ok: false,
            status: 500,
            json: async () => ({ title: 'Error', detail: 'Summary error' }),
          } as Response;
        }
        return { ok: true, status: 200, json: async () => MOCK_T44_SUMMARY_MAYA } as Response;
      }
      if (url.endsWith('/profiles/dev/rewards/summary')) {
        return { ok: true, status: 200, json: async () => MOCK_T44_SUMMARY_DEV } as Response;
      }
      return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
    });

    render(<App initialEntries={['/rewards']} />);
    const retryBtn = await screen.findByRole('button', { name: 'Retry Rewards Summary' });
    failSummary = false;
    fireEvent.click(retryBtn);
    expect(await screen.findByTestId('rewards-row-NW_CASH')).toBeInTheDocument();

    // Switch to Dev -> Maya's data does not remain visible
    fireEvent.change(screen.getByLabelText('Select demo profile'), { target: { value: 'dev' } });
    expect(await screen.findByTestId('rewards-row-DEV_PTS')).toBeInTheDocument();
    expect(screen.queryByTestId('rewards-row-NW_CASH')).not.toBeInTheDocument();
  });
});

describe('T45 Accessibility and Empty-State Polish', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows clear no-profile messages on Dashboard without perpetual loading or profile API calls', async () => {
    const fetchSpy = mockFetchHandlers({ profiles: [] });
    render(<App initialEntries={['/']} />);

    expect(
      await screen.findByText('Select a demo profile to view benefit alerts.'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Select a demo profile to view rewards snapshot.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Select a demo profile to view held cards.')).toBeInTheDocument();

    expect(screen.queryByText('Loading benefit alerts...')).not.toBeInTheDocument();
    expect(screen.queryByText('Loading rewards snapshot...')).not.toBeInTheDocument();
    expect(screen.queryByText('Loading cards...')).not.toBeInTheDocument();
    expect(
      fetchSpy.mock.calls.some(([u]) => String(u).includes('/profiles/')),
    ).toBe(false);
  });

  it('does not display $0.00 on Dashboard when no currencies are valued', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      if (url.endsWith('/healthz')) {
        return { ok: true, status: 200, json: async () => ({ status: 'ok' }) } as Response;
      }
      if (url.endsWith('/profiles')) {
        return { ok: true, status: 200, json: async () => MOCK_PROFILES } as Response;
      }
      if (url.endsWith('/profiles/maya/cards')) {
        return { ok: true, status: 200, json: async () => MOCK_CARDS.maya } as Response;
      }
      if (url.endsWith('/profiles/maya/benefits')) {
        return { ok: true, status: 200, json: async () => [] } as Response;
      }
      if (url.endsWith('/profiles/maya/rewards/summary')) {
        return {
          ok: true,
          status: 200,
          json: async () => MOCK_T44_SUMMARY_NONE_VALUED,
        } as Response;
      }
      return { ok: false, status: 404, json: async () => ({ title: 'Not Found' }) } as Response;
    });

    render(<App initialEntries={['/']} />);

    expect(
      await screen.findByText('Estimated total unavailable — no currencies have a valuation.'),
    ).toBeInTheDocument();
    expect(screen.queryByText('$0.00')).not.toBeInTheDocument();
  });

  it('provides skip-to-main-content navigation, focusable main landmark, and aria-hidden decorative emojis', async () => {
    mockFetchHandlers();
    render(<App initialEntries={['/']} />);

    const skipLink = screen.getByRole('link', { name: 'Skip to main content' });
    expect(skipLink).toHaveAttribute('href', '#main-content');

    const main = screen.getByRole('main');
    expect(main).toHaveAttribute('id', 'main-content');
    expect(main).toHaveAttribute('tabindex', '-1');
    main.focus();
    expect(main).toHaveFocus();

    const alertsHeading = await screen.findByRole('heading', {
      level: 3,
      name: /Upcoming Benefit Resets/i,
    });
    const emojiSpan = alertsHeading.querySelector('span[aria-hidden="true"]');
    expect(emojiSpan).toBeInTheDocument();
  });
});
