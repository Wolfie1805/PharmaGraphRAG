import React, { useEffect, useRef, useState } from 'react';
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
  const [isMenuOpen, setIsMenuOpen] = useState<boolean>(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

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

  // Back to top appears only after user scrolls past hero section
  useEffect(() => {
    const handleScroll = () => {
      const hero = document.getElementById('hero');
      const scrollY = window.scrollY || window.pageYOffset || 0;
      if (hero) {
        const rect = hero.getBoundingClientRect();
        // Scrolled past hero: top is negative (or scrollY past hero) and bottom is above nav height
        const hasScrolledPast = rect.bottom <= 64 && (rect.top < 0 || scrollY > 200);
        setShowBackToTop(hasScrolledPast);
      } else {
        setShowBackToTop(scrollY > 500);
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Keyboard accessibility: Escape key closes menu and returns focus
  useEffect(() => {
    if (!isMenuOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        setIsMenuOpen(false);
        menuButtonRef.current?.focus();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isMenuOpen]);

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

        {/* Desktop nav links */}
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

        {/* Desktop actions */}
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

        {/* Mobile menu button (compact bar at 400px) */}
        <button
          ref={menuButtonRef}
          type="button"
          className="nav-menu-btn"
          aria-expanded={isMenuOpen}
          aria-controls="landing-mobile-menu"
          aria-label={isMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
          onClick={() => setIsMenuOpen((prev) => !prev)}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            {isMenuOpen ? (
              <path d="M18 6L6 18M6 6l12 12" />
            ) : (
              <path d="M3 12h18M3 6h18M3 18h18" />
            )}
          </svg>
          <span>Menu</span>
        </button>
      </header>

      {/* Accessible mobile disclosure drawer */}
      {isMenuOpen && (
        <div
          id="landing-mobile-menu"
          className="mobile-nav-drawer"
          role="region"
          aria-label="Mobile Navigation Menu"
        >
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                setIsMenuOpen(false);
                menuButtonRef.current?.focus();
                scrollToSection(item.id, { reduceEffects });
              }}
              className={`nav-link-btn mobile ${activeSection === item.id ? 'active' : ''}`}
              aria-current={activeSection === item.id ? 'true' : undefined}
            >
              {item.label}
            </button>
          ))}
          <div className="mobile-nav-footer">
            <button
              type="button"
              onClick={() => {
                onToggleEffects();
              }}
              className={`btn-toggle-effects ${reduceEffects ? 'active' : ''}`}
              aria-pressed={reduceEffects}
              aria-label="Toggle visual animation effects"
            >
              {reduceEffects ? 'Effects: Reduced' : 'Reduce effects'}
            </button>
            <a href="#/app" className="btn-open-app" onClick={() => setIsMenuOpen(false)}>
              Open the app
              <span aria-hidden="true">→</span>
            </a>
          </div>
        </div>
      )}

      {/* Back to top button: strictly omitted from tab order and accessibility tree while hidden */}
      {showBackToTop && (
        <button
          type="button"
          className="back-to-top-btn visible"
          onClick={() => scrollToSection('hero', { reduceEffects })}
          aria-label="Back to top"
        >
          ↑ Back to top
        </button>
      )}
    </>
  );
};

export default LandingNav;
