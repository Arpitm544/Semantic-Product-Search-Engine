'use client';

import { useState, useEffect } from 'react';
import { Search, Sparkles, Zap, Activity, BarChart3, LayoutGrid, CheckCircle2, RefreshCw, Sliders } from 'lucide-react';

export default function SearchPage() {
  const [activeTab, setActiveTab] = useState('search'); // 'search' | 'analytics'
  
  // Search state
  const [query, setQuery] = useState('warm jacket for cold weather');
  const [mode, setMode] = useState('hybrid');
  const [semanticWeight, setSemanticWeight] = useState(0.7); // 0.0 to 1.0
  const [category, setCategory] = useState('All');
  const [maxPrice, setMaxPrice] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [healthStatus, setHealthStatus] = useState(null);

  // Evaluation Analytics state
  const [evalData, setEvalData] = useState(null);
  const [evalLoading, setEvalLoading] = useState(false);

  const presets = [
    "warm jacket for cold weather",
    "wireless bluetooth headphones for gym",
    "laptop for software programming",
    "ergonomic chair for coding",
    "solar outdoor security camera",
    "espresso machine coffee maker"
  ];

  const categories = [
    "All",
    "Jackets & Outerwear",
    "Audio & Electronics",
    "Laptops & Computers",
    "Wearables",
    "Footwear",
    "Furniture",
    "Home & Kitchen",
    "Smart Home & Security",
    "Gaming & Accessories",
    "Outdoor & Camping"
  ];

  useEffect(() => {
    fetchHealth();
    handleSearch();
    fetchEvaluation();
  }, []);

  const fetchHealth = async () => {
    try {
      const res = await fetch('http://localhost:8000/health');
      if (res.ok) {
        const data = await res.json();
        setHealthStatus(data);
      } else {
        setHealthStatus({ status: 'error' });
      }
    } catch (e) {
      setHealthStatus({ status: 'offline' });
    }
  };

  const fetchEvaluation = async () => {
    setEvalLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/v1/eval');
      if (res.ok) {
        const data = await res.json();
        setEvalData(data);
      }
    } catch (err) {
      console.error('Failed to fetch evaluation metrics:', err);
    } finally {
      setEvalLoading(false);
    }
  };

  const handleSearch = async (overrideQuery = null, overrideMode = null, overrideWeight = null) => {
    const activeQuery = overrideQuery !== null ? overrideQuery : query;
    const activeMode = overrideMode !== null ? overrideMode : mode;
    const activeWeight = overrideWeight !== null ? overrideWeight : semanticWeight;

    if (!activeQuery.trim()) return;

    setLoading(true);

    try {
      const payload = {
        query: activeQuery,
        mode: activeMode,
        semanticWeight: activeWeight,
        topK: 12,
        filters: {
          category: category !== 'All' ? category : null,
          max_price: maxPrice ? parseFloat(maxPrice) : null
        }
      };

      const res = await fetch('http://localhost:8000/api/v1/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const data = await res.json();
        setResults(data);
      } else {
        console.error('Search API error:', res.statusText);
      }
    } catch (err) {
      console.error('Failed to connect to search API:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleWeightChange = (e) => {
    const newWeight = parseFloat(e.target.value);
    setSemanticWeight(newWeight);
    handleSearch(query, mode, newWeight);
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <main className="container">
      {/* Header */}
      <header className="header">
        <div className="title-badge">
          <Sparkles size={14} /> Interactive AI Search Sandbox & Weight Tuner
        </div>
        <h1 className="main-title">Semantic Product Search & Hybrid Sandbox</h1>
        <p className="subtitle">
          Tune vector embedding scores vs BM25 keyword matching in real-time. Powered by Sentence Transformers, FAISS, & FastAPI.
        </p>

        {/* Navigation Tabs */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', marginTop: '1.5rem' }}>
          <button
            className={`mode-btn ${activeTab === 'search' ? 'active' : ''}`}
            onClick={() => setActiveTab('search')}
            style={{ padding: '0.65rem 1.4rem', fontSize: '0.95rem' }}
          >
            <LayoutGrid size={16} /> Search & Weight Sandbox
          </button>
          <button
            className={`mode-btn ${activeTab === 'analytics' ? 'active' : ''}`}
            onClick={() => setActiveTab('analytics')}
            style={{ padding: '0.65rem 1.4rem', fontSize: '0.95rem' }}
          >
            <BarChart3 size={16} /> Quality Benchmark & Metrics
          </button>
        </div>

        {/* Health status indicator */}
        <div style={{ marginTop: '1.25rem', display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', color: '#9ca3af' }}>
          <Activity size={14} color={healthStatus?.status === 'ok' ? '#10b981' : '#f59e0b'} />
          <span>Search Engines: </span>
          <span style={{ color: healthStatus?.status === 'ok' ? '#10b981' : '#f59e0b', fontWeight: 600 }}>
            {healthStatus?.status === 'ok' ? `Active (Indexed ${healthStatus?.totalProductsIndexed || 50} Products)` : 'Connecting / Offline'}
          </span>
        </div>
      </header>

      {/* SEARCH & SANDBOX TAB */}
      {activeTab === 'search' && (
        <>
          {/* Search Input Card */}
          <div className="search-card">
            <div className="search-input-wrapper">
              <Search className="search-icon" />
              <input
                type="text"
                className="search-input"
                placeholder="Try 'warm jacket for cold weather' or 'gaming mouse'..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
              />
              <button className="search-btn" onClick={() => handleSearch()} disabled={loading}>
                {loading ? 'Searching...' : 'Search'}
              </button>
            </div>

            {/* Controls: Mode Selector & Filters */}
            <div className="controls-grid">
              <div className="mode-selector">
                <button
                  className={`mode-btn ${mode === 'semantic' ? 'active' : ''}`}
                  onClick={() => { setMode('semantic'); handleSearch(query, 'semantic'); }}
                >
                  <Sparkles size={14} /> Semantic
                </button>
                <button
                  className={`mode-btn ${mode === 'keyword' ? 'active' : ''}`}
                  onClick={() => { setMode('keyword'); handleSearch(query, 'keyword'); }}
                >
                  <Search size={14} /> BM25 Keyword
                </button>
                <button
                  className={`mode-btn ${mode === 'hybrid' ? 'active' : ''}`}
                  onClick={() => { setMode('hybrid'); handleSearch(query, 'hybrid'); }}
                >
                  <Zap size={14} /> Live Hybrid Tuner
                </button>
              </div>

              <div className="filters-group">
                <select
                  className="filter-select"
                  value={category}
                  onChange={(e) => { setCategory(e.target.value); setTimeout(handleSearch, 50); }}
                >
                  {categories.map((cat) => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>

                <input
                  type="number"
                  className="filter-input"
                  placeholder="Max Price (₹)"
                  value={maxPrice}
                  onChange={(e) => setMaxPrice(e.target.value)}
                  onBlur={() => handleSearch()}
                  style={{ width: '130px' }}
                />
              </div>
            </div>

            {/* Live Weight Slider (Active in Hybrid Mode) */}
            {mode === 'hybrid' && (
              <div className="tuner-container">
                <div className="tuner-header">
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Sliders size={16} color="#818cf8" />
                    <strong>Live Hybrid Score Fusion Weight Tuner</strong>
                  </span>
                  <span style={{ fontFamily: 'monospace', color: '#38bdf8' }}>
                    Formula: {Math.round(semanticWeight * 100)}% Semantic + {Math.round((1 - semanticWeight) * 100)}% BM25 Keyword
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  className="weight-slider"
                  value={semanticWeight}
                  onChange={handleWeightChange}
                />
                <div className="tuner-labels">
                  <span className="kw-label">0% Semantic / 100% Keyword</span>
                  <span style={{ color: '#94a3b8' }}>50 / 50 Balanced</span>
                  <span className="sem-label">100% Semantic / 0% Keyword</span>
                </div>
              </div>
            )}

            {/* Search Presets */}
            <div className="presets-row">
              <span className="preset-label">Try searching:</span>
              {presets.map((p) => (
                <button
                  key={p}
                  className="preset-chip"
                  onClick={() => { setQuery(p); handleSearch(p, mode); }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {/* Results Header */}
          {results && (
            <div className="stats-bar">
              <div className="stats-left">
                Found <span className="stats-highlight">{results.totalResults}</span> products for &ldquo;
                <span className="stats-highlight">{results.query}</span>&rdquo; using mode <span className="stats-highlight" style={{ textTransform: 'uppercase' }}>{results.mode}</span>
                {mode === 'hybrid' && (
                  <span style={{ marginLeft: '0.5rem', color: '#818cf8' }}>
                    (&alpha; = {results.semanticWeight})
                  </span>
                )}
              </div>
              <div className="latency-badge">
                <Zap size={13} /> {results.latencyMs} ms
              </div>
            </div>
          )}

          {/* Products Grid */}
          {results && results.results.length > 0 ? (
            <div className="products-grid">
              {results.results.map((item) => {
                const semContrib = (item.semScore * (mode === 'hybrid' ? item.semanticWeight : mode === 'semantic' ? 1 : 0) * 100);
                const kwContrib = (item.kwScore * (mode === 'hybrid' ? (1 - item.semanticWeight) : mode === 'keyword' ? 1 : 0) * 100);

                return (
                  <div key={item.id} className="product-card">
                    <div>
                      <div className="card-top">
                        <span className="rank-badge">#{item.rank}</span>
                        <span className="category-tag">{item.category}</span>
                      </div>

                      <h3 className="product-title">{item.title}</h3>
                      <p className="product-desc">{item.description}</p>

                      {/* Score & Dual Breakdown Bar */}
                      <div className="score-wrapper">
                        <div className="score-header">
                          <span>Final Relevance Score</span>
                          <span className="score-val">{(item.score * 100).toFixed(1)}% ({item.score})</span>
                        </div>

                        {/* Dual Color Contribution Bar */}
                        <div className="score-bar-bg">
                          <div
                            className="score-bar-sem"
                            style={{ width: `${Math.min(100, semContrib)}%` }}
                            title={`Semantic Contribution: ${semContrib.toFixed(1)}%`}
                          />
                          <div
                            className="score-bar-kw"
                            style={{ width: `${Math.min(100, kwContrib)}%` }}
                            title={`Keyword Contribution: ${kwContrib.toFixed(1)}%`}
                          />
                        </div>

                        {/* Score Breakdown Legend */}
                        <div className="score-breakdown-legend">
                          <span style={{ color: '#818cf8' }}>
                            ● Vector: {item.semScore}
                          </span>
                          <span style={{ color: '#c084fc' }}>
                            ● BM25: {item.kwScore}
                          </span>
                        </div>
                      </div>

                      {/* Attribute tags */}
                      {item.attributes && item.attributes.length > 0 && (
                        <div className="attributes-row">
                          {item.attributes.map((attr, idx) => (
                            <span key={idx} className="attr-tag">{attr}</span>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="card-footer">
                      <div className="price-text">₹{item.price.toLocaleString('en-IN')}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            results && (
              <div className="empty-state">
                <h3>No matching products found</h3>
                <p style={{ marginTop: '0.5rem', fontSize: '0.9rem' }}>
                  Try adjusting your query or resetting filters.
                </p>
              </div>
            )
          )}
        </>
      )}

      {/* ANALYTICS TAB */}
      {activeTab === 'analytics' && (
        <div className="search-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <div>
              <h2 style={{ fontSize: '1.4rem', color: 'white', fontWeight: 700 }}>Search Engine Benchmark & Quality Evaluation</h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
                Offline ground-truth evaluation across BM25 Keyword Search, Vector Semantic Search, & Hybrid Reciprocal Rank Fusion.
              </p>
            </div>
            <button
              className="search-btn"
              onClick={fetchEvaluation}
              disabled={evalLoading}
              style={{ position: 'relative', right: '0', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
            >
              <RefreshCw size={14} className={evalLoading ? 'spin' : ''} /> {evalLoading ? 'Running...' : 'Re-Run Benchmark'}
            </button>
          </div>

          {evalData ? (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '0.85rem 1rem' }}>Search Engine Mode</th>
                    <th style={{ padding: '0.85rem 1rem' }}>Precision@5</th>
                    <th style={{ padding: '0.85rem 1rem' }}>Recall@5</th>
                    <th style={{ padding: '0.85rem 1rem' }}>NDCG@5</th>
                    <th style={{ padding: '0.85rem 1rem' }}>MRR</th>
                    <th style={{ padding: '0.85rem 1rem' }}>P50 Latency</th>
                    <th style={{ padding: '0.85rem 1rem' }}>P95 Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(evalData.metrics).map(([engineMode, metrics]) => (
                    <tr key={engineMode} style={{ borderBottom: '1px solid var(--border-color)', transition: 'background 0.2s ease' }}>
                      <td style={{ padding: '1rem', fontWeight: 700, color: 'white', textTransform: 'capitalize' }}>
                        {engineMode === 'hybrid' ? 'Hybrid (RRF Fusion)' : engineMode === 'semantic' ? 'Semantic (FAISS Vector)' : 'Keyword (BM25)'}
                      </td>
                      <td style={{ padding: '1rem', fontFamily: 'monospace', color: '#38bdf8', fontWeight: 600 }}>
                        {metrics.precision_at_5.toFixed(4)}
                      </td>
                      <td style={{ padding: '1rem', fontFamily: 'monospace', color: '#34d399', fontWeight: 600 }}>
                        {metrics.recall_at_5.toFixed(4)}
                      </td>
                      <td style={{ padding: '1rem', fontFamily: 'monospace', color: '#a78bfa', fontWeight: 600 }}>
                        {metrics.ndcg_at_5.toFixed(4)}
                      </td>
                      <td style={{ padding: '1rem', fontFamily: 'monospace', color: '#f43f5e', fontWeight: 600 }}>
                        {metrics.mrr.toFixed(4)}
                      </td>
                      <td style={{ padding: '1rem', fontFamily: 'monospace', color: '#fbbf24' }}>
                        {metrics.p50_latency_ms} ms
                      </td>
                      <td style={{ padding: '1rem', fontFamily: 'monospace', color: '#f97316' }}>
                        {metrics.p95_latency_ms} ms
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div style={{ marginTop: '1.5rem', padding: '1rem', background: 'rgba(99, 102, 241, 0.1)', borderRadius: '0.5rem', border: '1px solid rgba(99, 102, 241, 0.2)', fontSize: '0.85rem', color: '#cbd5e1' }}>
                <CheckCircle2 size={16} color="#818cf8" style={{ display: 'inline', marginRight: '0.4rem', verticalAlign: 'middle' }} />
                <strong>PRD Metric Insights:</strong> Hybrid Reciprocal Rank Fusion balances broad keyword recall with deep semantic relevance while reducing latency outliers relative to raw high-dimensional vector scoring.
              </div>
            </div>
          ) : (
            <div style={{ textAlignment: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
              Loading benchmark evaluation metrics...
            </div>
          )}
        </div>
      )}
    </main>
  );
}
