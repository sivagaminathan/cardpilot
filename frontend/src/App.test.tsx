import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { App } from './App';
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
  it('renders application brand, header, and demo disclaimer banner', () => {
    render(<App />);

    expect(screen.getByRole('heading', { level: 1, name: /CardPilot/i })).toBeInTheDocument();
    expect(screen.getByRole('complementary', { name: /Demo Disclaimer/i })).toBeInTheDocument();
    expect(screen.getByText(/DEMO DATA ONLY/i)).toBeInTheDocument();
  });

  it('renders default profile portfolio cards and benefit alerts for Maya', () => {
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
  });

  it('updates dashboard portfolio and alerts when switching demo profile', () => {
    render(<App />);

    const select = screen.getByLabelText(/Select demo profile/i);
    fireEvent.change(select, { target: { value: 'dev' } });

    // Verify Dev profile is active
    expect(screen.getByText(/Active Profile: Dev/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 4, name: 'Platinum Lux' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 4, name: 'Grocery Gold' })).toBeInTheDocument();
    expect(screen.getByText('Monthly Dining Statement Credit')).toBeInTheDocument();
  });

  it('navigates to placeholder views and returns to dashboard', () => {
    render(<App />);

    // Click Compare navigation button
    const compareNavButton = screen.getByRole('button', { name: /^Compare$/i });
    fireEvent.click(compareNavButton);

    expect(screen.getByRole('heading', { level: 2, name: /Compare View/i })).toBeInTheDocument();

    // Click Return to Dashboard button
    const returnButton = screen.getByRole('button', { name: /Return to Dashboard/i });
    fireEvent.click(returnButton);

    expect(screen.getByRole('heading', { level: 2, name: /Cardholder Portfolio Overview/i })).toBeInTheDocument();
  });
});
