import React from 'react';
import { formatCentsToUsd } from '../lib/formatters';

export interface DemoCard {
  id: string;
  nickname: string;
  productName: string;
  issuer: string;
  currencyCode: string;
  currencyName: string;
  currencyKind: 'cash_back' | 'points' | 'miles';
  annualFeeCents: number;
  highlightBenefit: string;
}

export interface BenefitAlert {
  id: string;
  cardNickname: string;
  name: string;
  amountCents: number;
  resetDate: string;
  daysRemaining: number;
  period: string;
}

export interface RewardBalance {
  currencyCode: string;
  currencyName: string;
  kind: 'cash_back' | 'points' | 'miles';
  units: string;
  estimatedValueCents: number;
}

const PROFILE_CARDS: Record<string, DemoCard[]> = {
  maya: [
    {
      id: 'c1',
      nickname: 'Daily Sapphire',
      productName: 'Apex Rewards Preferred',
      issuer: 'Nova Bank',
      currencyCode: 'APEX_PTS',
      currencyName: 'Apex Points',
      currencyKind: 'points',
      annualFeeCents: 9500,
      highlightBenefit: '$50 Annual Hotel Credit',
    },
    {
      id: 'c2',
      nickname: 'Dining Unlimited',
      productName: 'Aurora Freedom Cash',
      issuer: 'Aurora Trust',
      currencyCode: 'USD_CASH',
      currencyName: 'Cash Back USD',
      currencyKind: 'cash_back',
      annualFeeCents: 0,
      highlightBenefit: '3% Dining & Drugstores',
    },
    {
      id: 'c3',
      nickname: 'Skyward Explorer',
      productName: 'AeroSky Voyager Elite',
      issuer: 'Global Horizon',
      currencyCode: 'AERO_MILES',
      currencyName: 'AeroMiles',
      currencyKind: 'miles',
      annualFeeCents: 25000,
      highlightBenefit: 'Free Checked Bags & Priority Boarding',
    },
  ],
  dev: [
    {
      id: 'c4',
      nickname: 'Platinum Lux',
      productName: 'Summit Reserve Elite',
      issuer: 'Summit Bank',
      currencyCode: 'SUMMIT_PTS',
      currencyName: 'Summit Points',
      currencyKind: 'points',
      annualFeeCents: 69500,
      highlightBenefit: '$20/mo Dining Credit ($240/yr)',
    },
    {
      id: 'c5',
      nickname: 'Grocery Gold',
      productName: 'Harvest Select Card',
      issuer: 'Pinnacle Financial',
      currencyCode: 'USD_CASH',
      currencyName: 'Cash Back USD',
      currencyKind: 'cash_back',
      annualFeeCents: 9500,
      highlightBenefit: '$10/mo Food Delivery Credit',
    },
  ],
  rivera: [
    {
      id: 'c6',
      nickname: 'Reviewer Cash 2%',
      productName: 'Vanguard Flat 2.0',
      issuer: 'Vanguard Federal',
      currencyCode: 'USD_CASH',
      currencyName: 'Cash Back USD',
      currencyKind: 'cash_back',
      annualFeeCents: 0,
      highlightBenefit: 'Deterministic 2% Everywhere',
    },
    {
      id: 'c7',
      nickname: 'Academic Points Plus',
      productName: 'Horizon Multiplier Scholar',
      issuer: 'Nova Bank',
      currencyCode: 'APEX_PTS',
      currencyName: 'Apex Points',
      currencyKind: 'points',
      annualFeeCents: 9500,
      highlightBenefit: 'Quarterly Category Caps (5× Dining)',
    },
  ],
};

const BENEFIT_ALERTS: Record<string, BenefitAlert[]> = {
  maya: [
    {
      id: 'b1',
      cardNickname: 'Daily Sapphire',
      name: 'Annual Hotel Statement Credit',
      amountCents: 5000,
      resetDate: '2026-12-31',
      daysRemaining: 16,
      period: 'Calendar Year',
    },
  ],
  dev: [
    {
      id: 'b2',
      cardNickname: 'Platinum Lux',
      name: 'Monthly Dining Statement Credit',
      amountCents: 2000,
      resetDate: '2026-11-30',
      daysRemaining: 15,
      period: 'Monthly',
    },
    {
      id: 'b3',
      cardNickname: 'Grocery Gold',
      name: 'Monthly Food Delivery Allowance',
      amountCents: 1000,
      resetDate: '2026-11-30',
      daysRemaining: 15,
      period: 'Monthly',
    },
  ],
  rivera: [
    {
      id: 'b4',
      cardNickname: 'Academic Points Plus',
      name: 'Quarterly 5× Category Spend Cap',
      amountCents: 50000,
      resetDate: '2026-12-31',
      daysRemaining: 16,
      period: 'Quarterly',
    },
  ],
};

const REWARD_BALANCES: Record<string, RewardBalance[]> = {
  maya: [
    {
      currencyCode: 'APEX_PTS',
      currencyName: 'Apex Points',
      kind: 'points',
      units: '42,500',
      estimatedValueCents: 63750,
    },
    {
      currencyCode: 'USD_CASH',
      currencyName: 'Cash Back USD',
      kind: 'cash_back',
      units: '$128.40',
      estimatedValueCents: 12840,
    },
    {
      currencyCode: 'AERO_MILES',
      currencyName: 'AeroMiles',
      kind: 'miles',
      units: '18,200',
      estimatedValueCents: 21840,
    },
  ],
  dev: [
    {
      currencyCode: 'SUMMIT_PTS',
      currencyName: 'Summit Points',
      kind: 'points',
      units: '85,000',
      estimatedValueCents: 144500,
    },
    {
      currencyCode: 'USD_CASH',
      currencyName: 'Cash Back USD',
      kind: 'cash_back',
      units: '$45.20',
      estimatedValueCents: 4520,
    },
  ],
  rivera: [
    {
      currencyCode: 'USD_CASH',
      currencyName: 'Cash Back USD',
      kind: 'cash_back',
      units: '$240.00',
      estimatedValueCents: 24000,
    },
    {
      currencyCode: 'APEX_PTS',
      currencyName: 'Apex Points',
      kind: 'points',
      units: '15,000',
      estimatedValueCents: 22500,
    },
  ],
};

interface DashboardProps {
  profileId: string;
  onNavigateTab: (tab: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ profileId, onNavigateTab }) => {
  const cards = PROFILE_CARDS[profileId] ?? [];
  const alerts = BENEFIT_ALERTS[profileId] ?? [];
  const balances = REWARD_BALANCES[profileId] ?? [];

  return (
    <div className="dashboard-container" data-testid="dashboard-view">
      <section className="hero-section">
        <div className="hero-text">
          <h2 className="hero-title">Cardholder Portfolio Overview</h2>
          <p className="hero-subtitle">
            Deterministic optimization, benefit reset reminders, and currency-honest tracking.
          </p>
        </div>
        <div className="hero-actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => onNavigateTab('compare')}
          >
            Compare Card for Purchase
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => onNavigateTab('transactions')}
          >
            Record Purchase
          </button>
        </div>
      </section>

      {/* Benefit Reset Alerts (FR-25) */}
      <section className="section-card alert-section" aria-labelledby="alerts-heading">
        <div className="section-header">
          <h3 id="alerts-heading" className="section-title">
            ⚠️ Upcoming Benefit Resets (Expiring in &lt; 30 Days)
          </h3>
          <span className="badge badge-warning">{alerts.length} Active Alerts</span>
        </div>

        {alerts.length === 0 ? (
          <p className="empty-message">No upcoming benefit credits expiring within 30 days.</p>
        ) : (
          <div className="alerts-grid">
            {alerts.map((alert) => (
              <div key={alert.id} className="alert-card" data-testid="benefit-alert-card">
                <div className="alert-header">
                  <span className="card-badge">{alert.cardNickname}</span>
                  <span className="expiry-tag">{alert.daysRemaining} days left</span>
                </div>
                <h4 className="benefit-name">{alert.name}</h4>
                <div className="benefit-details">
                  <span className="benefit-amount">{formatCentsToUsd(alert.amountCents)}</span>
                  <span className="benefit-reset">Resets on {alert.resetDate}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Rewards Balances Per Currency (FR-27) */}
      <section className="section-card" aria-labelledby="rewards-heading">
        <div className="section-header">
          <h3 id="rewards-heading" className="section-title">
            🏆 Rewards Balances by Currency
          </h3>
          <small className="currency-note">
            Currencies stay separate. Never summed across different reward units.
          </small>
        </div>

        <div className="balances-grid">
          {balances.map((bal) => (
            <div key={bal.currencyCode} className="balance-card">
              <span className={`currency-kind-tag kind-${bal.kind}`}>{bal.kind.replace('_', ' ')}</span>
              <div className="balance-units">{bal.units}</div>
              <div className="currency-title">{bal.currencyName}</div>
              <div className="balance-estimate">
                Est. Value: <strong>{formatCentsToUsd(bal.estimatedValueCents)}</strong>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Active Cards Portfolio */}
      <section className="section-card" aria-labelledby="cards-heading">
        <div className="section-header">
          <h3 id="cards-heading" className="section-title">
            💳 Held Credit Cards ({cards.length})
          </h3>
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => onNavigateTab('cards')}
          >
            Manage Cards
          </button>
        </div>

        <div className="cards-grid">
          {cards.map((card) => (
            <article key={card.id} className="card-item" data-testid="portfolio-card-item">
              <div className="card-item-header">
                <span className="issuer-name">{card.issuer}</span>
                <span className="fee-badge">
                  {card.annualFeeCents === 0 ? '$0 Fee' : `${formatCentsToUsd(card.annualFeeCents)}/yr`}
                </span>
              </div>
              <h4 className="card-nickname">{card.nickname}</h4>
              <p className="card-product">{card.productName}</p>
              <div className="card-footer">
                <span className="reward-type-label">Earns: {card.currencyName}</span>
                <div className="perk-note">✨ {card.highlightBenefit}</div>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
};
