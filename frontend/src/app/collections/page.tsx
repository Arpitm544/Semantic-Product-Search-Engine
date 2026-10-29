'use client';
import { useEffect, useState } from 'react';
import AccountShell, { accountButton, accountInput, accountPanel } from '@/components/AccountShell';
import { ConfirmDelete, ResourceStatus, SavedProductPicker } from '@/components/AccountControls';
import { useAccountResource, productPrice, type ProductCollection, type Page } from '@/lib/account';

export default function CollectionsPage() {
  const resource = useAccountResource<Page<ProductCollection>>('/api/collections');
  const { api, data, busy } = resource;
  const [name, setName] = useState('');
  const [active, setActive] = useState('');
  const [detail, setDetail] = useState<ProductCollection | null>(null);
  const [detailError, setDetailError] = useState('');
  const [rename, setRename] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [extra, setExtra] = useState<ProductCollection[]>([]);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  useEffect(() => { if (data) { setExtra([]); setHasMore(data.hasMore); } }, [data]);
  useEffect(() => {
    let live = true;
    setDetail(null); setDetailError(''); setSelected([]);
    if (active) api<ProductCollection>(`/api/collections/${active}`).then(result => { if (live) { setDetail(result); setRename(result.name); } }).catch(reason => { if (live) setDetailError(reason.message); });
    return () => { live = false; };
  }, [api, active, data]);
  async function create(event: React.FormEvent) {
    event.preventDefault();
    const created = await resource.mutate(() => api<ProductCollection>('/api/collections', { method: 'POST', body: JSON.stringify({ name }) }), 'Collection created.');
    if (created) { setName(''); setActive(created.id); }
  }
  async function addProducts() {
    const success = await resource.mutate(async () => { for (const id of selected) await api(`/api/collections/${active}/products/${id}`, { method: 'PUT' }); return true; }, 'Products added to your collection.');
    if (success) setSelected([]);
  }
  async function more() {
    setLoadingMore(true);
    try {
      const page = await api<Page<ProductCollection>>(`/api/collections?offset=${(data?.items.length || 0) + extra.length}`);
      setExtra(old => [...old, ...page.items]); setHasMore(page.hasMore);
    } catch (reason) { resource.setError(reason instanceof Error ? reason.message : 'Could not load collections.'); }
    finally { setLoadingMore(false); }
  }
  return <AccountShell active="/collections" title="Your collections" description="Bring related finds together, from college essentials to your next workspace. Removing a collection keeps the products in your wishlist.">
    <form onSubmit={create} className={`${accountPanel} mb-6 flex flex-wrap items-end gap-3`}><label className="min-w-48 flex-1 text-sm">Collection name<input required maxLength={100} value={name} onChange={e => setName(e.target.value)} className={`${accountInput} mt-2`} placeholder="College essentials" /></label><button disabled={busy || !name.trim()} className={accountButton}>Create collection</button></form>
    <ResourceStatus busy={busy} error={resource.error} notice={resource.notice} retry={resource.reload} />
    <div className="grid items-start gap-6 md:grid-cols-[240px_1fr]">
      <aside className={`${accountPanel} space-y-3`} aria-label="Your collections">{!busy && !data?.items.length && <p className="text-sm opacity-70">Create your first collection above.</p>}{[...(data?.items || []), ...extra].map(item => <button key={item.id} className={`${accountButton} block w-full break-words text-left ${item.id === active ? 'bg-[var(--sage)]' : ''}`} onClick={() => setActive(item.id)}>{item.name}</button>)}{hasMore && <button disabled={busy || loadingMore} className={accountButton} onClick={more}>Load more collections</button>}</aside>
      <section className={accountPanel}>{!active && <p className="text-sm opacity-70">Choose a collection to organize its products.</p>}{active && !detail && !detailError && <p role="status">Loading collection…</p>}{detailError && <p role="alert">{detailError}</p>}
        {detail && <><form className="flex flex-wrap items-end gap-3" onSubmit={async e => { e.preventDefault(); await resource.mutate(() => api(`/api/collections/${active}`, { method: 'PATCH', body: JSON.stringify({ name: rename }) }), 'Collection renamed.'); }}><label className="min-w-40 flex-1 text-sm">Name<input required maxLength={100} className={`${accountInput} mt-2`} value={rename} onChange={e => setRename(e.target.value)} /></label><button disabled={busy || !rename.trim()} className={accountButton}>Rename</button></form>
          <p className="my-4 text-xs opacity-65">{detail.items?.length || 0} saved products · up to 100 per collection</p>
          <ul className="divide-y divide-[var(--line)]">{detail.items?.map(item => <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-4"><div className="min-w-0 flex-1"><h2 className="text-sm font-semibold">{item.product.title}</h2><p className="mt-1 text-xs opacity-65">{productPrice(item.product)}</p></div><button disabled={busy} className={accountButton} onClick={() => resource.mutate(() => api(`/api/collections/${active}/products/${item.id}`, { method: 'DELETE' }), 'Product removed from this collection.')}>Remove from collection</button></li>)}</ul>
          <SavedProductPicker selected={selected} onChange={setSelected} max={10} disabled={busy} /><button className={accountButton} disabled={busy || !selected.length} onClick={addProducts}>Add selected products</button>
          <div className="mt-6 border-t border-[var(--line)] pt-5"><ConfirmDelete disabled={busy} description="Delete this collection? Your saved products will stay in your wishlist." onConfirm={async () => { const result = await resource.mutate(() => api(`/api/collections/${active}`, { method: 'DELETE' }), 'Collection deleted.'); if (result) setActive(''); }} /></div>
        </>}
      </section>
    </div>
  </AccountShell>;
}
