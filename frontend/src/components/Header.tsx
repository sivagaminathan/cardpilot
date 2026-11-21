import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import type { ProfileSummary } from '../api/client';
import { BackendStatus } from './BackendStatus';

interface NavRoute {
  to: string;
  label: string;
  end?: boolean;
}

const NAV_ROUTES: NavRoute[] = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/cards', label: 'Cards' },
  { to: '/compare', label: 'Compare' },
  { to: '/transactions', label: 'Transactions' },
  { to: '/benefits', label: 'Benefits' },
  { to: '/rewards', label: 'Rewards' },
  { to: '/settings', label: 'Settings' },
  { to: '/rules', label: 'Rules' },
];

export interface ResetFeedback {
  kind: 'success' | 'error';
  message: string;
}

interface HeaderProps {
  profiles: ProfileSummary[];
  isLoadingProfiles: boolean;
  profilesError: string | null;
  onRetryProfiles: () => void;
  currentProfileKey: string;
  onSelectProfile: (profileSlug: string) => void;
  onResetProfile: () => void;
  isResetting: boolean;
  resetFeedback: ResetFeedback | null;
}

export const Header: React.FC<HeaderProps> = ({
  profiles,
  isLoadingProfiles,
  profilesError,
  onRetryProfiles,
  currentProfileKey,
  onSelectProfile,
  onResetProfile,
  isResetting,
  resetFeedback,
}) => {
  const [confirmingReset, setConfirmingReset] = useState(false);

  const handleConfirmReset = (): void => {
    setConfirmingReset(false);
    onResetProfile();
  };

  return (
    <header className="app-header">
      <div className="header-top">
        <div className="brand">
          <span className="brand-icon" aria-hidden="true">
            💳
          </span>
          <h1 className="brand-title">CardPilot</h1>
          <span className="version-tag">v0.1.0</span>
          <BackendStatus />
        </div>

        <div className="profile-selector-container">
          {isLoadingProfiles ? (
            <span className="profile-status-text" role="status">
              Loading profiles...
            </span>
          ) : profilesError ? (
            <div className="profile-error-group" role="alert">
              <span className="profile-error-text">{profilesError}</span>
              <button type="button" className="btn btn-secondary" onClick={onRetryProfiles}>
                Retry
              </button>
            </div>
          ) : profiles.length === 0 ? (
            <span className="profile-status-text" role="status">
              No profiles available
            </span>
          ) : (
            <>
              <label htmlFor="profile-select" className="profile-label">
                Demo Profile:
              </label>
              <select
                id="profile-select"
                className="profile-select"
                value={currentProfileKey}
                onChange={(e) => {
                  setConfirmingReset(false);
                  onSelectProfile(e.target.value);
                }}
                aria-label="Select demo profile"
              >
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.slug}>
                    {profile.display_name}
                  </option>
                ))}
              </select>

              {!confirmingReset ? (
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={!currentProfileKey || isResetting}
                  onClick={() => setConfirmingReset(true)}
                >
                  {isResetting ? 'Resetting...' : 'Reset Demo Data'}
                </button>
              ) : (
                <div className="reset-confirm-group" role="group" aria-label="Confirm demo reset">
                  <button
                    type="button"
                    className="btn btn-danger"
                    disabled={isResetting}
                    onClick={handleConfirmReset}
                  >
                    Confirm Reset
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={isResetting}
                    onClick={() => setConfirmingReset(false)}
                  >
                    Cancel
                  </button>
                </div>
              )}
            </>
          )}

          {resetFeedback && (
            <span
              className={`reset-feedback reset-feedback--${resetFeedback.kind}`}
              role={resetFeedback.kind === 'error' ? 'alert' : 'status'}
            >
              {resetFeedback.message}
            </span>
          )}
        </div>
      </div>

      <nav className="main-nav" aria-label="Main Navigation">
        {NAV_ROUTES.map((route) => (
          <NavLink
            key={route.to}
            to={route.to}
            end={route.end}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            {route.label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
};
