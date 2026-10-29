'use client';
import { useEffect, useState } from 'react';
import AccountShell, { accountButton, accountInput, accountPanel } from '@/components/AccountShell';
import { ConfirmDelete, ResourceStatus, SavedProductPicker } from '@/components/AccountControls';
import { accountError, useAccountResource, productPrice, safeProductUrl, type Comparison, type Page } from '@/lib/account';
import type { SearchProduct } from '@/lib/types';

function ComparisonTable({ comparison }: { comparison: Comparison }) {
  const detail = (value: unknown): string => value == null || value === '' ? 'Unavailable' : Array.isArray(value) ? value.join(' · ') || 'Unavailable' : String(value);
  const rows: [string, (product: SearchProduct) => string][] = [
    ['Saved price', productPrice], ['Brand', p => detail(p.brand)], ['Category', p => detail(p.category)],
    ['Rating', p => p.rating == null ? 'Unavailable' : `${p.rating} / 5`], ['Reviews', p => detail(p.reviews)],
    ['Stock', p => detail(p.stock)], ['Merchant', p => detail(p.merchant)],
    ['Specifications', p => detail(p.attributes)], ['Description', p => detail(p.description)],
  ];
  return <div className="mt-5 overflow-x-auto"><table className="w-full min-w-[600px] table-fixed border-collapse text-left text-sm"><caption className="mb-4 text-left text-xs opacity-65">Saved snapshots. Prices can change; currencies and product categories may differ. Missing details are shown as unavailable.</caption><thead><tr><th scope="col" className="w-32 border-b border-[var(--line)] p-3">Details</th>{comparison.products.map(item => <th key={item.savedId} scope="col" className="min-w-48 border-b border-[var(--line)] p-3 align-top"><p className="break-words">{item.product.title}</p><p className="mt-2 text-xs font-normal opacity-60">{item.source === 'mongo' ? 'Catalog' : 'Google Shopping'}</p>{safeProductUrl(item.product.url) && <a className="mt-2 inline-block text-xs font-normal underline" href={safeProductUrl(item.product.url)} target="_blank" rel="noopener noreferrer">View current offer ↗</a>}</th>)}</tr></thead><tbody>{rows.map(([label, value]) => <tr key={label}><th scope="row" className="border-b border-[var(--line)] p-3 align-top font-medium">{label}</th>{comparison.products.map(item => <td className="break-words border-b border-[var(--line)] p-3 align-top" key={item.savedId}>{value(item.product)}</td>)}</tr>)}</tbody></table></div>;
}
function SavedComparison({ item, busy, rename, remove }: { item: Comparison; busy: boolean; rename: (id: string, name: string) => void; remove: (id: string) => void }) {
  const [name, setName] = useState(item.name);
  return <article className={accountPanel}><form className="flex flex-wrap items-center gap-3" onSubmit={e => { e.preventDefault(); rename(item.id, name); }}><label className="min-w-48 flex-1 text-sm">Comparison name<input required maxLength={100} className={`${accountInput} mt-2`} value={name} onChange={e => setName(e.target.value)} /></label><button disabled={busy || !name.trim()} className={accountButton}>Rename</button></form><ComparisonTable comparison={item} /><div className="mt-5"><ConfirmDelete disabled={busy} description="Delete this saved comparison? Your wishlist products will stay." onConfirm={() => remove(item.id)} /></div></article>;
}
function useComparisons() {
  const resource = useAccountResource<Page<Comparison>>('/api/comparisons');
  const [selected, setSelected] = useState<string[]>([]);
  const [name, setName] = useState('');
  const [extra, setExtra] = useState<Comparison[]>([]);
  const [more, setMore] = useState<boolean | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  useEffect(() => { setExtra([]); setMore(null); }, [resource.data]);
  const all = [...(resource.data?.items || []), ...extra].filter((item, i, list) => list.findIndex(other => other.id === item.id) === i);
  async function create(event: React.FormEvent) {
    event.preventDefault();
    const result = await resource.mutate(() => resource.api('/api/comparisons', { method: 'POST', body: JSON.stringify({ name, savedIds: selected }) }), 'Comparison saved.');
    if (result) { setName(''); setSelected([]); setExtra([]); setMore(null); }
  }
  async function loadMore() {
    setLoadingMore(true);
    try { const page = await resource.api<Page<Comparison>>(`/api/comparisons?offset=${all.length}`); setExtra(old => [...old, ...page.items]); setMore(page.hasMore); }
    catch (reason) { resource.setError(accountError(reason, 'Could not load comparisons.')); }
    finally { setLoadingMore(false); }
  }
  return { resource, selected, setSelected, name, setName, setExtra, more, loadingMore, all, create, loadMore };
}

function ComparisonForm({ state }: { state: ReturnType<typeof useComparisons> }) {
  const { resource, selected, setSelected, name, setName, create } = state;
  return <form onSubmit={create} className={`${accountPanel} mb-6`}><label className="text-sm">Comparison name<input required maxLength={100} className={`${accountInput} mt-2`} placeholder="Headphones for commuting" value={name} onChange={e => setName(e.target.value)} /></label><SavedProductPicker selected={selected} onChange={setSelected} disabled={resource.busy} /><button className={accountButton} disabled={resource.busy || selected.length < 2 || !name.trim()}>Save comparison</button></form>;
}

export default function ComparisonsPage() {
  const state = useComparisons();
  const { resource, setExtra, more, loadingMore, all, loadMore } = state;
  return <AccountShell active="/comparisons" title="Your saved comparisons" description="Keep two to four shortlisted products side by side. Comparisons keep their snapshots even if you later remove a product from your wishlist.">
    <ComparisonForm state={state} />
    <ResourceStatus busy={resource.busy} error={resource.error} notice={resource.notice} retry={resource.reload} />
    {!resource.busy && !all.length && <p className={`${accountPanel} text-sm opacity-70`}>Choose at least two saved products to create your first comparison.</p>}
    <div className="space-y-6">{all.map(item => <SavedComparison key={item.id} item={item} busy={resource.busy} rename={(id, value) => resource.mutate(() => resource.api(`/api/comparisons/${id}`, { method: 'PATCH', body: JSON.stringify({ name: value }) }), 'Comparison renamed.')} remove={async id => { const result = await resource.mutate(() => resource.api(`/api/comparisons/${id}`, { method: 'DELETE' }), 'Comparison deleted.'); if (result) setExtra(old => old.filter(item => item.id !== id)); }} />)}</div>
    {(more ?? resource.data?.hasMore) && <button className={`${accountButton} mt-6`} disabled={resource.busy || loadingMore} onClick={loadMore}>{loadingMore ? 'Loading…' : 'Load more comparisons'}</button>}
  </AccountShell>;
}
