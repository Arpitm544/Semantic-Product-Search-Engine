'use client';
import { useCallback, useEffect, useState } from 'react';
import { API_BASE, useAuthenticatedFetch } from '@/lib/api';
import { Icon, PanelHeader, Skeleton, card, ghostButton, heading } from '@/components/dashboard/ui';

/** Shape of GET /api/observability (backend/api/observability.py). */
interface Timing { count: number; p50: number | null; p95: number | null }
export interface Health {
  startedAt: string;
  uptimeSeconds: number;
  limits: { searchWindow: number; zeroResultTexts: number };
  requests: { total: number; errors: number; errorRate: number; byStatus: Record<string, number> };
  routes: { route: string; count: number; errors: number; p50: number | null; p95: number | null }[];
  search: { total: number; bySource: Record<string, number>; zeroResults: number; noCloseMatch: number; missRate: number; closeMatchFloor: number; stages: Record<string, Timing> };
  zeroResultSearches: { query: string; source: string; count: number; reason: 'no-results' | 'no-close-match'; lastSeen: string }[] | null;
  viewer: { userId: string; canSeeSearchText: boolean };
}

const REFRESH_MS = 15000;
const STEPS: { key: string; label: string; help: string }[] = [
  { key: 'spelling', label: 'Spelling', help: 'Correcting typos and building query variations.' },
  { key: 'keyword', label: 'Keyword search', help: 'BM25 word matching over the catalog.' },
  { key: 'semantic', label: 'Meaning search', help: 'Encoding the query and finding similar products.' },
  { key: 'reranker', label: 'Careful check', help: 'The cross-encoder rescoring candidates.' },
  { key: 'total', label: 'Whole search', help: 'From request start to results ready.' },
];
const SOURCES: Record<string, string> = { mongo: 'Product catalog', shops: 'Online shops', serpapi: 'Google Shopping' };

const pct = (value: number) => `${(value * 100).toFixed(value > 0 && value < 0.01 ? 1 : 0)}%`;
const ms = (value: number | null) => (value == null ? '—' : value >= 100 ? `${Math.round(value)} ms` : `${value.toFixed(1)} ms`);
const count = (value: number) => value.toLocaleString();

function uptime(seconds: number) {
  const days = Math.floor(seconds / 86400), hours = Math.floor(seconds / 3600) % 24, minutes = Math.floor(seconds / 60) % 60;
  if (days) return `${days}d ${hours}h`;
  if (hours) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function ago(iso: string) {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  return `${Math.round(minutes / 60)} h ago`;
}

function useHealth() {
  const authenticatedFetch = useAuthenticatedFetch();
  const [data, setData] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const load = useCallback(async () => {
    setBusy(true);
    try {
      const response = await authenticatedFetch(`${API_BASE}/api/observability`);
      if (!response.ok) throw new Error('System health could not be loaded.');
      setData(await response.json());
      setError(null);
    } catch (problem) {
      setError(problem instanceof TypeError ? 'The backend could not be reached. Is it running?' : (problem as Error).message);
    } finally {
      setBusy(false);
    }
  }, [authenticatedFetch]);
  useEffect(() => {
    void load();
    // Live numbers: refresh while the tab is visible.
    const timer = setInterval(() => { if (document.visibilityState === 'visible') void load(); }, REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);
  return { data, error, busy, load };
}

function Tile({ label, value, note, warn }: { label: string; value: string; note: string; warn?: boolean }) {
  return <div className={`${card} p-4 ${warn ? 'ring-1 ring-[var(--accent)]' : ''}`}>
    <span className="block text-[12.5px] text-[var(--muted)]">{label}</span>
    <strong className={`${heading} mt-2 block text-[26px] leading-none`}>{value}</strong>
    <span className="mt-2 block text-[12.5px] text-[var(--muted)]">{note}</span>
  </div>;
}

function StepTimes({ stages, window }: { stages: Record<string, Timing>; window: number }) {
  const slowest = Math.max(1, ...STEPS.map(step => stages[step.key]?.p95 ?? 0));
  const sampled = stages.total?.count ?? 0;
  return <section aria-labelledby="steps-title" className={card}>
    <PanelHeader id="steps-title" title="Time per search step" description={`From the last ${count(Math.min(sampled, window))} catalog and shop searches (up to ${count(window)} are kept).`} />
    {sampled === 0 ? <p className="px-5 py-6 text-[13px] text-[var(--muted)]">No searches yet since the server started. Run a search and this fills in.</p> : <div className="px-5 py-4">
      <ul aria-label="Legend" className="mb-4 flex flex-wrap gap-4 text-[12.5px] text-[var(--muted)]">
        <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[2px] bg-[var(--accent)]" />Typical (median)</li>
        <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[2px] bg-[var(--accent)] opacity-30" />Slowest 5%</li>
      </ul>
      <ol className="space-y-3">
        {STEPS.map(step => {
          const timing = stages[step.key];
          if (!timing?.count) return null;
          return <li key={step.key} className="grid grid-cols-[minmax(0,1fr)] items-center gap-x-4 gap-y-1 sm:grid-cols-[150px_minmax(0,1fr)_130px]">
            <span className="text-[13px] font-medium" title={step.help}>{step.label}</span>
            <span className="relative h-4" aria-hidden="true">
              <span className="absolute inset-y-0 left-0 rounded-r-[4px] bg-[var(--accent)] opacity-30" style={{ width: `${((timing.p95 ?? 0) / slowest) * 100}%`, minWidth: 4 }} />
              <span className="absolute inset-y-0 left-0 rounded-r-[4px] bg-[var(--accent)]" style={{ width: `${((timing.p50 ?? 0) / slowest) * 100}%`, minWidth: 4 }} />
            </span>
            <span className="text-[12.5px] tabular-nums sm:text-right"><strong>{ms(timing.p50)}</strong> <span className="text-[var(--muted)]">/ {ms(timing.p95)}</span></span>
          </li>;
        })}
      </ol>
    </div>}
  </section>;
}

function ZeroResults({ data }: { data: Health }) {
  const rows = data.zeroResultSearches;
  return <section aria-labelledby="zero-title" className={card}>
    <PanelHeader id="zero-title" title="Searches that found nothing good" description={`No results, or no result the careful check rated as a close match. The last ${count(data.limits.zeroResultTexts)} are kept, with no names or user IDs.`} />
    {!data.viewer.canSeeSearchText ? <div className="px-5 py-5 text-[13px] leading-relaxed text-[var(--muted)]">
      <p className="flex items-start gap-2"><Icon name="info" size={15} className="mt-0.5 shrink-0" />Search text comes from all shoppers, so only admins can see it.</p>
      <p className="mt-2">To see it, add your user ID to <code className="rounded bg-[var(--sage)] px-1.5 py-0.5 text-[12px] text-[var(--ink)]">OBSERVABILITY_ADMINS</code> in <code className="rounded bg-[var(--sage)] px-1.5 py-0.5 text-[12px] text-[var(--ink)]">backend/.env</code> and restart the backend:</p>
      <code className="mt-2 block break-all rounded-lg bg-[var(--sage)] px-3 py-2 text-[12px] text-[var(--ink)]">OBSERVABILITY_ADMINS={data.viewer.userId}</code>
    </div> : !rows?.length ? <p className="px-5 py-6 text-[13px] text-[var(--muted)]">Every search since the server started found a close match.</p> : <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] border-collapse text-[13px]">
        <thead><tr className="text-left text-[12px] text-[var(--muted)]">
          <th className="px-5 py-2.5 font-medium">Search</th><th className="px-3 py-2.5 font-medium">Why</th><th className="px-3 py-2.5 font-medium">Source</th>
          <th className="px-3 py-2.5 text-right font-medium">Times</th><th className="px-5 py-2.5 text-right font-medium">Last</th>
        </tr></thead>
        <tbody>{rows.map(row => <tr key={`${row.source}:${row.query}`} className="border-t border-[var(--line)]">
          <td className="max-w-[320px] truncate px-5 py-2.5 font-medium" title={row.query}>{row.query}</td>
          <td className="px-3 py-2.5 text-[var(--muted)]">{row.reason === 'no-results' ? 'No results' : 'No close match'}</td>
          <td className="px-3 py-2.5 text-[var(--muted)]">{SOURCES[row.source] ?? row.source}</td>
          <td className="px-3 py-2.5 text-right tabular-nums">{row.count}</td>
          <td className="px-5 py-2.5 text-right text-[var(--muted)]">{ago(row.lastSeen)}</td>
        </tr>)}</tbody>
      </table>
    </div>}
  </section>;
}

function Routes({ data }: { data: Health }) {
  return <details className={`${card} group overflow-hidden`}>
    <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 [&::-webkit-details-marker]:hidden">
      <span><span className={`${heading} block text-base`}>API requests</span><span className="mt-1 block text-[13px] text-[var(--muted)]">Every endpoint, busiest first, with typical and slowest times.</span></span>
      <span aria-hidden="true" className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-[var(--line)] text-[var(--muted)] transition-transform group-open:rotate-90"><Icon name="arrow" size={14} /></span>
    </summary>
    <div className="overflow-x-auto border-t border-[var(--line)]">
      <table className="w-full min-w-[560px] border-collapse text-[13px]">
        <thead><tr className="text-left text-[12px] text-[var(--muted)]">
          <th className="px-5 py-2.5 font-medium">Endpoint</th><th className="px-3 py-2.5 text-right font-medium">Requests</th>
          <th className="px-3 py-2.5 text-right font-medium">Errors</th><th className="px-3 py-2.5 text-right font-medium">Typical</th><th className="px-5 py-2.5 text-right font-medium">Slowest 5%</th>
        </tr></thead>
        <tbody>{data.routes.map(row => <tr key={row.route} className="border-t border-[var(--line)]">
          <td className="px-5 py-2.5 font-mono text-[12px]">{row.route}</td>
          <td className="px-3 py-2.5 text-right tabular-nums">{count(row.count)}</td>
          <td className={`px-3 py-2.5 text-right tabular-nums ${row.errors ? 'font-semibold text-[var(--accent)]' : ''}`}>{count(row.errors)}</td>
          <td className="px-3 py-2.5 text-right tabular-nums">{ms(row.p50)}</td>
          <td className="px-5 py-2.5 text-right tabular-nums">{ms(row.p95)}</td>
        </tr>)}</tbody>
      </table>
    </div>
  </details>;
}

export default function SystemHealthView() {
  const { data, error, busy, load } = useHealth();
  if (!data && busy) return <div className="space-y-6" aria-busy="true"><Skeleton className="h-9 w-64" /><div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[0, 1, 2, 3].map(i => <Skeleton key={i} className="h-[104px] rounded-2xl" />)}</div><Skeleton className="h-64 rounded-2xl" /></div>;
  if (!data) return <div role="alert" className={`${card} flex flex-col items-start gap-3 p-6`}>
    <strong className={`${heading} text-lg`}>System health is not available</strong>
    <p className="text-[13.5px] text-[var(--muted)]">{error}</p>
    <button type="button" onClick={() => void load()} className={ghostButton}><Icon name="refresh" size={14} />Try again</button>
  </div>;

  return <HealthReport data={data} busy={busy} error={error} onRefresh={() => void load()} />;
}

/** The page body for one snapshot; kept apart from loading so it is easy to preview. */
export function HealthReport({ data, busy, error, onRefresh }: { data: Health; busy: boolean; error: string | null; onRefresh: () => void }) {
  const load = onRefresh;
  const started = new Date(data.startedAt).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  const sources = Object.entries(data.search.bySource).sort((a, b) => b[1] - a[1]);
  return <>
    <section className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className="text-[13px] text-[var(--muted)]">Live · updates every {REFRESH_MS / 1000} seconds</p>
        <h1 className={`${heading} mt-1 text-[clamp(26px,3.4vw,34px)] leading-tight`}>System health</h1>
        <p className="mt-1.5 max-w-2xl text-[14px] text-[var(--muted)]">How the backend is doing right now: speed, errors and searches that found nothing good. Numbers count from the last restart, {started} (up {uptime(data.uptimeSeconds)}).</p>
      </div>
      <button type="button" onClick={() => void load()} disabled={busy} className={ghostButton}><Icon name="refresh" size={14} />{busy ? 'Refreshing…' : 'Refresh'}</button>
    </section>
    {error && <p role="status" className="rounded-xl bg-[var(--sage)] px-4 py-2.5 text-[13px]">Showing the last numbers: {error}</p>}

    <section aria-label="Headline numbers" className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Tile label="Searches" value={count(data.search.total)} note={sources.length ? sources.map(([source, n]) => `${SOURCES[source] ?? source} ${count(n)}`).join(' · ') : 'None yet'} />
      <Tile label="Typical search time" value={ms(data.search.stages.total?.p50 ?? null)} note={`Slowest 5%: ${ms(data.search.stages.total?.p95 ?? null)}`} />
      <Tile label="Requests that failed" value={pct(data.requests.errorRate)} note={`${count(data.requests.errors)} of ${count(data.requests.total)} requests (server errors)`} warn={data.requests.errorRate > 0.02} />
      <Tile label="Found nothing good" value={pct(data.search.missRate)} note={`${count(data.search.zeroResults)} no results · ${count(data.search.noCloseMatch)} no close match`} />
    </section>

    <StepTimes stages={data.search.stages} window={data.limits.searchWindow} />
    <ZeroResults data={data} />
    <Routes data={data} />

    <p className="text-[12px] leading-relaxed text-[var(--muted)]">
      Numbers live in the backend&apos;s memory and start again after a restart. Memory stays small: only the last {count(data.limits.searchWindow)} searches and {count(data.limits.zeroResultTexts)} texts of searches that found nothing good are kept.
      Each request also writes one log line with a request ID, which is sent back in the <code>X-Request-ID</code> header.
    </p>
  </>;
}
