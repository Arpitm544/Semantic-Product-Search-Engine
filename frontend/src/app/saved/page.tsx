'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth, UserButton } from '@clerk/nextjs';
import ThemeToggle from '@/components/ThemeToggle';
import { API_BASE, readJsonResponse, requireResponseOk, useAuthenticatedFetch } from '@/lib/api';
import type { SearchProduct } from '@/lib/types';
import { productPrice, safeProductUrl } from '@/lib/account';

type SavedItem = { id: string; source: string; product: SearchProduct; savedAt: string };
function mergeSavedItems(old: SavedItem[], incoming: SavedItem[], offset: number) {
  if (!offset) return incoming;
  return [...old, ...incoming.filter(item => !old.some(existing => existing.id === item.id))];
}

function errorMessage(reason: unknown) {
  return reason instanceof Error ? reason.message : 'Please try again.';
}

type SavedState = {
  request: ReturnType<typeof useAuthenticatedFetch>;
  userId: ReturnType<typeof useAuth>['userId'];
  owner: React.RefObject<ReturnType<typeof useAuth>['userId']>;
  sequence: React.RefObject<number>;
  setBusy: React.Dispatch<React.SetStateAction<boolean>>;
  setError: React.Dispatch<React.SetStateAction<string>>;
  setLoadedOwner: React.Dispatch<React.SetStateAction<ReturnType<typeof useAuth>['userId']>>;
  setItems: React.Dispatch<React.SetStateAction<SavedItem[]>>;
  setMore: React.Dispatch<React.SetStateAction<boolean>>;
  setRemoving: React.Dispatch<React.SetStateAction<string | null>>;
};
function useSavedLoad({ request, userId, owner, sequence, setBusy, setError, setLoadedOwner, setItems, setMore }: SavedState) {
  const load = useCallback(async (offset = 0) => {
    const current = ++sequence.current;
    const isCurrent = () => current === sequence.current && owner.current === userId;
    setBusy(true); setError('');
    try {
      const response = await request(`${API_BASE}/api/saved-products?offset=${offset}`);
      const data = await readJsonResponse<{ items: SavedItem[]; hasMore: boolean }>(response, 'Could not load your saved products. Please try again.');
      if (!isCurrent()) return;
      setLoadedOwner(userId);
      setItems(old => mergeSavedItems(old, data.items, offset));
      setMore(data.hasMore);
    } catch (reason) { if (isCurrent()) setError(errorMessage(reason)); }
    finally { if (isCurrent()) setBusy(false); }
  }, [request, userId]);
  return load;
}
function useSavedRemove({ request, userId, owner, sequence, setError, setItems, setRemoving }: SavedState) {
  async function remove(id: string) {
    sequence.current++;
    setRemoving(id); setError('');
    try {
      const response = await request(`${API_BASE}/api/saved-products/${id}`, { method: 'DELETE' });
      requireResponseOk(response, 'Could not remove this product. Please try again.');
      if (owner.current === userId) setItems(old => old.filter(item => item.id !== id));
    } catch (reason) { if (owner.current === userId) setError(errorMessage(reason)); }
    finally { if (owner.current === userId) setRemoving(null); }
  }
  return remove;
}
function useSavedProducts() {
  const request = useAuthenticatedFetch();
  const { userId, isLoaded } = useAuth();
  const owner = useRef(userId); owner.current = userId;
  const sequence = useRef(0);
  const [loadedOwner, setLoadedOwner] = useState(userId);
  const [items, setItems] = useState<SavedItem[]>([]);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(true);
  const [removing, setRemoving] = useState<string | null>(null);
  const [error, setError] = useState('');
  const state = { request, userId, owner, sequence, setBusy, setError, setLoadedOwner, setItems, setMore, setRemoving };
  const load = useSavedLoad(state);
  const remove = useSavedRemove(state);
  useEffect(() => { setItems([]); setMore(false); setRemoving(null); setError(''); setBusy(!isLoaded || !!userId); if (isLoaded && userId) void load(); return () => { sequence.current++; }; }, [load, isLoaded, userId]);
  return { items: loadedOwner === userId ? items : [], more, busy, removing, error, load, remove };
}

function savedSourceLabel(source: string, product: SearchProduct) {
  if (source === 'serpapi') return product.merchant || 'Google Shopping';
  return 'Product catalog';
}

function SavedProductCard({ item, disabled, removing, remove }: {
  item: SavedItem;
  disabled: boolean;
  removing: boolean;
  remove: (id: string) => Promise<void>;
}) {
  const { id, product, source, savedAt } = item;
  const url = safeProductUrl(product.url);
  return <li className="flex flex-col gap-3 rounded-2xl border border-[var(--line)] p-5">
    <span className="text-xs uppercase opacity-60">{savedSourceLabel(source, product)}</span>
    <h2 className="text-lg font-semibold">{product.title}</h2>
    <p className="text-sm">{productPrice(product, 'Price unavailable')}</p>
    <p className="text-xs opacity-60">Saved {new Date(savedAt).toLocaleDateString()}</p>
    <div className="mt-auto flex items-center justify-between gap-4">
      {url ? <a href={url} target="_blank" rel="noopener noreferrer" className="text-sm underline">View product ↗</a> : <span className="text-xs opacity-60">Saved from the catalog</span>}
      <button disabled={disabled} onClick={() => remove(id)} className="rounded-full border border-current px-4 py-2 text-sm disabled:opacity-50">{removing ? 'Removing…' : 'Remove'}</button>
    </div>
  </li>;
}

type SavedProductsState = ReturnType<typeof useSavedProducts>;
function SavedProductsEmpty({ state }: { state: SavedProductsState }) {
  const { busy, error, items } = state;
  if (busy) return null;
  if (error) return null;
  if (items.length) return null;
  return <div className="rounded-2xl border border-[var(--line)] p-10 text-center"><p>No saved products yet.</p><a href="/search" className="mt-4 inline-block underline">Find your first good find →</a></div>;
}

function SavedProductsError({ state }: { state: SavedProductsState }) {
  const { error, load } = state;
  return <>
    {error && <div role="alert" className="my-4 rounded-lg border border-current p-4">{error} <button onClick={() => load()} className="underline">Retry</button></div>}</>;
}

export default function SavedProductsPage() {
  const state = useSavedProducts();
  const { items, more, busy, removing, load, remove } = state;
  return <main className="min-h-screen bg-[var(--paper)] text-[var(--ink)] px-5 py-6">
    <header className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 border-b border-[var(--line)] pb-5">
      <a href="/" className="text-xl font-bold">✳ semantic.</a>
      <nav className="flex flex-wrap items-center gap-4 text-sm"><a href="/search">Search</a><a href="/dashboard">Dashboard</a><a href="/collections">Collections</a><a href="/comparisons">Compare</a><a href="/alerts">Price alerts</a><ThemeToggle /><UserButton /></nav>
    </header>
    <section className="mx-auto max-w-5xl py-10">
      <h1 className="text-4xl font-semibold">Your saved products</h1>
      <p className="mt-3 mb-8 text-sm opacity-70">Good finds, kept together. Prices reflect when you saved them and may change.</p>
      <SavedProductsError state={state} />
      <SavedProductsEmpty state={state} />
      <ul className="grid gap-4 sm:grid-cols-2">
        {items.map(item => <SavedProductCard key={item.id} item={item} disabled={removing !== null || busy} removing={removing === item.id} remove={remove} />)}
      </ul>
      {busy && <p role="status" className="py-6">Loading saved products…</p>}
      {more && !busy && <button onClick={() => load(items.length)} className="mt-6 rounded-full border border-current px-5 py-2">Load more</button>}
    </section>
  </main>;
}
