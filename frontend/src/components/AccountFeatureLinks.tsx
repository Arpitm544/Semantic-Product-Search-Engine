'use client';
import { useEffect } from 'react';
import { useAccountResource, type ProductCollection } from '@/lib/account';
import { accountButton, accountPanel } from './AccountShell';
import { ResourceStatus } from './AccountControls';
interface Overview { collectionCount: number; comparisonCount: number; activeAlertCount: number; unreadAlertCount: number; collections: ProductCollection[] }
export default function AccountFeatureLinks() {
  const resource = useAccountResource<Overview>('/api/account-overview');
  useEffect(() => { const timer = setInterval(() => { if (document.visibilityState === 'visible' && !resource.busy) void resource.reload(); }, 60000); return () => clearInterval(timer); }, [resource.reload, resource.busy]);
  const data = resource.data;
  return <section className="mb-8 space-y-4" aria-label="Your collections and alerts">
    <div className="grid gap-4 sm:grid-cols-2 min-[1200px]:grid-cols-4">{[
      ['/collections', 'Collections', data?.collectionCount], ['/comparisons', 'Saved comparisons', data?.comparisonCount],
      ['/alerts', 'Active price alerts', data?.activeAlertCount], ['/alerts#notification-title', 'Unread price drops', data?.unreadAlertCount],
    ].map(([url, label, count]) => <a key={String(url)} href={String(url)} className={accountPanel}><span className="text-xs opacity-65">{label}</span><strong className="mt-2 block text-2xl">{count ?? '—'}</strong></a>)}</div>
    <ResourceStatus busy={resource.busy} error={resource.error} retry={resource.reload} />
    {!!data?.collections.length && <div className="flex flex-wrap items-center gap-3"><span className="text-xs opacity-65">Your recent collections:</span>{data.collections.map(item => <a key={item.id} className={accountButton} href="/collections">{item.name}</a>)}</div>}
    <a href="/preferences" className="inline-block text-xs underline underline-offset-4">Manage your budget, brands, and search preferences →</a>
  </section>;
}
