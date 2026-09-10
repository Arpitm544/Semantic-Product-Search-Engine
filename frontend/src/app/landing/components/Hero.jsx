'use client';
import { motion } from 'framer-motion';
import ScrollReveal from './ScrollReveal';

const floatingCards = [
  { title: 'Winter Parka', cat: 'Jackets', emoji: '🧥', delay: 0, x: -420, y: -200, rot: -8 },
  { title: 'Wireless Headphones', cat: 'Audio', emoji: '🎧', delay: 0.2, x: 400, y: -180, rot: 6 },
  { title: 'Gaming Laptop', cat: 'Laptops', emoji: '💻', delay: 0.4, x: -380, y: 140, rot: 5 },
  { title: 'Smart Lock', cat: 'Security', emoji: '🔐', delay: 0.6, x: 420, y: 160, rot: -7 },
  { title: 'Hiking Boots', cat: 'Footwear', emoji: '🥾', delay: 0.1, x: -180, y: -280, rot: 12 },
  { title: 'Espresso Machine', cat: 'Kitchen', emoji: '☕', delay: 0.3, x: 200, y: 260, rot: -4 },
];

export default function Hero() {
  return (
    <section className="lp-hero">
      <div className="hero-glow hero-glow-1" />
      <div className="hero-glow hero-glow-2" />

      {/* Floating Product Cards — pushed far from center */}
      {floatingCards.map((card, i) => (
        <motion.div
          key={i}
          className="floating-card"
          initial={{ opacity: 0, y: 40 }}
          animate={{
            opacity: [0, 0.85, 0.65],
            y: [40, card.y - 10, card.y],
            x: [0, card.x],
            rotateZ: [0, card.rot],
          }}
          transition={{ duration: 2.5, delay: card.delay + 0.8, ease: 'easeOut' }}
          style={{ left: '50%', top: '50%' }}
        >
          <div className="fc-cat">{card.cat}</div>
          <div className="fc-title">{card.emoji} {card.title}</div>
        </motion.div>
      ))}

      {/* Central AI Sphere */}
      <motion.div
        className="ai-sphere"
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 1.4, delay: 0.3, type: 'spring' }}
      >
        <div className="sphere-ring sphere-ring-1" />
        <div className="sphere-ring sphere-ring-2" />
        <div className="sphere-ring sphere-ring-3" />
        <div className="sphere-core">AI</div>
      </motion.div>

      {/* Hero Text */}
      <div className="hero-content">
        <ScrollReveal delay={0.2}>
          <span className="hero-badge">✦ Semantic Search Engine • Proof of Concept</span>
        </ScrollReveal>
        <ScrollReveal delay={0.4}>
          <h1 className="hero-title">Search That<br />Understands <span className="gradient-text">Meaning</span></h1>
        </ScrollReveal>
        <ScrollReveal delay={0.6}>
          <p className="hero-sub">Not just keywords — intent, context, and semantics. Powered by Sentence Transformers, FAISS, BM25, and Hybrid Rank Fusion.</p>
        </ScrollReveal>
        <ScrollReveal delay={0.8}>
          <a href="#pipeline" className="hero-cta">
            Explore the Pipeline ↓
          </a>
        </ScrollReveal>
      </div>
    </section>
  );
}
