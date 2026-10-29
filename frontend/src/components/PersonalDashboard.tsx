'use client';

import { useState } from 'react';
import { usePersonalDashboard } from '@/hooks/usePersonalDashboard';
import type { HistoryEntry, PersonalData } from '@/hooks/usePersonalDashboard';
import type { SearchProduct } from '@/lib/types';

type Dashboard = ReturnType<typeof usePersonalDashboard>;

const panel = 'rounded-xl border border-[var(--line)] bg-[var(--surface-fff)] p-5';
const action = 'rounded-full border border-[var(--line)] px-3 py-2 text-xs font-medium transition hover:bg-[var(--sage)] focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50';

function repeatUrl(entry: HistoryEntry) {
  return `/search?${new URLSearchParams({ q: entry.query, source: entry.source, fuzzy: entry.fuzzy ? '1' : '0' })}`;
}
function SavedPreview({ product }: { product: SearchProduct }) {
  const [failed, setFailed] = useState(false);
  const image = product.imageUrl && /^https?:\/\//i.test(product.imageUrl) ? product.imageUrl : undefined;
  return <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-[var(--sage)]" aria-hidden="true">
    {image && !failed ? <img src={image} alt="" referrerPolicy="no-referrer" loading="lazy" className="h-full w-full object-contain" onError={() => setFailed(true)} /> : <span className="text-xl">♡</span>}
  </div>;
}

function DashboardHeader({ user }: Pick<Dashboard, 'user'>) {
  const name = user?.firstName || user?.username;
  return <>
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-[10px] font-bold uppercase tracking-[1.5px] opacity-60">Your discovery space</p>
        <h1 className="my-2 text-[clamp(26px,4vw,38px)] font-bold tracking-tight">{name ? `Welcome back, ${name}.` : 'Welcome to your space.'}</h1>
        <p className="text-sm opacity-65">Pick up a recent search or revisit a good find.</p></div>
      <a href="/search" className="rounded-full bg-[var(--ink)] px-5 py-3 text-sm font-semibold text-[var(--paper)]">Find something new ↗</a>
    </div>
  </>;
}

function DashboardFeedback({ error, notice, busy, data, mutation, load }: Pick<Dashboard, 'error' | 'notice' | 'busy' | 'data' | 'mutation' | 'load'>) {
  return <>
    {error && <div role="alert" className={`${panel} flex flex-wrap items-center justify-between gap-3`}><span>{error}</span><button className={action} disabled={busy || !!mutation} onClick={() => load()}>Retry</button></div>}
    {notice && <p role="status" className="text-sm">{notice}</p>}
    {busy && !data && <p role="status" className="py-6 text-sm opacity-70">Loading your saved products and searches…</p>}
  </>;
}

function DashboardStats({ data }: { data: PersonalData | null }) {
  return <>
    <div className="grid gap-4 sm:grid-cols-2">
      <a href="/saved" className={panel}><span className="text-xs opacity-65">Saved products</span><strong className="my-2 block text-3xl">{data?.savedCount ?? '—'}</strong><span className="text-xs opacity-65">Your wishlist, available across devices ↗</span></a>
      <a href="#recent-searches" className={panel}><span className="text-xs opacity-65">Searches in your history</span><strong className="my-2 block text-3xl">{data?.searchCount ?? '—'}</strong><span className="text-xs opacity-65">Distinct successful searches, most recent first</span></a>
    </div>
  </>;
}

function HistoryHeading({ count, disabled, onClear }: { count?: number; disabled: boolean; onClear: () => void }) {
  return <>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><h2 id="recent-searches-title" className="text-base font-semibold">Recent searches</h2>
          {!!count && <button className={action} disabled={disabled} onClick={onClear}>Clear history</button>}</div>
  </>;
}

function ClearConfirmation({ confirmClear, mutation, disabled, mutate, setConfirmClear }: Pick<Dashboard, 'confirmClear' | 'mutation' | 'mutate' | 'setConfirmClear'> & { disabled: boolean }) {
  return <>
        {confirmClear && <div className="mb-4 rounded-lg border border-[var(--line)] p-3">
          <p className="mb-3 text-sm">Delete all your search history? Your saved products will stay.</p>
          <div className="flex gap-2"><button className={action} disabled={disabled} onClick={() => mutate()}>Yes, clear history</button><button className={action} disabled={!!mutation} onClick={() => setConfirmClear(false)}>Cancel</button></div>
        </div>}
  </>;
}

function HistoryRow({ entry, disabled, removing, mutate }: { entry: HistoryEntry; disabled: boolean; removing: boolean; mutate: Dashboard['mutate'] }) {
  return <li className="flex flex-wrap items-center justify-between gap-3 py-4">
          <div className="min-w-0 flex-1 basis-40"><a href={repeatUrl(entry)} className="block break-words text-sm font-semibold hover:underline">{entry.query}</a>
            <p className="mt-1 text-xs opacity-65">{entry.source === 'serpapi' ? 'Google Shopping' : 'Product catalog'} · {entry.resultCount} shown</p>
            <time dateTime={entry.searchedAt} className="mt-1 block text-[11px] opacity-60">{new Date(entry.searchedAt).toLocaleString()}</time></div>
          <div className="flex items-center gap-2"><a className={action} href={repeatUrl(entry)}>Search again</a><button className={action} aria-label={`Delete search for ${entry.query}`} disabled={disabled} onClick={() => mutate(entry.id)}>{removing ? 'Removing…' : 'Delete'}</button></div>
        </li>;
}

function MoreSearches({ hasMore, busy, disabled, loadMore }: { hasMore?: boolean; busy: boolean; disabled: boolean; loadMore: Dashboard['loadMore'] }) {
  return <>
        {hasMore && <button className={`${action} mt-4`} disabled={disabled} onClick={loadMore}>{busy ? 'Loading…' : 'Load more searches'}</button>}
  </>;
}

function RecentSearches({ data, mutation, busy, confirmClear, mutate, loadMore, setConfirmClear }: Pick<Dashboard, 'data' | 'mutation' | 'busy' | 'confirmClear' | 'mutate' | 'loadMore' | 'setConfirmClear'>) {
  const disabled = busy || !!mutation;
  return <>
      <section id="recent-searches" className={panel} aria-labelledby="recent-searches-title">
        <HistoryHeading count={data?.searchCount} disabled={disabled} onClear={() => setConfirmClear(true)} />
        <p className="mb-4 text-xs opacity-65">Only you can see this history. Repeat a search with its original source and spelling settings.</p>
        <ClearConfirmation confirmClear={confirmClear} mutation={mutation} disabled={disabled} mutate={mutate} setConfirmClear={setConfirmClear} />
        {data && !data.recentSearches.length && <div className="py-8 text-center"><p className="text-sm">Your next search starts here.</p><a className="mt-3 inline-block text-xs underline" href="/search">Search for a product →</a></div>}
        <ul className="divide-y divide-[var(--line)]">{data?.recentSearches.map(entry => <HistoryRow key={entry.id} entry={entry} disabled={disabled} removing={mutation === entry.id} mutate={mutate} />)}</ul>
        <MoreSearches hasMore={data?.hasMoreSearches} busy={busy} disabled={disabled} loadMore={loadMore} />
      </section>
  </>;
}

function savedPrice(product: SearchProduct) {
  return product.priceLabel || (product.price != null ? `${product.currency || ''} ${product.price}` : 'Price unavailable');
}

function SavedRow({ item }: { item: PersonalData['savedProducts'][number] }) {
  return <li className="flex gap-3 py-4"><SavedPreview product={item.product} /><div className="min-w-0"><a href="/saved" className="text-sm font-semibold hover:underline">{item.product.title}</a><p className="mt-1 text-xs opacity-65">{savedPrice(item.product)}</p></div></li>;
}

function SavedProducts({ data }: { data: PersonalData | null }) {
  return <>
      <section className={panel} aria-labelledby="saved-previews-title"><div className="mb-4 flex items-center justify-between gap-3"><h2 id="saved-previews-title" className="text-base font-semibold">Saved for later</h2><a className="text-xs underline" href="/saved">View all ↗</a></div>
        {data && !data.savedProducts.length && <div className="py-8 text-center"><p className="text-sm">Keep your good finds here.</p><p className="mt-2 text-xs opacity-65">Use the heart button on search results to save a product.</p><a className="mt-3 inline-block text-xs underline" href="/search">Explore products →</a></div>}
        <ul className="divide-y divide-[var(--line)]">{data?.savedProducts.map(item => <SavedRow key={item.id} item={item} />)}</ul>
        {!!data?.savedProducts.length && <p className="mt-3 text-[11px] opacity-60">Prices reflect when you saved each product and may change.</p>}
      </section>
  </>;
}

export default function PersonalDashboard() {
  const dashboard = usePersonalDashboard();
  return <section aria-label="Your personal dashboard" className="mb-8 space-y-5">
    <DashboardHeader user={dashboard.user} />
    <DashboardFeedback {...dashboard} />
    <DashboardStats data={dashboard.data} />
    <div className="grid items-start gap-5 min-[1050px]:grid-cols-[1.2fr_1fr]">
      <RecentSearches {...dashboard} />
      <SavedProducts data={dashboard.data} />
    </div>
  </section>;
}
