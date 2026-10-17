'use client';

import { useEffect, useRef, useState } from 'react';
import { API_BASE } from '@/lib/api';
import './search.css';

const SOURCES = { mongo: 'MongoDB catalog', serpapi: 'Google Shopping · SerpApi' };

function money(product) {
  if (product.priceLabel) return product.priceLabel;
  if (product.price == null || product.price === '' || !Number.isFinite(Number(product.price))) return 'Price unavailable';
  try {
    // SerpApi prices without a currency label must not be assigned a guessed currency.
    if (product.matchSources?.includes('google-shopping')) return new Intl.NumberFormat('en-IN').format(Number(product.price));
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: product.currency || 'USD' }).format(Number(product.price));
  } catch {
    return 'Price unavailable';
  }
}

function webUrl(value) {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}

function ProductImage({ product, index }) {
  const [failed, setFailed] = useState(false);
  const url = webUrl(product.imageUrl);
  return (
    <div className={`search-result-art art-${index % 5}`}>
      {url && !failed
        ? <img src={url} alt={product.title} loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} />
        : <span aria-label="Product image unavailable">{product.title?.slice(0, 1) || 'P'}</span>}
    </div>
  );
}

export default function SearchPage() {
  const [input, setInput] = useState('');
  const [source, setSource] = useState('mongo');
  const [searched, setSearched] = useState('');
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [warning, setWarning] = useState('');
  const [correctedQuery, setCorrectedQuery] = useState(null);
  const pending = useRef(null);
  const shopping = source === 'serpapi';

  useEffect(() => () => pending.current?.abort(), []);

  function changeSource(value) {
    pending.current?.abort();
    pending.current = null;
    setSource(value);
    setSearched('');
    setResults([]);
    setTotal(0);
    setError('');
    setWarning('');
    setCorrectedQuery(null);
    setLoading(false);
  }

  async function submitSearch(event) {
    event.preventDefault();
    await runSearch(input.trim());
  }

  async function runSearch(query, fuzzy = true) {
    if (!query) return;
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 45000);
    setSearched(query);
    setLoading(true);
    setResults([]);
    setTotal(0);
    setError('');
    setWarning('');
    setCorrectedQuery(null);
    try {
      const params = new URLSearchParams({ q: query, source, fuzzy: fuzzy ? '1' : '0' });
      const response = await fetch(`${API_BASE}/api/search?${params}`, { signal: controller.signal });
      let payload;
      try {
        payload = await response.json();
      } catch {
        throw new Error('Search returned an unreadable response. Please try again shortly.');
      }
      if (!response.ok) throw new Error(typeof payload?.error === 'string' ? payload.error : 'Search could not be completed. Please try again shortly.');
      if (!Array.isArray(payload?.results) || payload.results.some((product) => !product || typeof product.title !== 'string')) {
        throw new Error('Search returned an invalid response. Please try again shortly.');
      }
      if (pending.current !== controller) return;
      setResults(payload.results);
      setTotal(Number.isFinite(payload.total) ? payload.total : payload.results.length);
      setCorrectedQuery(typeof payload.correctedQuery === 'string' ? payload.correctedQuery : null);
      setWarning(typeof payload.warning === 'string' ? payload.warning : '');
    } catch (reason) {
      if (pending.current !== controller) return;
      if (controller.signal.aborted && !timedOut) return;
      setError(timedOut ? 'Search took too long. Please try again.' : reason instanceof TypeError
        ? 'Cannot reach the search service. Make sure the backend is running and try again.'
        : (reason.message || 'Search could not be completed.'));
    } finally {
      clearTimeout(timeout);
      if (pending.current === controller) {
        pending.current = null;
        setLoading(false);
      }
    }
  }

  return (
    <main className="product-search-page">
      <header className="search-page-header"><a className="search-page-brand" href="/"><span>✳</span> semantic<span>.</span></a><a className="back-dashboard" href="/dashboard">Back to dashboard <span>↗</span></a></header>
      <section className="search-hero">
        <span className="search-page-eyebrow">PRODUCT DISCOVERY</span>
        <h1>Find what you’re<br/><em>looking for.</em></h1>
        <p>Choose a source and search by product, brand, or detail.</p>
        <fieldset className="search-source-picker">
          <legend>Search source</legend>
          {Object.entries(SOURCES).map(([value, label]) => <label key={value} className={source === value ? 'is-selected' : ''}>
            <input type="radio" name="search-source" value={value} checked={source === value} onChange={() => changeSource(value)} />
            <span>{label}</span>
          </label>)}
        </fieldset>
        <form className="real-search-form" onSubmit={submitSearch}>
          <span className="search-glass" aria-hidden="true">⌕</span>
          <input autoFocus maxLength={512} value={input} onChange={(event) => setInput(event.target.value)} placeholder="Try ‘wireless headphones’ or ‘mascara’" aria-label="Search products" />
          <button type="submit" disabled={!input.trim() || loading}>{loading ? 'Searching…' : 'Search'} <span>→</span></button>
        </form>
        <span className="search-data-note">{shopping ? 'Google Shopping products ranked by our search engine. Prices and availability can change.' : 'Semantic catalog search with spelling suggestions. Images and prices may be unavailable.'}</span>
      </section>

      <section className="search-results-section" aria-live="polite" aria-busy={loading}>
        {error && <div className="search-error" role="alert"><span>{error}</span><button type="button" onClick={() => runSearch(searched)}>Try again</button></div>}
        {loading && <div className="search-state">Searching {SOURCES[source]}…</div>}
        {!loading && !error && !searched && <div className="search-state search-empty-start"><span>✳</span><strong>Start with a product or a need</strong><small>Enter a product, brand, or category to search {SOURCES[source]}.</small></div>}
        {!loading && !error && searched && <>
          <div className="search-results-heading"><div><span className="search-page-eyebrow">{SOURCES[source]} · RESULTS FOR</span><h2>“{searched}”</h2></div><span>{shopping ? `${results.length} products shown` : `${total} matching products`}</span></div>
          {warning && <div className="search-ranking-warning" role="status">{warning}</div>}
          {correctedQuery && <div className="search-spelling-note"><span>Also searching for <strong>“{correctedQuery}”</strong>.</span><button type="button" onClick={() => runSearch(searched, false)}>Use original spelling</button></div>}
          {results.length ? <div className="search-result-list">{results.map((product, index) => {
            const url = webUrl(product.url);
            return <article className="search-result-card" key={product.id || index}>
              <ProductImage key={`${product.id}:${product.imageUrl}`} product={product} index={index} />
              <div className="search-result-copy">
                <span className="search-result-category">{shopping ? product.merchant || 'Google Shopping' : [product.category, product.brand].filter(Boolean).join(' · ')}</span>
                <h3>{url ? <a href={url} target="_blank" rel="noopener noreferrer">{product.title} <span aria-hidden="true">↗</span></a> : product.title}</h3>
                {product.description && <p>{product.description}</p>}
                <div className="search-result-meta"><strong>{money(product)}</strong>{product.rating != null && <span>★ {Number(product.rating).toFixed(1)}{product.reviews != null ? ` (${Number(product.reviews).toLocaleString()} reviews)` : ''}</span>}{product.stock != null && <span>{product.stock} in stock</span>}</div>
              </div>
              <span className="relevance-score">{shopping ? product.matchSources?.includes('reranker') ? 'Engine ranked' : 'Google ranked' : product.matchSources?.some((source) => source === 'fuzzy' || source === 'semantic-corrected') ? 'Spelling match' : product.matchSources?.includes('keyword') ? 'Product match' : 'Related match'}</span>
            </article>;
          })}</div> : <div className="search-state search-no-results"><strong>No matching products found.</strong><small>Try a shorter query or choose another search source.</small></div>}
        </>}
      </section>
      <footer className="search-page-footer">{shopping ? 'Products from Google Shopping · Open a product to check its latest offer' : 'MongoDB product catalog · Spelling suggestions available'}</footer>
    </main>
  );
}
