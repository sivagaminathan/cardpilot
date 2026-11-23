import React, { useEffect, useMemo, useState } from 'react';
import {
  QueryClient,
  QueryClientProvider,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { MemoryRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { ApiError, fetchProfiles, resetProfile } from './api/client';
import { BenefitsView } from './components/BenefitsView';
import { CardsView } from './components/CardsView';
import { CompareView } from './components/CompareView';
import { Dashboard } from './components/Dashboard';
import { DisclaimerBanner } from './components/DisclaimerBanner';
import { Header, type ResetFeedback } from './components/Header';
import { RewardsView } from './components/RewardsView';
import { RulesView } from './components/RulesView';
import { SettingsView } from './components/SettingsView';
import { TransactionsView } from './components/TransactionsView';

interface AppShellProps {
  rulesReferenceDate?: Date | string;
}

export const AppShell: React.FC<AppShellProps> = ({ rulesReferenceDate }) => {
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
                profileId={activeProfileKey}
                onNavigateTab={(tab) => navigate(tab === 'dashboard' ? '/' : `/${tab}`)}
              />
            }
          />
          <Route path="/cards" element={<CardsView profileId={activeProfileKey} />} />
          <Route path="/compare" element={<CompareView profileId={activeProfileKey} />} />
          <Route path="/transactions" element={<TransactionsView profileId={activeProfileKey} />} />
          <Route path="/benefits" element={<BenefitsView profileId={activeProfileKey} />} />
          <Route path="/rewards" element={<RewardsView profileId={activeProfileKey} />} />
          <Route path="/settings" element={<SettingsView profileId={activeProfileKey} />} />
          <Route path="/rules" element={<RulesView referenceDate={rulesReferenceDate} />} />
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

export const App: React.FC<{
  initialEntries?: string[];
  rulesReferenceDate?: Date | string;
}> = ({ initialEntries, rulesReferenceDate }) => {
  const [queryClient] = useState(createAppQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <AppShell rulesReferenceDate={rulesReferenceDate} />
      </MemoryRouter>
    </QueryClientProvider>
  );
};
