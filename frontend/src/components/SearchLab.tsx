'use client';

import { SignInButton, useAuth } from '@clerk/nextjs';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import SearchLabResults, { methods, type LabReport } from '@/components/SearchLabResults';
import { card, ghostButton, primaryButton } from '@/components/dashboard/ui';
import { API_BASE, useAuthenticatedFetch } from '@/lib/api';

const examples = [
  'wireless headphones for commuting',
  'warm gloves for cycling',
  'something to keep coffee hot',
];

function isProductList(value: unknown): boolean {
  return Array.isArray(value) && value.every(product =>
    typeof product?.id === 'string' && typeof product.title === 'string');
}

function isLabReport(value: unknown): value is LabReport {
  if (!value || typeof value !== 'object') return false;
  const { query, limit, rankings } = value as Partial<LabReport>;
  return typeof query === 'string' && typeof limit === 'number' &&
    methods.every(({ id }) => isProductList(rankings?.[id]));
}

function searchServiceError(response: Response, body: { error?: string; detail?: string } | null) {
  if (response.status === 404) return 'Search Lab is unavailable on the connected search service.';
  return body?.error || body?.detail || 'The search comparison could not be completed.';
}

async function readRankings(response: Response): Promise<LabReport> {
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(searchServiceError(response, body));
  if (isLabReport(body)) return body;
  throw new Error('The search service returned invalid rankings.');
}

function comparisonError(reason: unknown, timedOut: boolean) {
  if (timedOut) return 'The search comparison took too long. Try again.';
  if (reason instanceof TypeError) return 'The search service could not be reached. Check that the backend is running.';
  return reason instanceof Error ? reason.message : 'The search comparison could not be completed.';
}

export default function SearchLab() {
  const { isLoaded, isSignedIn, userId } = useAuth();
  const request = useAuthenticatedFetch();
  const [query, setQuery] = useState(examples[0]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [report, setReport] = useState<LabReport | null>(null);
  const pending = useRef<AbortController | null>(null);

  useEffect(() => () => {
    const controller = pending.current;
    pending.current = null;
    controller?.abort();
  }, []);

  async function run(value: string) {
    const text = value.trim();
    if (!text || pending.current) return;
    const controller = new AbortController();
    pending.current = controller;
    const timeout = setTimeout(() => controller.abort(), 45000);
    setError('');
    setReport(null);
    setLoading(true);
    try {
      const response = await request(`${API_BASE}/api/search-lab?${new URLSearchParams({ q: text })}`, { signal: controller.signal });
      const rankings = await readRankings(response);
      if (pending.current === controller) setReport(rankings);
    } catch (reason) {
      if (pending.current === controller) setError(comparisonError(reason, controller.signal.aborted));
    } finally {
      clearTimeout(timeout);
      if (pending.current === controller) {
        pending.current = null;
        setLoading(false);
      }
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSignedIn) void run(query);
  }

  return <div className="space-y-6">
    <header className="rounded-2xl border border-[var(--line)] bg-[var(--sage)] p-6 sm:p-8">
      <h1 className="m-0 text-4xl leading-tight [font-family:var(--serif)] sm:text-5xl">Search Lab</h1>
      <p className="mb-0 mt-3 max-w-xl text-sm leading-relaxed">Run the same catalog query through keyword, semantic, and hybrid search. See which products move up, move down, or enter the top results.</p>
    </header>

    {isLoaded && !isSignedIn ? <section className={`${card} flex flex-wrap items-center justify-between gap-4 p-5`}>
      <p className="m-0 text-sm">Sign in to run live queries against the product catalog.</p>
      <SignInButton mode="modal" forceRedirectUrl="/search-lab" signUpForceRedirectUrl="/search-lab">
        <button type="button" className={`${primaryButton} cursor-pointer`}>Sign in</button>
      </SignInButton>
    </section> : <form onSubmit={submit} className={`${card} p-5`}>
      <label htmlFor="lab-query" className="text-sm font-semibold">Search query</label>
      <div className="mt-2 flex flex-col gap-2 sm:flex-row">
        <input id="lab-query" type="search" value={query} onChange={event => setQuery(event.target.value)} maxLength={512} required
          className="min-w-0 flex-1 rounded-xl border border-[var(--line)] bg-[var(--paper)] px-3 py-2.5 text-sm text-[var(--ink)] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)]" />
        <button type="submit" disabled={!isSignedIn || loading || !query.trim()} className={`${primaryButton} cursor-pointer`}>
          {loading ? 'Comparing…' : 'Compare rankings'}
        </button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-xs text-[var(--muted)]">Try an example</span>
        {examples.map(example => <button key={example} type="button" disabled={!isSignedIn || loading}
          onClick={() => { setQuery(example); void run(example); }} className={`${ghostButton} cursor-pointer`}>{example}</button>)}
      </div>
    </form>}

    {loading && <p role="status" className="text-sm text-[var(--muted)]">Running keyword, semantic, and hybrid retrieval…</p>}
    {error && <p role="alert" className={`${card} p-4 text-sm`}>{error}</p>}
    {report && isSignedIn && userId && <SearchLabResults
      key={JSON.stringify([userId, report.query])}
      report={report}
      userId={userId}
    />}
    <p className="text-xs leading-relaxed text-[var(--muted)]">
      The lab uses the original query. The benchmarks also measure spelling correction and reranking. <a href="/quality" className="font-semibold underline underline-offset-4">View the search quality benchmarks</a>
    </p>
  </div>;
}
