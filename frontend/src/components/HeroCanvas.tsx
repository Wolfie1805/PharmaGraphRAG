import React, { useEffect, useRef } from 'react';
import { tokens } from '../tokens';

interface HeroCanvasProps {
  reduceEffects?: boolean;
  particleCount?: number;
}

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  alpha: number;
}

export const HeroCanvas: React.FC<HeroCanvasProps> = ({
  reduceEffects = false,
  particleCount = tokens.motion.defaultParticles,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId = 0;
    let isVisible = true;
    let lastTime = 0;
    const fps = tokens.motion.fpsCap;
    const frameInterval = 1000 / fps;

    // Check system prefers-reduced-motion
    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const shouldFreeze = reduceEffects || prefersReducedMotion;

    let width = 0;
    let height = 0;

    const particles: Particle[] = [];

    const handleResize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, tokens.motion.dprCap);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      if (typeof ctx.setTransform === 'function') {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
      }
      ctx.scale(dpr, dpr);

      // Re-init particles to fit viewport
      if (particles.length === 0) {
        for (let i = 0; i < particleCount; i++) {
          particles.push({
            x: Math.random() * (width || 800),
            y: Math.random() * (height || 600),
            vx: (Math.random() - 0.5) * 0.4,
            vy: (Math.random() - 0.5) * 0.4,
            radius: Math.random() * 1.5 + 0.8,
            alpha: Math.random() * 0.25 + 0.1,
          });
        }
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);

    // Pause when off-screen
    let observer: IntersectionObserver | null = null;
    if (typeof IntersectionObserver === 'function') {
      observer = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            isVisible = entry.isIntersecting;
          }
        },
        { threshold: 0.05 }
      );
      observer.observe(canvas);
    }

    // Pause when document is hidden
    const handleVisibilityChange = () => {
      isVisible = !document.hidden;
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    let angle = 0;

    const renderFrame = (timestamp: number) => {
      if (!isVisible) {
        animId = requestAnimationFrame(renderFrame);
        return;
      }

      const elapsed = timestamp - lastTime;
      if (elapsed < frameInterval && !shouldFreeze) {
        animId = requestAnimationFrame(renderFrame);
        return;
      }
      lastTime = timestamp - (elapsed % frameInterval);

      ctx.clearRect(0, 0, width, height);

      // Helper to check text and button zones
      const centerX = width * 0.5;
      const isInButtonArea = (x: number, y: number) => Math.abs(x - centerX) < 200 && y > height * 0.64 && y < height * 0.82;
      const isInCenterText = (x: number, y: number) => Math.abs(x - centerX) < 320 && y > height * 0.2 && y < height * 0.72;

      // 1. Draw drifting particles and soft connective lines
      ctx.lineWidth = 0.5;
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        if (!shouldFreeze) {
          p.x += p.vx;
          p.y += p.vy;
          if (p.x < 0) p.x = width;
          if (p.x > width) p.x = 0;
          if (p.y < 0) p.y = height;
          if (p.y > height) p.y = 0;
        }

        let pAlpha = p.alpha;
        if (isInButtonArea(p.x, p.y)) {
          pAlpha *= 0.05; // avoid buttons
        } else if (isInCenterText(p.x, p.y)) {
          pAlpha *= 0.25; // soften behind text
        }

        ctx.fillStyle = `rgba(255, 255, 255, ${pAlpha})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();

        // Connect nearby particles within 50px
        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const dx = p.x - p2.x;
          const dy = p.y - p2.y;
          const distSq = dx * dx + dy * dy;
          if (distSq < 2500) {
            let lineAlpha = (1 - Math.sqrt(distSq) / 50) * 0.08;
            if (isInButtonArea(p.x, p.y) || isInButtonArea(p2.x, p2.y)) {
              lineAlpha *= 0.05;
            } else if (isInCenterText(p.x, p.y) || isInCenterText(p2.x, p2.y)) {
              lineAlpha *= 0.25;
            }
            ctx.strokeStyle = `rgba(255, 255, 255, ${lineAlpha})`;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
      }

      // 2. Draw rotating DNA Double Helix
      const helixHeight = Math.min(height * 0.85, 480);
      const startY = (height - helixHeight) * 0.5;
      const numRungs = 24;
      const amplitude = Math.min(width * 0.22, 130);

      ctx.save();
      for (let r = 0; r <= numRungs; r++) {
        const progress = r / numRungs;
        const y = startY + progress * helixHeight;
        // Slow rotation angle
        const theta = progress * Math.PI * 3 + angle;

        const sinT = Math.sin(theta);
        const cosT = Math.cos(theta);

        const x1 = centerX + sinT * amplitude;
        const x2 = centerX - sinT * amplitude;

        // Depth perspective (z between -1 and 1)
        const z1 = cosT;
        const z2 = -cosT;

        let alphaRung = Math.max(0.08, (z1 + 1) * 0.15 + (z2 + 1) * 0.15);
        if (isInButtonArea(centerX, y)) {
          alphaRung *= 0.05;
        } else if (isInCenterText(centerX, y)) {
          alphaRung *= 0.25;
        }

        ctx.strokeStyle = `rgba(255, 255, 255, ${alphaRung * 0.6})`;
        ctx.beginPath();
        ctx.moveTo(x1, y);
        ctx.lineTo(x2, y);
        ctx.stroke();

        // Strand 1 node
        if (!isInButtonArea(x1, y)) {
          const r1 = 2 + (z1 + 1) * 1.2;
          let a1 = 0.25 + (z1 + 1) * 0.35;
          if (isInCenterText(x1, y)) a1 *= 0.3;
          ctx.fillStyle = `rgba(255, 255, 255, ${a1})`;
          ctx.shadowColor = 'rgba(255, 255, 255, 0.4)';
          ctx.shadowBlur = 4;
          ctx.beginPath();
          ctx.arc(x1, y, r1, 0, Math.PI * 2);
          ctx.fill();
        }

        // Strand 2 node
        if (!isInButtonArea(x2, y)) {
          const r2 = 2 + (z2 + 1) * 1.2;
          let a2 = 0.25 + (z2 + 1) * 0.35;
          if (isInCenterText(x2, y)) a2 *= 0.3;
          ctx.fillStyle = `rgba(255, 255, 255, ${a2})`;
          ctx.beginPath();
          ctx.arc(x2, y, r2, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.shadowBlur = 0;
      }
      ctx.restore();

      if (!shouldFreeze) {
        angle += 0.008;
        animId = requestAnimationFrame(renderFrame);
      }
    };

    if (shouldFreeze) {
      renderFrame(0);
    } else {
      animId = requestAnimationFrame(renderFrame);
    }

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', handleResize);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      observer?.disconnect();
    };
  }, [reduceEffects, particleCount]);

  return <canvas ref={canvasRef} className="hero-canvas" aria-hidden="true" />;
};

export default HeroCanvas;
