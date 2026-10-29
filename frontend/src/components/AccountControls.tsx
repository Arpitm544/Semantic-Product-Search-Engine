'use client';
import { useAuth } from '@clerk/nextjs';
import { useEffect, useState } from 'react';
import { useAccountApi, type SavedItem, type Page } from '@/lib/account';
import { accountButton, accountPanel } from './AccountShell';

export function ResourceStatus({ busy, error, notice, retry }: { busy: boolean; error: string; notice?: string; retry: () => void }) {
  return <>{busy && <p role="status" className="my-4 text-sm opacity-70">Loading…</p>}{notice && <p role="status" className="my-4 text-sm">{notice}</p>}{error && <div role="alert" className={`${accountPanel} my-4 flex flex-wrap items-center justify-between gap-3`}><p>{error}</p><button disabled={busy} className={accountButton} onClick={retry}>Retry</button></div>}</>;
}
export function ConfirmDelete({ label = 'Delete', description, disabled, onConfirm }: { label?: string; description: string; disabled?: boolean; onConfirm: () => void }) {
  const [confirming, setConfirming] = useState(false);
  if (!confirming) return <button className={accountButton} disabled={disabled} onClick={() => setConfirming(true)}>{label}</button>;
  return <div className="rounded-xl border border-[var(--line)] p-3"><p className="mb-3 text-sm">{description}</p><div className="flex flex-wrap gap-2"><button disabled={disabled} className={accountButton} onClick={() => { onConfirm(); setConfirming(false); }}>Confirm {label.toLowerCase()}</button><button className={accountButton} disabled={disabled} onClick={() => setConfirming(false)}>Cancel</button></div></div>;
}
function mergeSavedItems(previous: SavedItem[], incoming: SavedItem[], reset: boolean) {
  if (reset) return incoming;
  const ids = new Set(previous.map(item => item.id));
  return [...previous, ...incoming.filter(item => !ids.has(item.id))];
}
function useSavedPickerItems() {
  const api = useAccountApi();
  const { userId, isLoaded } = useAuth();
  const [items, setItems] = useState<SavedItem[]>([]);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setItems([]); setError(''); setBusy(true);
    if (!isLoaded || !userId) return () => { active = false; };
    api<Page<SavedItem>>('/api/saved-products').then(result => { if (active) { setItems(result.items); setMore(result.hasMore); } })
      .catch(reason => { if (active) setError(reason.message); }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [api, isLoaded, userId]);
  async function loadMore(reset = false) {
    setBusy(true); setError('');
    try { const result = await api<Page<SavedItem>>(`/api/saved-products?offset=${reset ? 0 : items.length}`); setItems(old => mergeSavedItems(old, result.items, reset)); setMore(result.hasMore); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load products.'); }
    finally { setBusy(false); }
  }
  return { items, more, busy, error, loadMore };
}
function SavedChoice({ item, selected, onChange, max, disabled }: { item: SavedItem; selected: string[]; onChange: (value: string[]) => void; max: number; disabled: boolean }) {
  const checked = selected.includes(item.id);
  const atLimit = !checked && selected.length >= max;
  return <label className="flex items-start gap-3 text-sm"><input type="checkbox" className="mt-1" checked={checked} disabled={disabled || atLimit} onChange={event => onChange(event.target.checked ? [...selected, item.id] : selected.filter(id => id !== item.id))} /><span className="min-w-0 break-words">{item.product.title}<small className="block opacity-60">{item.source === 'mongo' ? 'Catalog' : item.product.merchant || 'Google Shopping'}</small></span></label>;
}
export function SavedProductPicker({ selected, onChange, max = 4, disabled = false }: { selected: string[]; onChange: (value: string[]) => void; max?: number; disabled?: boolean }) {
  const { items, more, busy, error, loadMore } = useSavedPickerItems();
  return <fieldset disabled={disabled} className="my-4 min-w-0 rounded-xl border border-[var(--line)] p-4"><legend className="px-2 text-sm font-semibold">Choose saved products ({selected.length}/{max})</legend>
    <ResourceStatus busy={busy} error={error} retry={() => { void loadMore(true); }} />
    {!busy && !error && !items.length && <p className="text-sm">Save products from <a className="underline" href="/search">search results</a> first.</p>}
    <div className="max-h-64 space-y-3 overflow-y-auto">{items.map(item => <SavedChoice key={item.id} item={item} selected={selected} onChange={onChange} max={max} disabled={disabled} />)}</div>
    {more && <button type="button" className={`${accountButton} mt-4`} disabled={busy} onClick={() => loadMore()}>Load more saved products</button>}
  </fieldset>;
}
