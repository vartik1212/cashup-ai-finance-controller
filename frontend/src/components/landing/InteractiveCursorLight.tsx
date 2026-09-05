import React, { useEffect, useRef } from 'react';

export const InteractiveCursorLight: React.FC = () => {
  const lightRef = useRef<HTMLDivElement>(null);
  const posRef = useRef({ x: window.innerWidth / 2, y: window.innerHeight / 3 });
  const targetPosRef = useRef({ x: window.innerWidth / 2, y: window.innerHeight / 3 });
  const animFrameRef = useRef<number | null>(null);

  useEffect(() => {
    // Disable on small devices / touch screens / reduced motion preference
    if (window.innerWidth < 768 || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }

    const handleMouseMove = (e: MouseEvent) => {
      targetPosRef.current = { x: e.clientX, y: e.clientY };
    };

    const updatePosition = () => {
      if (document.hidden) {
        animFrameRef.current = requestAnimationFrame(updatePosition);
        return;
      }

      // Smooth mechanical dampening
      posRef.current.x += (targetPosRef.current.x - posRef.current.x) * 0.06;
      posRef.current.y += (targetPosRef.current.y - posRef.current.y) * 0.06;

      if (lightRef.current) {
        const x = posRef.current.x;
        const y = posRef.current.y;
        const xPercent = (x / window.innerWidth) * 100;
        const yPercent = (y / window.innerHeight) * 100;

        // Subtle color modulation based on pointer quadrant (graphite navy base with restrained indigo/cyan shift)
        const indigoWeight = 0.045 - (xPercent / 100) * 0.015;
        const cyanWeight = 0.02 + (xPercent / 100) * 0.02;

        lightRef.current.style.background = `radial-gradient(900px circle at ${x}px ${y}px, rgba(108, 92, 231, ${indigoWeight.toFixed(3)}) 0%, rgba(34, 211, 238, ${cyanWeight.toFixed(3)}) 35%, transparent 70%)`;

        // Subtle desktop spatial tilt (max 1 degree) and shift (max 4px)
        const shiftX = ((x / window.innerWidth) - 0.5) * 8; // -4px to +4px
        const shiftY = ((y / window.innerHeight) - 0.5) * 8; // -4px to +4px
        const tiltX = -((y / window.innerHeight) - 0.5) * 1.6; // max ~0.8 deg
        const tiltY = ((x / window.innerWidth) - 0.5) * 1.6; // max ~0.8 deg

        document.documentElement.style.setProperty('--spatial-shift-x', `${shiftX.toFixed(2)}px`);
        document.documentElement.style.setProperty('--spatial-shift-y', `${shiftY.toFixed(2)}px`);
        document.documentElement.style.setProperty('--spatial-tilt-x', `${tiltX.toFixed(2)}deg`);
        document.documentElement.style.setProperty('--spatial-tilt-y', `${tiltY.toFixed(2)}deg`);
      }

      animFrameRef.current = requestAnimationFrame(updatePosition);
    };

    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    animFrameRef.current = requestAnimationFrame(updatePosition);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, []);

  return (
    <div
      ref={lightRef}
      aria-hidden="true"
      className="fixed inset-0 pointer-events-none z-10 transition-opacity duration-700"
      style={{
        background: 'radial-gradient(900px circle at 50% 30%, rgba(108, 92, 231, 0.03) 0%, transparent 60%)',
      }}
    />
  );
};
