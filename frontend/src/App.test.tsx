import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { App } from './App';
import { BackendStatus, getHealthUrl } from './components/BackendStatus';
import { formatCentsToUsd } from './lib/formatters';

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
    expect(screen.getByRole('heading', { level: 2, name: /Cards View/i })).toBeInTheDocument();

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
    expect(screen.getByRole('heading', { level: 2, name: /Rules View/i })).toBeInTheDocument();

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
