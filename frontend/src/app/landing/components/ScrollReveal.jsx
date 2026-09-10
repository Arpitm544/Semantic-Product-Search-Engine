'use client';
import { useRef } from 'react';
import { useInView } from 'framer-motion';

export default function ScrollReveal({ children, className = '', delay = 0, direction = 'up' }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-80px' });

  const directionStyles = {
    up: { transform: isInView ? 'translateY(0)' : 'translateY(60px)', opacity: isInView ? 1 : 0 },
    down: { transform: isInView ? 'translateY(0)' : 'translateY(-60px)', opacity: isInView ? 1 : 0 },
    left: { transform: isInView ? 'translateX(0)' : 'translateX(-60px)', opacity: isInView ? 1 : 0 },
    right: { transform: isInView ? 'translateX(0)' : 'translateX(60px)', opacity: isInView ? 1 : 0 },
    scale: { transform: isInView ? 'scale(1)' : 'scale(0.85)', opacity: isInView ? 1 : 0 },
  };

  return (
    <div
      ref={ref}
      className={className}
      style={{
        ...directionStyles[direction] || directionStyles.up,
        transition: `all 0.8s cubic-bezier(0.17, 0.55, 0.55, 1) ${delay}s`,
      }}
    >
      {children}
    </div>
  );
}
