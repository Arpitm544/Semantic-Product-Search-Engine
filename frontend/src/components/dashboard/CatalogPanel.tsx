'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { DashboardData } from '@/lib/types';
import { API_BASE, useAuthenticatedFetch } from '@/lib/api';
import { Icon, PanelHeader, Skeleton, card } from './ui';

const PREVIEW_SIZE = 6;
const format = (value: number) => Number.isFinite(value) ? value.toLocaleString('en-US') : '—';

export function useCatalog() {
  const authenticatedFetch = useAuthenticatedFetch();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  const controller = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setBusy(true); setError('');
    try {
      const response = await authenticatedFetch(`${API_BASE}/api/dashboard`, { signal: current.signal });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error || 'Could not load the catalog.');
      }
      const payload = await response.json();
      if (!current.signal.aborted) setData(payload);
    } catch (reason) {
      if (current.signal.aborted) return;
      setError(reason instanceof TypeError ? 'The server is not reachable.' : reason instanceof Error ? reason.message : 'Could not load the catalog.');
    } finally {
      if (!current.signal.aborted) setBusy(false);
    }
  }, [authenticatedFetch]);

  useEffect(() => { void load(); return () => controller.current?.abort(); }, [load]);
  return { data, error, busy, load };
}

const tones = ['bg-[#e4ebdd] text-[#4f6b52]', 'bg-[#efe6dc] text-[#8a6a4d]', 'bg-[#e7e5f0] text-[#6c6590]', 'bg-[#e1ebed] text-[#56767e]', 'bg-[#f1e4e1] text-[#94675e]'];

export default function CatalogPanel({ catalog }: { catalog: ReturnType<typeof useCatalog> }) {
  const { data, busy, error } = catalog;
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');

  const products = useMemo(() => {
    const term = query.trim().toLowerCase();
    return (data?.products ?? [])
      .filter(item => !category || item.category === category)
      .filter(item => !term || `${item.title} ${item.category} ${item.brand || ''} ${item.description || ''}`.toLowerCase().includes(term))
      .slice(0, PREVIEW_SIZE);
  }, [data, query, category]);

  const categories = data?.categories.slice(0, 10) ?? [];
  const summary = data
    ? `${format(data.productCount)} products · ${format(data.categories.length)} categories${data.totalStock != null ? ` · ${format(data.totalStock)} units in stock` : ''}`
    : busy ? 'Loading catalog…' : 'Catalog unavailable';

  return <section id="catalog" className={card} aria-labelledby="catalog-title">
    <PanelHeader id="catalog-title" title="Explore the catalog" description={summary}
      action={<label className="flex h-9 w-full items-center gap-2 rounded-full border border-[var(--line)] bg-[var(--paper)] px-3 text-[var(--muted)] sm:w-60">
        <Icon name="search" size={15} />
        <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Filter products" aria-label="Filter catalog preview" disabled={!data} className="w-full bg-transparent text-[13px] text-[var(--ink)] outline-none placeholder:text-[var(--muted)]" />
      </label>} />

    {!!categories.length && <div className="flex gap-2 overflow-x-auto border-b border-[var(--line)] px-5 py-3 [scrollbar-width:thin]" role="group" aria-label="Filter by category">
      {['', ...categories].map(name => <button key={name || 'all'} type="button" aria-pressed={category === name} onClick={() => setCategory(name)}
        className={`shrink-0 rounded-full border px-3 py-1 text-[12.5px] font-medium transition-colors ${category === name ? 'border-[var(--accent)] bg-[var(--accent)] text-[var(--accent-ink)]' : 'border-[var(--line)] bg-transparent text-[var(--ink)] hover:bg-[var(--sage)]'}`}>{name || 'All'}</button>)}
    </div>}

    {busy && !data && <ul className="grid gap-px bg-[var(--line)] sm:grid-cols-2">{Array.from({ length: 4 }, (_, i) => <li key={i} className="flex items-center gap-3 bg-[var(--surface-fff)] px-5 py-4"><Skeleton className="h-10 w-10 rounded-lg" /><span className="flex-1 space-y-2"><Skeleton className="h-3.5 w-2/3" /><Skeleton className="h-3 w-1/3" /></span></li>)}</ul>}
    {!data && !busy && error && <p className="px-5 py-10 text-center text-[13px] text-[var(--muted)]">The catalog preview is unavailable right now.</p>}

    {!!products.length && <ul className="grid gap-px bg-[var(--line)] sm:grid-cols-2">{products.map((product, index) => <li key={product.id} className="bg-[var(--surface-fff)]">
      <a href={`/search?${new URLSearchParams({ q: product.title })}`} className="flex items-center gap-3 px-5 py-3.5 hover:bg-[var(--paper)]">
        <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-lg text-sm font-bold [font-family:Manrope,sans-serif] ${tones[index % tones.length]}`}>{product.title.slice(0, 1).toUpperCase()}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13.5px] font-semibold">{product.title}</span>
          <span className="mt-0.5 block truncate text-[12.5px] text-[var(--muted)]">{product.brand || 'Unknown brand'} · {product.category}</span>
        </span>
      </a>
    </li>)}</ul>}
    {data && !products.length && <p className="px-5 py-8 text-center text-[13px] text-[var(--muted)]">No products in this preview match{query ? ` “${query}”` : ''}{category ? ` in ${category}` : ''}.</p>}

    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--line)] px-5 py-3 text-[12px] text-[var(--muted)]">
      <span>{data ? `Preview of the first ${format(data.displayedProductCount ?? data.products.length)} records${data.sources?.catalog ? ` from ${data.sources.catalog}` : ''}` : 'Product catalog'}</span>
      <a href="/search" className="inline-flex items-center gap-1 font-semibold text-[var(--accent)] hover:underline">Search the full catalog <Icon name="arrow" size={14} /></a>
    </div>
  </section>;
}
