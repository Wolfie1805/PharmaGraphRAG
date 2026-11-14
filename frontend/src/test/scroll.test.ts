import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { scrollToSection, cancelScrollAnimation } from '../utils/scroll';

describe('scrollToSection Smooth Scroll Helper', () => {
  let targetSection: HTMLElement;
  let targetHeading: HTMLElement;

  beforeEach(() => {
    document.body.innerHTML = '';
    window.location.hash = '#/';

    targetSection = document.createElement('section');
    targetSection.id = 'test-section';
    targetHeading = document.createElement('h2');
    targetHeading.textContent = 'Test Section Heading';
    targetSection.appendChild(targetHeading);
    document.body.appendChild(targetSection);

    // Mock bounding rects
    vi.spyOn(targetSection, 'getBoundingClientRect').mockReturnValue({
      top: 500,
      bottom: 800,
      left: 0,
      right: 1000,
      width: 1000,
      height: 300,
      x: 0,
      y: 500,
      toJSON: () => {},
    });

    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  });

  afterEach(() => {
    cancelScrollAnimation();
    vi.restoreAllMocks();
  });

  it('does NOT mutate window.location.hash', () => {
    window.location.hash = '#/';
    scrollToSection('test-section', { reduceEffects: true });
    expect(window.location.hash).toBe('#/');
  });

  it('jumps instantly without animation when reduceEffects is true', () => {
    const scrollToSpy = vi.spyOn(window, 'scrollTo');
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame');

    scrollToSection('test-section', { reduceEffects: true, navHeight: 64 });

    expect(scrollToSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        top: Math.max(0, 500 - (64 + 16)),
        behavior: 'instant',
      })
    );
    expect(rafSpy).not.toHaveBeenCalled();
  });

  it('jumps instantly when prefers-reduced-motion matches', () => {
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: query === '(prefers-reduced-motion: reduce)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    const scrollToSpy = vi.spyOn(window, 'scrollTo');
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame');

    scrollToSection('test-section', { navHeight: 64 });

    expect(scrollToSpy).toHaveBeenCalled();
    expect(rafSpy).not.toHaveBeenCalled();

    window.matchMedia = originalMatchMedia;
  });

  it('focuses the section heading with tabindex="-1" upon arrival', () => {
    scrollToSection('test-section', { reduceEffects: true });

    expect(targetHeading.getAttribute('tabindex')).toBe('-1');
    expect(document.activeElement).toBe(targetHeading);
  });

  it('cancels the animation on user wheel event', () => {
    vi.spyOn(window, 'matchMedia').mockReturnValue({
      matches: false,
      media: '',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    });

    let rafCallback: FrameRequestCallback | null = null;
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      rafCallback = cb;
      return 123;
    });
    const cancelRafSpy = vi.spyOn(window, 'cancelAnimationFrame');

    scrollToSection('test-section', { reduceEffects: false });
    expect(rafCallback).toBeDefined();

    // Trigger wheel event to interrupt animation
    window.dispatchEvent(new Event('wheel'));

    expect(cancelRafSpy).toHaveBeenCalledWith(123);
  });
});
