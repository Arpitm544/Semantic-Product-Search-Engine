'use client';
import { useEffect, useRef, useState } from 'react';
import { useAuth } from '@clerk/nextjs';
import AccountShell, { accountButton, accountInput, accountPanel } from '@/components/AccountShell';
import { ConfirmDelete, ResourceStatus, SavedProductPicker } from '@/components/AccountControls';
import { useAccountResource, safeProductUrl, type Page } from '@/lib/account';

interface Alert { id: string; title: string; currency: string; baselinePrice: number; targetPrice: number; currentPrice: number | null; enabled: boolean; status: string; message?: string; lastCheckedAt: string | null; nextCheckAt: string }
interface Notification { id: string; title: string; price: number; previousPrice: number; currency: string; read: boolean; createdAt: string; url?: string }
interface AlertPage extends Page<Alert> { intervalSeconds: number; schedulerEnabled: boolean }
interface Eligibility { eligible: boolean; price: { amount: number; currency: string } | null; reason: string | null }
export default function AlertsPage() {
  const alerts = useAccountResource<AlertPage>('/api/price-alerts');
  const notifications = useAccountResource<Page<Notification>>('/api/notifications');
  const [selected, setSelected] = useState<string[]>([]);
  const [eligibility, setEligibility] = useState<Eligibility | null>(null);
  const [eligibilityError, setEligibilityError] = useState('');
  const [target, setTarget] = useState('');
  const [extraAlerts, setExtraAlerts] = useState<Alert[]>([]);
  const [extraNotifications, setExtraNotifications] = useState<Notification[]>([]);
  const [moreAlerts, setMoreAlerts] = useState<boolean | null>(null);
  const [moreNotifications, setMoreNotifications] = useState<boolean | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const { userId } = useAuth();
  const owner = useRef(userId); owner.current = userId;
  const visibleCounts = useRef({ alerts: 50, notifications: 50 });
  const polling = useRef(false);
  const refreshVersion = useRef(0);
  useEffect(() => { refreshVersion.current++; }, [alerts.data, notifications.data]);
  useEffect(() => { setExtraAlerts([]); setExtraNotifications([]); setMoreAlerts(null); setMoreNotifications(null); }, [userId]);
  useEffect(() => {
    let live = true;
    const timer = setInterval(async () => {
      if (document.visibilityState !== 'visible' || alerts.busy || notifications.busy || loadingMore || polling.current) return;
      polling.current = true;
      const version = refreshVersion.current;
      async function pages<T>(path: string, count: number): Promise<{ first: Page<T>; rest: T[]; more: boolean }> {
        const first = await alerts.api<Page<T>>(path);
        const all = [...first.items]; let more = first.hasMore;
        while (more && all.length < count) {
          const next = await alerts.api<Page<T>>(`${path}?offset=${all.length}`);
          all.push(...next.items); more = next.hasMore;
          if (!next.items.length) break;
        }
        return { first, rest: all.slice(first.items.length), more };
      }
      try {
        const [a, n] = await Promise.all([pages<Alert>('/api/price-alerts', visibleCounts.current.alerts), pages<Notification>('/api/notifications', visibleCounts.current.notifications)]);
        if (!live || owner.current !== userId || refreshVersion.current !== version) return;
        alerts.setError(''); notifications.setError('');
        alerts.setData(a.first as AlertPage); setExtraAlerts(a.rest); setMoreAlerts(a.more);
        notifications.setData(n.first); setExtraNotifications(n.rest); setMoreNotifications(n.more);
      } catch (reason) { if (live && owner.current === userId) alerts.setError(reason instanceof Error ? reason.message : 'Could not refresh alerts.'); }
      finally { polling.current = false; }
    }, 60000);
    return () => { live = false; clearInterval(timer); };
  }, [alerts.api, alerts.busy, notifications.busy, loadingMore, userId]);
  useEffect(() => {
    let live = true; setEligibility(null); setEligibilityError(''); setTarget('');
    if (selected[0]) alerts.api<Eligibility>(`/api/price-alerts/eligibility/${selected[0]}`).then(data => { if (live) setEligibility(data); }).catch(reason => { if (live) setEligibilityError(reason.message); });
    return () => { live = false; };
  }, [alerts.api, selected]);
  async function create(event: React.FormEvent) {
    event.preventDefault();
    const result = await alerts.mutate(() => alerts.api('/api/price-alerts', { method: 'PUT', body: JSON.stringify({ savedId: selected[0], targetPrice: target ? Number(target) : null }) }), 'Price alert enabled. Verified drops will appear below and on your dashboard.');
    if (result) { setSelected([]); setExtraAlerts([]); setMoreAlerts(null); }
  }
  async function check(id: string) {
    await alerts.mutate(() => alerts.api(`/api/price-alerts/${id}/check`, { method: 'POST' }), 'Price check finished.');
    await notifications.reload();
  }
  const alertItems = [...(alerts.data?.items || []), ...extraAlerts].filter((item, i, all) => all.findIndex(other => other.id === item.id) === i);
  const notificationItems = [...(notifications.data?.items || []), ...extraNotifications].filter((item, i, all) => all.findIndex(other => other.id === item.id) === i);
  visibleCounts.current = { alerts: Math.max(50, alertItems.length), notifications: Math.max(50, notificationItems.length) };
  async function loadMore(kind: 'alerts' | 'notifications') {
    setLoadingMore(true);
    try {
      if (kind === 'alerts') { const page = await alerts.api<Page<Alert>>(`/api/price-alerts?offset=${alertItems.length}`); setExtraAlerts(old => [...old, ...page.items]); setMoreAlerts(page.hasMore); }
      else { const page = await notifications.api<Page<Notification>>(`/api/notifications?offset=${notificationItems.length}`); setExtraNotifications(old => [...old, ...page.items]); setMoreNotifications(page.hasMore); }
    } catch (reason) { alerts.setError(reason instanceof Error ? reason.message : 'Could not load more items.'); }
    finally { setLoadingMore(false); }
  }
  return <AccountShell active="/alerts" title="Your price-drop alerts" description="Get private notifications here when a verifiable saved offer becomes cheaper. Check the merchant’s current offer before buying; shipping, stock, and taxes may change.">
    <form onSubmit={create} className={`${accountPanel} mb-6`}><h2 className="text-lg font-semibold">Track a saved product</h2><SavedProductPicker selected={selected} onChange={setSelected} max={1} disabled={alerts.busy} />
      {selected.length > 0 && !eligibility && !eligibilityError && <p role="status" className="my-3 text-sm">Checking whether this offer can be tracked…</p>}
      {eligibilityError && <p role="alert" className="my-3 text-sm">{eligibilityError}</p>}
      {eligibility?.reason && <p role="status" className="my-3 text-sm">{eligibility.reason} Choose a priced product with a stable identity.</p>}
      {eligibility?.eligible && <label className="my-4 block max-w-sm text-sm">Target price in {eligibility.price?.currency} (optional)<input className={`${accountInput} mt-2`} type="number" min="0.01" max={eligibility.price?.amount} step="0.01" placeholder={String(eligibility.price?.amount)} value={target} onChange={e => setTarget(e.target.value)} /><small className="mt-2 block opacity-65">Saved price: {eligibility.price?.currency} {eligibility.price?.amount}. Leave blank to watch for any drop.</small></label>}
      <p className="my-4 text-xs leading-relaxed opacity-65">Checks run about every {alerts.data ? alerts.data.intervalSeconds / 3600 : 6} hours while the backend is running. Google Shopping checks use your configured SerpApi quota. Only the same product, merchant, region, and currency are compared. Offers with unavailable or ambiguous prices cannot be tracked.</p>
      {alerts.data?.schedulerEnabled === false && <p className="my-3 text-sm">Automatic checks are disabled on this server. Scheduled host checks or the Check now action can still run due alerts.</p>}
      <button className={accountButton} disabled={alerts.busy || !eligibility?.eligible}>Enable price alert</button>
    </form>
    <ResourceStatus busy={alerts.busy} error={alerts.error} notice={alerts.notice} retry={alerts.reload} />
    <section className="mb-8" aria-labelledby="watch-title"><h2 id="watch-title" className="mb-4 text-xl font-semibold">Tracked products</h2>{!alerts.busy && !alertItems.length && <p className={`${accountPanel} text-sm`}>No price alerts yet. Select a supported saved product above.</p>}
      <ul className="grid gap-4 md:grid-cols-2">{alertItems.map(item => <li key={item.id} className={accountPanel}><h3 className="font-semibold">{item.title}</h3><p className="my-3 text-sm">Saved: {item.currency} {item.baselinePrice} · Target: {item.currency} {item.targetPrice}</p><p className="text-sm">Last verified price: {item.currentPrice == null ? 'Not checked' : `${item.currency} ${item.currentPrice}`}</p><p className="my-2 text-xs opacity-65">{item.enabled ? item.status === 'price_drop' ? 'Price dropped' : item.status === 'unavailable' ? 'Temporarily unavailable' : item.status === 'pending' ? 'Awaiting first check' : 'Monitoring' : 'Paused'}{item.lastCheckedAt ? ` · Checked ${new Date(item.lastCheckedAt).toLocaleString()}` : ''}</p>{item.message && <p className="my-2 text-xs">{item.message}</p>}<p className="mb-4 text-xs opacity-65">Next check: {new Date(item.nextCheckAt).toLocaleString()}</p>
        <div className="flex flex-wrap gap-2"><button disabled={alerts.busy || !item.enabled || new Date(item.nextCheckAt).getTime() > Date.now()} className={accountButton} onClick={() => check(item.id)}>Check now</button><button className={accountButton} disabled={alerts.busy} onClick={() => alerts.mutate(() => alerts.api(`/api/price-alerts/${item.id}`, { method: 'PATCH', body: JSON.stringify({ enabled: !item.enabled }) }), item.enabled ? 'Alert paused.' : 'Alert resumed.')}>{item.enabled ? 'Pause' : 'Resume'}</button><ConfirmDelete disabled={alerts.busy} description="Remove this price alert? Past notifications will stay." onConfirm={async () => { const result = await alerts.mutate(() => alerts.api(`/api/price-alerts/${item.id}`, { method: 'DELETE' }), 'Alert removed.'); if (result) setExtraAlerts(old => old.filter(row => row.id !== item.id)); }} /></div>
      </li>)}</ul>{(moreAlerts ?? alerts.data?.hasMore) && <button disabled={loadingMore || alerts.busy} className={`${accountButton} mt-4`} onClick={() => loadMore('alerts')}>Load more alerts</button>}
    </section>
    <section aria-labelledby="notification-title"><h2 id="notification-title" className="mb-4 text-xl font-semibold">Price-drop notifications</h2><ResourceStatus busy={notifications.busy} error={notifications.error} notice={notifications.notice} retry={notifications.reload} />
      {!notifications.busy && !notificationItems.length && <p className={`${accountPanel} text-sm`}>Verified price drops will appear here. You will not receive email or SMS messages.</p>}
      <ul className="space-y-4">{notificationItems.map(item => <li className={accountPanel} key={item.id}><p className="mb-2 text-xs font-bold uppercase opacity-65">{item.read ? 'Read' : 'New price drop'}</p><h3 className="font-semibold">{item.title}</h3><p className="my-3 text-sm">{item.currency} {item.previousPrice} → {item.currency} {item.price}</p><p className="mb-3 text-xs opacity-65">Verified {new Date(item.createdAt).toLocaleString()}</p><div className="flex flex-wrap gap-3">{safeProductUrl(item.url) && <a href={safeProductUrl(item.url)} target="_blank" rel="noopener noreferrer" className={accountButton}>View offer ↗</a>}{!item.read && <button disabled={notifications.busy} className={accountButton} onClick={async () => { await notifications.mutate(() => notifications.api(`/api/notifications/${item.id}/read`, { method: 'PATCH' }), 'Notification marked as read.'); setExtraNotifications(old => old.map(row => row.id === item.id ? { ...row, read: true } : row)); }}>Mark as read</button>}</div></li>)}</ul>{(moreNotifications ?? notifications.data?.hasMore) && <button disabled={loadingMore || notifications.busy} className={`${accountButton} mt-4`} onClick={() => loadMore('notifications')}>Load more notifications</button>}
    </section>
  </AccountShell>;
}
