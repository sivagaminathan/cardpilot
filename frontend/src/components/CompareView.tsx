import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  ApiError,
  fetchCategories,
  fetchMerchants,
  fetchProfileCards,
  recommendCards,
  type CardRecommendationItem,
  type CategorySummary,
  type MerchantSummary,
  type ProfileCardSummary,
  type RecommendationRequest,
  type RecommendationResponse,
} from '../api/client';
import { formatCentsToUsd, getTodayLocalIsoDate, parseUsdToCents } from '../lib/formatters';

interface CompareViewProps {
  profileId: string;
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

interface RecommendationItemCardProps {
  item: CardRecommendationItem;
  sectionKey: 'ranked' | 'unranked' | 'ineligible';
  isExpanded: boolean;
  onToggleExpand: () => void;
}

const RecommendationItemCard: React.FC<RecommendationItemCardProps> = ({
  item,
  sectionKey,
  isExpanded,
  onToggleExpand,
}) => {
  const explanationId = `explanation-${sectionKey}-${item.profile_card_id}`;
  const warnings = item.warnings ?? [];

  return (
    <article
      className="compare-result-card"
      data-testid={`compare-${sectionKey}-item`}
    >
      <div className="compare-result-header">
        <div>
          <h4 className="compare-card-title">
            {sectionKey === 'ranked' && item.rank != null ? `#${item.rank} ` : ''}
            {item.card_name}
          </h4>
          {sectionKey !== 'ineligible' ? (
            <p className="compare-reward-line">
              Earned: <strong>{item.reward_units}</strong> {item.reward_currency}
              {sectionKey === 'ranked' && item.estimated_value_cents != null ? (
                <>
                  {' '}
                  · Est. Value: <strong>{formatCentsToUsd(item.estimated_value_cents)}</strong>
                </>
              ) : null}
            </p>
          ) : null}
        </div>
        <span className={`badge ${sectionKey === 'ranked' ? 'badge-fresh' : 'badge-warning'}`}>
          {item.status}
        </span>
      </div>

      {item.message && <p className="compare-item-message">{item.message}</p>}
      {!item.message && item.reason && <p className="compare-item-message">Reason: {item.reason}</p>}

      {item.applied.length > 0 && (
        <div className="compare-applied-list">
          <strong>Applied rules:</strong>
          <ul>
            {item.applied.map((portion, idx) => (
              <li key={`${portion.rule_id}-${idx}`}>
                {formatCentsToUsd(portion.portion_cents)} at {portion.multiplier}× ({portion.rule_key}{' '}
                v{portion.rule_version}) → {portion.reward_units} {item.reward_currency}
              </li>
            ))}
          </ul>
        </div>
      )}

      {warnings.length > 0 && (
        <ul className="compare-warnings-list" aria-label={`Warnings for ${item.card_name}`}>
          {warnings.map((warning, idx) => (
            <li key={idx} className="compare-warning-item">
              Warning: {warning}
            </li>
          ))}
        </ul>
      )}

      {item.explanation.length > 0 && (
        <div className="compare-explanation-block">
          <button
            type="button"
            className="btn btn-outline compare-explain-toggle"
            aria-expanded={isExpanded}
            aria-controls={explanationId}
            onClick={onToggleExpand}
          >
            {isExpanded ? 'Hide explanation' : 'Show explanation'}
          </button>
          {isExpanded && (
            <ol id={explanationId} className="compare-explanation-list">
              {item.explanation.map((step, idx) => (
                <li key={idx}>{step}</li>
              ))}
            </ol>
          )}
        </div>
      )}
    </article>
  );
};

export const CompareView: React.FC<CompareViewProps> = ({ profileId }) => {
  const hasProfile = Boolean(profileId);
  const activeProfileRef = useRef<string>(profileId);
  activeProfileRef.current = profileId;

  const [amountUsd, setAmountUsd] = useState<string>('100.00');
  const [categoryCode, setCategoryCode] = useState<string>('');
  const [categoryManuallyChanged, setCategoryManuallyChanged] = useState<boolean>(false);
  const [merchantId, setMerchantId] = useState<string>('');
  const [purchaseDate, setPurchaseDate] = useState<string>(() => getTodayLocalIsoDate());
  const [excludedCardIds, setExcludedCardIds] = useState<number[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  const [result, setResult] = useState<RecommendationResponse | null>(null);
  const [expandedCards, setExpandedCards] = useState<Record<number, boolean>>({});

  // Clear profile-specific selection, results, and errors when switching profiles.
  useEffect(() => {
    setExcludedCardIds([]);
    setFormError(null);
    setResult(null);
    setExpandedCards({});
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

  const categories = useMemo(() => categoriesQuery.data ?? [], [categoriesQuery.data]);
  const merchants = useMemo(() => merchantsQuery.data ?? [], [merchantsQuery.data]);
  const allProfileCards = useMemo(() => cardsQuery.data ?? [], [cardsQuery.data]);
  const activeCards = useMemo(
    () => allProfileCards.filter((card) => card.is_active),
    [allProfileCards],
  );
  const inactiveCardsCount = allProfileCards.length - activeCards.length;

  useEffect(() => {
    if (categories.length > 0 && !categories.some((cat) => cat.code === categoryCode)) {
      setCategoryCode(categories[0].code);
      setCategoryManuallyChanged(false);
    }
  }, [categories, categoryCode]);

  const recommendMutation = useMutation({
    mutationFn: (variables: { targetProfile: string; payload: RecommendationRequest }) =>
      recommendCards(variables.targetProfile, variables.payload),
    onSuccess: (data, variables) => {
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setFormError(null);
      setResult(data);
      setExpandedCards({});
    },
    onError: (err, variables) => {
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setResult(null);
      setFormError(getErrorMessage(err, 'Unable to run recommendation comparison.'));
    },
  });

  const includedCardIds = useMemo(
    () => activeCards.filter((card) => !excludedCardIds.includes(card.id)).map((card) => card.id),
    [activeCards, excludedCardIds],
  );

  const handleMerchantChange = (nextMerchantId: string): void => {
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

  const handleToggleCard = (cardId: number): void => {
    setExcludedCardIds((prev) =>
      prev.includes(cardId) ? prev.filter((id) => id !== cardId) : [...prev, cardId],
    );
  };

  const handleToggleExplanation = (profileCardId: number): void => {
    setExpandedCards((prev) => ({
      ...prev,
      [profileCardId]: !prev[profileCardId],
    }));
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setFormError(null);

    if (!hasProfile) {
      setFormError('Select a demo profile before comparing cards.');
      return;
    }

    const amountCents = parseUsdToCents(amountUsd);
    if (amountCents === null) {
      setFormError('Enter a positive USD amount with up to two decimal places (e.g. 125.00).');
      return;
    }

    if (!categoryCode) {
      setFormError('Select a spending category.');
      return;
    }

    if (activeCards.length > 0 && includedCardIds.length === 0) {
      setFormError('Select at least one active card to compare.');
      return;
    }

    const parsedMerchantId = merchantId ? Number(merchantId) : null;
    const cardIdsPayload =
      activeCards.length > 0 && includedCardIds.length < activeCards.length
        ? includedCardIds
        : null;

    recommendMutation.mutate({
      targetProfile: profileId,
      payload: {
        amount_cents: amountCents,
        category_code: categoryCode,
        merchant_id: parsedMerchantId,
        purchase_date: purchaseDate.trim() ? purchaseDate.trim() : null,
        card_ids: cardIdsPayload,
      },
    });
  };

  const isReferenceLoading = categoriesQuery.isLoading || merchantsQuery.isLoading;

  return (
    <div className="compare-view">
      <section className="section-card" aria-labelledby="compare-heading">
        <h2 id="compare-heading" className="section-title">
          Compare Cards for Purchase
        </h2>

        {!hasProfile && (
          <p className="empty-message" role="status">
            Select a demo profile to compare cards.
          </p>
        )}

        {isReferenceLoading ? (
          <p className="loading-message" role="status">
            Loading categories and merchants...
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
        ) : (
          <form onSubmit={handleSubmit} className="compare-form" noValidate>
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
                <label htmlFor="compare-amount" className="form-label">
                  Amount (USD)
                </label>
                <input
                  id="compare-amount"
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
                  disabled={!hasProfile || recommendMutation.isPending}
                />
              </div>

              <div className="form-field">
                <label htmlFor="compare-category" className="form-label">
                  Category
                </label>
                <select
                  id="compare-category"
                  className="form-control"
                  value={categoryCode}
                  onChange={(e) => {
                    setCategoryCode(e.target.value);
                    setCategoryManuallyChanged(true);
                  }}
                  disabled={!hasProfile || categories.length === 0 || recommendMutation.isPending}
                >
                  {categories.map((category) => (
                    <option key={category.id} value={category.code}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label htmlFor="compare-merchant" className="form-label">
                  Merchant (optional)
                </label>
                <select
                  id="compare-merchant"
                  className="form-control"
                  value={merchantId}
                  onChange={(e) => handleMerchantChange(e.target.value)}
                  disabled={!hasProfile || merchantsQuery.isError || recommendMutation.isPending}
                >
                  <option value="">None / Any merchant</option>
                  {merchants.map((merchant) => (
                    <option key={merchant.id} value={String(merchant.id)}>
                      {merchant.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label htmlFor="compare-date" className="form-label">
                  Purchase Date
                </label>
                <input
                  id="compare-date"
                  type="date"
                  className="form-control"
                  value={purchaseDate}
                  onChange={(e) => setPurchaseDate(e.target.value)}
                  disabled={!hasProfile || recommendMutation.isPending}
                />
              </div>
            </div>

            {hasProfile && (
              <fieldset className="compare-cards-fieldset">
                <legend className="form-label">Cards to Compare (active cards only)</legend>
                {cardsQuery.isLoading ? (
                  <p className="loading-message" role="status">
                    Loading active cards...
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
                ) : activeCards.length === 0 ? (
                  <p className="empty-message">
                    No active cards in this profile. Inactive cards are excluded by default.
                  </p>
                ) : (
                  <>
                    <div className="compare-card-checkboxes">
                      {activeCards.map((card) => {
                        const checked = !excludedCardIds.includes(card.id);
                        return (
                          <label key={card.id} className="compare-card-checkbox-label">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => handleToggleCard(card.id)}
                              disabled={recommendMutation.isPending}
                            />
                            <span>
                              {card.nickname} ({card.card_product.name})
                            </span>
                          </label>
                        );
                      })}
                    </div>
                    {inactiveCardsCount > 0 && (
                      <p className="form-hint">
                        {inactiveCardsCount} inactive{' '}
                        {inactiveCardsCount === 1 ? 'card is' : 'cards are'} excluded by default.
                      </p>
                    )}
                  </>
                )}
              </fieldset>
            )}

            {formError && (
              <div className="error-state" role="alert">
                <p>{formError}</p>
              </div>
            )}

            <div className="form-actions">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={
                  !hasProfile || categories.length === 0 || recommendMutation.isPending
                }
              >
                {recommendMutation.isPending ? 'Comparing...' : 'Compare Cards'}
              </button>
            </div>
          </form>
        )}
      </section>

      {result && (
        <section className="section-card" aria-labelledby="compare-results-heading">
          <div className="section-header">
            <h3 id="compare-results-heading" className="section-title">
              Comparison Results
            </h3>
            <span className="badge">Engine v{result.engine_version}</span>
          </div>

          {result.ranked.length === 0 &&
          result.unranked.length === 0 &&
          result.ineligible.length === 0 ? (
            <p className="empty-message">No cards were evaluated for this comparison.</p>
          ) : (
            <div className="compare-results-sections">
              <div className="compare-section">
                <h4 className="compare-subsection-title">
                  Ranked Cards ({result.ranked.length})
                </h4>
                {result.ranked.length === 0 ? (
                  <p className="empty-message">No rankable cards for this profile.</p>
                ) : (
                  <div className="compare-results-list">
                    {result.ranked.map((item) => (
                      <RecommendationItemCard
                        key={item.profile_card_id}
                        item={item}
                        sectionKey="ranked"
                        isExpanded={Boolean(expandedCards[item.profile_card_id])}
                        onToggleExpand={() => handleToggleExplanation(item.profile_card_id)}
                      />
                    ))}
                  </div>
                )}
              </div>

              {result.unranked.length > 0 && (
                <div className="compare-section">
                  <h4 className="compare-subsection-title">
                    Unranked Cards ({result.unranked.length})
                  </h4>
                  <div className="compare-results-list">
                    {result.unranked.map((item) => (
                      <RecommendationItemCard
                        key={item.profile_card_id}
                        item={item}
                        sectionKey="unranked"
                        isExpanded={Boolean(expandedCards[item.profile_card_id])}
                        onToggleExpand={() => handleToggleExplanation(item.profile_card_id)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {result.ineligible.length > 0 && (
                <div className="compare-section">
                  <h4 className="compare-subsection-title">
                    Ineligible Cards ({result.ineligible.length})
                  </h4>
                  <div className="compare-results-list">
                    {result.ineligible.map((item) => (
                      <RecommendationItemCard
                        key={item.profile_card_id}
                        item={item}
                        sectionKey="ineligible"
                        isExpanded={Boolean(expandedCards[item.profile_card_id])}
                        onToggleExpand={() => handleToggleExplanation(item.profile_card_id)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {result.global_notes.length > 0 && (
                <div className="compare-global-notes" role="note">
                  <strong>Comparison Notes:</strong>
                  <ul>
                    {result.global_notes.map((note, idx) => (
                      <li key={idx}>{note}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
};
