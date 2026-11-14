/**
 * Smooth scroll helper using requestAnimationFrame with easeInOutCubic.
 * Clamped duration: 500ms to 1100ms based on distance.
 * Target offset: sticky nav height + 16px.
 * Cancels on 'wheel', 'touchstart', or 'keydown'.
 * Instant jump if prefers-reduced-motion or reduceEffects is active.
 * Focuses section heading with tabindex="-1" and preventScroll: true upon arrival.
 */

let activeAnimationId: number | null = null;
let activeCleanup: (() => void) | null = null;

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

export interface ScrollOptions {
  reduceEffects?: boolean;
  navHeight?: number;
  onArrival?: () => void;
}

export function cancelScrollAnimation(): void {
  if (activeCleanup) {
    activeCleanup();
  }
}

export function scrollToSection(id: string, options?: ScrollOptions): void {
  cancelScrollAnimation();

  const target = document.getElementById(id);
  if (!target) return;

  const nav = typeof document !== 'undefined' ? document.querySelector('.landing-nav') : null;
  const navHeight = options?.navHeight ?? (nav ? nav.getBoundingClientRect().height : 64);
  const targetOffset = navHeight + 16;

  const startY = typeof window !== 'undefined' ? window.scrollY || window.pageYOffset || 0 : 0;
  const rect = target.getBoundingClientRect();
  const targetY = Math.max(0, rect.top + startY - targetOffset);
  const distance = Math.abs(targetY - startY);

  const prefersReduced =
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const isReduceEffects =
    options?.reduceEffects ||
    (typeof document !== 'undefined' &&
      (document.documentElement.classList.contains('reduce-effects') ||
        document.body.classList.contains('reduce-effects')));

  const finishScroll = () => {
    const heading = target.querySelector<HTMLElement>(
      'h1, h2, h3, [data-section-heading]'
    );
    if (heading) {
      heading.setAttribute('tabindex', '-1');
      heading.focus({ preventScroll: true });
    }
    options?.onArrival?.();
  };

  if (prefersReduced || isReduceEffects || distance < 2) {
    if (typeof window !== 'undefined') {
      window.scrollTo({ top: targetY, behavior: 'instant' as ScrollBehavior });
    }
    finishScroll();
    return;
  }

  // Duration scaled by distance: clamped between 500ms and 1100ms
  const duration = Math.min(1100, Math.max(500, Math.round(distance * 0.55)));

  let startTime: number | null = null;
  let isCancelled = false;

  const cancelEvents = ['wheel', 'touchstart', 'keydown'] as const;
  const handleCancel = () => {
    isCancelled = true;
    cleanup();
  };

  const cleanup = () => {
    if (activeAnimationId !== null) {
      cancelAnimationFrame(activeAnimationId);
      activeAnimationId = null;
    }
    cancelEvents.forEach((evt) => {
      window.removeEventListener(evt, handleCancel, { capture: true } as EventListenerOptions);
    });
    activeCleanup = null;
  };

  activeCleanup = cleanup;
  cancelEvents.forEach((evt) => {
    window.addEventListener(evt, handleCancel, { capture: true, passive: true });
  });

  const step = (timestamp: number) => {
    if (isCancelled) {
      return;
    }
    if (startTime === null) {
      startTime = timestamp;
    }
    const elapsed = timestamp - startTime;
    const progress = Math.min(1, elapsed / duration);
    const eased = easeInOutCubic(progress);

    window.scrollTo(0, Math.round(startY + (targetY - startY) * eased));

    if (progress < 1) {
      activeAnimationId = requestAnimationFrame(step);
    } else {
      cleanup();
      finishScroll();
    }
  };

  activeAnimationId = requestAnimationFrame(step);
}
