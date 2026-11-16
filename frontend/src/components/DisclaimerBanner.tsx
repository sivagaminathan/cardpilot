import React from 'react';

export const DisclaimerBanner: React.FC = () => {
  return (
    <aside className="disclaimer-banner" role="complementary" aria-label="Demo Disclaimer">
      <div className="disclaimer-content">
        <span className="disclaimer-badge">DEMO DATA ONLY</span>
        <p className="disclaimer-text">
          All card issuers, reward programs, rules, and user profiles in CardPilot are completely
          fictional. This application is an educational demo and does not represent actual credit card terms or provide financial advice. Never input real card credentials.
        </p>
      </div>
    </aside>
  );
};
