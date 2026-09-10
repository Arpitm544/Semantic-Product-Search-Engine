'use client';
import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import ScrollReveal from './ScrollReveal';

const words = ["waterproof", "winter", "jacket", "thermal", "fleece", "insulated", "cold", "weather"];
const vectorNums = [0.12, -0.84, 0.31, 0.67, -0.45, 0.19, -0.73, 0.55, 0.08, -0.92, 0.44, 0.27];

export default function EmbeddingSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section className="lp-section" ref={ref}>
      <ScrollReveal>
        <div className="section-badge">Step 2</div>
        <h2 className="section-title">Text → Vector Embedding</h2>
        <p className="section-sub">The Sentence Transformer model converts natural language into 384-dimensional dense vectors that capture semantic meaning.</p>
      </ScrollReveal>

      <div className="embedding-flow">
        {/* Words */}
        <ScrollReveal delay={0.2} direction="left">
          <div className="embed-stage">
            <div className="embed-label">Input Text</div>
            <div className="word-cloud">
              {words.map((w, i) => (
                <motion.span
                  key={i}
                  className="word-pill"
                  initial={{ opacity: 0, scale: 0.5 }}
                  animate={isInView ? { opacity: 1, scale: 1 } : {}}
                  transition={{ delay: 0.3 + i * 0.1, type: 'spring' }}
                >
                  {w}
                </motion.span>
              ))}
            </div>
          </div>
        </ScrollReveal>

        {/* Transformer Model */}
        <ScrollReveal delay={0.5} direction="scale">
          <div className="transformer-block">
            <div className="transformer-rings">
              {[0, 1, 2].map((r) => (
                <motion.div
                  key={r}
                  className={`t-ring t-ring-${r}`}
                  animate={isInView ? {
                    scale: [1, 1.2, 1],
                    opacity: [0.3, 0.7, 0.3],
                  } : {}}
                  transition={{ duration: 2, repeat: Infinity, delay: r * 0.4 }}
                />
              ))}
              <div className="t-core">
                <div className="t-icon">🧠</div>
                <div className="t-name">all-MiniLM-L6-v2</div>
              </div>
            </div>
          </div>
        </ScrollReveal>

        {/* Vector Output */}
        <ScrollReveal delay={0.7} direction="right">
          <div className="embed-stage">
            <div className="embed-label">384-D Vector</div>
            <div className="vector-grid">
              {vectorNums.map((n, i) => (
                <motion.span
                  key={i}
                  className={`vector-num ${n < 0 ? 'neg' : 'pos'}`}
                  initial={{ opacity: 0, y: 20 }}
                  animate={isInView ? { opacity: 1, y: 0 } : {}}
                  transition={{ delay: 0.8 + i * 0.08 }}
                >
                  {n.toFixed(2)}
                </motion.span>
              ))}
              <span className="vector-ellipsis">... ×384</span>
            </div>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
