'use client';

import { useState } from 'react';
import { API_BASE } from '@/lib/api';
import './search.css';

const money = (value, currency = 'USD') => value != null && value !== '' && Number.isFinite(Number(value)) ? new Intl.NumberFormat('en-US', { style: 'currency', currency: currency || 'USD' }).format(Number(value)) : 'Price unavailable';

export default function SearchPage() {
  const [input, setInput] = useState('');
  const [searched, setSearched] = useState('');
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [correctedQuery, setCorrectedQuery] = useState(null);

  async function submitSearch(event) {
    event.preventDefault();
    await runSearch(input.trim());
  }

  async function runSearch(query, fuzzy = true) {
    if (!query) return;
    setSearched(query);
    setLoading(true);
    setError('');
    setCorrectedQuery(null);
    try {
      const response = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(query)}&fuzzy=${fuzzy ? '1' : '0'}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Search could not be completed.');
      setResults(payload.results || []);
      setTotal(payload.total || 0);
      setCorrectedQuery(payload.correctedQuery || null);
    } catch (reason) {
      setError(reason instanceof TypeError
        ? 'Search is unavailable right now. Please try again shortly.'
        : (reason.message || 'Search could not be completed.'));
      setResults([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="product-search-page">
      <header className="search-page-header"><a className="search-page-brand" href="/"><span>✳</span> semantic<span>.</span></a><a className="back-dashboard" href="/dashboard">Back to dashboard <span>↗</span></a></header>
      <section className="search-hero">
        <span className="search-page-eyebrow">PRODUCT DISCOVERY</span>
        <h1>Find what you’re<br/><em>looking for.</em></h1>
        <p>Search the project catalog by product, brand, category, or detail.</p>
        <form className="real-search-form" onSubmit={submitSearch}>
          <span className="search-glass" aria-hidden="true">⌕</span>
          <input autoFocus value={input} onChange={(event) => setInput(event.target.value)} placeholder="Try ‘wireless headphones’ or ‘mascara’" aria-label="Search products" />
          <button type="submit" disabled={!input.trim() || loading}>{loading ? 'Searching…' : 'Search'} <span>→</span></button>
        </form>
        <span className="search-data-note">Spelling suggestions help with small typing mistakes.</span>
      </section>

      <section className="search-results-section" aria-live="polite">
        {error && <div className="search-error" role="alert">{error}</div>}
        {loading && <div className="search-state">Searching the catalog…</div>}
        {!loading && !error && !searched && <div className="search-state search-empty-start"><span>✳</span><strong>Start with a product or a need</strong><small>Enter a product, brand, or category to search the catalog.</small></div>}
        {!loading && !error && searched && <>
          <div className="search-results-heading"><div><span className="search-page-eyebrow">RESULTS FOR</span><h2>“{searched}”</h2></div><span>{total} matching products</span></div>
          {correctedQuery && <div className="search-spelling-note"><span>Also searching for <strong>“{correctedQuery}”</strong>.</span><button type="button" onClick={() => runSearch(searched, false)}>Use original spelling</button></div>}
          {results.length ? <div className="search-result-list">{results.map((product, index) => <article className="search-result-card" key={product.id}><div className={`search-result-art art-${index % 5}`} aria-hidden="true">{product.title?.slice(0, 1) || 'P'}</div><div className="search-result-copy"><span className="search-result-category">{product.category}{product.brand ? ` · ${product.brand}` : ''}</span><h3>{product.title}</h3><p>{product.description}</p><div className="search-result-meta"><strong>{money(product.price, product.currency)}</strong>{product.rating != null && <span>★ {Number(product.rating).toFixed(2)}</span>}{product.stock != null && <span>{product.stock} in stock</span>}</div></div><span className="relevance-score">{product.matchSources?.includes('fuzzy') ? 'Spelling match' : product.matchSources?.includes('keyword') ? 'Product match' : 'Related match'}</span></article>)}</div> : <div className="search-state search-no-results"><strong>No matching products found.</strong><small>Try a shorter query or use a product name, brand, or category.</small></div>}
        </>}
      </section>
      <footer className="search-page-footer">Product catalog · Spelling suggestions available</footer>
    </main>
  );
}
