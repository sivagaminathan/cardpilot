import React from 'react';
import { DEMO_PROFILES } from '../types/profile';
import { BackendStatus } from './BackendStatus';

interface HeaderProps {
  currentProfileId: string;
  onSelectProfile: (profileId: string) => void;
  activeTab: string;
  onSelectTab: (tab: string) => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentProfileId,
  onSelectProfile,
  activeTab,
  onSelectTab,
}) => {
  const currentProfile = DEMO_PROFILES.find((p) => p.id === currentProfileId) ?? DEMO_PROFILES[0];

  return (
    <header className="app-header">
      <div className="header-top">
        <div className="brand">
          <span className="brand-icon" aria-hidden="true">💳</span>
          <h1 className="brand-title">CardPilot</h1>
          <span className="version-tag">v0.1.0</span>
          <BackendStatus />
        </div>

        <div className="profile-selector-container">
          <label htmlFor="profile-select" className="profile-label">
            Demo Profile:
          </label>
          <select
            id="profile-select"
            className="profile-select"
            value={currentProfileId}
            onChange={(e) => onSelectProfile(e.target.value)}
            aria-label="Select demo profile"
          >
            {DEMO_PROFILES.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name} — {profile.role}
              </option>
            ))}
          </select>
        </div>
      </div>

      <nav className="main-nav" aria-label="Main Navigation">
        <button
          type="button"
          className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => onSelectTab('dashboard')}
          aria-current={activeTab === 'dashboard' ? 'page' : undefined}
        >
          Dashboard
        </button>
        <button
          type="button"
          className={`nav-item ${activeTab === 'cards' ? 'active' : ''}`}
          onClick={() => onSelectTab('cards')}
          aria-current={activeTab === 'cards' ? 'page' : undefined}
        >
          Cards
        </button>
        <button
          type="button"
          className={`nav-item ${activeTab === 'compare' ? 'active' : ''}`}
          onClick={() => onSelectTab('compare')}
          aria-current={activeTab === 'compare' ? 'page' : undefined}
        >
          Compare
        </button>
        <button
          type="button"
          className={`nav-item ${activeTab === 'transactions' ? 'active' : ''}`}
          onClick={() => onSelectTab('transactions')}
          aria-current={activeTab === 'transactions' ? 'page' : undefined}
        >
          Transactions
        </button>
        <button
          type="button"
          className={`nav-item ${activeTab === 'benefits' ? 'active' : ''}`}
          onClick={() => onSelectTab('benefits')}
          aria-current={activeTab === 'benefits' ? 'page' : undefined}
        >
          Benefits
        </button>
        <button
          type="button"
          className={`nav-item ${activeTab === 'rewards' ? 'active' : ''}`}
          onClick={() => onSelectTab('rewards')}
          aria-current={activeTab === 'rewards' ? 'page' : undefined}
        >
          Rewards
        </button>
        <button
          type="button"
          className={`nav-item ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => onSelectTab('settings')}
          aria-current={activeTab === 'settings' ? 'page' : undefined}
        >
          Settings
        </button>
      </nav>

      <div className="profile-banner">
        <div className="profile-info">
          <strong>Active Profile: {currentProfile.name}</strong> ({currentProfile.role}) — {currentProfile.description}
        </div>
      </div>
    </header>
  );
};
