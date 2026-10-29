'use client';
import { useEffect, useState } from 'react';
import { API_BASE, useAuthenticatedFetch } from '@/lib/api';
import type { SearchProduct } from '@/lib/types';

type SaveProductProps = { product: SearchProduct; source: 'mongo' | 'serpapi' };

function productIdentity(product: SearchProduct) {
  return String(product.id ?? product.url ?? `${product.title}:${product.merchant || ''}`);
}

function savedProductUpdate(saved: boolean, id: string, snapshot: SaveProductProps & { identity: string }) {
  if (saved) return { path: `/${id}`, options: { method: 'DELETE', headers: { 'Content-Type': 'application/json' } } };
  return { path: '', options: { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(snapshot) } };
}

function useSaveProduct({ product, source }: SaveProductProps) {
  const request = useAuthenticatedFetch();
  const identity = productIdentity(product);
  const [saved, setSaved] = useState(false);
  const [id, setId] = useState('');
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  useSavedStatus(request, source, identity, setBusy, setError, setId, setSaved);
  async function toggle() {
    setBusy(true); setError('');
    try {
      const update = savedProductUpdate(saved, id, { source, identity, product });
      const response = await request(`${API_BASE}/api/saved-products${update.path}`, update.options);
      if (!response.ok) throw new Error('Could not update saved products. Please try again.');
      const data = await response.json();
      setSaved(data.saved); if (data.id) setId(data.id);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setBusy(false); }
  }
  return { saved, busy, error, toggle };
}

function useSavedStatus(
  request: ReturnType<typeof useAuthenticatedFetch>, source: SaveProductProps['source'], identity: string,
  setBusy: (value: boolean) => void, setError: (value: string) => void,
  setId: (value: string) => void, setSaved: (value: boolean) => void,
) {
  useEffect(() => {
    let active = true;
    setBusy(true); setError(''); setId(''); setSaved(false);
    request(`${API_BASE}/api/saved-products/status?${new URLSearchParams({ source, identity })}`)
      .then(async response => { if (!response.ok) throw new Error('Could not check saved status.'); return response.json(); })
      .then(data => { if (active) { setSaved(data.saved); setId(data.id); } })
      .catch(() => { if (active) setError('Saved status unavailable. You can retry saving.'); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [request, identity, source, setBusy, setError, setId, setSaved]);
}

export default function SaveProductButton(props: SaveProductProps) {
  const { saved, busy, error, toggle } = useSaveProduct(props);
  const { product } = props;
  return <div className="flex flex-col items-start gap-1">
    <button type="button" onClick={toggle} disabled={busy} aria-pressed={saved} aria-label={`${saved ? 'Remove' : 'Save'} ${product.title}`} className="rounded-full border border-current px-3 py-2 text-xs disabled:opacity-50 hover:opacity-75">
      <span aria-hidden="true">{saved ? '♥' : '♡'}</span> {busy ? 'Updating…' : saved ? 'Saved' : 'Save'}
    </button>
    {error && <span role="alert" className="max-w-48 text-xs">{error}</span>}
  </div>;
}
