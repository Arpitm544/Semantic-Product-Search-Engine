'use client';

import { useEffect, useMemo, useState } from 'react';
import { API_BASE } from '@/lib/api';
import './dashboard.css';

function DashboardIcon({ name, size = 18 }) {
  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
    search: <><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4 4"/></>,
    box: <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 8 9 5 9-5M3 8v9l9 5 9-5V8M12 13v9"/></>,
    trend: <><path d="M3 17 9 11l4 4 8-9"/><path d="M15 6h6v6"/></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

const number = (value, digits = 0) => Number.isFinite(value) ? value.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits }) : '—';

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [query, setQuery] = useState('');

  useEffect(() => {
    fetch(`${API_BASE}/api/dashboard`)
      .then(async (response) => {
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.error || 'Could not load the local project data.');
        }
        return response.json();
      })
      .then(setData)
      .catch((error) => setLoadError(error instanceof TypeError
        ? 'The backend API is not reachable. Stop the current dev server and restart with npm run dev from the frontend folder.'
        : error.message));
  }, []);

  const products = useMemo(() => {
    if (!data?.products) return [];
    const term = query.trim().toLowerCase();
    return data.products
      .filter((item) => !term || `${item.title} ${item.category} ${item.brand || ''} ${item.description || ''}`.toLowerCase().includes(term))
      .sort((a, b) => (Number(b.rating) || 0) - (Number(a.rating) || 0))
      .slice(0, 5);
  }, [data, query]);

  return (
    <main className="dashboard-shell">
      <aside className="dashboard-sidebar">
        <a className="dashboard-brand" href="/"><span className="dashboard-brand-mark">✳</span><span>semantic<span>.</span></span></a>
        <div className="dashboard-workspace"><span className="workspace-avatar">S</span><span><strong>Search workspace</strong><small>MongoDB catalog</small></span><span className="workspace-caret">⌄</span></div>
        <span className="sidebar-label">WORKSPACE</span>
        <nav className="dashboard-nav" aria-label="Dashboard navigation">
          <a className="selected" href="/dashboard"><DashboardIcon name="grid" /> Overview</a>
          <a href="/search"><DashboardIcon name="search" /> Product search</a>
          <a href="#catalog"><DashboardIcon name="box" /> Catalog <span className="nav-count">{data?.productCount ?? '—'}</span></a>
        </nav>
        <div className="sidebar-bottom"><div className="sidebar-tip"><span className="tip-star">✳</span><strong>Search the catalog</strong><p>Search products by words or meaning.</p><a href="/search">Open product search <DashboardIcon name="arrow" size={15} /></a></div><div className="sidebar-user"><span className="user-avatar">A</span><span><strong>Local workspace</strong><small>Product catalog</small></span><span className="user-more">···</span></div></div>
      </aside>

      <section className="dashboard-main">
        <header className="dashboard-topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>Overview</strong></div><div className="topbar-actions"><span className="data-live-label"><i/> Product catalog</span><span className="topbar-divider"/><span className="user-avatar small">A</span></div></header>
        <div className="dashboard-content">
          <div className="dashboard-heading"><div><span className="dashboard-eyebrow">PROJECT DATA OVERVIEW</span><h1>Search, grounded in data<span>.</span></h1><p>Browse the product catalog and its categories.</p></div><span className="dataset-badge">MongoDB catalog</span></div>

          {loadError && <div className="dashboard-error" role="alert">{loadError}</div>}

          <section className="metric-grid" aria-label="Catalog metrics">
            <article className="metric-card"><div className="metric-top"><span>Catalog products</span><span className="metric-icon mint"><DashboardIcon name="box" size={17}/></span></div><strong>{data ? number(data.productCount) : '—'}</strong><div className="metric-foot"><span className="metric-neutral">Product catalog</span><span>stored products</span></div></article>
            <article className="metric-card"><div className="metric-top"><span>Categories</span><span className="metric-icon lavender"><DashboardIcon name="grid" size={17}/></span></div><strong>{data ? number(data.categories.length) : '—'}</strong><div className="metric-foot"><span className="metric-neutral">Distinct categories</span><span>in catalog</span></div></article>
          </section>

          <section className="panel products-panel" id="catalog"><div className="panel-heading products-heading"><div><h2>Catalog products</h2><p>A preview of products in your catalog</p></div><label className="product-filter"><DashboardIcon name="search" size={15}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter catalog" aria-label="Filter catalog" /></label></div><div className="products-table-wrap"><table className="products-table"><thead><tr><th>PRODUCT</th><th>CATEGORY</th><th>PRICE</th><th>RATING</th><th>STOCK</th></tr></thead><tbody>{products.map((product, index) => <tr key={product.id}><td><span className={`product-thumb tone-${index % 5}`}>{product.title.slice(0, 1)}</span><span className="product-name"><strong>{product.title}</strong><small>{product.brand || 'Unknown brand'} · ID {product.id}</small></span></td><td>{product.category}</td><td>{Number.isFinite(Number(product.price)) ? `$${number(Number(product.price), 2)}` : '—'}</td><td>{product.rating != null ? `★ ${number(Number(product.rating), 2)}` : '—'}</td><td>{product.stock != null ? number(Number(product.stock)) : '—'}</td></tr>)}</tbody></table>{data && !products.length && <p className="empty-products">No catalog products match “{query}”.</p>}</div><div className="data-provenance"><span>Source: <code>{data?.sources?.catalog || 'Catalog database'}</code></span><span>Search history is not available in this project.</span></div></section>
          <footer className="dashboard-footer"><span>✳ semantic</span><span>{data ? (data.totalStock == null ? 'Stock unavailable' : `${number(data.totalStock)} total units in catalog`) : 'Loading the catalog…'}</span></footer>
        </div>
      </section>
    </main>
  );
}
