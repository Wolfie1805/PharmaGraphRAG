import React from 'react';
import { HeroCanvas } from '../HeroCanvas';
import { scrollToSection } from '../../utils/scroll';

interface HeroSectionProps {
  reduceEffects: boolean;
}

export const HeroSection: React.FC<HeroSectionProps> = ({ reduceEffects }) => {
  return (
    <section id="hero" className="hero-section" aria-labelledby="hero-heading">
      <HeroCanvas reduceEffects={reduceEffects} />
      <div className="hero-scrim" aria-hidden="true" />

      <div className="hero-content">
        <div className="hero-pill-tags" role="list" aria-label="Core entities">
          <span className="hero-pill" role="listitem">Genes</span>
          <span className="hero-pill" role="listitem">Medicines</span>
          <span className="hero-pill" role="listitem">Evidence</span>
        </div>

        <h1 id="hero-heading" className="hero-title">
          EVIDENCE FOR HOW GENES SHAPE MEDICINE
        </h1>

        <p className="hero-subtitle">
          A pharmacogenomics evidence search tool. Explore what published sources and curated annotations record about how genetic variants relate to drug response, with every result linked to its source.
        </p>

        <div className="hero-actions">
          <a href="#/app" className="btn-primary">
            Try the search
          </a>
          <button
            type="button"
            onClick={() => scrollToSection('how-it-works', { reduceEffects })}
            className="btn-secondary"
          >
            How it works
          </button>
        </div>
      </div>

      {/* Animated subtle scroll cue */}
      <button
        type="button"
        onClick={() => scrollToSection('what-it-is', { reduceEffects })}
        className="hero-scroll-cue"
        aria-label="Scroll to explore"
      >
        <span>Scroll to explore</span>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
    </section>
  );
};

export default HeroSection;
