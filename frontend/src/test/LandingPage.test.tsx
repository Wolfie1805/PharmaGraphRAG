import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { LandingPage } from '../components/LandingPage';
import { Root } from '../Root';
import { SiteStats } from '../types';
import siteStatsFixture from '../../public/site_stats.json';

const fullFixture = siteStatsFixture as unknown as SiteStats;

describe('LandingPage Component Suite', () => {
  it('renders all 13 sections with fixture stats', () => {
    const { container } = render(<LandingPage initialStats={fullFixture} />);

    // Section 1: Hero
    expect(screen.getByRole('heading', { level: 1, name: /EVIDENCE FOR HOW GENES SHAPE MEDICINE/i })).toBeInTheDocument();
    expect(screen.getByText('Genes')).toBeInTheDocument();
    expect(screen.getByText('Medicines')).toBeInTheDocument();
    expect(screen.getByText('Evidence')).toBeInTheDocument();

    // Section 2: What It Is (Plain Words)
    expect(screen.getByRole('heading', { level: 2, name: /WHAT IT IS, IN PLAIN WORDS/i })).toBeInTheDocument();
    expect(screen.getByText(/A medicine is the key/i)).toBeInTheDocument();
    expect(screen.getByText(/A gene is the instruction/i)).toBeInTheDocument();

    // Section 3: How It Works
    expect(screen.getByRole('heading', { level: 2, name: /HOW IT WORKS/i })).toBeInTheDocument();
    expect(screen.getAllByText(/Collect official data/i).length).toBeGreaterThanOrEqual(1);

    // Section 4: Does / Does NOT Do
    expect(screen.getByRole('heading', { level: 2, name: /WHAT IT DOES \/ WHAT IT DOES NOT DO/i })).toBeInTheDocument();
    expect(screen.getAllByText(/WHAT IT DOES NOT DO/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Does not diagnose/i).length).toBeGreaterThanOrEqual(1);

    // Section 5: Benefits
    expect(screen.getByRole('heading', { level: 2, name: /KEY SYSTEM BENEFITS/i })).toBeInTheDocument();
    expect(screen.getByText(/Traceable to a source/i)).toBeInTheDocument();
    expect(screen.getByText(/Nothing made up/i)).toBeInTheDocument();

    // Section 6: Where It Can Be Used
    expect(screen.getByRole('heading', { level: 2, name: /WHERE IT CAN BE USED/i })).toBeInTheDocument();
    expect(screen.getByText(/Research Literature Scouting/i)).toBeInTheDocument();
    expect(screen.getByText(/NOT FOR CLINICAL OR PERSONAL MEDICAL USE/i)).toBeInTheDocument();

    // Section 7: Questions It Can Answer
    expect(screen.getByRole('heading', { level: 2, name: /QUESTIONS IT CAN ANSWER/i })).toBeInTheDocument();
    expect(screen.getByText(/"What is the relationship between CYP2C19 and clopidogrel\?"/i)).toBeInTheDocument();
    expect(screen.getByText(/"warfarin VKORC1"/i)).toBeInTheDocument();
    expect(screen.getByText(/"Does SLCO1B1 matter for simvastatin\?"/i)).toBeInTheDocument();

    // Section 8: The Data
    expect(screen.getByRole('heading', { level: 2, name: /THE DATA/i })).toBeInTheDocument();
    expect(screen.getByText('22,503')).toBeInTheDocument();
    expect(screen.getByText('3,096')).toBeInTheDocument();
    expect(screen.getByText('246,714')).toBeInTheDocument();

    // Section 9: Reliability
    expect(screen.getByRole('heading', { level: 2, name: /RELIABILITY & PROVENANCE/i })).toBeInTheDocument();
    expect(screen.getByText(/101 automated tests are defined in the repository/i)).toBeInTheDocument();
    expect(screen.getByText(/19 automated tests are defined in the repository/i)).toBeInTheDocument();

    // Section 10: Search Honesty
    expect(screen.getByRole('heading', { level: 2, name: /HOW SEARCH WORKS, HONESTLY/i })).toBeInTheDocument();
    expect(screen.getAllByText(/Covered by keyword and graph search only/i).length).toBeGreaterThanOrEqual(1);

    // Section 11: Measured Quality
    expect(screen.getByRole('heading', { level: 2, name: /MEASURED QUALITY/i })).toBeInTheDocument();
    expect(screen.getByText('Pipeline diagnostic, not a quality score, not human-verified')).toBeInTheDocument();
    expect(screen.getByText('6/6')).toBeInTheDocument();
    expect(screen.getByText('2/2')).toBeInTheDocument();
    expect(container.textContent).not.toContain('0.8571');

    // Section 12: Limits & Roadmap
    expect(screen.getByRole('heading', { level: 2, name: /KNOWN LIMITS & ROADMAP/i })).toBeInTheDocument();
    expect(screen.getByText(/Brand names not recognized/i)).toBeInTheDocument();

    // Section 13: License & FAQ & Footer
    expect(screen.getByRole('heading', { level: 2, name: /DATA LICENSING & FAQ/i })).toBeInTheDocument();
    expect(screen.getAllByText(/Discrepancy unresolved between site footer and bundled license/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/RESEARCH PROTOTYPE — NOT MEDICAL ADVICE/i)).toBeInTheDocument();
    expect(screen.getByText(/Data snapshot generated on 2026-11-14/i)).toBeInTheDocument();

    // Confirm no git commit or dirty status leaked into the rendered view
    if (fullFixture.git?.commit) {
      expect(container.textContent).not.toContain(fullFixture.git.commit);
    }
  });

  it('renders "Stats unavailable" when stats fetch fails (stats is null)', () => {
    render(<LandingPage initialStats={null} />);
    expect(screen.getByText('Stats unavailable')).toBeInTheDocument();
  });

  it('gracefully handles missing and null fields in stats', () => {
    const sparseStats: SiteStats = {
      generated_at: '2026-11-14T00:00:00Z',
      git: { commit: 'abcdef', latest_tag: 'v1.0', dirty: false },
      raw_files: {
        clinpgx: { source_name: 'ClinPGx', count: 1, bytes: 100, release_label: 'test' },
        pubmed: { source_name: 'PubMed', count: 1, bytes: 100, release_label: 'test' },
      },
      processed_tables: {
        entities: 0,
        synonyms: 0,
        cross_references: 0,
        relationships: 0,
        publications: 0,
        chunks: 0,
      },
      entities_by_type: {
        chemical: 0,
        cnv: 0,
        gene: 0,
        haplotype: 0,
        phenotype: 0,
        snv: 0,
        variant: 0,
      },
      relationships: { total: 0, dangling: 0 },
      chunks_by_source_type: {},
      papers: { count: 0, year_min: 0, year_max: 0, year_range: 'none', with_abstracts: 0 },
      retrieval: {
        path_names: [],
        embedding_model: 'test',
        meaning_coverage: {},
        default_answer_mode: 'extractive',
      },
      sources: [],
      tests: { pytest_collected: 0, vitest_collected: 0 },
      benchmark: null,
    };

    render(<LandingPage initialStats={sparseStats} />);
    expect(screen.getByText('Benchmark results pending')).toBeInTheDocument();
  });

  it('renders license_notes verbatim quotes exactly as written', () => {
    render(<LandingPage initialStats={fullFixture} />);
    // Check ClinPGx license note quotes
    expect(
      screen.getAllByText(
        /"Creative Commons Attribution-ShareAlike 4.0 International \(CC BY-SA 4.0\)"/i
      ).length
    ).toBeGreaterThanOrEqual(1);

    // Check PubMed license note quotes
    expect(
      screen.getByText(
        /"NLM does not claim copyright on PubMed bibliographic records; individual journal publishers and authors typically hold copyright on abstracts."/i
      )
    ).toBeInTheDocument();
  });

  it('renders planted markup strings as literal plain text without DOM injection', () => {
    const plantedStats: SiteStats = {
      ...fullFixture,
      sources: [
        {
          name: 'Planted Source',
          description: '<script id="planted-script">alert("xss")</script><b>Bold Injected</b>',
          date_checked: '2026-11-14',
          license_notes: [
            {
              quote: '<img src="fake.png" onerror="alert(1)" />',
              location: 'docs/licenses.md#L99',
            },
          ],
        },
      ],
    };

    const { container } = render(<LandingPage initialStats={plantedStats} />);
    // Verify script or img tag was NOT created in DOM
    expect(container.querySelector('#planted-script')).toBeNull();
    expect(container.querySelector('img[src="fake.png"]')).toBeNull();

    // Verify it is displayed literally as plain text
    expect(container.textContent).toContain('<script id="planted-script">');
    expect(container.textContent).toContain('<img src="fake.png"');
  });

  it('toggles reduced effects mode when toggle button is clicked', () => {
    const { container } = render(<LandingPage initialStats={fullFixture} />);
    const toggleBtn = screen.getByRole('button', { name: /toggle visual animation effects/i });

    expect(container.querySelector('.landing-root')).not.toHaveClass('reduce-effects');
    fireEvent.click(toggleBtn);
    expect(container.querySelector('.landing-root')).toHaveClass('reduce-effects');
    expect(toggleBtn).toHaveTextContent(/Effects: Reduced/i);

    fireEvent.click(toggleBtn);
    expect(container.querySelector('.landing-root')).not.toHaveClass('reduce-effects');
    expect(toggleBtn).toHaveTextContent(/Reduce effects/i);
  });
  it('verifies exact wording policies for D5 polish', () => {
    render(<LandingPage initialStats={fullFixture} />);

    // Hero subtitle exact wording
    expect(
      screen.getByText(
        'A pharmacogenomics evidence search tool. Explore what published sources and curated annotations record about how genetic variants relate to drug response, with every result linked to its source.'
      )
    ).toBeInTheDocument();

    // How it works section subtitle exact wording
    expect(
      screen.getByText(
        'A repeatable six-step pipeline from official downloads to quoted evidence with sources.'
      )
    ).toBeInTheDocument();

    // How it works step 1 exact wording
    expect(
      screen.getAllByText(
        'Collects curated ClinPGx files (annotations, drug label annotations and guideline annotations), CPIC allele definitions and PubMed abstracts.'
      ).length
    ).toBeGreaterThanOrEqual(1);

    // Reliability card exact relabeling
    expect(
      screen.getByRole('heading', {
        level: 3,
        name: 'Original files are stored with SHA-256 fingerprints in manifests',
      })
    ).toBeInTheDocument();
  });

  it('supports arrow key navigation across How It Works tablist', () => {
    render(<LandingPage initialStats={fullFixture} />);
    const tablist = screen.getByRole('tablist', { name: /Pipeline Steps/i });
    const tab1 = screen.getByRole('tab', { name: /1 Collect official data/i });
    const tab2 = screen.getByRole('tab', { name: /2 Keep originals untouched/i });

    expect(tab1).toHaveAttribute('aria-selected', 'true');
    expect(tab2).toHaveAttribute('aria-selected', 'false');

    // ArrowRight switches to tab 2
    fireEvent.keyDown(tablist, { key: 'ArrowRight' });
    expect(tab2).toHaveAttribute('aria-selected', 'true');
    expect(tab1).toHaveAttribute('aria-selected', 'false');

    // ArrowLeft switches back to tab 1
    fireEvent.keyDown(tablist, { key: 'ArrowLeft' });
    expect(tab1).toHaveAttribute('aria-selected', 'true');

    // End key switches to tab 6
    fireEvent.keyDown(tablist, { key: 'End' });
    const tab6 = screen.getByRole('tab', { name: /6 Show quoted evidence with sources/i });
    expect(tab6).toHaveAttribute('aria-selected', 'true');

    // Home key switches back to tab 1
    fireEvent.keyDown(tablist, { key: 'Home' });
    expect(tab1).toHaveAttribute('aria-selected', 'true');
  });

  it('disables questions carousel prev/next buttons at the ends', () => {
    render(<LandingPage initialStats={fullFixture} />);
    const prevBtn = screen.getByRole('button', { name: /Previous question/i });
    const nextBtn = screen.getByRole('button', { name: /Next question/i });

    // At index 0, prev is disabled, next is enabled
    expect(prevBtn).toBeDisabled();
    expect(nextBtn).not.toBeDisabled();

    // Click next
    fireEvent.click(nextBtn);
    expect(prevBtn).not.toBeDisabled();

    // Click next again to reach last slide
    fireEvent.click(nextBtn);
    expect(nextBtn).toBeDisabled();
    expect(prevBtn).not.toBeDisabled();
  });

  it('verifies back-to-top is hidden then visible upon scrolling past hero', () => {
    render(<LandingPage initialStats={fullFixture} />);
    // Initially when scrolled to top, back-to-top button is not in accessibility tree
    expect(screen.queryByRole('button', { name: /Back to top/i })).toBeNull();

    // Mock scrolling past the hero (scrollY > 500 or boundingClientRect bottom <= 64)
    const hero = document.getElementById('hero');
    if (hero) {
      vi.spyOn(hero, 'getBoundingClientRect').mockReturnValue({
        bottom: 0,
        top: -900,
        left: 0,
        right: 1440,
        width: 1440,
        height: 900,
        x: 0,
        y: -900,
        toJSON: () => {},
      });
    }

    fireEvent.scroll(window);

    // Now back to top should be visible and in tab order
    const backToTop = screen.getByRole('button', { name: /Back to top/i });
    expect(backToTop).toBeInTheDocument();
  });

  it('keeps location.hash unchanged after clicking a navigation link', () => {
    window.location.hash = '#/';
    render(<LandingPage initialStats={fullFixture} />);

    const nav = screen.getByRole('navigation', { name: /Primary Navigation/i });
    const howItWorksBtn = within(nav).getByRole('button', { name: /^How It Works$/i });
    fireEvent.click(howItWorksBtn);

    // Hash must remain exactly '#/' without jumping to '#how-it-works'
    expect(window.location.hash).toBe('#/');
  });

  it('implements accessible Menu button disclosure pattern with Escape key return focus', () => {
    render(<LandingPage initialStats={fullFixture} />);
    const menuBtn = screen.getByRole('button', { name: /Open navigation menu/i });
    expect(menuBtn).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('region', { name: /Mobile Navigation Menu/i })).toBeNull();

    // Open disclosure
    fireEvent.click(menuBtn);
    expect(menuBtn).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('region', { name: /Mobile Navigation Menu/i })).toBeInTheDocument();

    // Press Escape to close and verify focus returns to menu button
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(menuBtn).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('region', { name: /Mobile Navigation Menu/i })).toBeNull();
    expect(document.activeElement).toBe(menuBtn);
  });
});

describe('Root Hash Routing Switch', () => {
  it('renders LandingPage for hash "#/"', () => {
    render(<Root initialHash="#/" />);
    expect(screen.getByRole('heading', { level: 1, name: /EVIDENCE FOR HOW GENES SHAPE MEDICINE/i })).toBeInTheDocument();
  });

  it('renders App for hash "#/app"', () => {
    render(<Root initialHash="#/app" />);
    expect(screen.getByLabelText(/Enter Gene-Drug Pharmacogenomic Question/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Back to Overview/i })).toBeInTheDocument();
  });

  it('prefills question without auto-submitting for hash "#/app?q=<text>"', () => {
    const testQuery = 'What is the relationship between CYP2C19 and clopidogrel?';
    render(<Root initialHash={`#/app?q=${encodeURIComponent(testQuery)}`} />);

    const input = screen.getByLabelText(/Enter Gene-Drug Pharmacogenomic Question/i) as HTMLInputElement;
    expect(input.value).toBe(testQuery);

    // Verify it was NOT auto-submitted: no response panel or error shown
    expect(screen.queryByText(/Direct Biological Answers/i)).toBeNull();
    expect(screen.queryByText(/Clinical Guard Refusal/i)).toBeNull();
  });
});
