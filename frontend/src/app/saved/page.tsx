'use client';
import { useCallback, useEffect, useState } from 'react';
import { UserButton } from '@clerk/nextjs';
import ThemeToggle from '@/components/ThemeToggle';
import { API_BASE, useAuthenticatedFetch } from '@/lib/api';
import type { SearchProduct } from '@/lib/types';

type SavedItem = { id: string; source: string; product: SearchProduct; savedAt: string };
function safeUrl(value?: string) {
  try { const url = new URL(value || ''); return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : undefined; } catch { return undefined; }
}
export default function SavedProductsPage() {
  const request = useAuthenticatedFetch();
  const [items, setItems] = useState<SavedItem[]>([]);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(true);
  const [removing, setRemoving] = useState<string | null>(null);
  const [error, setError] = useState('');
  const load = useCallback(async (offset = 0) => {
    setBusy(true); setError('');
    try {
      const response = await request(`${API_BASE}/api/saved-products?offset=${offset}`);
      if (!response.ok) throw new Error('Could not load your saved products. Please try again.');
      const data = await response.json();
      setItems(old => offset ? [...old, ...data.items.filter((item: SavedItem) => !old.some(existing => existing.id === item.id))] : data.items);
      setMore(data.hasMore);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setBusy(false); }
  }, [request]);
  useEffect(() => { void load(); }, [load]);
  async function remove(id: string) {
    setRemoving(id); setError('');
    try {
      const response = await request(`${API_BASE}/api/saved-products/${id}`, { method: 'DELETE' });
      if (!response.ok) throw new Error('Could not remove this product. Please try again.');
      setItems(old => old.filter(item => item.id !== id));
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setRemoving(null); }
  }
  return <main className="min-h-screen bg-[var(--paper)] text-[var(--ink)] px-5 py-6">
    <header className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 border-b border-[var(--line)] pb-5">
      <a href="/" className="text-xl font-bold">✳ semantic.</a>
      <nav className="flex items-center gap-4 text-sm"><a href="/search">Search</a><a href="/dashboard">Dashboard</a><ThemeToggle /><UserButton /></nav>
    </header>
    <section className="mx-auto max-w-5xl py-10">
      <h1 className="text-4xl font-semibold">Your saved products</h1>
      <p className="mt-3 mb-8 text-sm opacity-70">Good finds, kept together. Prices reflect when you saved them and may change.</p>
      {error && <div role="alert" className="my-4 rounded-lg border border-current p-4">{error} <button onClick={() => load()} className="underline">Retry</button></div>}
      {!busy && !error && !items.length && <div className="rounded-2xl border border-[var(--line)] p-10 text-center"><p>No saved products yet.</p><a href="/search" className="mt-4 inline-block underline">Find your first good find →</a></div>}
      <ul className="grid gap-4 sm:grid-cols-2">
        {items.map(({ id, product, source, savedAt }) => <li key={id} className="flex flex-col gap-3 rounded-2xl border border-[var(--line)] p-5">
          <span className="text-xs uppercase opacity-60">{source === 'serpapi' ? product.merchant || 'Google Shopping' : 'Product catalog'}</span>
          <h2 className="text-lg font-semibold">{product.title}</h2>
          <p className="text-sm">{product.priceLabel || (product.price != null ? `${product.currency || ''} ${product.price}` : 'Price unavailable')}</p>
          <p className="text-xs opacity-60">Saved {new Date(savedAt).toLocaleDateString()}</p>
          <div className="mt-auto flex items-center justify-between gap-4">
            {safeUrl(product.url) ? <a href={safeUrl(product.url)} target="_blank" rel="noopener noreferrer" className="text-sm underline">View product ↗</a> : <span className="text-xs opacity-60">Saved from the catalog</span>}
            <button disabled={removing !== null || busy} onClick={() => remove(id)} className="rounded-full border border-current px-4 py-2 text-sm disabled:opacity-50">{removing === id ? 'Removing…' : 'Remove'}</button>
          </div>
        </li>)}
      </ul>
      {busy && <p role="status" className="py-6">Loading saved products…</p>}
      {more && !busy && <button onClick={() => load(items.length)} className="mt-6 rounded-full border border-current px-5 py-2">Load more</button>}
    </section>
  </main>;
}
