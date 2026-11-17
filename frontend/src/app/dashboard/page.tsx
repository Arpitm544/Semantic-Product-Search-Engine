'use client';
import { useEffect } from 'react';
import DashboardShell from '@/components/dashboard/DashboardShell';
import DashboardLoading from './loading';
import CatalogPanel, { useCatalog } from '@/components/dashboard/CatalogPanel';
import { CollectionsCard, RecentSearches, SavedForLater } from '@/components/dashboard/ActivitySections';
import { Icon, ProblemBanner, StatTile, heading, primaryButton, type Problem } from '@/components/dashboard/ui';
import { useAccountResource, type ProductCollection } from '@/lib/account';
import { usePersonalDashboard } from '@/lib/usePersonalDashboard';

interface Overview { collectionCount: number; comparisonCount: number; activeAlertCount: number; unreadAlertCount: number; collections: ProductCollection[] }

function useOverview() {
  const resource = useAccountResource<Overview>('/api/account-overview');
  const { reload, busy } = resource;
  // Keep price-drop counts fresh while the tab is open.
  useEffect(() => {
    const timer = setInterval(() => { if (document.visibilityState === 'visible' && !busy) void reload(); }, 60000);
    return () => clearInterval(timer);
  }, [reload, busy]);
  return resource;
}

function Greeting({ name }: { name?: string | null }) {
  const today = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
  return <section className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
    <div>
      <p className="text-[13px] text-[var(--muted)]">{today}</p>
      <h1 className={`${heading} mt-1 text-[clamp(26px,3.4vw,34px)] leading-tight`}>{name ? `Welcome back, ${name}` : 'Welcome back'}</h1>
      <p className="mt-1.5 text-[14px] text-[var(--muted)]">Pick up a recent search or revisit something you saved.</p>
    </div>
    <form action="/search" method="get" role="search" className="flex w-full items-center gap-2 rounded-full border border-[var(--line)] bg-[var(--surface-fff)] py-1.5 pl-4 pr-1.5 md:w-[400px]">
      <Icon name="search" size={17} className="text-[var(--muted)]" />
      <input name="q" required placeholder="Describe what you're looking for" aria-label="Search products" className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[var(--muted)]" />
      <button type="submit" className={`${primaryButton} py-2`}>Search</button>
    </form>
  </section>;
}

export default function DashboardPage() {
  const personal = usePersonalDashboard();
  const overview = useOverview();
  const catalog = useCatalog();
  const p = personal.data;
  const o = overview.data;

  const problems: Problem[] = [
    personal.error && { label: 'Your activity', message: personal.error, retry: () => void personal.load() },
    overview.error && { label: 'Your library', message: overview.error, retry: () => void overview.reload() },
    catalog.error && { label: 'The catalog', message: catalog.error, retry: () => void catalog.load() },
  ].filter(Boolean) as Problem[];

  const personalLoading = personal.busy && !p;
  const overviewLoading = overview.busy && !o;

  if (personalLoading && overviewLoading && catalog.busy && !catalog.data) return <DashboardLoading />;

  return <DashboardShell unreadAlerts={o?.unreadAlertCount}>
    <Greeting name={personal.user?.firstName || personal.user?.username} />
    <ProblemBanner problems={problems} busy={personal.busy || overview.busy || catalog.busy} />
    {personal.notice && <p role="status" className="rounded-xl bg-[var(--sage)] px-4 py-2.5 text-[13px]">{personal.notice}</p>}

    <section aria-label="Your numbers" className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      <StatTile href="/saved" icon="heart" label="Saved products" value={p?.savedCount} loading={personalLoading} />
      <StatTile href="#recent-searches" icon="clock" label="Searches" value={p?.searchCount} loading={personalLoading} />
      <StatTile href="/collections" icon="folder" label="Collections" value={o?.collectionCount} loading={overviewLoading} />
      <StatTile href="/comparisons" icon="columns" label="Comparisons" value={o?.comparisonCount} loading={overviewLoading} />
      <StatTile href="/alerts" icon="tag" label="Price alerts" value={o?.activeAlertCount} loading={overviewLoading} />
      <StatTile href="/alerts#notification-title" icon="bell" label="Unread price drops" value={o?.unreadAlertCount} loading={overviewLoading} highlight={!!o?.unreadAlertCount} />
    </section>

    <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-6 lg:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
      <RecentSearches state={personal} />
      <div className="space-y-6">
        <SavedForLater data={p} busy={personal.busy} error={personal.error} />
        <CollectionsCard collections={o?.collections} loading={overview.busy} />
      </div>
    </div>

    <CatalogPanel catalog={catalog} />
  </DashboardShell>;
}
