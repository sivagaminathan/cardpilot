import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { App } from './App';
import { BackendStatus, getHealthUrl } from './components/BackendStatus';
import { formatCentsToUsd } from './lib/formatters';

const MOCK_PROFILES = [
  { id: 1, slug: 'maya', display_name: 'Maya — The Optimizer', is_demo: true },
  { id: 2, slug: 'dev', display_name: 'Dev — Benefit Tracker', is_demo: true },
];

function mockFetchHandlers(options?: {
  profiles?: typeof MOCK_PROFILES;
  profilesOk?: boolean;
  resetOk?: boolean;
}) {
  const profiles = options?.profiles ?? MOCK_PROFILES;
  const profilesOk = options?.profilesOk ?? true;
  const resetOk = options?.resetOk ?? true;

  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
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
      return {
        ok: true,
        status: 200,
        json: async () => profiles,
      } as Response;
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
      return {
        ok: true,
        status: 200,
        json: async () => ({
          status: 'reset',
          profile: profiles[0],
          cards_restored: 4,
          valuations_restored: 2,
        }),
      } as Response;
    }
    return { ok: false, status: 404, json: async () => ({ title: 'Not Found', status: 404 }) } as Response;
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

describe('CardPilot App Shell, Router, Disclaimer, and Profile Picker', () => {
  beforeEach(() => {
    mockFetchHandlers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('loads profiles from GET /api/v1/profiles and renders persistent disclaimer', async () => {
    render(<App />);

    expect(screen.getByRole('heading', { level: 1, name: /CardPilot/i })).toBeInTheDocument();
    expect(screen.getByText('Loading profiles...')).toBeInTheDocument();
    const banner = screen.getByRole('complementary', { name: /Demo Disclaimer/i });
    expect(
      within(banner).getByText(/Sample data only\. Not issuer terms\. Not financial advice\./i),
    ).toBeInTheDocument();

    const select = await screen.findByLabelText(/Select demo profile/i);
    expect(select).toHaveValue('maya');
    expect(screen.getByRole('option', { name: 'Maya — The Optimizer' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Dev — Benefit Tracker' })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('API Connected')).toBeInTheDocument();
    });
  });

  it('switches profiles and supports two-step demo reset with feedback', async () => {
    const fetchSpy = mockFetchHandlers();
    render(<App />);

    const select = await screen.findByLabelText(/Select demo profile/i);
    fireEvent.change(select, { target: { value: 'dev' } });
    expect(select).toHaveValue('dev');
    expect(screen.getByRole('heading', { level: 4, name: 'Platinum Lux' })).toBeInTheDocument();

    // First click opens confirmation without calling POST /reset yet
    fireEvent.click(screen.getByRole('button', { name: 'Reset Demo Data' }));
    expect(screen.getByRole('button', { name: 'Confirm Reset' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.getByRole('button', { name: 'Reset Demo Data' })).toBeInTheDocument();

    // Confirm reset executes POST /profiles/dev/reset
    fireEvent.click(screen.getByRole('button', { name: 'Reset Demo Data' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Reset' }));

    await waitFor(() => {
      expect(screen.getByText(/4 cards, 2 valuations restored/i)).toBeInTheDocument();
    });
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/profiles/dev/reset',
      expect.objectContaining({ method: 'POST' }),
    );
    // Query invalidation triggers a refetch of /api/v1/profiles
    await waitFor(() => {
      const profileGets = fetchSpy.mock.calls.filter(
        ([url, init]: [RequestInfo | URL, RequestInit?]) =>
          String(url).endsWith('/profiles') && (!init?.method || init.method === 'GET'),
      );
      expect(profileGets.length).toBeGreaterThanOrEqual(2);
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

  it('handles profile loading error, retry, empty list, and reset error states', async () => {
    vi.restoreAllMocks();
    mockFetchHandlers({ profilesOk: false });
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/Database unavailable/i);
    });

    vi.restoreAllMocks();
    mockFetchHandlers({ profiles: [] });
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    await waitFor(() => {
      expect(screen.getByText('No profiles available')).toBeInTheDocument();
    });
  });

  it('navigates across all routes while keeping the disclaimer banner visible', async () => {
    render(<App />);
    await screen.findByLabelText(/Select demo profile/i);

    const routeChecks: Array<{ link: RegExp; heading: RegExp }> = [
      { link: /^Cards$/i, heading: /Cards View/i },
      { link: /^Compare$/i, heading: /Compare Cards for Purchase/i },
      { link: /^Transactions$/i, heading: /Transactions View/i },
      { link: /^Benefits$/i, heading: /Benefits View/i },
      { link: /^Rewards$/i, heading: /Rewards View/i },
      { link: /^Settings$/i, heading: /Settings View/i },
      { link: /^Rules$/i, heading: /Rules View/i },
      { link: /^Dashboard$/i, heading: /Cardholder Portfolio Overview/i },
    ];

    for (const check of routeChecks) {
      fireEvent.click(screen.getByRole('link', { name: check.link }));
      expect(screen.getByRole('heading', { level: 2, name: check.heading })).toBeInTheDocument();
      const banner = screen.getByRole('complementary', { name: /Demo Disclaimer/i });
      expect(
        within(banner).getByText(/Sample data only\. Not issuer terms\. Not financial advice\./i),
      ).toBeInTheDocument();
    }
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
