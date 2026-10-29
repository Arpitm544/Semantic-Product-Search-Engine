'use client';
import { useEffect, useState } from 'react';
import { API_BASE, useAuthenticatedFetch } from '@/lib/api';
import type { SearchProduct } from '@/lib/types';

export default function SaveProductButton({ product, source }: { product: SearchProduct; source: 'mongo' | 'serpapi' }) {
  const request = useAuthenticatedFetch();
  const identity = String(product.id ?? product.url ?? `${product.title}:${product.merchant || ''}`);
  const [saved, setSaved] = useState(false);
  const [id, setId] = useState('');
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setBusy(true); setError(''); setId(''); setSaved(false);
    request(`${API_BASE}/api/saved-products/status?${new URLSearchParams({ source, identity })}`)
      .then(async response => { if (!response.ok) throw new Error('Could not check saved status.'); return response.json(); })
      .then(data => { if (active) { setSaved(data.saved); setId(data.id); } })
      .catch(() => { if (active) setError('Saved status unavailable. You can retry saving.'); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [request, identity, source]);
  async function toggle() {
    setBusy(true); setError('');
    try {
      const response = await request(`${API_BASE}/api/saved-products${saved ? `/${id}` : ''}`, {
        method: saved ? 'DELETE' : 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: saved ? undefined : JSON.stringify({ source, identity, product }),
      });
      if (!response.ok) throw new Error('Could not update saved products. Please try again.');
      const data = await response.json();
      setSaved(data.saved); if (data.id) setId(data.id);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Please try again.'); }
    finally { setBusy(false); }
  }
  return <div className="flex flex-col items-start gap-1">
    <button type="button" onClick={toggle} disabled={busy} aria-pressed={saved} aria-label={`${saved ? 'Remove' : 'Save'} ${product.title}`} className="rounded-full border border-current px-3 py-2 text-xs disabled:opacity-50 hover:opacity-75">
      <span aria-hidden="true">{saved ? '♥' : '♡'}</span> {busy ? 'Updating…' : saved ? 'Saved' : 'Save'}
    </button>
    {error && <span role="alert" className="max-w-48 text-xs">{error}</span>}
  </div>;
}
