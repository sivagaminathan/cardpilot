import React, { useState } from 'react';
import { formatCentsToUsd } from '../lib/formatters';

interface AppliedPortion {
  portion_cents: number;
  rule_id: number;
  rule_key: string;
  rule_version: number;
  multiplier: string;
  reward_units: string;
}

interface CardRecommendationItem {
  rank: number | null;
  profile_card_id: number;
  card_name: string;
  reward_currency: string;
  status: string;
  reward_units: string;
  estimated_value_cents: number | null;
  reason: string | null;
  message: string | null;
  applied: AppliedPortion[];
  explanation: string[];
}

interface RecommendationResponse {
  ranked: CardRecommendationItem[];
  unranked: CardRecommendationItem[];
  ineligible: CardRecommendationItem[];
  global_notes: string[];
  engine_version: string;
}

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  return configured ? configured.replace(/\/+$/, '') : '/api/v1';
}

interface CompareViewProps {
  profileId: string;
}

export const CompareView: React.FC<CompareViewProps> = ({ profileId }) => {
  const [amountUsd, setAmountUsd] = useState<string>('125.00');
  const [categoryCode, setCategoryCode] = useState<string>('groceries');
  const [purchaseDate, setPurchaseDate] = useState<string>('2026-08-15');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RecommendationResponse | null>(null);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError(null);

    const parsed = Number.parseFloat(amountUsd);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setError('Please enter a positive purchase amount.');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/profiles/${profileId}/recommendations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount_cents: Math.round(parsed * 100),
          category_code: categoryCode,
          purchase_date: purchaseDate,
        }),
      });
      if (!res.ok) {
        setError(`Recommendation request failed (HTTP ${res.status}).`);
        setResult(null);
        return;
      }
      const data = (await res.json()) as RecommendationResponse;
      setResult(data);
    } catch {
      setError('Unable to reach recommendation API.');
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="section-card" aria-labelledby="compare-heading">
      <h2 id="compare-heading" className="section-title">
        Compare Cards for Purchase
      </h2>
      <form onSubmit={(e) => void handleSubmit(e)} className="compare-form">
        <label htmlFor="compare-amount">
          Amount (USD)
          <input
            id="compare-amount"
            type="text"
            value={amountUsd}
            onChange={(e) => setAmountUsd(e.target.value)}
          />
        </label>
        <label htmlFor="compare-category">
          Category
          <select
            id="compare-category"
            value={categoryCode}
            onChange={(e) => setCategoryCode(e.target.value)}
          >
            <option value="groceries">Groceries</option>
            <option value="dining">Dining</option>
            <option value="gas">Gas</option>
            <option value="travel">Travel</option>
            <option value="streaming">Streaming</option>
            <option value="online_retail">Online Retail</option>
            <option value="utilities">Utilities</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label htmlFor="compare-date">
          Date
          <input
            id="compare-date"
            type="date"
            value={purchaseDate}
            onChange={(e) => setPurchaseDate(e.target.value)}
          />
        </label>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Comparing...' : 'Compare Cards'}
        </button>
      </form>

      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}

      {result && (
        <div className="compare-results">
          <h3>Ranked Cards</h3>
          {result.ranked.length === 0 ? (
            <p>No rankable cards for this profile.</p>
          ) : (
            <ul>
              {result.ranked.map((item) => (
                <li key={item.profile_card_id}>
                  <strong>
                    #{item.rank} {item.card_name}
                  </strong>{' '}
                  — {item.reward_units} {item.reward_currency} (
                  {item.estimated_value_cents !== null
                    ? formatCentsToUsd(item.estimated_value_cents)
                    : 'N/A'}
                  )
                  {item.explanation.length > 0 && <p>{item.explanation.join(' ')}</p>}
                </li>
              ))}
            </ul>
          )}

          {result.unranked.length > 0 && (
            <>
              <h3>Unranked Cards</h3>
              <ul>
                {result.unranked.map((item) => (
                  <li key={item.profile_card_id}>
                    <strong>{item.card_name}</strong> — {item.reward_units} {item.reward_currency}{' '}
                    ({item.message ?? item.reason ?? 'No valuation configured'})
                  </li>
                ))}
              </ul>
            </>
          )}

          {result.global_notes.length > 0 && (
            <p className="footer-disclaimer">{result.global_notes.join(' ')}</p>
          )}
        </div>
      )}
    </section>
  );
};
