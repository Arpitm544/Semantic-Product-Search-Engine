'use client';
import { useState } from 'react';
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
        <div className="section-badge">Interactive</div>
        <h2 className="section-title">Test the Pipeline</h2>
        <p className="section-sub">Try the live FastAPI backend right here.</p>
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
              <div className="pg-loading">Querying Vector Index & BM25...</div>
            ) : results.length > 0 ? (
              <div className="pg-result-list">
                {results.slice(0, 3).map((r, i) => (
                  <div key={r.id} className="pg-result-item" style={{ animationDelay: `${i * 0.1}s` }}>
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
                  </div>
                ))}
              </div>
            ) : (
              <div className="pg-no-results">No results found.</div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
