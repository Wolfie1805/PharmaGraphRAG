import React from 'react';

interface RefusalPanelProps {
  answer: string;
  flags: string[];
}

export const RefusalPanel: React.FC<RefusalPanelProps> = ({ answer, flags }) => {
  const isEmergency =
    answer.toLowerCase().includes('emergency') ||
    answer.toLowerCase().includes('urgent medical care');

  return (
    <section className="refusal-panel" aria-label="Query Refusal Notice">
      <div className="refusal-header">
        <span className="refusal-badge" role="status">
          Query Refused by Safety Guard
        </span>
        <div className="refusal-flags">
          {flags.map((flag) => (
            <span key={flag} className="flag-tag">
              {flag}
            </span>
          ))}
        </div>
      </div>

      {isEmergency && (
        <div className="emergency-alert-banner" role="alert">
          <strong>URGENT MEDICAL NOTICE:</strong> If you or someone you know is experiencing severe symptoms, please contact local emergency services or seek immediate urgent medical care.
        </div>
      )}

      <div className="refusal-message">
        <p>{answer}</p>
      </div>
    </section>
  );
};
