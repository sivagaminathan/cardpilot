import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ApiError,
  addProfileCard,
  deleteProfileCard,
  fetchCardProducts,
  fetchProfileCards,
  updateProfileCard,
  type CardProductSummary,
  type ProfileCardCreate,
  type ProfileCardSummary,
  type ProfileCardUpdate,
} from '../api/client';
import { formatCentsToUsd } from '../lib/formatters';

interface CardsViewProps {
  profileId: string;
}

interface ActionFeedback {
  kind: 'success' | 'error';
  message: string;
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.errors && error.errors.length > 0) {
      const detailText = error.errors
        .map((item) => item.msg)
        .filter((msg) => msg.length > 0)
        .join('; ');
      if (detailText) {
        return `${error.message} (${detailText})`;
      }
    }
    return error.message;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export const CardsView: React.FC<CardsViewProps> = ({ profileId }) => {
  const queryClient = useQueryClient();
  const hasProfile = Boolean(profileId);
  const feedbackRef = useRef<HTMLDivElement | null>(null);
  const activeProfileRef = useRef<string>(profileId);
  activeProfileRef.current = profileId;

  const [selectedProductId, setSelectedProductId] = useState<string>('');
  const [nickname, setNickname] = useState<string>('');
  const [openedOn, setOpenedOn] = useState<string>('');
  const [formError, setFormError] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback | null>(null);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<number | null>(null);

  // Clear transient form/mutation state on profile switch so feedback never leaks across profiles.
  useEffect(() => {
    setFormError(null);
    setActionFeedback(null);
    setConfirmingDeleteId(null);
  }, [profileId]);

  const catalogQuery = useQuery<CardProductSummary[]>({
    queryKey: ['card-products'],
    queryFn: () => fetchCardProducts(),
  });

  const cardsQuery = useQuery<ProfileCardSummary[]>({
    queryKey: ['profile', profileId, 'cards'],
    queryFn: () => fetchProfileCards(profileId),
    enabled: hasProfile,
  });

  const catalogProducts = useMemo(() => catalogQuery.data ?? [], [catalogQuery.data]);
  const heldCards = cardsQuery.data ?? [];

  useEffect(() => {
    if (
      catalogProducts.length > 0 &&
      !catalogProducts.some((product) => String(product.id) === selectedProductId)
    ) {
      setSelectedProductId(String(catalogProducts[0].id));
    }
  }, [catalogProducts, selectedProductId]);

  const addCardMutation = useMutation({
    mutationFn: (payload: { targetProfile: string; body: ProfileCardCreate }) =>
      addProfileCard(payload.targetProfile, payload.body),
    onSuccess: (created, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['profile', variables.targetProfile] });
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setNickname('');
      setOpenedOn('');
      setFormError(null);
      setActionFeedback({
        kind: 'success',
        message: `Added "${created.nickname}" (${created.card_product.name}).`,
      });
      feedbackRef.current?.focus();
    },
    onError: (err, variables) => {
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setFormError(getErrorMessage(err, 'Failed to add card to profile.'));
    },
  });

  const updateCardMutation = useMutation({
    mutationFn: (payload: { targetProfile: string; cardId: number; body: ProfileCardUpdate }) =>
      updateProfileCard(payload.targetProfile, payload.cardId, payload.body),
    onSuccess: (updated, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['profile', variables.targetProfile] });
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setActionFeedback({
        kind: 'success',
        message: `"${updated.nickname}" is now ${updated.is_active ? 'Active' : 'Inactive'}.`,
      });
    },
    onError: (err, variables) => {
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setActionFeedback({
        kind: 'error',
        message: getErrorMessage(err, 'Failed to update card status.'),
      });
    },
  });

  const deleteCardMutation = useMutation({
    mutationFn: (payload: { targetProfile: string; cardId: number; nickname: string }) =>
      deleteProfileCard(payload.targetProfile, payload.cardId),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['profile', variables.targetProfile] });
      if (activeProfileRef.current !== variables.targetProfile) {
        return;
      }
      setConfirmingDeleteId(null);
      setActionFeedback({
        kind: 'success',
        message: `Removed "${variables.nickname}" from this profile.`,
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
        message: getErrorMessage(err, 'Failed to remove card from profile.'),
      });
      feedbackRef.current?.focus();
    },
  });

  const handleAddSubmit = (event: React.FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setFormError(null);
    setActionFeedback(null);

    if (!hasProfile) {
      setFormError('Select a demo profile before adding a card.');
      return;
    }

    const parsedProductId = Number(selectedProductId);
    if (!Number.isInteger(parsedProductId) || parsedProductId <= 0) {
      setFormError('Select a card product from the catalog.');
      return;
    }

    const trimmedNickname = nickname.trim();
    if (!trimmedNickname) {
      setFormError('Nickname is required and must not be blank.');
      return;
    }

    addCardMutation.mutate({
      targetProfile: profileId,
      body: {
        card_product_id: parsedProductId,
        nickname: trimmedNickname,
        opened_on: openedOn.trim() ? openedOn.trim() : null,
        is_active: true,
      },
    });
  };

  return (
    <div className="cards-view">
      <section className="section-card" aria-labelledby="add-card-heading">
        <div className="section-header">
          <h2 id="add-card-heading" className="section-title">
            Add Card from Fictional Catalog
          </h2>
          <Link to="/rules" className="btn btn-outline">
            Browse Rules &amp; Sources
          </Link>
        </div>

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
          <form className="add-card-form" onSubmit={handleAddSubmit} noValidate>
            <div className="form-grid">
              <div className="form-field">
                <label htmlFor="catalog-product-select" className="form-label">
                  Catalog Card Product
                </label>
                <select
                  id="catalog-product-select"
                  className="form-control"
                  value={selectedProductId}
                  onChange={(e) => setSelectedProductId(e.target.value)}
                  disabled={!hasProfile || addCardMutation.isPending}
                >
                  {catalogProducts.map((product) => (
                    <option key={product.id} value={String(product.id)}>
                      {product.issuer_name} — {product.name} ({product.reward_currency.name},{' '}
                      {product.annual_fee_cents === 0
                        ? '$0 fee'
                        : `${formatCentsToUsd(product.annual_fee_cents)}/yr`}
                      )
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label htmlFor="card-nickname-input" className="form-label">
                  Card Nickname
                </label>
                <input
                  id="card-nickname-input"
                  type="text"
                  className="form-control"
                  value={nickname}
                  onChange={(e) => {
                    setNickname(e.target.value);
                    if (formError) {
                      setFormError(null);
                    }
                  }}
                  maxLength={128}
                  placeholder="e.g. Everyday Groceries"
                  aria-describedby="card-nickname-safety-hint"
                  disabled={!hasProfile || addCardMutation.isPending}
                />
                <p id="card-nickname-safety-hint" className="form-hint">
                  Do not enter real card numbers or sensitive data.
                </p>
              </div>

              <div className="form-field">
                <label htmlFor="card-opened-on-input" className="form-label">
                  Opened Date (optional)
                </label>
                <input
                  id="card-opened-on-input"
                  type="date"
                  className="form-control"
                  value={openedOn}
                  onChange={(e) => setOpenedOn(e.target.value)}
                  disabled={!hasProfile || addCardMutation.isPending}
                />
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
                disabled={!hasProfile || addCardMutation.isPending}
              >
                {addCardMutation.isPending ? 'Adding Card...' : 'Add Card'}
              </button>
            </div>
          </form>
        )}
      </section>

      <section className="section-card" aria-labelledby="held-cards-heading">
        <div className="section-header">
          <h2 id="held-cards-heading" className="section-title">
            Profile Cards ({heldCards.length})
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
            Select a demo profile to view and manage held cards.
          </p>
        ) : cardsQuery.isLoading ? (
          <p className="loading-message" role="status">
            Loading held cards...
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
              Retry Held Cards
            </button>
          </div>
        ) : heldCards.length === 0 ? (
          <p className="empty-message">No cards added to this profile yet.</p>
        ) : (
          <div className="cards-grid">
            {heldCards.map((card) => {
              const isConfirming = confirmingDeleteId === card.id;
              const isUpdatingThis =
                updateCardMutation.isPending && updateCardMutation.variables?.cardId === card.id;
              const isDeletingThis =
                deleteCardMutation.isPending && deleteCardMutation.variables?.cardId === card.id;

              return (
                <article key={card.id} className="card-item" data-testid="held-card-item">
                  <div className="card-item-header">
                    <span className="issuer-name">{card.card_product.issuer_name}</span>
                    <span className="fee-badge">
                      {card.card_product.annual_fee_cents === 0
                        ? '$0 Fee'
                        : `${formatCentsToUsd(card.card_product.annual_fee_cents)}/yr`}
                    </span>
                  </div>

                  <h3 className="card-nickname">{card.nickname}</h3>
                  <p className="card-product">{card.card_product.name}</p>

                  <div className="card-meta-row">
                    <span className="reward-type-label">
                      Earns: {card.card_product.reward_currency.name} (
                      {card.card_product.reward_currency.code})
                    </span>
                    <span className={`card-status-badge ${card.is_active ? 'active' : 'inactive'}`}>
                      Status: {card.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>

                  {card.opened_on && <p className="card-opened-date">Opened: {card.opened_on}</p>}

                  <div className="card-actions-row">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      disabled={isUpdatingThis || isDeletingThis}
                      onClick={() => {
                        setActionFeedback(null);
                        updateCardMutation.mutate({
                          targetProfile: profileId,
                          cardId: card.id,
                          body: { is_active: !card.is_active },
                        });
                      }}
                    >
                      {isUpdatingThis
                        ? 'Updating...'
                        : card.is_active
                          ? 'Deactivate'
                          : 'Activate'}
                    </button>

                    <Link
                      to={`/rules?productId=${card.card_product_id}`}
                      className="btn btn-outline"
                    >
                      View Rules
                    </Link>

                    {!isConfirming ? (
                      <button
                        type="button"
                        className="btn btn-danger"
                        disabled={isUpdatingThis || isDeletingThis}
                        onClick={() => {
                          setActionFeedback(null);
                          setConfirmingDeleteId(card.id);
                        }}
                      >
                        Remove
                      </button>
                    ) : (
                      <div
                        className="confirm-delete-group"
                        role="group"
                        aria-label={`Confirm removal of ${card.nickname}`}
                      >
                        <button
                          type="button"
                          className="btn btn-danger"
                          disabled={isDeletingThis}
                          onClick={() => {
                            deleteCardMutation.mutate({
                              targetProfile: profileId,
                              cardId: card.id,
                              nickname: card.nickname,
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
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
};
