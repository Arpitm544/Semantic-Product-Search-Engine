'use client';
import { motion } from 'framer-motion';
import ParticleBackground from './ParticleBackground';

export default function Hero() {
  return (
    <section className="lp-hero">
      {/* Particle canvas fills the whole hero */}
      <ParticleBackground />

      {/* Ambient glow blobs */}
      <div className="hero-glow hero-glow-1" />
      <div className="hero-glow hero-glow-2" />

      {/* Content */}
      <div className="hero-content">
        <motion.span
          className="hero-badge"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2 }}
        >
          ✦ Semantic Product Search · Proof of Concept
        </motion.span>

        <motion.h1
          className="hero-title"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.4 }}
        >
          Search That<br />
          Understands <span className="gradient-text">Meaning</span>
        </motion.h1>

        <motion.p
          className="hero-sub"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.6 }}
        >
          Not keywords — intent. Powered by Sentence Transformers, FAISS vector search, BM25, and Reciprocal Rank Fusion.
        </motion.p>

        <motion.div
          className="hero-ctas"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.8 }}
        >
          <a href="#pipeline" className="hero-cta primary">
            Explore the Pipeline ↓
          </a>
          <a href="#playground" className="hero-cta secondary">
            Try Search →
          </a>
        </motion.div>

        {/* Scroll indicator */}
        <motion.div
          className="scroll-indicator"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.4, duration: 1 }}
        >
          <div className="scroll-dot" />
        </motion.div>
      </div>
    </section>
  );
}
