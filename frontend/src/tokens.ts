/**
 * Design Tokens for PharmaGraph Landing Page
 * Strict matte black aesthetic with soft white illumination.
 */

export const tokens = {
  colors: {
    bg: '#0b0b0c',
    surface: '#131314',
    card: '#1a1a1c',
    cardHover: '#202023',
    text: '#f2f2f2',
    muted: '#9a9aa0',
    border: 'rgba(255, 255, 255, 0.08)',
    borderHover: 'rgba(255, 255, 255, 0.16)',
    highlightInner: 'rgba(255, 255, 255, 0.08)',
    dimTintWarning: 'rgba(245, 158, 11, 0.12)',
    dimTintSuccess: 'rgba(16, 185, 129, 0.12)',
    dimTintDanger: 'rgba(239, 68, 68, 0.12)',
  },
  glows: {
    card: '0 0 0 1px rgba(255, 255, 255, 0.06), 0 0 24px rgba(255, 255, 255, 0.05)',
    cardHover: '0 0 0 1px rgba(255, 255, 255, 0.14), 0 0 32px rgba(255, 255, 255, 0.09)',
    buttonHover: '0 0 0 1px rgba(255, 255, 255, 0.25), 0 0 16px rgba(255, 255, 255, 0.15)',
    focusRing: '0 0 0 2px #0b0b0c, 0 0 0 4px rgba(255, 255, 255, 0.7)',
  },
  typography: {
    fontHeading: 'var(--font-heading)',
    fontBody: 'var(--font-body)',
    fontMono: 'var(--font-mono)',
    cssVars: {
      '--font-heading': "'Sora', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      '--font-body': "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      '--font-mono': "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
    },
  },
  breakpoints: {
    desktop: '1440px',
    tablet: '768px',
    mobile: '400px',
  },
  motion: {
    fpsCap: 30,
    dprCap: 1.5,
    defaultParticles: 80,
  },
} as const;

export default tokens;
