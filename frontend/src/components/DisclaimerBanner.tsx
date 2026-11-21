import React from 'react';

export const DisclaimerBanner: React.FC = () => {
  return (
    <aside className="disclaimer-banner" role="complementary" aria-label="Demo Disclaimer">
      <div className="disclaimer-content">
        <span className="disclaimer-badge">DEMO DATA ONLY</span>
        <p className="disclaimer-text">
          Sample data only. Not issuer terms. Not financial advice. All card issuers, reward
          programs, rules, and user profiles in CardPilot are fictional. Never input real card
          credentials.
        </p>
      </div>
    </aside>
  );
};
