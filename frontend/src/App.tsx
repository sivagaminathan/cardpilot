import React, { useEffect, useMemo, useState } from 'react';
import {
  QueryClient,
  QueryClientProvider,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { Link, MemoryRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { ApiError, fetchProfiles, resetProfile } from './api/client';
import { CompareView } from './components/CompareView';
import { Dashboard } from './components/Dashboard';
import { DisclaimerBanner } from './components/DisclaimerBanner';
import { Header, type ResetFeedback } from './components/Header';

interface PlaceholderPageProps {
  title: string;
  description: string;
}

const PlaceholderPage: React.FC<PlaceholderPageProps> = ({ title, description }) => (
  <section className="section-card placeholder-card">
    <h2 className="section-title">{title}</h2>
    <p className="placeholder-text">{description}</p>
    <Link to="/" className="btn btn-primary">
      Return to Dashboard
    </Link>
  </section>
);

export const AppShell: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedProfileKey, setSelectedProfileKey] = useState<string>('');
  const [resetFeedback, setResetFeedback] = useState<ResetFeedback | null>(null);

  const profilesQuery = useQuery({
    queryKey: ['profiles'],
    queryFn: () => fetchProfiles(),
  });

  const profiles = useMemo(() => profilesQuery.data ?? [], [profilesQuery.data]);

  useEffect(() => {
    if (profiles.length > 0 && !profiles.some((p) => p.slug === selectedProfileKey)) {
      setSelectedProfileKey(profiles[0].slug);
    }
  }, [profiles, selectedProfileKey]);

  const activeProfileKey =
    profiles.some((p) => p.slug === selectedProfileKey)
      ? selectedProfileKey
      : (profiles[0]?.slug ?? '');

  const resetMutation = useMutation({
    mutationFn: (profileKey: string) => resetProfile(profileKey),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ['profiles'] });
      void queryClient.invalidateQueries({ queryKey: ['profile', res.profile.slug] });
      setResetFeedback({
        kind: 'success',
        message: `Reset ${res.profile.display_name} (${res.cards_restored} cards, ${res.valuations_restored} valuations restored).`,
      });
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : 'Failed to reset demo profile.';
      setResetFeedback({ kind: 'error', message: msg });
    },
  });

  const profilesError = profilesQuery.isError
    ? profilesQuery.error instanceof ApiError
      ? profilesQuery.error.message
      : 'Failed to load profiles.'
    : null;

  return (
    <div className="app-container">
      <DisclaimerBanner />
      <Header
        profiles={profiles}
        isLoadingProfiles={profilesQuery.isLoading}
        profilesError={profilesError}
        onRetryProfiles={() => {
          void profilesQuery.refetch();
        }}
        currentProfileKey={activeProfileKey}
        onSelectProfile={(slug) => {
          setResetFeedback(null);
          setSelectedProfileKey(slug);
        }}
        onResetProfile={() => {
          if (activeProfileKey) {
            setResetFeedback(null);
            resetMutation.mutate(activeProfileKey);
          }
        }}
        isResetting={resetMutation.isPending}
        resetFeedback={resetFeedback}
      />

      <main className="main-content" id="main-content" tabIndex={-1}>
        <Routes>
          <Route
            path="/"
            element={
              <Dashboard
                profileId={activeProfileKey || 'maya'}
                onNavigateTab={(tab) => navigate(tab === 'dashboard' ? '/' : `/${tab}`)}
              />
            }
          />
          <Route
            path="/cards"
            element={
              <PlaceholderPage
                title="Cards View"
                description="Card portfolio management and rules viewer are scheduled for T39."
              />
            }
          />
          <Route path="/compare" element={<CompareView profileId={activeProfileKey || 'maya'} />} />
          <Route
            path="/transactions"
            element={
              <PlaceholderPage
                title="Transactions View"
                description="Transaction recording and snapshot history are scheduled for T42."
              />
            }
          />
          <Route
            path="/benefits"
            element={
              <PlaceholderPage
                title="Benefits View"
                description="Benefit status and usage logging are scheduled for T43."
              />
            }
          />
          <Route
            path="/rewards"
            element={
              <PlaceholderPage
                title="Rewards View"
                description="Per-currency rewards summary is scheduled for T44."
              />
            }
          />
          <Route
            path="/settings"
            element={
              <PlaceholderPage
                title="Settings View"
                description="Currency valuations editor is scheduled for T41."
              />
            }
          />
          <Route
            path="/rules"
            element={
              <PlaceholderPage
                title="Rules View"
                description="Earning rules, sources, and staleness viewer are scheduled for T39."
              />
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <footer className="app-footer">
        <p>CardPilot — Deterministic Rewards Optimizer &amp; Benefits Tracker (Demo Application)</p>
        <p className="footer-disclaimer">
          Sample data only. Not issuer terms. Not financial advice.
        </p>
      </footer>
    </div>
  );
};

function createAppQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}

export const App: React.FC<{ initialEntries?: string[] }> = ({ initialEntries }) => {
  const [queryClient] = useState(createAppQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <AppShell />
      </MemoryRouter>
    </QueryClientProvider>
  );
};
