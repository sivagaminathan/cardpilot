import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ApiError,
  fetchProfileBenefits,
  fetchProfileCards,
  fetchRewardsSummary,
} from '../api/client';
import { formatCentsToUsd } from '../lib/formatters';

interface DashboardProps {
  profileId: string;
  onNavigateTab: (tab: string) => void;
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

export const Dashboard: React.FC<DashboardProps> = ({ profileId, onNavigateTab }) => {
  const hasProfile = Boolean(profileId);

  const cardsQuery = useQuery({
    queryKey: ['profile', profileId, 'cards'],
    queryFn: () => fetchProfileCards(profileId),
    enabled: hasProfile,
  });

  const benefitsQuery = useQuery({
    queryKey: ['profile', profileId, 'benefits'],
    queryFn: () => fetchProfileBenefits(profileId),
    enabled: hasProfile,
  });

  const rewardsQuery = useQuery({
    queryKey: ['profile', profileId, 'rewards-summary'],
    queryFn: () => fetchRewardsSummary(profileId),
    enabled: hasProfile,
  });

  const cards = cardsQuery.data ?? [];
  const benefits = benefitsQuery.data ?? [];
  const alerts = benefits.filter(
    (b) =>
      b.status === 'unused' &&
      b.days_until_reset != null &&
      b.days_until_reset >= 0 &&
      b.days_until_reset <= 30,
  );
  const rewardsSummary = rewardsQuery.data;

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
            ⚠️ Upcoming Benefit Resets (Expiring Within 30 Days)
          </h3>
          <div className="section-actions">
            <span className="badge badge-warning">{alerts.length} Active Alerts</span>
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => onNavigateTab('benefits')}
            >
              View All Benefits
            </button>
          </div>
        </div>

        {!hasProfile || benefitsQuery.isLoading ? (
          <p className="loading-message" role="status">
            Loading benefit alerts...
          </p>
        ) : benefitsQuery.isError ? (
          <div className="error-state" role="alert">
            <p>{getErrorMessage(benefitsQuery.error, 'Failed to load benefit alerts.')}</p>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                void benefitsQuery.refetch();
              }}
            >
              Retry Benefit Alerts
            </button>
          </div>
        ) : alerts.length === 0 ? (
          <p className="empty-message">No unused benefits expiring within 30 days.</p>
        ) : (
          <div className="alerts-grid">
            {alerts.map((alert) => {
              const displayCents = alert.remaining_cents ?? alert.value_cents;
              return (
                <div
                  key={`${alert.profile_card_id}-${alert.benefit_id}`}
                  className="alert-card"
                  data-testid="benefit-alert-card"
                >
                  <div className="alert-header">
                    <span className="card-badge">{alert.card_name}</span>
                    <span className="expiry-tag">
                      {alert.days_until_reset}{' '}
                      {alert.days_until_reset === 1 ? 'day' : 'days'} left
                    </span>
                  </div>
                  <h4 className="benefit-name">{alert.name}</h4>
                  <div className="benefit-details">
                    <span className="benefit-amount">
                      {displayCents != null ? formatCentsToUsd(displayCents) : 'Perk'}
                    </span>
                    <span className="benefit-reset">
                      {alert.next_reset_date
                        ? `Resets on ${alert.next_reset_date}`
                        : alert.reset_period}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Rewards Snapshot Per Currency (FR-27, AC-10) */}
      <section className="section-card" aria-labelledby="rewards-heading">
        <div className="section-header">
          <h3 id="rewards-heading" className="section-title">
            🏆 Rewards Snapshot by Currency
          </h3>
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => onNavigateTab('rewards')}
          >
            View Full Rewards
          </button>
        </div>

        {!hasProfile || rewardsQuery.isLoading ? (
          <p className="loading-message" role="status">
            Loading rewards snapshot...
          </p>
        ) : rewardsQuery.isError ? (
          <div className="error-state" role="alert">
            <p>{getErrorMessage(rewardsQuery.error, 'Failed to load rewards snapshot.')}</p>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                void rewardsQuery.refetch();
              }}
            >
              Retry Rewards Snapshot
            </button>
          </div>
        ) : !rewardsSummary || rewardsSummary.currencies.length === 0 ? (
          <p className="empty-message">No reward activity recorded for this profile yet.</p>
        ) : (
          <>
            <div className="balances-grid">
              {rewardsSummary.currencies.map((bal) => (
                <div key={bal.reward_currency_id} className="balance-card">
                  <span className={`currency-kind-tag kind-${bal.reward_currency_kind}`}>
                    {bal.reward_currency_kind.replace('_', ' ')}
                  </span>
                  <div className="balance-units">
                    {bal.total_reward_units} {bal.reward_currency_code}
                  </div>
                  <div className="currency-title">{bal.reward_currency_name}</div>
                  <div className="balance-estimate">
                    Est. Value:{' '}
                    <strong>
                      {bal.estimated_value_cents != null
                        ? formatCentsToUsd(bal.estimated_value_cents)
                        : 'Unvalued'}
                    </strong>
                  </div>
                  {!bal.is_valued && bal.limitation_note && (
                    <p className="limitation-note">{bal.limitation_note}</p>
                  )}
                </div>
              ))}
            </div>

            <div className="estimated-total-summary">
              <div className="estimated-total-row">
                <span className="estimated-total-label">
                  {rewardsSummary.estimated_total_label}:
                </span>{' '}
                <strong className="estimated-total-value">
                  {formatCentsToUsd(rewardsSummary.estimated_total_usd_cents)}
                </strong>
              </div>
              {rewardsSummary.limitation_message && (
                <p className="limitation-note" role="note">
                  {rewardsSummary.limitation_message}
                </p>
              )}
            </div>
          </>
        )}
      </section>

      {/* Active Cards Portfolio (FR-2) */}
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

        {!hasProfile || cardsQuery.isLoading ? (
          <p className="loading-message" role="status">
            Loading cards...
          </p>
        ) : cardsQuery.isError ? (
          <div className="error-state" role="alert">
            <p>{getErrorMessage(cardsQuery.error, 'Failed to load profile cards.')}</p>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                void cardsQuery.refetch();
              }}
            >
              Retry Cards
            </button>
          </div>
        ) : cards.length === 0 ? (
          <p className="empty-message">No cards added to this profile yet.</p>
        ) : (
          <div className="cards-grid">
            {cards.map((card) => (
              <article key={card.id} className="card-item" data-testid="portfolio-card-item">
                <div className="card-item-header">
                  <span className="issuer-name">{card.card_product.issuer_name}</span>
                  <span className="fee-badge">
                    {card.card_product.annual_fee_cents === 0
                      ? '$0 Fee'
                      : `${formatCentsToUsd(card.card_product.annual_fee_cents)}/yr`}
                  </span>
                </div>
                <h4 className="card-nickname">{card.nickname}</h4>
                <p className="card-product">{card.card_product.name}</p>
                <div className="card-footer">
                  <span className="reward-type-label">
                    Earns: {card.card_product.reward_currency.name} (
                    {card.card_product.reward_currency.code})
                  </span>
                  <span className={`card-status-badge ${card.is_active ? 'active' : 'inactive'}`}>
                    {card.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};
