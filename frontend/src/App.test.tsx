import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App } from './App';
import { BackendStatus, getHealthUrl } from './components/BackendStatus';
import { formatCentsToUsd } from './lib/formatters';

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

describe('CardPilot App and Dashboard', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok', version: '0.1.0' }),
    } as Response);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders application brand, header, and demo disclaimer banner', async () => {
    render(<App />);

    expect(screen.getByRole('heading', { level: 1, name: /CardPilot/i })).toBeInTheDocument();
    expect(screen.getByRole('complementary', { name: /Demo Disclaimer/i })).toBeInTheDocument();
    expect(screen.getByText(/DEMO DATA ONLY/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('API Connected')).toBeInTheDocument();
    });
  });

  it('renders default profile portfolio cards and benefit alerts for Maya', async () => {
    render(<App />);

    // Default profile check
    expect(screen.getByText(/Active Profile: Maya/i)).toBeInTheDocument();

    // Verify Maya's cards are present by role
    expect(screen.getByRole('heading', { level: 4, name: 'Daily Sapphire' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 4, name: 'Dining Unlimited' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 4, name: 'Skyward Explorer' })).toBeInTheDocument();

    // Verify upcoming benefit alerts
    const alertHeading = screen.getByRole('heading', { level: 3, name: /Upcoming Benefit Resets/i });
    expect(alertHeading).toBeInTheDocument();
    expect(screen.getByText('Annual Hotel Statement Credit')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('API Connected')).toBeInTheDocument();
    });
  });

  it('updates dashboard portfolio and alerts when switching demo profile', async () => {
    render(<App />);

    const select = screen.getByLabelText(/Select demo profile/i);
    fireEvent.change(select, { target: { value: 'dev' } });

    // Verify Dev profile is active
    expect(screen.getByText(/Active Profile: Dev/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 4, name: 'Platinum Lux' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 4, name: 'Grocery Gold' })).toBeInTheDocument();
    expect(screen.getByText('Monthly Dining Statement Credit')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('API Connected')).toBeInTheDocument();
    });
  });

  it('navigates to placeholder views and returns to dashboard', async () => {
    render(<App />);

    // Click Compare navigation button
    const compareNavButton = screen.getByRole('button', { name: /^Compare$/i });
    fireEvent.click(compareNavButton);

    expect(screen.getByRole('heading', { level: 2, name: /Compare View/i })).toBeInTheDocument();

    // Click Return to Dashboard button
    const returnButton = screen.getByRole('button', { name: /Return to Dashboard/i });
    fireEvent.click(returnButton);

    expect(screen.getByRole('heading', { level: 2, name: /Cardholder Portfolio Overview/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('API Connected')).toBeInTheDocument();
    });
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

  it('displays API Connected when /healthz returns ok', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'ok', version: '0.1.0' }),
    } as Response);

    render(<BackendStatus />);

    await waitFor(() => {
      expect(screen.getByText('API Connected')).toBeInTheDocument();
    });
  });

  it('displays API Offline when /healthz fetch fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error('Network error'));

    render(<BackendStatus />);

    await waitFor(() => {
      expect(screen.getByText('API Offline')).toBeInTheDocument();
    });
  });

  it('displays API Offline when /healthz returns non-200', async () => {
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
