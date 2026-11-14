import React from 'react';
import { SiteStats } from '../../types';

interface LandingFooterProps {
  stats: SiteStats | null;
}

export const LandingFooter: React.FC<LandingFooterProps> = ({ stats }) => {
  const dateStr = stats?.generated_at ? stats.generated_at.split('T')[0] : 'unavailable';

  return (
    <footer className="landing-footer" role="contentinfo" aria-label="Medical Disclaimer and Attribution">
      <div className="footer-pill-notice">
        RESEARCH PROTOTYPE — NOT MEDICAL ADVICE
      </div>

      <p className="footer-disclaimer-text">
        PharmaGraph does not provide medical diagnoses, does not prescribe medications, and does not treat
        any disease or illness. Always consult a licensed physician or pharmacist for clinical decisions.
      </p>

      <div className="footer-timestamp">
        Data snapshot generated on {dateStr}
      </div>
    </footer>
  );
};

export default LandingFooter;
