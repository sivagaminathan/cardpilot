import React, { useState } from 'react';
import { DisclaimerBanner } from './components/DisclaimerBanner';
import { Header } from './components/Header';
import { Dashboard } from './components/Dashboard';

export const App: React.FC = () => {
  const [currentProfileId, setCurrentProfileId] = useState<string>('maya');
  const [activeTab, setActiveTab] = useState<string>('dashboard');

  return (
    <div className="app-container">
      <DisclaimerBanner />
      <Header
        currentProfileId={currentProfileId}
        onSelectProfile={setCurrentProfileId}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
      />

      <main className="main-content" id="main-content" tabIndex={-1}>
        {activeTab === 'dashboard' ? (
          <Dashboard profileId={currentProfileId} onNavigateTab={setActiveTab} />
        ) : (
          <section className="section-card placeholder-card">
            <h2 className="section-title">
              {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} View
            </h2>
            <p className="placeholder-text">
              The {activeTab} feature is scheduled for Phase 4 of the CardPilot implementation roadmap.
            </p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setActiveTab('dashboard')}
            >
              Return to Dashboard
            </button>
          </section>
        )}
      </main>

      <footer className="app-footer">
        <p>CardPilot — Deterministic Rewards Optimizer &amp; Benefits Tracker (Demo Application)</p>
        <p className="footer-disclaimer">
          Fictional data only. Not affiliated with any financial institution.
        </p>
      </footer>
    </div>
  );
};
