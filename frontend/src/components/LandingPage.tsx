import React, { useEffect, useState } from 'react';
import { SiteStats } from '../types';
import { fetchSiteStats } from '../api';
import '../landing.css';

import { LandingNav } from './landing/LandingNav';
import { HeroSection } from './landing/HeroSection';
import { PlainWordsSection } from './landing/PlainWordsSection';
import { HowItWorksSection } from './landing/HowItWorksSection';
import { DoesNotDoSection } from './landing/DoesNotDoSection';
import { BenefitsSection } from './landing/BenefitsSection';
import { UseCasesSection } from './landing/UseCasesSection';
import { QuestionsSection } from './landing/QuestionsSection';
import { DataSection } from './landing/DataSection';
import { ReliabilitySection } from './landing/ReliabilitySection';
import { SearchHonestySection } from './landing/SearchHonestySection';
import { QualitySection } from './landing/QualitySection';
import { LimitsRoadmapSection } from './landing/LimitsRoadmapSection';
import { LicenseAndFaqSection } from './landing/LicenseAndFaqSection';
import { LandingFooter } from './landing/LandingFooter';

interface LandingPageProps {
  initialStats?: SiteStats | null;
}

export const LandingPage: React.FC<LandingPageProps> = ({ initialStats }) => {
  const [stats, setStats] = useState<SiteStats | null>(initialStats ?? null);
  const [reduceEffects, setReduceEffects] = useState<boolean>(() => {
    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }
    return false;
  });
  const [scrollProgress, setScrollProgress] = useState<number>(0);

  useEffect(() => {
    if (initialStats !== undefined) return;
    let active = true;

    fetchSiteStats()
      .then((data) => {
        if (active) {
          setStats(data);
        }
      })
      .catch(() => {
        if (active) {
          setStats(null);
        }
      });

    return () => {
      active = false;
    };
  }, [initialStats]);

  // Track scroll progress bar
  useEffect(() => {
    const handleScroll = () => {
      const totalScroll = document.documentElement.scrollTop || document.body.scrollTop;
      const windowHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      if (windowHeight > 0) {
        setScrollProgress((totalScroll / windowHeight) * 100);
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (reduceEffects) return;
    const cards = document.querySelectorAll<HTMLElement>('.spotlight-card');
    cards.forEach((card) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      card.style.setProperty('--mouse-x', `${x}px`);
      card.style.setProperty('--mouse-y', `${y}px`);
    });
  };

  return (
    <div
      className={`landing-root ${reduceEffects ? 'reduce-effects' : ''}`}
      onMouseMove={handleMouseMove}
    >
      {/* Scroll Progress Bar */}
      <div
        className="scroll-progress-bar"
        style={{ width: `${scrollProgress}%` }}
        aria-hidden="true"
      />

      {/* Navigation */}
      <LandingNav
        reduceEffects={reduceEffects}
        onToggleEffects={() => setReduceEffects((prev) => !prev)}
      />

      <main id="main-landing">
        {/* Section 1: Hero */}
        <HeroSection reduceEffects={reduceEffects} />

        {/* Section 2: What It Is (Plain Words & Glossary) */}
        <PlainWordsSection />

        {/* Section 3: How It Works (6-Step Animated Flow) */}
        <HowItWorksSection />

        {/* Section 4: What It Does / What It Does NOT Do */}
        <DoesNotDoSection />

        {/* Section 5: Benefits */}
        <BenefitsSection />

        {/* Section 6: Where It Can Be Used */}
        <UseCasesSection />

        {/* Section 7: Questions It Can Answer */}
        <QuestionsSection />

        {/* Section 8: The Data */}
        <DataSection stats={stats} />

        {/* Section 9: Reliability */}
        <ReliabilitySection stats={stats} />

        {/* Section 10: How Search Works, Honestly */}
        <SearchHonestySection stats={stats} />

        {/* Section 11: Measured Quality */}
        <QualitySection stats={stats} />

        {/* Section 12: Known Limits and Roadmap */}
        <LimitsRoadmapSection />

        {/* Section 13: Data & License Note, FAQ, CTA */}
        <LicenseAndFaqSection stats={stats} />
      </main>

      {/* Permanent Research Prototype Notice & Disclaimer Footer */}
      <LandingFooter stats={stats} />
    </div>
  );
};

export default LandingPage;
