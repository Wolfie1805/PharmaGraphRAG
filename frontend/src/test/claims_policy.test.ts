import { describe, it, expect } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';

const LANDING_COMPONENTS_DIR = path.resolve(__dirname, '../components');

// Explicit Allow-List of technical constants (UI dimensions, CSS properties, RGBA channels, algorithm parameters)
// All data numbers and domain statistics (e.g. record counts, entity counts, paper counts) must come from site_stats.json.
const ALLOW_LIST_DIGITS = new Set([
  '100', // Percentage (100%)
  '130', // DNA helix visual amplitude
  '180', // SVG curve coordinate
  '200', // SVG viewBox height / minmax width
  '239', // Red channel in RGB for alert tint (239, 68, 68)
  '255', // White RGB channel (255, 255, 255)
  '256', // Cryptographic algorithm name (SHA-256)
  '300', // Layout breakpoint / card minmax px
  '320', // Card minmax px
  '400', // Screen breakpoint px / card minmax px
  '480', // Canvas helix height px
  '500', // Font weight 500
  '600', // Font weight 600 / canvas fallback px
  '700', // Font weight 700 / SVG coordinate
  '768', // Tablet breakpoint px
  '800', // Canvas fallback px
  '900', // Desktop layout max-width
  '1000', // Milliseconds in 1 second / SVG viewBox width
  '1200', // Container max-width px
  '1440', // Desktop breakpoint px
  '2000', // Standard year / SVG namespace
  '2500', // Particle distance squared (50*50)
  '008', // Angle delta float (0.008)
  '8000', // Local port
  // Hex color codes if matched as digits
  '131314',
  '151314',
  '161214',
  '202023',
]);

const BANNED_PHRASES = [
  'AI-powered',
  'clinically validated',
  'guaranteed',
  'accurate answers',
  'clinical-grade',
  'FDA-approved',
  'peer-reviewed',
  'knowledge graph',
  'intelligence engine',
  'official clinical',
  'passing',
  'continuous integration',
];

const ALLOWED_MEDICAL_TERM_COMPONENTS = new Set([
  'DoesNotDoSection.tsx',
  'LicenseAndFaqSection.tsx',
  'LandingFooter.tsx',
]);

function getLandingComponentFiles(): { filePath: string; fileName: string; content: string }[] {
  const result: { filePath: string; fileName: string; content: string }[] = [];

  function traverse(dir: string) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === 'landing') {
          traverse(fullPath);
        }
      } else if (entry.isFile() && (entry.name.endsWith('.tsx') || entry.name.endsWith('.ts'))) {
        if (
          dir.endsWith('landing') ||
          entry.name === 'LandingPage.tsx' ||
          entry.name === 'HeroCanvas.tsx'
        ) {
          result.push({
            filePath: fullPath,
            fileName: entry.name,
            content: fs.readFileSync(fullPath, 'utf-8'),
          });
        }
      }
    }
  }

  traverse(LANDING_COMPONENTS_DIR);
  return result;
}

describe('Landing Page Claims Policy Verification', () => {
  const files = getLandingComponentFiles();

  it('scans all landing components and finds component files', () => {
    expect(files.length).toBeGreaterThanOrEqual(10);
  });

  it('prohibits all banned phrases across every landing component file', () => {
    for (const file of files) {
      for (const phrase of BANNED_PHRASES) {
        const regex = new RegExp(phrase, 'i');
        const match = file.content.match(regex);
        expect(
          match,
          `Banned phrase "${phrase}" found in ${file.fileName}`
        ).toBeNull();
      }
    }
  });

  it('enforces that no 3+ digit number is hardcoded outside the allow-list', () => {
    const violations: { file: string; digit: string }[] = [];

    for (const file of files) {
      // Find all digit sequences of 3 or more digits
      const matches = file.content.match(/\b\d{3,}\b/g) || [];
      for (const m of matches) {
        if (!ALLOW_LIST_DIGITS.has(m)) {
          violations.push({ file: file.fileName, digit: m });
        }
      }
    }

    expect(
      violations,
      `Hardcoded 3+ digit numbers found outside allow-list: ${JSON.stringify(violations)}`
    ).toEqual([]);
  });

  it('enforces that medical terms (diagnose, prescribe, treat) appear ONLY in allowed components', () => {
    const medicalTermsRegex = /\b(diagnose[ds]?|diagnosing|diagnoses|prescribe[ds]?|prescribing|prescriptions?|treat[s]?|treated|treating|treatments?)\b/gi;

    for (const file of files) {
      if (!ALLOWED_MEDICAL_TERM_COMPONENTS.has(file.fileName)) {
        const matches = file.content.match(medicalTermsRegex);
        expect(
          matches,
          `Restricted medical term found in non-allowed component ${file.fileName}: ${matches?.join(', ')}`
        ).toBeNull();
      }
    }
  });

  it('enforces that medical terms in allowed components appear strictly inside negations', () => {
    const negationKeywords = ['not', 'never', 'no', 'cannot', 'neither', 'nor', 'without'];
    const medicalTermsRegex = /\b(diagnose[ds]?|diagnosing|diagnoses|prescribe[ds]?|prescribing|prescriptions?|treat[s]?|treated|treating|treatments?)\b/gi;

    for (const file of files) {
      if (ALLOWED_MEDICAL_TERM_COMPONENTS.has(file.fileName)) {
        // Split content by sentences or lines
        const lines = file.content.split('\n');
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          if (medicalTermsRegex.test(line)) {
            // Reset regex
            medicalTermsRegex.lastIndex = 0;
            const hasNegation = negationKeywords.some((neg) =>
              new RegExp(`\\b${neg}\\b`, 'i').test(line)
            );
            expect(
              hasNegation,
              `Medical term in ${file.fileName}:${i + 1} must be in a negation: "${line.trim()}"`
            ).toBe(true);
          }
        }
      }
    }
  });
});
