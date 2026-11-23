import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ApiError,
  fetchRewardsSummary,
  type CurrencyRewardSummary,
  type RewardsSummaryResponse,
} from '../api/client';
import { formatCentsToUsd } from '../lib/formatters';

interface RewardsViewProps {
  profileId: string;
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

function formatValuationStatus(currency: CurrencyRewardSummary): string {
  if (!currency.is_valued || currency.valuation_status !== 'valued') {
    return 'Unvalued';
  }
  const sourceLabel = currency.is_user_set ? 'User-configured' : 'Illustrative default';
  return currency.current_cents_per_unit != null
    ? `${sourceLabel} (${currency.current_cents_per_unit}¢/unit)`
    : sourceLabel;
}

export const RewardsView: React.FC<RewardsViewProps> = ({ profileId }) => {
  const hasProfile = Boolean(profileId);

  const rewardsQuery = useQuery<RewardsSummaryResponse>({
    queryKey: ['profile', profileId, 'rewards-summary'],
    queryFn: () => fetchRewardsSummary(profileId),
    enabled: hasProfile,
  });

  const summary = rewardsQuery.data;
  const currencies = summary?.currencies ?? [];
  const hasValuedCurrency = currencies.some(
    (c) => c.is_valued && c.estimated_value_cents != null,
  );

  return (
    <div className="rewards-view">
      <section className="section-card" aria-labelledby="rewards-earned-heading">
        <div className="section-header">
          <h2 id="rewards-earned-heading" className="section-title">
            Earned Rewards by Currency
          </h2>
          <div className="rewards-links-row">
            <Link to="/settings" className="btn btn-outline">
              Manage Valuations
            </Link>
            <Link to="/transactions" className="btn btn-outline">
              View Transactions
            </Link>
          </div>
        </div>

        {!hasProfile ? (
          <p className="empty-message" role="status">
            Select a demo profile to view earned rewards.
          </p>
        ) : rewardsQuery.isLoading ? (
          <p className="loading-message" role="status">
            Loading rewards summary...
          </p>
        ) : rewardsQuery.isError ? (
          <div className="error-state" role="alert">
            <p>{getErrorMessage(rewardsQuery.error, 'Failed to load rewards summary.')}</p>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                void rewardsQuery.refetch();
              }}
            >
              Retry Rewards Summary
            </button>
          </div>
        ) : currencies.length === 0 ? (
          <p className="empty-message">
            No rewards earned yet for this profile. Record transactions to see per-currency totals.
          </p>
        ) : (
          <>
            <div className="rewards-table-wrapper">
              <table className="rewards-table" aria-labelledby="rewards-earned-heading">
                <thead>
                  <tr>
                    <th scope="col">Currency</th>
                    <th scope="col">Kind</th>
                    <th scope="col">Transactions</th>
                    <th scope="col">Earned Units</th>
                    <th scope="col">Valuation Status</th>
                  </tr>
                </thead>
                <tbody>
                  {currencies.map((currency) => (
                    <tr
                      key={currency.reward_currency_id}
                      data-testid={`rewards-row-${currency.reward_currency_code}`}
                    >
                      <td>
                        <strong>{currency.reward_currency_name}</strong> ({currency.reward_currency_code})
                      </td>
                      <td>{currency.reward_currency_kind}</td>
                      <td>{currency.transaction_count}</td>
                      <td>
                        <strong>{currency.total_reward_units}</strong> {currency.reward_currency_code}
                      </td>
                      <td>{formatValuationStatus(currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="form-hint">
              Raw reward units are grouped strictly by currency and are never combined across
              different currencies.
            </p>
          </>
        )}
      </section>

      {hasProfile && summary && currencies.length > 0 && (
        <section className="section-card" aria-labelledby="rewards-estimated-heading">
          <div className="section-header">
            <h2 id="rewards-estimated-heading" className="section-title">
              Estimated USD Value
            </h2>
          </div>

          <p className="rewards-estimate-disclaimer" role="note">
            All dollar figures below are estimates based on your current profile valuations, not
            historical transaction calculation snapshots.
          </p>

          <ul className="rewards-estimate-list" aria-label="Estimated USD value by currency">
            {currencies.map((currency) => (
              <li
                key={currency.reward_currency_id}
                className="rewards-estimate-item"
                data-testid={`rewards-estimate-${currency.reward_currency_code}`}
              >
                <div>
                  <strong>
                    {currency.reward_currency_name} ({currency.reward_currency_code})
                  </strong>
                  {!currency.is_valued && currency.limitation_note && (
                    <p className="limitation-note">{currency.limitation_note}</p>
                  )}
                </div>
                <div>
                  {currency.is_valued && currency.estimated_value_cents != null ? (
                    <strong>{formatCentsToUsd(currency.estimated_value_cents)}</strong>
                  ) : (
                    <span className="badge badge-warning">
                      Unvalued — excluded from estimate
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>

          <div className="estimated-total-summary">
            {hasValuedCurrency ? (
              <div className="estimated-total-row">
                <span className="estimated-total-label">{summary.estimated_total_label}:</span>{' '}
                <strong className="estimated-total-value">
                  {formatCentsToUsd(summary.estimated_total_usd_cents)}
                </strong>
              </div>
            ) : (
              <p className="limitation-note" role="note">
                Estimated total unavailable — no currencies have a valuation.
              </p>
            )}

            {summary.limitation_message && (
              <p className="limitation-note" role="note">
                {summary.limitation_message}
              </p>
            )}

            {summary.excluded_unvalued_currency_codes.length > 0 && (
              <p className="form-hint">
                Excluded unvalued currencies:{' '}
                {summary.excluded_unvalued_currency_codes.join(', ')}
              </p>
            )}
          </div>
        </section>
      )}
    </div>
  );
};
