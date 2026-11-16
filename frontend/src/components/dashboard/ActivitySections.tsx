'use client';
import { useState } from 'react';
import { productPrice, type ProductCollection } from '@/lib/account';
import type { HistoryEntry, PersonalData, usePersonalDashboard } from '@/lib/usePersonalDashboard';
import { SOURCE_LABELS, type SearchProduct } from '@/lib/types';
import { EmptyState, Icon, PanelHeader, Skeleton, card, ghostButton } from './ui';

type PersonalState = ReturnType<typeof usePersonalDashboard>;

function repeatUrl(entry: HistoryEntry) {
  return `/search?${new URLSearchParams({ q: entry.query, source: entry.source, fuzzy: entry.fuzzy ? '1' : '0', preferences: entry.usePreferences ? '1' : '0' })}`;
}

const relative = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
function timeAgo(iso: string) {
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  if (!Number.isFinite(seconds)) return '';
  const steps: [Intl.RelativeTimeFormatUnit, number][] = [['year', 31536000], ['month', 2592000], ['week', 604800], ['day', 86400], ['hour', 3600], ['minute', 60]];
  for (const [unit, size] of steps) if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  return 'just now';
}

function RowSkeleton() {
  return <li className="flex items-center gap-3 px-5 py-4"><Skeleton className="h-10 w-10 rounded-lg" /><span className="flex-1 space-y-2"><Skeleton className="h-3.5 w-1/2" /><Skeleton className="h-3 w-1/3" /></span></li>;
}

function HistoryRow({ entry, state }: { entry: HistoryEntry; state: PersonalState }) {
  const { mutation, blocked, mutate } = state;
  const removing = mutation === entry.id;
  return <li className={`group flex items-center gap-3 px-5 py-3.5 transition-colors hover:bg-[var(--paper)] ${removing ? 'opacity-50' : ''}`}>
    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-[var(--sage)] text-[var(--accent)]"><Icon name="search" size={17} /></span>
    <a href={repeatUrl(entry)} className="min-w-0 flex-1" title="Search again">
      <span className="block truncate text-sm font-semibold group-hover:underline">{entry.query}</span>
      <span className="mt-0.5 block text-[12.5px] text-[var(--muted)]">
        {SOURCE_LABELS[entry.source] ?? SOURCE_LABELS.mongo} · {entry.resultCount} result{entry.resultCount === 1 ? '' : 's'} · <time dateTime={entry.searchedAt} title={new Date(entry.searchedAt).toLocaleString()}>{timeAgo(entry.searchedAt)}</time>
      </span>
    </a>
    <a href={repeatUrl(entry)} className={`${ghostButton} max-sm:hidden`}>Search again</a>
    <button type="button" aria-label={`Delete search for ${entry.query}`} title="Remove from history" disabled={blocked} onClick={() => mutate(entry.id)} className="grid h-8 w-8 shrink-0 place-items-center rounded-full border-0 bg-transparent text-[var(--muted)] hover:bg-[var(--sage)] hover:text-[var(--ink)] disabled:opacity-40">
      <Icon name="trash" size={16} />
    </button>
  </li>;
}

export function RecentSearches({ state }: { state: PersonalState }) {
  const { data, busy, blocked, confirmClear, setConfirmClear, mutate, mutation, loadMore, error } = state;
  const loading = busy && !data;
  return <section id="recent-searches" className={card} aria-labelledby="recent-searches-title">
    <PanelHeader id="recent-searches-title" title="Recent searches" description="Private to you. Click a search to run it again with the same settings."
      action={!!data?.searchCount && !confirmClear && <button type="button" className={ghostButton} disabled={blocked} onClick={() => setConfirmClear(true)}>Clear history</button>} />
    {confirmClear && <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--line)] bg-[var(--sage)] px-5 py-3 text-[13px]">
      <span>Delete all search history? Saved products stay.</span>
      <span className="flex gap-2">
        <button type="button" className={`${ghostButton} bg-[var(--surface-fff)]`} disabled={!!mutation} onClick={() => setConfirmClear(false)}>Cancel</button>
        <button type="button" className={`${ghostButton} border-[#b5634a] text-[#a14d36] dark:text-[#f0b49f]`} disabled={blocked} onClick={() => mutate()}>{mutation === 'clear' ? 'Clearing…' : 'Yes, clear'}</button>
      </span>
    </div>}
    {loading && <ul className="divide-y divide-[var(--line)]"><RowSkeleton /><RowSkeleton /><RowSkeleton /></ul>}
    {data && !data.recentSearches.length && <EmptyState icon="search" title="No searches yet" body="Your searches will show up here so you can pick up where you left off." href="/search" cta="Search for a product" />}
    {!data && !busy && error && <p className="px-5 py-8 text-center text-[13px] text-[var(--muted)]">Your search history is unavailable right now.</p>}
    {!!data?.recentSearches.length && <ul className="divide-y divide-[var(--line)]">{data.recentSearches.map(entry => <HistoryRow key={entry.id} entry={entry} state={state} />)}</ul>}
    {data?.hasMoreSearches && <div className="border-t border-[var(--line)] px-5 py-3"><button type="button" className={ghostButton} disabled={blocked} onClick={loadMore}>{busy ? 'Loading…' : 'Show more searches'}</button></div>}
  </section>;
}

function SavedThumb({ product }: { product: SearchProduct }) {
  const [failed, setFailed] = useState(false);
  const image = product.imageUrl && /^https?:\/\//i.test(product.imageUrl) ? product.imageUrl : undefined;
  const showImage = image && !failed;
  return <span className={`grid h-12 w-12 shrink-0 place-items-center overflow-hidden rounded-lg border border-[var(--line)] text-[var(--accent)] ${showImage ? 'bg-white' : 'bg-[var(--sage)]'}`} aria-hidden="true">
    {showImage ? <img src={image} alt="" referrerPolicy="no-referrer" loading="lazy" className="h-full w-full object-contain p-1" onError={() => setFailed(true)} /> : <Icon name="heart" size={18} />}
  </span>;
}

export function SavedForLater({ data, busy, error }: { data: PersonalData | null; busy: boolean; error: string }) {
  return <section className={card} aria-labelledby="saved-title">
    <PanelHeader id="saved-title" title="Saved for later" action={<a href="/saved" className="inline-flex items-center gap-1 text-[13px] font-semibold text-[var(--accent)] hover:underline">View all <Icon name="arrow" size={14} /></a>} />
    {busy && !data && <ul className="divide-y divide-[var(--line)]"><RowSkeleton /><RowSkeleton /></ul>}
    {!data && !busy && error && <p className="px-5 py-8 text-center text-[13px] text-[var(--muted)]">Saved products are unavailable right now.</p>}
    {data && !data.savedProducts.length && <EmptyState icon="heart" title="Nothing saved yet" body="Tap the heart on any search result to keep it here." href="/search" cta="Explore products" />}
    {!!data?.savedProducts.length && <>
      <ul className="divide-y divide-[var(--line)]">{data.savedProducts.map(item => <li key={item.id}>
        <a href="/saved" className="flex items-center gap-3 px-5 py-3 hover:bg-[var(--paper)]">
          <SavedThumb product={item.product} />
          <span className="min-w-0 flex-1">
            <span className="line-clamp-2 text-[13.5px] font-semibold leading-snug">{item.product.title}</span>
            <span className="mt-0.5 block text-[13px] font-semibold text-[var(--accent)]">{productPrice(item.product, 'Price unavailable')}</span>
          </span>
        </a>
      </li>)}</ul>
      <p className="border-t border-[var(--line)] px-5 py-2.5 text-[12px] text-[var(--muted)]">Prices are from when you saved each item.</p>
    </>}
  </section>;
}

export function CollectionsCard({ collections, loading }: { collections: ProductCollection[] | undefined; loading: boolean }) {
  return <section className={card} aria-labelledby="collections-title">
    <PanelHeader id="collections-title" title="Recent collections" action={<a href="/collections" className="inline-flex items-center gap-1 text-[13px] font-semibold text-[var(--accent)] hover:underline">Manage <Icon name="arrow" size={14} /></a>} />
    <div className="px-5 py-4">
      {loading && !collections && <div className="flex gap-2"><Skeleton className="h-8 w-24 rounded-full" /><Skeleton className="h-8 w-20 rounded-full" /></div>}
      {collections && !collections.length && <p className="text-[13px] text-[var(--muted)]">Group saved products into <a href="/collections" className="font-semibold text-[var(--accent)] hover:underline">collections</a> to plan a purchase.</p>}
      {!!collections?.length && <div className="flex flex-wrap gap-2">{collections.map(item => <a key={item.id} href="/collections" className={ghostButton}><Icon name="folder" size={14} />{item.name}<span className="text-[var(--muted)]">{item.productIds.length}</span></a>)}</div>}
      <a href="/preferences" className="mt-4 flex items-center gap-3 rounded-xl bg-[var(--sage)] px-3.5 py-3 text-[13px] hover:opacity-90">
        <Icon name="sliders" size={17} className="text-[var(--accent)]" />
        <span className="flex-1">Set your budget, brands and default search source</span>
        <Icon name="arrow" size={14} />
      </a>
    </div>
  </section>;
}
