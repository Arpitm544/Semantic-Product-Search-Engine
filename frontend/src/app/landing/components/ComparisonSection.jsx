'use client';
import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import ScrollReveal from './ScrollReveal';

export default function ComparisonSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section className="lp-section" ref={ref}>
      <ScrollReveal>
        <div className="section-badge">Step 4</div>
        <h2 className="section-title">Semantic vs BM25</h2>
        <p className="section-sub">See how traditional keyword search (BM25) compares to Semantic Vector search for the same query: "warm coat for snow".</p>
      </ScrollReveal>

      <div className="compare-grid">
        {/* Semantic Side */}
        <ScrollReveal delay={0.2} direction="left">
          <div className="compare-card semantic-card">
            <h3 className="c-title">Semantic Search</h3>
            <div className="c-query">Query: <span className="highlight">warm coat for snow</span></div>
            
            <div className="c-viz">
              <div className="meaning-cloud">
                {["warm", "coat", "snow"].map((w, i) => (
                  <motion.div 
                    key={w}
                    className="meaning-node"
                    initial={{ scale: 0 }}
                    animate={isInView ? { scale: 1 } : {}}
                    transition={{ delay: 0.5 + i * 0.2, type: 'spring' }}
                  >
                    {w}
                  </motion.div>
                ))}
                
                <motion.div 
                  className="meaning-node matched"
                  initial={{ scale: 0 }}
                  animate={isInView ? { scale: 1 } : {}}
                  transition={{ delay: 1.2, type: 'spring' }}
                >
                  "insulated parka"
                </motion.div>
              </div>
            </div>
            
            <div className="c-result">
              <div className="r-title">ArcticShield Insulated Winter Parka</div>
              <div className="r-desc">Understands that "warm coat for snow" means "insulated winter parka".</div>
              <div className="r-score semantic-score">Score: 0.85</div>
            </div>
          </div>
        </ScrollReveal>

        <div className="compare-vs">VS</div>

        {/* BM25 Side */}
        <ScrollReveal delay={0.4} direction="right">
          <div className="compare-card bm25-card">
            <h3 className="c-title">BM25 (Keyword)</h3>
            <div className="c-query">Query: <span className="highlight">warm coat for snow</span></div>
            
            <div className="c-viz">
              <div className="keyword-match-box">
                <div className="kw-text">
                  ArcticShield Insulated Winter Parka
                </div>
                <div className="kw-matches">
                  Matches: <span className="kw-none">0/4 terms found</span>
                </div>
              </div>
            </div>
            
            <div className="c-result missed">
              <div className="r-title">ArcticShield Insulated Winter Parka</div>
              <div className="r-desc">Misses the product entirely because the exact words "warm", "coat", "snow" are not in the title.</div>
              <div className="r-score bm25-score">Score: 0.00</div>
            </div>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
