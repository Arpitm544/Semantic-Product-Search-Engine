'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useUser } from '@clerk/nextjs';
import { API_BASE, useAuthenticatedFetch } from '@/lib/api';
import type { SearchProduct } from '@/lib/types';

interface HistoryEntry {
  id: string; query: string; source: 'mongo' | 'serpapi'; fuzzy: boolean;
  resultCount: number; searchedAt: string; usePreferences?: boolean;
}
interface PersonalData {
  searchCount: number; savedCount: number; recentSearches: HistoryEntry[];
  hasMoreSearches: boolean;
  savedProducts: { id: string; product: SearchProduct; source: string; savedAt: string }[];
}
const panel = 'rounded-xl border border-[var(--line)] bg-[var(--surface-fff)] p-5';
const action = 'rounded-full border border-[var(--line)] px-3 py-2 text-xs font-medium transition hover:bg-[var(--sage)] focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50';

function repeatUrl(entry: HistoryEntry) {
  return `/search?${new URLSearchParams({ q: entry.query, source: entry.source, fuzzy: entry.fuzzy ? '1' : '0', preferences: entry.usePreferences ? '1' : '0' })}`;
}
function SavedPreview({ product }: { product: SearchProduct }) {
  const [failed, setFailed] = useState(false);
  const image = product.imageUrl && /^https?:\/\//i.test(product.imageUrl) ? product.imageUrl : undefined;
  return <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-[var(--sage)]" aria-hidden="true">
    {image && !failed ? <img src={image} alt="" referrerPolicy="no-referrer" loading="lazy" className="h-full w-full object-contain" onError={() => setFailed(true)} /> : <span className="text-xl">♡</span>}
  </div>;
}

function appendHistory(old: PersonalData | null, result: { hasMore: boolean; items: HistoryEntry[] }) {
  if (!old) return old;
  const ids = new Set(old.recentSearches.map(item => item.id));
  return { ...old, hasMoreSearches: result.hasMore,
    recentSearches: [...old.recentSearches, ...result.items.filter(entry => !ids.has(entry.id))] };
}
function dashboardName(user: { firstName: string | null; username: string | null } | null | undefined) {
  return user?.firstName || user?.username;
}
function errorMessage(reason: unknown, fallback = 'Please try again.') {
  return reason instanceof Error ? reason.message : fallback;
}

async function checkedResponse(request: Promise<Response>, message: string) {
  const response = await request;
  if (!response.ok) throw new Error(message);
  return response;
}

export default function PersonalDashboard() {
  const request = useAuthenticatedFetch();
  const { user } = useUser();
  const [data, setData] = useState<PersonalData | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  const [mutation, setMutation] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [notice, setNotice] = useState('');
  const version = useRef(0);
  const userId = user?.id;
  function applyCurrent(current: number, update: () => void) {
    if (current === version.current) update();
  }
  const load = useCallback(async () => {
    const current = ++version.current;
    setBusy(true); setError('');
    try {
      const response = await checkedResponse(request(`${API_BASE}/api/personal-dashboard`), 'Could not load your personal dashboard. Please try again.');
      const result = await response.json();
      applyCurrent(current, () => setData(result));
    } catch (reason) {
      applyCurrent(current, () => setError(errorMessage(reason, 'Could not load your dashboard.')));
    } finally { applyCurrent(current, () => setBusy(false)); }
  }, [request]);
  useEffect(() => {
    setData(null); setNotice(''); setConfirmClear(false);
    if (userId) void load();
    return () => { version.current++; };
  }, [load, userId]);

  async function mutate(id?: string) {
    if (mutation || busy) return;
    setMutation(id || 'clear'); setError(''); setNotice('');
    try {
      await checkedResponse(request(`${API_BASE}/api/search-history${id ? `/${encodeURIComponent(id)}` : ''}`, { method: 'DELETE' }), 'Could not delete search history. Please try again.');
      setConfirmClear(false);
      setNotice(id ? 'Search removed from your history.' : 'Your search history has been cleared.');
      await load();
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setMutation(null); }
  }
  async function loadMore() {
    if (!data) return;
    if (mutation) return;
    if (busy) return;
    setBusy(true); setError('');
    const current = version.current;
    try {
      const response = await checkedResponse(request(`${API_BASE}/api/search-history?offset=${data.recentSearches.length}&limit=6`), 'Could not load more searches. Please try again.');
      const result = await response.json();
      applyCurrent(current, () => setData(old => appendHistory(old, result)));
    } catch (reason) { applyCurrent(current, () => setError(errorMessage(reason))); }
    finally { applyCurrent(current, () => setBusy(false)); }
  }
  const name = dashboardName(user);
  return <section aria-label="Your personal dashboard" className="mb-8 space-y-5">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-[10px] font-bold uppercase tracking-[1.5px] opacity-60">Your discovery space</p>
        <h1 className="my-2 text-[clamp(26px,4vw,38px)] font-bold tracking-tight">{name ? `Welcome back, ${name}.` : 'Welcome to your space.'}</h1>
        <p className="text-sm opacity-65">Pick up a recent search or revisit a good find.</p></div>
      <a href="/search" className="rounded-full bg-[var(--ink)] px-5 py-3 text-sm font-semibold text-[var(--paper)]">Find something new ↗</a>
    </div>
    {error && <div role="alert" className={`${panel} flex flex-wrap items-center justify-between gap-3`}><span>{error}</span><button className={action} disabled={busy || !!mutation} onClick={() => load()}>Retry</button></div>}
    {notice && <p role="status" className="text-sm">{notice}</p>}
    {busy && !data && <p role="status" className="py-6 text-sm opacity-70">Loading your saved products and searches…</p>}
    <div className="grid gap-4 sm:grid-cols-2">
      <a href="/saved" className={panel}><span className="text-xs opacity-65">Saved products</span><strong className="my-2 block text-3xl">{data?.savedCount ?? '—'}</strong><span className="text-xs opacity-65">Your wishlist, available across devices ↗</span></a>
      <a href="#recent-searches" className={panel}><span className="text-xs opacity-65">Searches in your history</span><strong className="my-2 block text-3xl">{data?.searchCount ?? '—'}</strong><span className="text-xs opacity-65">Distinct successful searches, most recent first</span></a>
    </div>
    <div className="grid items-start gap-5 min-[1050px]:grid-cols-[1.2fr_1fr]">
      <section id="recent-searches" className={panel} aria-labelledby="recent-searches-title">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><h2 id="recent-searches-title" className="text-base font-semibold">Recent searches</h2>
          {!!data?.searchCount && <button className={action} disabled={!!mutation || busy} onClick={() => setConfirmClear(true)}>Clear history</button>}</div>
        <p className="mb-4 text-xs opacity-65">Only you can see this history. Repeat a search with its original source and spelling settings.</p>
        {confirmClear && <div className="mb-4 rounded-lg border border-[var(--line)] p-3">
          <p className="mb-3 text-sm">Delete all your search history? Your saved products will stay.</p>
          <div className="flex gap-2"><button className={action} disabled={!!mutation || busy} onClick={() => mutate()}>Yes, clear history</button><button className={action} disabled={!!mutation} onClick={() => setConfirmClear(false)}>Cancel</button></div>
        </div>}
        {data && !data.recentSearches.length && <div className="py-8 text-center"><p className="text-sm">Your next search starts here.</p><a className="mt-3 inline-block text-xs underline" href="/search">Search for a product →</a></div>}
        <ul className="divide-y divide-[var(--line)]">{data?.recentSearches.map(entry => <li key={entry.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
          <div className="min-w-0 flex-1 basis-40"><a href={repeatUrl(entry)} className="block break-words text-sm font-semibold hover:underline">{entry.query}</a>
            <p className="mt-1 text-xs opacity-65">{entry.source === 'serpapi' ? 'Google Shopping' : 'Product catalog'} · {entry.resultCount} shown</p>
            <time dateTime={entry.searchedAt} className="mt-1 block text-[11px] opacity-60">{new Date(entry.searchedAt).toLocaleString()}</time></div>
          <div className="flex items-center gap-2"><a className={action} href={repeatUrl(entry)}>Search again</a><button className={action} aria-label={`Delete search for ${entry.query}`} disabled={!!mutation || busy} onClick={() => mutate(entry.id)}>{mutation === entry.id ? 'Removing…' : 'Delete'}</button></div>
        </li>)}</ul>
        {data?.hasMoreSearches && <button className={`${action} mt-4`} disabled={busy || !!mutation} onClick={loadMore}>{busy ? 'Loading…' : 'Load more searches'}</button>}
      </section>
      <section className={panel} aria-labelledby="saved-previews-title"><div className="mb-4 flex items-center justify-between gap-3"><h2 id="saved-previews-title" className="text-base font-semibold">Saved for later</h2><a className="text-xs underline" href="/saved">View all ↗</a></div>
        {data && !data.savedProducts.length && <div className="py-8 text-center"><p className="text-sm">Keep your good finds here.</p><p className="mt-2 text-xs opacity-65">Use the heart button on search results to save a product.</p><a className="mt-3 inline-block text-xs underline" href="/search">Explore products →</a></div>}
        <ul className="divide-y divide-[var(--line)]">{data?.savedProducts.map(item => <li key={item.id} className="flex gap-3 py-4"><SavedPreview product={item.product} /><div className="min-w-0"><a href="/saved" className="text-sm font-semibold hover:underline">{item.product.title}</a><p className="mt-1 text-xs opacity-65">{item.product.priceLabel || (item.product.price != null ? `${item.product.currency || ''} ${item.product.price}` : 'Price unavailable')}</p></div></li>)}</ul>
        {!!data?.savedProducts.length && <p className="mt-3 text-[11px] opacity-60">Prices reflect when you saved each product and may change.</p>}
      </section>
    </div>
  </section>;
}
