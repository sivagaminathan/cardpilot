import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ApiError,
  fetchProfileValuations,
  fetchRewardCurrencies,
  upsertProfileValuation,
  type CurrencyValuationSummary,
  type RewardCurrencySummary,
} from '../api/client';
import { parseValuationInput } from '../lib/formatters';

interface SettingsViewProps {
  profileId: string;
}

interface RowFeedback {
  kind: 'success' | 'error';
  message: string;
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.errors && error.errors.length > 0) {
      const details = error.errors
        .map((item) => item.msg)
        .filter((msg) => msg.length > 0)
        .join('; ');
      if (details) {
        return `${error.message} (${details})`;
      }
    }
    return error.message;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export const SettingsView: React.FC<SettingsViewProps> = ({ profileId }) => {
  const queryClient = useQueryClient();
  const hasProfile = Boolean(profileId);
  const activeProfileRef = useRef<string>(profileId);
  activeProfileRef.current = profileId;

  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [rowFeedback, setRowFeedback] = useState<Record<string, RowFeedback>>({});

  // Clear per-profile drafts and feedback when switching profiles.
  useEffect(() => {
    setDrafts({});
    setRowFeedback({});
  }, [profileId]);

  const currenciesQuery = useQuery<RewardCurrencySummary[]>({
    queryKey: ['reward-currencies'],
    queryFn: () => fetchRewardCurrencies(),
  });

  const valuationsQuery = useQuery<CurrencyValuationSummary[]>({
    queryKey: ['profile', profileId, 'valuations'],
    queryFn: () => fetchProfileValuations(profileId),
    enabled: hasProfile,
  });

  const currencies = useMemo(() => currenciesQuery.data ?? [], [currenciesQuery.data]);
  const valuationsByCurrencyId = useMemo(() => {
    const map = new Map<number, CurrencyValuationSummary>();
    for (const val of valuationsQuery.data ?? []) {
      map.set(val.reward_currency_id, val);
    }
    return map;
  }, [valuationsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: (variables: {
      targetProfile: string;
      currencyCode: string;
      centsPerUnit: string;
    }) =>
      upsertProfileValuation(variables.targetProfile, variables.currencyCode, {
        cents_per_unit: variables.centsPerUnit,
      }),
    onSuccess: (saved, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['profile', variables.targetProfile] });
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setDrafts((prev) => ({
        ...prev,
        [variables.currencyCode]: saved.cents_per_unit,
      }));
      setRowFeedback((prev) => ({
        ...prev,
        [variables.currencyCode]: {
          kind: 'success',
          message: `Saved ${saved.cents_per_unit}¢ per ${saved.reward_currency.name} unit.`,
        },
      }));
    },
    onError: (err, variables) => {
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setRowFeedback((prev) => ({
        ...prev,
        [variables.currencyCode]: {
          kind: 'error',
          message: getErrorMessage(err, 'Failed to save valuation.'),
        },
      }));
    },
  });

  const handleSave = (event: React.FormEvent<HTMLFormElement>, currency: RewardCurrencySummary) => {
    event.preventDefault();
    if (!hasProfile) {
      return;
    }

    const existing = valuationsByCurrencyId.get(currency.id);
    const rawValue = drafts[currency.code] ?? existing?.cents_per_unit ?? '';
    const normalized = parseValuationInput(rawValue);
    if (normalized === null) {
      setRowFeedback((prev) => ({
        ...prev,
        [currency.code]: {
          kind: 'error',
          message:
            'Enter a positive valuation greater than 0 and up to 10 cents per unit (max 4 decimal places).',
        },
      }));
      return;
    }

    setRowFeedback((prev) => {
      const next = { ...prev };
      delete next[currency.code];
      return next;
    });

    saveMutation.mutate({
      targetProfile: profileId,
      currencyCode: currency.code,
      centsPerUnit: normalized,
    });
  };

  return (
    <div className="settings-view">
      <section className="section-card" aria-labelledby="settings-heading">
        <div className="section-header">
          <h2 id="settings-heading" className="section-title">
            Currency Valuations (Cents per Unit)
          </h2>
          <span className="badge">Range: 0 &lt; v ≤ 10¢</span>
        </div>

        <p className="settings-explanation" role="note">
          Valuations represent your estimated USD cents per reward unit (for example, 1.5000¢ per
          point). Changing a valuation updates future recommendations and estimated USD summaries,
          without altering historical transaction calculation snapshots. Use Reset Demo Data in the
          header to restore seeded defaults.
        </p>

        {!hasProfile && (
          <p className="empty-message" role="status">
            Select a demo profile to view and edit currency valuations.
          </p>
        )}

        {currenciesQuery.isLoading ? (
          <p className="loading-message" role="status">
            Loading reward currencies...
          </p>
        ) : currenciesQuery.isError ? (
          <div className="error-state" role="alert">
            <p>{getErrorMessage(currenciesQuery.error, 'Failed to load reward currencies.')}</p>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                void currenciesQuery.refetch();
              }}
            >
              Retry Currencies
            </button>
          </div>
        ) : currencies.length === 0 ? (
          <p className="empty-message">No reward currencies available in the catalog.</p>
        ) : hasProfile && valuationsQuery.isLoading ? (
          <p className="loading-message" role="status">
            Loading profile valuations...
          </p>
        ) : hasProfile && valuationsQuery.isError ? (
          <div className="error-state" role="alert">
            <p>{getErrorMessage(valuationsQuery.error, 'Failed to load profile valuations.')}</p>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                void valuationsQuery.refetch();
              }}
            >
              Retry Valuations
            </button>
          </div>
        ) : (
          <div className="valuations-list">
            {currencies.map((currency) => {
              const existing = hasProfile ? valuationsByCurrencyId.get(currency.id) : undefined;
              const inputValue = drafts[currency.code] ?? existing?.cents_per_unit ?? '';
              const feedback = rowFeedback[currency.code];
              const isSavingThis =
                saveMutation.isPending &&
                saveMutation.variables?.currencyCode === currency.code;

              const statusLabel = !hasProfile
                ? 'Select a profile'
                : existing
                  ? existing.is_user_set
                    ? 'User-configured'
                    : 'Illustrative default'
                  : 'Not configured (unranked in Compare)';

              const statusBadgeClass =
                existing && existing.is_user_set ? 'badge-fresh' : 'badge-warning';

              const inputId = `valuation-input-${currency.code}`;
              const hintId = `valuation-hint-${currency.code}`;

              return (
                <form
                  key={currency.id}
                  className="valuation-card"
                  data-testid={`valuation-row-${currency.code}`}
                  onSubmit={(e) => handleSave(e, currency)}
                  noValidate
                >
                  <div className="valuation-card-header">
                    <div>
                      <h3 className="valuation-currency-name">
                        {currency.name} ({currency.code})
                      </h3>
                      <p className="valuation-currency-kind">
                        Kind: {currency.kind}
                        {currency.is_cash_equivalent ? ' · Cash equivalent' : ''}
                      </p>
                    </div>
                    <span className={`badge ${statusBadgeClass}`}>{statusLabel}</span>
                  </div>

                  <div className="valuation-controls-row">
                    <div className="form-field valuation-input-field">
                      <label htmlFor={inputId} className="form-label">
                        Estimated cents per {currency.name} unit
                      </label>
                      <input
                        id={inputId}
                        type="text"
                        inputMode="decimal"
                        className="form-control"
                        value={inputValue}
                        onChange={(e) => {
                          const val = e.target.value;
                          setDrafts((prev) => ({ ...prev, [currency.code]: val }));
                          if (feedback) {
                            setRowFeedback((prev) => {
                              const next = { ...prev };
                              delete next[currency.code];
                              return next;
                            });
                          }
                        }}
                        placeholder="e.g. 1.5000"
                        aria-describedby={hintId}
                        disabled={!hasProfile || isSavingThis}
                      />
                      <p id={hintId} className="form-hint">
                        {existing
                          ? `Current saved value: ${existing.cents_per_unit}¢`
                          : `Illustrative default reference: ${currency.default_cents_per_unit}¢ (not yet configured for this profile)`}
                      </p>
                    </div>

                    <button
                      type="submit"
                      className="btn btn-primary valuation-save-btn"
                      disabled={!hasProfile || isSavingThis}
                    >
                      {isSavingThis ? 'Saving...' : 'Save'}
                    </button>
                  </div>

                  {feedback && (
                    <div
                      className={
                        feedback.kind === 'error'
                          ? 'error-state'
                          : 'reset-feedback reset-feedback--success'
                      }
                      role={feedback.kind === 'error' ? 'alert' : 'status'}
                    >
                      <p>{feedback.message}</p>
                    </div>
                  )}
                </form>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
};
