'use client';
import { useState } from 'react';
import { motion } from 'framer-motion';
import ScrollReveal from './ScrollReveal';

export default function PlaygroundSection() {
  const [query, setQuery] = useState('warm jacket for trekking');
  const [mode, setMode] = useState('hybrid');
  const [weight, setWeight] = useState(0.7);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    setLoading(true);
    setSearched(true);
    
    try {
      const res = await fetch(`http://localhost:8000/api/v1/search?q=${encodeURIComponent(query)}&mode=${mode}&semantic_weight=${weight}`);
      const data = await res.json();
      setResults(data.results || []);
    } catch (err) {
      console.error("Search failed", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="lp-section" id="playground">
      <ScrollReveal>
        <div className="section-badge">Step 6 — Live Playground</div>
        <h2 className="section-title">Test the Pipeline</h2>
        <p className="section-sub">Try the real-time FastAPI backend. Adjust the weights to see how Hybrid Search impacts the final rankings.</p>
      </ScrollReveal>

      <div className="playground-container">
        <ScrollReveal delay={0.2}>
          <div className="pg-controls">
            <form onSubmit={handleSearch} className="pg-form">
              <input 
                type="text" 
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pg-input"
                placeholder="Type a search query..."
              />
              <button type="submit" className="pg-btn" disabled={loading}>
                {loading ? 'Searching...' : 'Search'}
              </button>
            </form>
            
            <div className="pg-settings">
              <div className="mode-toggle">
                <button className={`mode-btn ${mode === 'semantic' ? 'active' : ''}`} onClick={() => setMode('semantic')}>Semantic</button>
                <button className={`mode-btn ${mode === 'bm25' ? 'active' : ''}`} onClick={() => setMode('bm25')}>BM25</button>
                <button className={`mode-btn ${mode === 'hybrid' ? 'active' : ''}`} onClick={() => setMode('hybrid')}>Hybrid</button>
              </div>
              
              {mode === 'hybrid' && (
                <div className="weight-slider-container">
                  <label>Semantic Weight: {weight.toFixed(2)}</label>
                  <input 
                    type="range" 
                    min="0" max="1" step="0.1" 
                    value={weight}
                    onChange={(e) => setWeight(parseFloat(e.target.value))}
                    className="weight-slider"
                  />
                </div>
              )}
            </div>
          </div>
        </ScrollReveal>

        {searched && (
          <div className="pg-results">
            {loading ? (
              <motion.div 
                className="pg-loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <motion.div
                  animate={{ opacity: [0.3, 1, 0.3], scale: [0.98, 1, 0.98] }}
                  transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
                >
                  <span style={{ color: '#f97316' }}>■</span> Querying FAISS Index & BM25 Engine...
                </motion.div>
              </motion.div>
            ) : results.length > 0 ? (
              <div className="pg-result-list">
                {results.slice(0, 3).map((r, i) => (
                  <motion.div 
                    key={r.id} 
                    className="pg-result-item"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.15, duration: 0.5, ease: [0.2, 0.8, 0.2, 1] }}
                  >
                    <div className="r-meta">
                      <span className="r-id">#{i+1}</span>
                      <span className="r-cat">{r.category}</span>
                    </div>
                    <div className="r-title">{r.title}</div>
                    <div className="r-scores">
                      <div className="score-pill semantic" style={{ opacity: mode === 'bm25' ? 0.3 : 1 }}>S: {r.semantic_score.toFixed(3)}</div>
                      <div className="score-pill bm25" style={{ opacity: mode === 'semantic' ? 0.3 : 1 }}>B: {r.bm25_score.toFixed(3)}</div>
                      {mode === 'hybrid' && <div className="score-pill combined">Total: {r.combined_score.toFixed(3)}</div>}
                    </div>
                  </motion.div>
                ))}
              </div>
            ) : (
              <motion.div className="pg-no-results" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>No results found.</motion.div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
