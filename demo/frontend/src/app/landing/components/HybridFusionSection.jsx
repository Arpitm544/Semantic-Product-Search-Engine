'use client';
import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import ScrollReveal from './ScrollReveal';

export default function HybridFusionSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section className="lp-section" ref={ref}>
      <ScrollReveal>
        <div className="section-badge">Step 5</div>
        <h2 className="section-title">Hybrid Fusion Engine</h2>
        <p className="section-sub">Combine the best of both worlds. Reciprocal Rank Fusion (RRF) and convex combination blend semantic meaning with exact keyword precision.</p>
      </ScrollReveal>

      <div className="fusion-diagram">
        <div className="f-top">
          <ScrollReveal delay={0.2} direction="down">
            <div className="f-stream semantic-stream">
              <div className="stream-label">Semantic Score</div>
              <div className="stream-val">0.72</div>
              {[0, 1, 2].map(i => (
                <motion.div 
                  key={`s-${i}`}
                  className="stream-particle s-particle"
                  animate={isInView ? { y: [0, 80], opacity: [0, 1, 0] } : {}}
                  transition={{ duration: 1.5, repeat: Infinity, ease: 'linear', delay: i * 0.5 }}
                />
              ))}
            </div>
          </ScrollReveal>
          
          <ScrollReveal delay={0.3} direction="down">
            <div className="f-stream bm25-stream">
              <div className="stream-label">BM25 Score</div>
              <div className="stream-val">0.28</div>
              {[0, 1, 2].map(i => (
                <motion.div 
                  key={`b-${i}`}
                  className="stream-particle b-particle"
                  animate={isInView ? { y: [0, 80], opacity: [0, 1, 0] } : {}}
                  transition={{ duration: 1.5, repeat: Infinity, ease: 'linear', delay: i * 0.5 }}
                />
              ))}
            </div>
          </ScrollReveal>
        </div>

        <ScrollReveal delay={0.5} direction="scale">
          <div className="f-engine">
            <motion.div 
              className="engine-core"
              animate={isInView ? { boxShadow: ['0 0 30px rgba(249,115,22,0.06)', '0 0 50px rgba(249,115,22,0.15)', '0 0 30px rgba(249,115,22,0.06)'] } : {}}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            >
              FUSION<br/>ENGINE
            </motion.div>
            <div className="engine-formula">
              Score = (α * Semantic) + ((1-α) * BM25)
            </div>
          </div>
        </ScrollReveal>

        <div className="f-bottom">
          {[0, 1, 2].map(i => (
            <motion.div 
              key={`c-${i}`}
              className="stream-particle combined-particle"
              animate={isInView ? { y: [0, 60], opacity: [0, 1, 0] } : {}}
              transition={{ duration: 1.2, repeat: Infinity, ease: 'linear', delay: i * 0.4 }}
            />
          ))}
          <ScrollReveal delay={0.8} direction="up">
            <div className="ranked-results">
              <div className="r-item">
                <span className="r-rank">#1</span>
                <span className="r-name">Waterproof Winter Jacket</span>
                <span className="r-final">0.94</span>
              </div>
              <div className="r-item">
                <span className="r-rank">#2</span>
                <span className="r-name">North Face Winter Coat</span>
                <span className="r-final">0.91</span>
              </div>
              <div className="r-item">
                <span className="r-rank">#3</span>
                <span className="r-name">Insulated Hiking Jacket</span>
                <span className="r-final">0.87</span>
              </div>
            </div>
          </ScrollReveal>
        </div>
      </div>
    </section>
  );
}
