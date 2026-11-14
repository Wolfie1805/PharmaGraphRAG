import React, { useEffect, useState } from 'react';
import { scrollToSection } from '../../utils/scroll';

interface LandingNavProps {
  reduceEffects: boolean;
  onToggleEffects: () => void;
}

const NAV_ITEMS = [
  { id: 'how-it-works', label: 'How It Works' },
  { id: 'the-data', label: 'The Data' },
  { id: 'search-architecture', label: 'How search works' },
  { id: 'faq', label: 'FAQ' },
] as const;

export const LandingNav: React.FC<LandingNavProps> = ({
  reduceEffects,
  onToggleEffects,
}) => {
  const [activeSection, setActiveSection] = useState<string>('');
  const [showBackToTop, setShowBackToTop] = useState<boolean>(false);

  useEffect(() => {
    // Track active section via IntersectionObserver
    if (typeof IntersectionObserver !== 'undefined') {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              setActiveSection(entry.target.id);
            }
          });
        },
        { rootMargin: '-70px 0px -40% 0px', threshold: 0.1 }
      );

      NAV_ITEMS.forEach((item) => {
        const el = document.getElementById(item.id);
        if (el) observer.observe(el);
      });

      return () => observer.disconnect();
    }
  }, []);

  useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY || window.pageYOffset || 0;
      setShowBackToTop(scrollY > 400);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <>
      <header className="landing-nav" role="banner">
        <button
          type="button"
          onClick={() => scrollToSection('main-landing', { reduceEffects })}
          className="skip-link"
        >
          Skip to main content
        </button>

        <a href="#/" className="nav-brand" aria-label="PharmaGraph Home">
          <svg
            className="brand-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M10 2v7.31M14 9.3V1.99M8.5 2h7M14 9.3a6.5 6.5 0 1 1-4 0" />
            <circle cx="12" cy="14" r="2" />
          </svg>
          <span className="brand-name">PharmaGraph</span>
        </a>

        <nav className="nav-links" aria-label="Primary Navigation">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => scrollToSection(item.id, { reduceEffects })}
              className={`nav-link-btn ${activeSection === item.id ? 'active' : ''}`}
              aria-current={activeSection === item.id ? 'true' : undefined}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="nav-actions">
          <button
            type="button"
            onClick={onToggleEffects}
            className={`btn-toggle-effects ${reduceEffects ? 'active' : ''}`}
            aria-pressed={reduceEffects}
            aria-label="Toggle visual animation effects"
          >
            {reduceEffects ? 'Effects: Reduced' : 'Reduce effects'}
          </button>

          <a href="#/app" className="btn-open-app">
            Open the app
            <span aria-hidden="true">→</span>
          </a>
        </div>
      </header>

      {/* Back to top button */}
      <button
        type="button"
        className={`back-to-top-btn ${showBackToTop ? 'visible' : ''}`}
        onClick={() => scrollToSection('hero', { reduceEffects })}
        aria-label="Back to top"
      >
        ↑ Back to top
      </button>
    </>
  );
};

export default LandingNav;
