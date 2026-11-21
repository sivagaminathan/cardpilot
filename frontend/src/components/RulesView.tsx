import React, { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  ApiError,
  fetchCardProductRules,
  fetchCardProducts,
  type CardProductSummary,
  type EarningRuleSummary,
} from '../api/client';
import { formatCentsToUsd } from '../lib/formatters';
import { DEFAULT_RULE_STALENESS_DAYS, getRuleStaleness } from '../lib/rules';

interface RulesViewProps {
  referenceDate?: Date | string;
  stalenessThresholdDays?: number;
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

function formatScopeLabel(rule: EarningRuleSummary): string {
  if (rule.scope_type === 'merchant' && rule.merchant_name) {
    return `Merchant: ${rule.merchant_name}`;
  }
  if (rule.scope_type === 'category' && rule.category_code) {
    return `Category: ${rule.category_code}`;
  }
  return `Scope: ${rule.scope_type}`;
}

function isSafeHttpUrl(rawUrl: string): boolean {
  try {
    const parsed = new URL(rawUrl);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export const RulesView: React.FC<RulesViewProps> = ({
  referenceDate,
  stalenessThresholdDays = DEFAULT_RULE_STALENESS_DAYS,
}) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const productParam = searchParams.get('productId');
  const [selectedProductId, setSelectedProductId] = useState<string>(productParam ?? '');

  const catalogQuery = useQuery<CardProductSummary[]>({
    queryKey: ['card-products'],
    queryFn: () => fetchCardProducts(),
  });

  const catalogProducts = useMemo(() => catalogQuery.data ?? [], [catalogQuery.data]);

  useEffect(() => {
    if (catalogProducts.length === 0) {
      return;
    }
    if (productParam && catalogProducts.some((p) => String(p.id) === productParam)) {
      setSelectedProductId(productParam);
      return;
    }
    if (!catalogProducts.some((p) => String(p.id) === selectedProductId)) {
      setSelectedProductId(String(catalogProducts[0].id));
    }
  }, [catalogProducts, productParam, selectedProductId]);

  const activeProduct =
    catalogProducts.find((p) => String(p.id) === selectedProductId) ?? null;
  const activeProductId = activeProduct ? activeProduct.id : null;

  const rulesQuery = useQuery<EarningRuleSummary[]>({
    queryKey: ['card-products', activeProductId, 'rules'],
    queryFn: () => fetchCardProductRules(activeProductId as number),
    enabled: activeProductId !== null,
  });

  const rules = rulesQuery.data ?? [];

  return (
    <div className="rules-view">
      <section className="section-card" aria-labelledby="rules-viewer-heading">
        <div className="section-header">
          <h2 id="rules-viewer-heading" className="section-title">
            Earning Rules &amp; Source Provenance
          </h2>
          <span className="badge">Staleness threshold: {stalenessThresholdDays} days</span>
        </div>

        <p className="rules-disclaimer-note" role="note">
          These are fictional sample rules for demonstration only, not current issuer terms.
        </p>

        {catalogQuery.isLoading ? (
          <p className="loading-message" role="status">
            Loading card catalog...
          </p>
        ) : catalogQuery.isError ? (
          <div className="error-state" role="alert">
            <p>{getErrorMessage(catalogQuery.error, 'Failed to load card catalog.')}</p>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                void catalogQuery.refetch();
              }}
            >
              Retry Catalog
            </button>
          </div>
        ) : catalogProducts.length === 0 ? (
          <p className="empty-message">No catalog card products available.</p>
        ) : (
          <div className="rules-product-picker">
            <label htmlFor="rules-product-select" className="form-label">
              Inspect Rules for Card Product
            </label>
            <select
              id="rules-product-select"
              className="form-control"
              value={activeProduct ? String(activeProduct.id) : ''}
              onChange={(e) => {
                const nextId = e.target.value;
                setSelectedProductId(nextId);
                setSearchParams({ productId: nextId }, { replace: true });
              }}
            >
              {catalogProducts.map((product) => (
                <option key={product.id} value={String(product.id)}>
                  {product.issuer_name} — {product.name} ({product.reward_currency.name})
                </option>
              ))}
            </select>
            {activeProduct && (
              <p className="product-description">
                {activeProduct.description} · {activeProduct.network_label} ·{' '}
                {activeProduct.annual_fee_cents === 0
                  ? '$0 Annual Fee'
                  : `${formatCentsToUsd(activeProduct.annual_fee_cents)}/yr`}
              </p>
            )}
          </div>
        )}
      </section>

      {activeProduct && (
        <section className="section-card" aria-labelledby="product-rules-list-heading">
          <div className="section-header">
            <h3 id="product-rules-list-heading" className="section-title">
              Rules for {activeProduct.name} ({rules.length})
            </h3>
          </div>

          {rulesQuery.isLoading ? (
            <p className="loading-message" role="status">
              Loading earning rules...
            </p>
          ) : rulesQuery.isError ? (
            <div className="error-state" role="alert">
              <p>{getErrorMessage(rulesQuery.error, 'Failed to load earning rules.')}</p>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  void rulesQuery.refetch();
                }}
              >
                Retry Rules
              </button>
            </div>
          ) : rules.length === 0 ? (
            <p className="empty-message">No earning rules defined for this card product.</p>
          ) : (
            <div className="rules-list">
              {rules.map((rule) => {
                const staleness = getRuleStaleness(
                  rule.source.last_reviewed_on,
                  referenceDate,
                  stalenessThresholdDays,
                );

                return (
                  <article key={rule.id} className="rule-card" data-testid="earning-rule-item">
                    <div className="rule-card-header">
                      <div>
                        <h4 className="rule-title">
                          {rule.rule_key} <span className="rule-version">(v{rule.version})</span>
                        </h4>
                        <p className="rule-scope">
                          {formatScopeLabel(rule)} · Multiplier:{' '}
                          <strong>{rule.multiplier}×</strong>
                        </p>
                      </div>

                      <div className="staleness-indicator">
                        <span
                          className={`badge ${staleness.isStale ? 'badge-warning' : 'badge-fresh'}`}
                        >
                          {staleness.isStale ? 'Stale' : 'Fresh'}
                        </span>
                        <span className="staleness-text">
                          {staleness.isStale
                            ? `Stale source (${staleness.ageDays} days since review; threshold ${staleness.thresholdDays} days)`
                            : staleness.ageDays !== null
                              ? `Reviewed ${staleness.ageDays} days ago`
                              : 'Review age unavailable'}
                        </span>
                      </div>
                    </div>

                    <dl className="rule-details-grid">
                      <div>
                        <dt>Effective Dates</dt>
                        <dd>
                          {rule.effective_from} to {rule.effective_to ?? 'No end date'}
                        </dd>
                      </div>
                      <div>
                        <dt>Priority &amp; Rounding</dt>
                        <dd>
                          Priority {rule.priority} · Rounding: {rule.rounding} · Post-cap:{' '}
                          {rule.post_cap_behavior}
                        </dd>
                      </div>

                      {rule.cap && (
                        <div>
                          <dt>Spend Cap</dt>
                          <dd>
                            {formatCentsToUsd(rule.cap.cap_amount_cents)} per {rule.cap.period} (
                            {rule.cap.cap_group_key})
                          </dd>
                        </div>
                      )}

                      {(rule.min_transaction_cents != null ||
                        rule.min_period_spend_cents != null) && (
                        <div>
                          <dt>Thresholds</dt>
                          <dd>
                            {rule.min_transaction_cents != null
                              ? `Min transaction: ${formatCentsToUsd(rule.min_transaction_cents)}`
                              : null}
                            {rule.min_transaction_cents != null &&
                            rule.min_period_spend_cents != null
                              ? ' · '
                              : null}
                            {rule.min_period_spend_cents != null
                              ? `Min period spend: ${formatCentsToUsd(rule.min_period_spend_cents)}${rule.threshold_period ? ` (${rule.threshold_period})` : ''}`
                              : null}
                          </dd>
                        </div>
                      )}
                    </dl>

                    {rule.exclusions.length > 0 && (
                      <div className="rule-exclusions">
                        <strong>Exclusions:</strong>
                        <ul>
                          {rule.exclusions.map((excl) => (
                            <li key={excl.id}>
                              {excl.exclusion_type}:{' '}
                              {excl.target_category_code ??
                                excl.target_merchant_name ??
                                excl.target_tag ??
                                'Unspecified target'}{' '}
                              — {excl.reason}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    <div className="rule-source-box">
                      <h5 className="rule-source-heading">Source Provenance</h5>
                      <p>
                        <strong>{rule.source.title}</strong> ({rule.source.kind}) · Last reviewed:{' '}
                        <span>{rule.source.last_reviewed_on}</span>
                      </p>
                      {rule.source.url && (
                        <p>
                          Source URL:{' '}
                          {isSafeHttpUrl(rule.source.url) ? (
                            <a
                              href={rule.source.url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              {rule.source.url}
                            </a>
                          ) : (
                            <span>{rule.source.url}</span>
                          )}
                        </p>
                      )}
                      {rule.source.notes && <p className="rule-source-notes">{rule.source.notes}</p>}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      )}
    </div>
  );
};
