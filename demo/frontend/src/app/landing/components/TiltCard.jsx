'use client';
import { useRef } from 'react';

export default function TiltCard({ children, className = '', intensity = 8, glowColor = 'rgba(249,115,22,0.15)' }) {
  const cardRef = useRef(null);

  const handleMouseMove = (e) => {
    const card = cardRef.current;
    if (!card) return;
    const rect = card.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dx = (e.clientX - cx) / (rect.width / 2);
    const dy = (e.clientY - cy) / (rect.height / 2);

    card.style.transform = `perspective(900px) rotateX(${-dy * intensity}deg) rotateY(${dx * intensity}deg) translateZ(4px)`;
    card.style.boxShadow = `0 20px 60px rgba(0,0,0,0.5), 0 0 30px ${glowColor}`;
  };

  const handleMouseLeave = () => {
    const card = cardRef.current;
    if (!card) return;
    card.style.transform = 'perspective(900px) rotateX(0deg) rotateY(0deg) translateZ(0px)';
    card.style.boxShadow = '';
  };

  return (
    <div
      ref={cardRef}
      className={`tilt-card ${className}`}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      {children}
    </div>
  );
}
