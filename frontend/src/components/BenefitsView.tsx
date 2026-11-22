import React, { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ApiError,
  deleteBenefitUsage,
  fetchProfileBenefits,
  logBenefitUsage,
  type BenefitStatusItem,
  type BenefitUsageCreate,
} from '../api/client';
import { formatCentsToUsd, getTodayLocalIsoDate, parseUsdToCents } from '../lib/formatters';

interface BenefitsViewProps {
  profileId: string;
}

interface UsageDraft {
  amountUsd: string;
  usedOn: string;
  note: string;
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

function getBenefitKey(item: BenefitStatusItem): string {
  return `${item.profile_card_id}:${item.benefit_id}`;
}

function formatStatusLabel(status: string): string {
  switch (status) {
    case 'unused':
      return 'Unused';
    case 'partially_used':
      return 'Partially used';
    case 'used':
      return 'Used';
    case 'over_used':
      return 'Overused';
    default:
      return status;
  }
}

export const BenefitsView: React.FC<BenefitsViewProps> = ({ profileId }) => {
  const queryClient = useQueryClient();
  const hasProfile = Boolean(profileId);
  const activeProfileRef = useRef<string>(profileId);
  activeProfileRef.current = profileId;
  const feedbackRef = useRef<HTMLDivElement | null>(null);

  const [drafts, setDrafts] = useState<Record<string, UsageDraft>>({});
  const [rowFeedback, setRowFeedback] = useState<Record<string, RowFeedback>>({});
  const [globalFeedback, setGlobalFeedback] = useState<RowFeedback | null>(null);
  const [confirmingDeleteUsageId, setConfirmingDeleteUsageId] = useState<number | null>(null);

  useEffect(() => {
    setDrafts({});
    setRowFeedback({});
    setGlobalFeedback(null);
    setConfirmingDeleteUsageId(null);
  }, [profileId]);

  const benefitsQuery = useQuery<BenefitStatusItem[]>({
    queryKey: ['profile', profileId, 'benefits'],
    queryFn: () => fetchProfileBenefits(profileId),
    enabled: hasProfile,
  });

  const benefits = benefitsQuery.data ?? [];

  const getDraft = (key: string): UsageDraft =>
    drafts[key] ?? {
      amountUsd: '',
      usedOn: getTodayLocalIsoDate(),
      note: '',
    };

  const updateDraft = (key: string, patch: Partial<UsageDraft>): void => {
    setDrafts((prev) => ({
      ...prev,
      [key]: {
        ...(prev[key] ?? {
          amountUsd: '',
          usedOn: getTodayLocalIsoDate(),
          note: '',
        }),
        ...patch,
      },
    }));
  };

  const logMutation = useMutation({
    mutationFn: (variables: {
      targetProfile: string;
      benefitId: number;
      benefitKey: string;
      payload: BenefitUsageCreate;
    }) => logBenefitUsage(variables.targetProfile, variables.benefitId, variables.payload),
    onSuccess: (saved, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['profile', variables.targetProfile] });
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setDrafts((prev) => ({
        ...prev,
        [variables.benefitKey]: {
          amountUsd: '',
          usedOn: getTodayLocalIsoDate(),
          note: '',
        },
      }));
      setRowFeedback((prev) => ({
        ...prev,
        [variables.benefitKey]: {
          kind: 'success',
          message:
            saved.amount_cents != null
              ? `Logged ${formatCentsToUsd(saved.amount_cents)} usage on ${saved.used_on}.`
              : `Logged perk usage on ${saved.used_on}.`,
        },
      }));
    },
    onError: (err, variables) => {
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setRowFeedback((prev) => ({
        ...prev,
        [variables.benefitKey]: {
          kind: 'error',
          message: getErrorMessage(err, 'Failed to log benefit usage.'),
        },
      }));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (variables: {
      targetProfile: string;
      benefitId: number;
      usageId: number;
    }) => deleteBenefitUsage(variables.targetProfile, variables.benefitId, variables.usageId),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['profile', variables.targetProfile] });
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setConfirmingDeleteUsageId(null);
      setGlobalFeedback({
        kind: 'success',
        message: 'Removed benefit usage entry.',
      });
      feedbackRef.current?.focus();
    },
    onError: (err, variables) => {
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setConfirmingDeleteUsageId(null);
      setGlobalFeedback({
        kind: 'error',
        message: getErrorMessage(err, 'Failed to remove benefit usage entry.'),
      });
      feedbackRef.current?.focus();
    },
  });

  const handleLogSubmit = (
    event: React.FormEvent<HTMLFormElement>,
    item: BenefitStatusItem,
  ): void => {
    event.preventDefault();
    if (!hasProfile) {
      return;
    }

    const key = getBenefitKey(item);
    const draft = getDraft(key);
    setGlobalFeedback(null);

    let amountCents: number | null = null;
    if (item.value_cents !== null && item.value_cents !== undefined) {
      amountCents = parseUsdToCents(draft.amountUsd);
      if (amountCents === null) {
        setRowFeedback((prev) => ({
          ...prev,
          [key]: {
            kind: 'error',
            message: 'Enter a positive USD amount with up to two decimal places (e.g. 10.00).',
          },
        }));
        return;
      }
    }

    if (!draft.usedOn.trim()) {
      setRowFeedback((prev) => ({
        ...prev,
        [key]: {
          kind: 'error',
          message: 'Select a usage date.',
        },
      }));
      return;
    }

    setRowFeedback((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });

    logMutation.mutate({
      targetProfile: profileId,
      benefitId: item.benefit_id,
      benefitKey: key,
      payload: {
        profile_card_id: item.profile_card_id,
        amount_cents: amountCents,
        used_on: draft.usedOn.trim(),
        note: draft.note.trim(),
      },
    });
  };

  return (
    <div className="benefits-view">
      <section className="section-card" aria-labelledby="benefits-heading">
        <div className="section-header">
          <h2 id="benefits-heading" className="section-title">
            Card Benefits &amp; Usage Tracking ({benefits.length})
          </h2>
        </div>

        <div ref={feedbackRef} tabIndex={-1} className="feedback-anchor">
          {globalFeedback && (
            <div
              className={
                globalFeedback.kind === 'error'
                  ? 'error-state'
                  : 'reset-feedback reset-feedback--success'
              }
              role={globalFeedback.kind === 'error' ? 'alert' : 'status'}
            >
              <p>{globalFeedback.message}</p>
            </div>
          )}
        </div>

        {!hasProfile ? (
          <p className="empty-message" role="status">
            Select a demo profile to view and log card benefits.
          </p>
        ) : benefitsQuery.isLoading ? (
          <p className="loading-message" role="status">
            Loading benefits...
          </p>
        ) : benefitsQuery.isError ? (
          <div className="error-state" role="alert">
            <p>{getErrorMessage(benefitsQuery.error, 'Failed to load profile benefits.')}</p>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                void benefitsQuery.refetch();
              }}
            >
              Retry Benefits
            </button>
          </div>
        ) : benefits.length === 0 ? (
          <p className="empty-message">No benefits defined for this profile&apos;s active cards.</p>
        ) : (
          <div className="benefits-list">
            {benefits.map((item) => {
              const key = getBenefitKey(item);
              const draft = getDraft(key);
              const feedback = rowFeedback[key];
              const isMonetary = item.value_cents !== null && item.value_cents !== undefined;
              const isLoggingThis =
                logMutation.isPending && logMutation.variables?.benefitKey === key;

              const statusBadgeClass =
                item.is_over_used || item.status === 'over_used'
                  ? 'badge-danger'
                  : item.status === 'used'
                    ? 'badge-fresh'
                    : 'badge-warning';

              const amountInputId = `benefit-amount-${key}`;
              const dateInputId = `benefit-date-${key}`;
              const noteInputId = `benefit-note-${key}`;
              const noteHintId = `benefit-note-hint-${key}`;

              return (
                <article
                  key={key}
                  className="benefit-card"
                  data-testid={`benefit-card-${item.profile_card_id}-${item.benefit_id}`}
                >
                  <div className="benefit-card-header">
                    <div>
                      <h3 className="benefit-card-title">{item.name}</h3>
                      <p className="benefit-card-subtitle">
                        {item.card_name} ({item.card_product_name}) · Type: {item.benefit_type} ·
                        Reset: {item.reset_period}
                      </p>
                    </div>
                    <span className={`badge ${statusBadgeClass}`}>
                      Status: {formatStatusLabel(item.status)}
                    </span>
                  </div>

                  {item.notes && <p className="benefit-notes">{item.notes}</p>}

                  <dl className="rule-details-grid">
                    {isMonetary && item.value_cents != null && (
                      <div>
                        <dt>Benefit Value</dt>
                        <dd>{formatCentsToUsd(item.value_cents)}</dd>
                      </div>
                    )}
                    {isMonetary && item.used_cents != null && (
                      <div>
                        <dt>Used</dt>
                        <dd>{formatCentsToUsd(item.used_cents)}</dd>
                      </div>
                    )}
                    {isMonetary && item.remaining_cents != null && (
                      <div>
                        <dt>Remaining</dt>
                        <dd>{formatCentsToUsd(item.remaining_cents)}</dd>
                      </div>
                    )}
                    {(item.is_over_used ||
                      (item.over_used_cents != null && item.over_used_cents > 0)) && (
                      <div>
                        <dt>Overuse</dt>
                        <dd className="benefit-overuse-text">
                          Overused by{' '}
                          {item.over_used_cents != null
                            ? formatCentsToUsd(item.over_used_cents)
                            : '$0.00'}
                        </dd>
                      </div>
                    )}
                    <div>
                      <dt>Current Period</dt>
                      <dd>
                        {item.period_start && item.period_end
                          ? `${item.period_start} to ${item.period_end}`
                          : 'Period unavailable'}
                      </dd>
                    </div>
                    <div>
                      <dt>Next Reset</dt>
                      <dd>
                        {item.next_reset_date ?? 'Reset date unavailable'}
                        {item.days_until_reset != null
                          ? ` (${item.days_until_reset === 1 ? '1 day left' : `${item.days_until_reset} days left`})`
                          : ''}
                      </dd>
                    </div>
                  </dl>

                  <form
                    className="benefit-usage-form"
                    onSubmit={(e) => handleLogSubmit(e, item)}
                    noValidate
                  >
                    <div className="form-grid">
                      {isMonetary ? (
                        <div className="form-field">
                          <label htmlFor={amountInputId} className="form-label">
                            Usage Amount (USD)
                          </label>
                          <input
                            id={amountInputId}
                            type="text"
                            inputMode="decimal"
                            className="form-control"
                            value={draft.amountUsd}
                            onChange={(e) => updateDraft(key, { amountUsd: e.target.value })}
                            placeholder="e.g. 10.00"
                            disabled={isLoggingThis}
                          />
                        </div>
                      ) : (
                        <div className="form-field">
                          <span className="form-label">Perk Usage</span>
                          <p className="form-hint">
                            Non-monetary perk (logged without a dollar amount).
                          </p>
                        </div>
                      )}

                      <div className="form-field">
                        <label htmlFor={dateInputId} className="form-label">
                          Used On
                        </label>
                        <input
                          id={dateInputId}
                          type="date"
                          className="form-control"
                          value={draft.usedOn}
                          onChange={(e) => updateDraft(key, { usedOn: e.target.value })}
                          disabled={isLoggingThis}
                        />
                      </div>

                      <div className="form-field">
                        <label htmlFor={noteInputId} className="form-label">
                          Note (optional)
                        </label>
                        <input
                          id={noteInputId}
                          type="text"
                          className="form-control"
                          value={draft.note}
                          onChange={(e) => updateDraft(key, { note: e.target.value })}
                          maxLength={1000}
                          placeholder="e.g. Monthly credit used"
                          aria-describedby={noteHintId}
                          disabled={isLoggingThis}
                        />
                        <p id={noteHintId} className="form-hint">
                          Do not enter real card numbers or sensitive data.
                        </p>
                      </div>
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

                    <div className="form-actions">
                      <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={isLoggingThis}
                      >
                        {isLoggingThis ? 'Logging...' : 'Log Usage'}
                      </button>
                    </div>
                  </form>

                  <div className="benefit-usages-section">
                    <h4 className="benefit-usages-heading">
                      Logged Usages ({item.usages.length})
                    </h4>
                    {item.usages.length === 0 ? (
                      <p className="empty-message">No usages logged in this period.</p>
                    ) : (
                      <ul className="benefit-usages-list">
                        {item.usages.map((usage) => {
                          const isConfirming = confirmingDeleteUsageId === usage.id;
                          const isDeletingThis =
                            deleteMutation.isPending &&
                            deleteMutation.variables?.usageId === usage.id;

                          return (
                            <li
                              key={usage.id}
                              className="benefit-usage-item"
                              data-testid={`benefit-usage-item-${usage.id}`}
                            >
                              <div>
                                <strong>{usage.used_on}</strong>
                                {usage.amount_cents != null
                                  ? ` — ${formatCentsToUsd(usage.amount_cents)}`
                                  : ' — Perk used'}
                                {usage.note ? ` (${usage.note})` : ''}
                              </div>

                              {!isConfirming ? (
                                <button
                                  type="button"
                                  className="btn btn-danger"
                                  disabled={isDeletingThis}
                                  onClick={() => {
                                    setGlobalFeedback(null);
                                    setConfirmingDeleteUsageId(usage.id);
                                  }}
                                >
                                  Remove
                                </button>
                              ) : (
                                <div
                                  className="confirm-delete-group"
                                  role="group"
                                  aria-label={`Confirm removal of usage ${usage.id}`}
                                >
                                  <button
                                    type="button"
                                    className="btn btn-danger"
                                    disabled={isDeletingThis}
                                    onClick={() => {
                                      deleteMutation.mutate({
                                        targetProfile: profileId,
                                        benefitId: item.benefit_id,
                                        usageId: usage.id,
                                      });
                                    }}
                                  >
                                    {isDeletingThis ? 'Removing...' : 'Confirm Remove'}
                                  </button>
                                  <button
                                    type="button"
                                    className="btn btn-secondary"
                                    disabled={isDeletingThis}
                                    onClick={() => setConfirmingDeleteUsageId(null)}
                                  >
                                    Cancel
                                  </button>
                                </div>
                              )}
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
};
