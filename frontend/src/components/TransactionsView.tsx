import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ApiError,
  createProfileTransaction,
  deleteProfileTransaction,
  fetchCategories,
  fetchMerchants,
  fetchProfileCards,
  fetchProfileTransactions,
  type CategorySummary,
  type MerchantSummary,
  type ProfileCardSummary,
  type TransactionCreate,
  type TransactionFilters,
  type TransactionSummary,
} from '../api/client';
import { formatCentsToUsd, getTodayLocalIsoDate, parseUsdToCents } from '../lib/formatters';

interface TransactionsViewProps {
  profileId: string;
}

interface ActionFeedback {
  kind: 'success' | 'error';
  message: string;
}

interface NarrowedTracePortion {
  portionCents: number | null;
  ruleKey: string | null;
  ruleVersion: number | null;
  multiplier: string | null;
  rewardUnits: string | null;
}

interface NarrowedTrace {
  status: string | null;
  explanation: string[];
  warnings: string[];
  appliedPortions: NarrowedTracePortion[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function narrowTransactionTrace(rawTrace: Record<string, unknown>): NarrowedTrace {
  const status = typeof rawTrace.status === 'string' ? rawTrace.status : null;
  const explanation = Array.isArray(rawTrace.explanation)
    ? rawTrace.explanation.filter((step): step is string => typeof step === 'string')
    : [];
  const warnings = Array.isArray(rawTrace.warnings)
    ? rawTrace.warnings.filter((w): w is string => typeof w === 'string')
    : [];
  const appliedPortions: NarrowedTracePortion[] = [];
  if (Array.isArray(rawTrace.applied_portions)) {
    for (const item of rawTrace.applied_portions) {
      if (!isRecord(item)) {
        continue;
      }
      appliedPortions.push({
        portionCents: typeof item.portion_cents === 'number' ? item.portion_cents : null,
        ruleKey: typeof item.rule_key === 'string' ? item.rule_key : null,
        ruleVersion: typeof item.rule_version === 'number' ? item.rule_version : null,
        multiplier: typeof item.multiplier === 'string' ? item.multiplier : null,
        rewardUnits: typeof item.reward_units === 'string' ? item.reward_units : null,
      });
    }
  }
  return { status, explanation, warnings, appliedPortions };
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

export const TransactionsView: React.FC<TransactionsViewProps> = ({ profileId }) => {
  const queryClient = useQueryClient();
  const hasProfile = Boolean(profileId);
  const activeProfileRef = useRef<string>(profileId);
  activeProfileRef.current = profileId;
  const feedbackRef = useRef<HTMLDivElement | null>(null);

  // Create form state
  const [selectedCardId, setSelectedCardId] = useState<string>('');
  const [amountUsd, setAmountUsd] = useState<string>('');
  const [categoryCode, setCategoryCode] = useState<string>('');
  const [categoryManuallyChanged, setCategoryManuallyChanged] = useState<boolean>(false);
  const [merchantMode, setMerchantMode] = useState<'seeded' | 'custom'>('seeded');
  const [merchantId, setMerchantId] = useState<string>('');
  const [merchantText, setMerchantText] = useState<string>('');
  const [occurredOn, setOccurredOn] = useState<string>(() => getTodayLocalIsoDate());
  const [note, setNote] = useState<string>('');
  const [formError, setFormError] = useState<string | null>(null);
  const [lastCreatedTx, setLastCreatedTx] = useState<TransactionSummary | null>(null);

  // Filter & list state
  const [filterCardId, setFilterCardId] = useState<string>('');
  const [filterCategoryCode, setFilterCategoryCode] = useState<string>('');
  const [filterDateFrom, setFilterDateFrom] = useState<string>('');
  const [filterDateTo, setFilterDateTo] = useState<string>('');
  const [expandedTxIds, setExpandedTxIds] = useState<Record<number, boolean>>({});
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<number | null>(null);
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback | null>(null);

  // Reset form, filters, confirmations, and feedback on profile switch.
  useEffect(() => {
    setSelectedCardId('');
    setAmountUsd('');
    setCategoryManuallyChanged(false);
    setMerchantMode('seeded');
    setMerchantId('');
    setMerchantText('');
    setOccurredOn(getTodayLocalIsoDate());
    setNote('');
    setFormError(null);
    setLastCreatedTx(null);
    setFilterCardId('');
    setFilterCategoryCode('');
    setFilterDateFrom('');
    setFilterDateTo('');
    setExpandedTxIds({});
    setConfirmingDeleteId(null);
    setActionFeedback(null);
  }, [profileId]);

  const categoriesQuery = useQuery<CategorySummary[]>({
    queryKey: ['categories'],
    queryFn: () => fetchCategories(),
  });

  const merchantsQuery = useQuery<MerchantSummary[]>({
    queryKey: ['merchants'],
    queryFn: () => fetchMerchants(),
  });

  const cardsQuery = useQuery<ProfileCardSummary[]>({
    queryKey: ['profile', profileId, 'cards'],
    queryFn: () => fetchProfileCards(profileId),
    enabled: hasProfile,
  });

  const isDateRangeInvalid =
    Boolean(filterDateFrom) && Boolean(filterDateTo) && filterDateFrom > filterDateTo;

  const activeFilters: TransactionFilters = useMemo(() => {
    const filters: TransactionFilters = {};
    if (filterCardId) {
      const parsed = Number(filterCardId);
      if (Number.isInteger(parsed) && parsed > 0) {
        filters.profile_card_id = parsed;
      }
    }
    if (filterCategoryCode) {
      filters.category_code = filterCategoryCode;
    }
    if (filterDateFrom) {
      filters.date_from = filterDateFrom;
    }
    if (filterDateTo) {
      filters.date_to = filterDateTo;
    }
    return filters;
  }, [filterCardId, filterCategoryCode, filterDateFrom, filterDateTo]);

  const transactionsQuery = useQuery<TransactionSummary[]>({
    queryKey: ['profile', profileId, 'transactions', activeFilters],
    queryFn: () => fetchProfileTransactions(profileId, activeFilters),
    enabled: hasProfile && !isDateRangeInvalid,
  });

  const categories = useMemo(() => categoriesQuery.data ?? [], [categoriesQuery.data]);
  const merchants = useMemo(() => merchantsQuery.data ?? [], [merchantsQuery.data]);
  const allProfileCards = useMemo(() => cardsQuery.data ?? [], [cardsQuery.data]);
  const activeCards = useMemo(
    () => allProfileCards.filter((card) => card.is_active),
    [allProfileCards],
  );
  const inactiveCardsCount = allProfileCards.length - activeCards.length;
  const transactions = transactionsQuery.data ?? [];

  useEffect(() => {
    if (categories.length > 0 && !categories.some((cat) => cat.code === categoryCode)) {
      setCategoryCode(categories[0].code);
      setCategoryManuallyChanged(false);
    }
  }, [categories, categoryCode]);

  useEffect(() => {
    if (
      activeCards.length > 0 &&
      !activeCards.some((card) => String(card.id) === selectedCardId)
    ) {
      setSelectedCardId(String(activeCards[0].id));
    } else if (activeCards.length === 0 && selectedCardId !== '') {
      setSelectedCardId('');
    }
  }, [activeCards, selectedCardId]);

  const createMutation = useMutation({
    mutationFn: (variables: { targetProfile: string; payload: TransactionCreate }) =>
      createProfileTransaction(variables.targetProfile, variables.payload),
    onSuccess: (created, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['profile', variables.targetProfile] });
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setFormError(null);
      setLastCreatedTx(created);
      setAmountUsd('');
      setMerchantId('');
      setMerchantText('');
      setNote('');
      setActionFeedback({
        kind: 'success',
        message: `Recorded ${formatCentsToUsd(created.amount_cents)} transaction on "${created.card_name}".`,
      });
    },
    onError: (err, variables) => {
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setLastCreatedTx(null);
      setFormError(getErrorMessage(err, 'Failed to record transaction.'));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (variables: { targetProfile: string; transactionId: number }) =>
      deleteProfileTransaction(variables.targetProfile, variables.transactionId),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['profile', variables.targetProfile] });
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setConfirmingDeleteId(null);
      if (lastCreatedTx?.id === variables.transactionId) {
        setLastCreatedTx(null);
      }
      setActionFeedback({
        kind: 'success',
        message: 'Transaction removed and cap capacity freed for future calculations.',
      });
      feedbackRef.current?.focus();
    },
    onError: (err, variables) => {
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setConfirmingDeleteId(null);
      setActionFeedback({
        kind: 'error',
        message: getErrorMessage(err, 'Failed to delete transaction.'),
      });
      feedbackRef.current?.focus();
    },
  });

  const handleMerchantSelectChange = (nextMerchantId: string): void => {
    setMerchantId(nextMerchantId);
    if (!nextMerchantId || categoryManuallyChanged) {
      return;
    }
    const chosen = merchants.find((m) => String(m.id) === nextMerchantId);
    if (
      chosen?.default_category_code &&
      categories.some((cat) => cat.code === chosen.default_category_code)
    ) {
      setCategoryCode(chosen.default_category_code);
    }
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setFormError(null);
    setActionFeedback(null);

    if (!hasProfile) {
      setFormError('Select a demo profile before recording a transaction.');
      return;
    }

    const parsedCardId = Number(selectedCardId);
    if (!Number.isInteger(parsedCardId) || parsedCardId <= 0) {
      setFormError('Select an active card for this transaction.');
      return;
    }

    const amountCents = parseUsdToCents(amountUsd);
    if (amountCents === null) {
      setFormError('Enter a positive USD amount with up to two decimal places (e.g. 42.50).');
      return;
    }

    if (!categoryCode) {
      setFormError('Select a spending category.');
      return;
    }

    if (!occurredOn.trim()) {
      setFormError('Select a transaction date.');
      return;
    }

    const payload: TransactionCreate = {
      profile_card_id: parsedCardId,
      amount_cents: amountCents,
      category_code: categoryCode,
      occurred_on: occurredOn.trim(),
      note: note.trim(),
    };

    if (merchantMode === 'seeded') {
      if (merchantId) {
        payload.merchant_id = Number(merchantId);
      }
    } else {
      const trimmedMerchant = merchantText.trim();
      if (trimmedMerchant) {
        payload.merchant_text = trimmedMerchant;
      }
    }

    createMutation.mutate({
      targetProfile: profileId,
      payload,
    });
  };

  const handleClearFilters = (): void => {
    setFilterCardId('');
    setFilterCategoryCode('');
    setFilterDateFrom('');
    setFilterDateTo('');
  };

  const lastCreatedTrace = lastCreatedTx ? narrowTransactionTrace(lastCreatedTx.reward_calc.trace) : null;

  return (
    <div className="transactions-view">
      <section className="section-card" aria-labelledby="record-tx-heading">
        <h2 id="record-tx-heading" className="section-title">
          Record Transaction
        </h2>

        {!hasProfile ? (
          <p className="empty-message" role="status">
            Select a demo profile to record and view transactions.
          </p>
        ) : categoriesQuery.isLoading || cardsQuery.isLoading ? (
          <p className="loading-message" role="status">
            Loading cards and categories...
          </p>
        ) : categoriesQuery.isError ? (
          <div className="error-state" role="alert">
            <p>{getErrorMessage(categoriesQuery.error, 'Failed to load spending categories.')}</p>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                void categoriesQuery.refetch();
              }}
            >
              Retry Categories
            </button>
          </div>
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
        ) : activeCards.length === 0 ? (
          <p className="empty-message">
            No active cards in this profile. Activate or add a card before recording a transaction.
          </p>
        ) : (
          <form className="tx-create-form" onSubmit={handleSubmit} noValidate>
            {merchantsQuery.isError && (
              <div className="error-state" role="alert">
                <p>{getErrorMessage(merchantsQuery.error, 'Failed to load merchants.')}</p>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    void merchantsQuery.refetch();
                  }}
                >
                  Retry Merchants
                </button>
              </div>
            )}

            <div className="form-grid">
              <div className="form-field">
                <label htmlFor="tx-card-select" className="form-label">
                  Active Card
                </label>
                <select
                  id="tx-card-select"
                  className="form-control"
                  value={selectedCardId}
                  onChange={(e) => setSelectedCardId(e.target.value)}
                  disabled={createMutation.isPending}
                >
                  {activeCards.map((card) => (
                    <option key={card.id} value={String(card.id)}>
                      {card.nickname} ({card.card_product.name})
                    </option>
                  ))}
                </select>
                {inactiveCardsCount > 0 && (
                  <p className="form-hint">
                    {inactiveCardsCount} inactive{' '}
                    {inactiveCardsCount === 1 ? 'card is' : 'cards are'} excluded.
                  </p>
                )}
              </div>

              <div className="form-field">
                <label htmlFor="tx-amount-input" className="form-label">
                  Amount (USD)
                </label>
                <input
                  id="tx-amount-input"
                  type="text"
                  inputMode="decimal"
                  className="form-control"
                  value={amountUsd}
                  onChange={(e) => {
                    setAmountUsd(e.target.value);
                    if (formError) {
                      setFormError(null);
                    }
                  }}
                  placeholder="e.g. 42.50"
                  disabled={createMutation.isPending}
                />
              </div>

              <div className="form-field">
                <label htmlFor="tx-category-select" className="form-label">
                  Category
                </label>
                <select
                  id="tx-category-select"
                  className="form-control"
                  value={categoryCode}
                  onChange={(e) => {
                    setCategoryCode(e.target.value);
                    setCategoryManuallyChanged(true);
                  }}
                  disabled={categories.length === 0 || createMutation.isPending}
                >
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.code}>
                      {cat.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label htmlFor="tx-date-input" className="form-label">
                  Transaction Date
                </label>
                <input
                  id="tx-date-input"
                  type="date"
                  className="form-control"
                  value={occurredOn}
                  onChange={(e) => setOccurredOn(e.target.value)}
                  disabled={createMutation.isPending}
                />
              </div>
            </div>

            <div className="form-grid">
              <div className="form-field">
                <label htmlFor="tx-merchant-mode" className="form-label">
                  Merchant Input Type
                </label>
                <select
                  id="tx-merchant-mode"
                  className="form-control"
                  value={merchantMode}
                  onChange={(e) => {
                    const nextMode = e.target.value === 'custom' ? 'custom' : 'seeded';
                    setMerchantMode(nextMode);
                    if (nextMode === 'seeded') {
                      setMerchantText('');
                    } else {
                      setMerchantId('');
                    }
                  }}
                  disabled={createMutation.isPending}
                >
                  <option value="seeded">Seeded merchant</option>
                  <option value="custom">Custom merchant text</option>
                </select>
              </div>

              {merchantMode === 'seeded' ? (
                <div className="form-field">
                  <label htmlFor="tx-merchant-select" className="form-label">
                    Seeded Merchant (optional)
                  </label>
                  <select
                    id="tx-merchant-select"
                    className="form-control"
                    value={merchantId}
                    onChange={(e) => handleMerchantSelectChange(e.target.value)}
                    disabled={merchantsQuery.isError || createMutation.isPending}
                  >
                    <option value="">None / Unspecified</option>
                    {merchants.map((merchant) => (
                      <option key={merchant.id} value={String(merchant.id)}>
                        {merchant.name}
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <div className="form-field">
                  <label htmlFor="tx-merchant-text" className="form-label">
                    Custom Merchant (optional)
                  </label>
                  <input
                    id="tx-merchant-text"
                    type="text"
                    className="form-control"
                    value={merchantText}
                    onChange={(e) => setMerchantText(e.target.value)}
                    maxLength={200}
                    placeholder="e.g. Corner Bakery"
                    aria-describedby="tx-merchant-safety-hint"
                    disabled={createMutation.isPending}
                  />
                  <p id="tx-merchant-safety-hint" className="form-hint">
                    Do not enter real card numbers or sensitive data.
                  </p>
                </div>
              )}

              <div className="form-field">
                <label htmlFor="tx-note-input" className="form-label">
                  Note (optional)
                </label>
                <input
                  id="tx-note-input"
                  type="text"
                  className="form-control"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  maxLength={1000}
                  placeholder="e.g. Team lunch"
                  aria-describedby="tx-note-safety-hint"
                  disabled={createMutation.isPending}
                />
                <p id="tx-note-safety-hint" className="form-hint">
                  Do not enter real card numbers or sensitive data.
                </p>
              </div>
            </div>

            {formError && (
              <div className="error-state" role="alert">
                <p>{formError}</p>
              </div>
            )}

            <div className="form-actions">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={createMutation.isPending}
              >
                {createMutation.isPending ? 'Recording...' : 'Record Transaction'}
              </button>
            </div>
          </form>
        )}

        {lastCreatedTx && lastCreatedTrace && (
          <div className="tx-snapshot-banner" data-testid="tx-created-snapshot" role="status">
            <h3 className="tx-snapshot-heading">Immutable Reward Snapshot</h3>
            <p>
              Earned <strong>{lastCreatedTx.reward_calc.reward_units}</strong>{' '}
              {lastCreatedTx.reward_calc.reward_currency}
              {lastCreatedTx.reward_calc.estimated_value_cents != null
                ? ` · Est. Value: ${formatCentsToUsd(lastCreatedTx.reward_calc.estimated_value_cents)}`
                : ' · Unvalued'}
              {lastCreatedTx.reward_calc.valuation_cents_per_unit_used != null
                ? ` (at ${lastCreatedTx.reward_calc.valuation_cents_per_unit_used}¢/unit)`
                : ''}
              {` · Engine v${lastCreatedTx.reward_calc.engine_version}`}
            </p>
            {lastCreatedTrace.warnings.length > 0 && (
              <ul className="compare-warnings-list">
                {lastCreatedTrace.warnings.map((w, idx) => (
                  <li key={idx}>Warning: {w}</li>
                ))}
              </ul>
            )}
            {lastCreatedTrace.explanation.length > 0 && (
              <ol className="compare-explanation-list">
                {lastCreatedTrace.explanation.map((step, idx) => (
                  <li key={idx}>{step}</li>
                ))}
              </ol>
            )}
          </div>
        )}
      </section>

      <section className="section-card" aria-labelledby="tx-history-heading">
        <div className="section-header">
          <h2 id="tx-history-heading" className="section-title">
            Transaction History ({transactions.length})
          </h2>
        </div>

        <div ref={feedbackRef} tabIndex={-1} className="feedback-anchor">
          {actionFeedback && (
            <div
              className={
                actionFeedback.kind === 'error'
                  ? 'error-state'
                  : 'reset-feedback reset-feedback--success'
              }
              role={actionFeedback.kind === 'error' ? 'alert' : 'status'}
            >
              <p>{actionFeedback.message}</p>
            </div>
          )}
        </div>

        {!hasProfile ? (
          <p className="empty-message" role="status">
            Select a demo profile to view transaction history.
          </p>
        ) : (
          <>
            <div className="tx-filters-bar">
              <div className="form-grid">
                <div className="form-field">
                  <label htmlFor="tx-filter-card" className="form-label">
                    Filter by Card
                  </label>
                  <select
                    id="tx-filter-card"
                    className="form-control"
                    value={filterCardId}
                    onChange={(e) => setFilterCardId(e.target.value)}
                  >
                    <option value="">All cards</option>
                    {allProfileCards.map((card) => (
                      <option key={card.id} value={String(card.id)}>
                        {card.nickname}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-field">
                  <label htmlFor="tx-filter-category" className="form-label">
                    Filter by Category
                  </label>
                  <select
                    id="tx-filter-category"
                    className="form-control"
                    value={filterCategoryCode}
                    onChange={(e) => setFilterCategoryCode(e.target.value)}
                  >
                    <option value="">All categories</option>
                    {categories.map((cat) => (
                      <option key={cat.id} value={cat.code}>
                        {cat.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-field">
                  <label htmlFor="tx-filter-date-from" className="form-label">
                    Date From
                  </label>
                  <input
                    id="tx-filter-date-from"
                    type="date"
                    className="form-control"
                    value={filterDateFrom}
                    onChange={(e) => setFilterDateFrom(e.target.value)}
                  />
                </div>

                <div className="form-field">
                  <label htmlFor="tx-filter-date-to" className="form-label">
                    Date To
                  </label>
                  <input
                    id="tx-filter-date-to"
                    type="date"
                    className="form-control"
                    value={filterDateTo}
                    onChange={(e) => setFilterDateTo(e.target.value)}
                  />
                </div>
              </div>

              <div className="tx-filter-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleClearFilters}
                >
                  Clear Filters
                </button>
              </div>
            </div>

            {isDateRangeInvalid ? (
              <div className="error-state" role="alert">
                <p>Date From must not be after Date To.</p>
              </div>
            ) : transactionsQuery.isLoading ? (
              <p className="loading-message" role="status">
                Loading transactions...
              </p>
            ) : transactionsQuery.isError ? (
              <div className="error-state" role="alert">
                <p>{getErrorMessage(transactionsQuery.error, 'Failed to load transactions.')}</p>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    void transactionsQuery.refetch();
                  }}
                >
                  Retry Transactions
                </button>
              </div>
            ) : transactions.length === 0 ? (
              <p className="empty-message">No transactions recorded for the selected filters.</p>
            ) : (
              <div className="tx-list">
                {transactions.map((tx) => {
                  const isExpanded = Boolean(expandedTxIds[tx.id]);
                  const isConfirming = confirmingDeleteId === tx.id;
                  const isDeletingThis =
                    deleteMutation.isPending && deleteMutation.variables?.transactionId === tx.id;
                  const trace = narrowTransactionTrace(tx.reward_calc.trace);
                  const tracePanelId = `tx-trace-${tx.id}`;
                  const merchantDisplay = tx.merchant_name ?? tx.merchant_text ?? 'Unspecified';

                  return (
                    <article key={tx.id} className="tx-item-card" data-testid="tx-list-item">
                      <div className="tx-item-header">
                        <div>
                          <h3 className="tx-item-title">
                            {formatCentsToUsd(tx.amount_cents)} at {merchantDisplay}
                          </h3>
                          <p className="tx-item-meta">
                            {tx.occurred_on} · {tx.card_name} · {tx.category_name}
                          </p>
                        </div>
                        <div className="tx-item-reward-badge">
                          <strong>
                            {tx.reward_calc.reward_units} {tx.reward_calc.reward_currency}
                          </strong>
                          {tx.reward_calc.estimated_value_cents != null
                            ? ` (${formatCentsToUsd(tx.reward_calc.estimated_value_cents)})`
                            : ' (Unvalued)'}
                        </div>
                      </div>

                      {tx.note && <p className="tx-item-note">Note: {tx.note}</p>}

                      <p className="tx-item-snapshot-meta">
                        Snapshot: Engine v{tx.reward_calc.engine_version}
                        {tx.reward_calc.valuation_cents_per_unit_used != null
                          ? ` · Valuation used: ${tx.reward_calc.valuation_cents_per_unit_used}¢/unit`
                          : ' · No valuation used'}
                      </p>

                      <div className="tx-item-actions">
                        <button
                          type="button"
                          className="btn btn-outline"
                          aria-expanded={isExpanded}
                          aria-controls={tracePanelId}
                          onClick={() =>
                            setExpandedTxIds((prev) => ({ ...prev, [tx.id]: !prev[tx.id] }))
                          }
                        >
                          {isExpanded ? 'Hide trace' : 'Show trace'}
                        </button>

                        {!isConfirming ? (
                          <button
                            type="button"
                            className="btn btn-danger"
                            disabled={isDeletingThis}
                            onClick={() => {
                              setActionFeedback(null);
                              setConfirmingDeleteId(tx.id);
                            }}
                          >
                            Remove
                          </button>
                        ) : (
                          <div
                            className="confirm-delete-group"
                            role="group"
                            aria-label={`Confirm removal of transaction ${tx.id}`}
                          >
                            <button
                              type="button"
                              className="btn btn-danger"
                              disabled={isDeletingThis}
                              onClick={() => {
                                deleteMutation.mutate({
                                  targetProfile: profileId,
                                  transactionId: tx.id,
                                });
                              }}
                            >
                              {isDeletingThis ? 'Removing...' : 'Confirm Remove'}
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              disabled={isDeletingThis}
                              onClick={() => setConfirmingDeleteId(null)}
                            >
                              Cancel
                            </button>
                          </div>
                        )}
                      </div>

                      {isExpanded && (
                        <div id={tracePanelId} className="tx-trace-panel">
                          {trace.appliedPortions.length > 0 && (
                            <ul className="compare-applied-list">
                              {trace.appliedPortions.map((p, idx) => (
                                <li key={idx}>
                                  {p.portionCents != null
                                    ? formatCentsToUsd(p.portionCents)
                                    : 'Portion'}{' '}
                                  at {p.multiplier ?? '?'}× ({p.ruleKey ?? 'rule'} v
                                  {p.ruleVersion ?? '?'}) → {p.rewardUnits ?? '?'}{' '}
                                  {tx.reward_calc.reward_currency}
                                </li>
                              ))}
                            </ul>
                          )}
                          {trace.warnings.length > 0 && (
                            <ul className="compare-warnings-list">
                              {trace.warnings.map((w, idx) => (
                                <li key={idx}>Warning: {w}</li>
                              ))}
                            </ul>
                          )}
                          {trace.explanation.length > 0 ? (
                            <ol className="compare-explanation-list">
                              {trace.explanation.map((step, idx) => (
                                <li key={idx}>{step}</li>
                              ))}
                            </ol>
                          ) : (
                            <p className="empty-message">No explanation steps recorded.</p>
                          )}
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
};
