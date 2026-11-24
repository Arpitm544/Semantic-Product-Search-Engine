'use client';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { API_BASE } from '@/lib/api';
import { METRICS, SEGMENTS, type MetricKey, type QualityExample, type QualityReport, type QualityStage, type Segment } from '@/lib/quality';
import { Icon, PanelHeader, Skeleton, card, ghostButton, heading } from '@/components/dashboard/ui';

const fmt = (value: number) => value.toFixed(3);
const pct = (value: number) => `${Math.round(value * 100)}%`;
const ms = (value: number) => (value >= 100 ? `${Math.round(value)} ms` : `${value.toFixed(1)} ms`);
const relative = (value: number, base: number) => (base > 0 ? (value - base) / base : 0);
const signed = (value: number) => `${value >= 0 ? '+' : '−'}${Math.abs(Math.round(value * 100))}%`;
const niceMax = (value: number) => Math.min(1, Math.max(0.2, Math.ceil(value * 10 + 0.5) / 10));

function useQualityReport() {
  const [report, setReport] = useState<QualityReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/quality`, { cache: 'no-store' });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(body?.error || 'The quality report could not be loaded.');
      setReport(body as QualityReport);
    } catch (problem) {
      setError(problem instanceof TypeError ? 'The search service could not be reached. Is the backend running?' : (problem as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);
  return { report, error, busy, load };
}

/** A focusable mark with a hover / keyboard tooltip. Values stay visible as labels too. */
function Tip({ children, tip, label, className = '' }: { children: ReactNode; tip: ReactNode; label: string; className?: string }) {
  return <span tabIndex={0} aria-label={label} className={`group relative block rounded-[4px] outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] ${className}`}>
    {children}
    <span role="tooltip" className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 hidden w-max max-w-[240px] -translate-x-1/2 rounded-lg border border-[var(--line)] bg-[var(--surface-fff)] px-3 py-2 text-[12px] leading-relaxed text-[var(--ink)] shadow-lg group-hover:block group-focus-visible:block">{tip}</span>
  </span>;
}

function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: { key: T; label: string }[]; onChange: (value: T) => void; label: string }) {
  // Scrolls sideways on narrow screens instead of wrapping onto a second line.
  return <div role="radiogroup" aria-label={label} className="flex max-w-full overflow-x-auto rounded-full border border-[var(--line)] p-0.5 [scrollbar-width:none]">
    {options.map(option => <button key={option.key} type="button" role="radio" aria-checked={value === option.key} onClick={() => onChange(option.key)}
      className={`shrink-0 whitespace-nowrap rounded-full border-0 px-3 py-1.5 text-[12.5px] font-medium transition-colors ${value === option.key ? 'bg-[var(--accent)] text-[var(--accent-ink)]' : 'bg-transparent text-[var(--muted)] hover:text-[var(--ink)]'}`}>{option.label}</button>)}
  </div>;
}

/** A small ⓘ that explains a term on hover or keyboard focus. */
function InfoTip({ text, label }: { text: ReactNode; label: string }) {
  return <Tip label={`About ${label}`} tip={text} className="inline-flex align-middle text-[var(--muted)] hover:text-[var(--ink)]">
    <Icon name="info" size={14} />
  </Tip>;
}

function Headline({ label, value, note, info }: { label: string; value: string; note: string; info?: string }) {
  return <div className={`${card} p-4`}>
    <span className="flex items-center gap-1.5 text-[12.5px] text-[var(--muted)]">{label}{info && <InfoTip label={label} text={info} />}</span>
    <strong className={`${heading} mt-2 block text-[28px] leading-none`}>{value}</strong>
    <span className="mt-2 block text-[12.5px] text-[var(--muted)]">{note}</span>
  </div>;
}

function Axis({ max, labels }: { max: number; labels: boolean }) {
  const ticks = [0, max / 2, max];
  return <div aria-hidden="true" className="pointer-events-none absolute inset-0">
    {ticks.map(tick => <span key={tick} className="absolute inset-y-0 border-l border-dashed border-[var(--line)]" style={{ left: `${(tick / max) * 100}%` }}>
      {labels && <span className="absolute -bottom-5 -translate-x-1/2 text-[11px] text-[var(--muted)]">{tick.toFixed(2).replace(/\.?0+$/, '') || '0'}</span>}
    </span>)}
  </div>;
}

function StageLadder({ stages, metric, segment }: { stages: QualityStage[]; metric: MetricKey; segment: Segment }) {
  const values = stages.map(stage => stage.metrics[segment][metric]);
  const max = niceMax(Math.max(...values));
  const base = values[0];
  const metricLabel = METRICS.find(item => item.key === metric)!.name.toLowerCase();
  return <ol className="space-y-3 pb-6">
    {stages.map((stage, index) => {
      const value = values[index];
      const served = stage.id === 'reranked';
      return <li key={stage.id} className="grid grid-cols-[minmax(0,1fr)] items-center gap-x-4 gap-y-1.5 sm:grid-cols-[180px_minmax(0,1fr)_92px]">
        <span className="text-[13px] font-medium">{stage.label}{served && <span className="ml-2 rounded-full bg-[var(--sage)] px-2 py-0.5 text-[11px] font-semibold text-[var(--accent)]">served</span>}</span>
        <span className="relative h-7">
          <Axis max={max} labels={index === stages.length - 1} />
          <Tip label={`${stage.label}: ${metricLabel} ${fmt(value)}`} className="absolute inset-y-1 left-0" tip={<>
            <strong className="block text-[13px]">{fmt(value)} {metricLabel}</strong>
            <span className="block text-[var(--muted)]">{stage.label} · {stage.metrics[segment].queries} queries</span>
            <span className="mt-1 block">{stage.description}</span>
          </>}>
            <span className="block h-5 rounded-r-[4px] bg-[var(--accent)] transition-[width] duration-500" style={{ width: `${Math.max(1, (value / max) * 100)}%`, minWidth: 4, opacity: served ? 1 : 0.55 }} />
          </Tip>
        </span>
        <span className="flex items-baseline gap-2 text-[13px] sm:justify-end">
          <strong className="tabular-nums">{fmt(value)}</strong>
          {index > 0 && <span className="text-[11.5px] tabular-nums text-[var(--muted)]">{signed(relative(value, base))}</span>}
        </span>
      </li>;
    })}
  </ol>;
}

function CleanVsTypo({ stages, metric }: { stages: QualityStage[]; metric: MetricKey }) {
  const max = niceMax(Math.max(...stages.flatMap(stage => [stage.metrics.clean[metric], stage.metrics.typo[metric]])));
  const metricLabel = METRICS.find(item => item.key === metric)!.name.toLowerCase();
  const series = [
    { key: 'clean' as const, label: 'Typed correctly', color: 'var(--series-clean)' },
    { key: 'typo' as const, label: 'With a typo', color: 'var(--series-typo)' },
  ];
  return <div className="quality-viz px-5 pb-5 pt-4">
    <ul aria-label="Legend" className="mb-4 flex flex-wrap gap-4 text-[12.5px] text-[var(--muted)]">
      {series.map(item => <li key={item.key} className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: item.color }} />{item.label}</li>)}
    </ul>
    <ol className="space-y-4 pb-6">
      {stages.map((stage, index) => <li key={stage.id} className="grid grid-cols-[minmax(0,1fr)] items-center gap-x-4 gap-y-1 sm:grid-cols-[180px_minmax(0,1fr)]">
        <span className="text-[13px] font-medium">{stage.label}</span>
        <span className="relative block">
          <Axis max={max} labels={index === stages.length - 1} />
          <span className="relative flex flex-col gap-[2px]">
            {series.map(item => {
              const value = stage.metrics[item.key][metric];
              return <Tip key={item.key} label={`${stage.label}, ${item.label}: ${metricLabel} ${fmt(value)}`} tip={<>
                <strong className="block text-[13px]">{fmt(value)} {metricLabel}</strong>
                <span className="block text-[var(--muted)]">{item.label} · {stage.label}</span>
              </>} className="flex items-center gap-2">
                <span className="block h-3.5 rounded-r-[4px]" style={{ width: `${Math.max(0.5, (value / max) * 100)}%`, minWidth: 4, background: item.color }} />
                <span className="text-[11.5px] tabular-nums text-[var(--muted)]">{fmt(value)}</span>
              </Tip>;
            })}
          </span>
        </span>
      </li>)}
    </ol>
  </div>;
}

function Latency({ stages }: { stages: QualityStage[] }) {
  const max = Math.max(...stages.map(stage => stage.latencyMs.p95)) || 1;
  return <div className="px-5 pb-5 pt-4">
    <ul aria-label="Legend" className="mb-4 flex flex-wrap gap-4 text-[12.5px] text-[var(--muted)]">
      <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[2px] bg-[var(--accent)]" />Typical (median)</li>
      <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[2px] bg-[var(--accent)] opacity-30" />Slowest 5% (p95)</li>
    </ul>
    <ol className="space-y-3">
      {stages.map(stage => <li key={stage.id} className="grid grid-cols-[minmax(0,1fr)] items-center gap-x-4 gap-y-1 sm:grid-cols-[180px_minmax(0,1fr)_120px]">
        <span className="text-[13px] font-medium">{stage.label}</span>
        <Tip label={`${stage.label}: median ${ms(stage.latencyMs.p50)}, p95 ${ms(stage.latencyMs.p95)}`} tip={<>
          <strong className="block text-[13px]">{ms(stage.latencyMs.p50)} median</strong>
          <span className="block">{ms(stage.latencyMs.p95)} p95 · {ms(stage.latencyMs.mean)} mean</span>
          <span className="block text-[var(--muted)]">{stage.id === 'reranked' ? 'Hybrid retrieval plus cross-encoder rescoring.' : 'Time for this stage alone.'}</span>
        </>} className="relative h-5">
          <span className="absolute inset-y-0 left-0 rounded-r-[4px] bg-[var(--accent)] opacity-30" style={{ width: `${(stage.latencyMs.p95 / max) * 100}%`, minWidth: 4 }} />
          <span className="absolute inset-y-0 left-0 rounded-r-[4px] bg-[var(--accent)]" style={{ width: `${(stage.latencyMs.p50 / max) * 100}%`, minWidth: 4 }} />
        </Tip>
        <span className="text-[12.5px] tabular-nums sm:text-right"><strong>{ms(stage.latencyMs.p50)}</strong> <span className="text-[var(--muted)]">/ {ms(stage.latencyMs.p95)}</span></span>
      </li>)}
    </ol>
  </div>;
}

function TypoKinds({ stages }: { stages: QualityStage[] }) {
  const shown = stages.filter(stage => ['keyword', 'spelling', 'semantic', 'reranked'].includes(stage.id));
  const kinds = Object.keys(stages[0]?.byTypoKind ?? {});
  const clean = Object.fromEntries(shown.map(stage => [stage.id, stage.metrics.clean['ndcg@10']]));
  return <div className="overflow-x-auto">
    <table className="w-full min-w-[520px] border-collapse text-[13px]">
      <caption className="sr-only">Overall quality (NDCG@10) by typo type for each stage</caption>
      <thead><tr className="text-left text-[12px] text-[var(--muted)]">
        <th className="px-5 py-2.5 font-medium">Typo type</th>
        {shown.map(stage => <th key={stage.id} className="px-3 py-2.5 text-right font-medium">{stage.label.replace('+ ', '')}</th>)}
      </tr></thead>
      <tbody>
        <tr className="border-t border-[var(--line)] bg-[var(--sage)]/40"><td className="px-5 py-2.5 font-medium">Typed correctly</td>
          {shown.map(stage => <td key={stage.id} className="px-3 py-2.5 text-right tabular-nums">{fmt(clean[stage.id])}</td>)}</tr>
        {kinds.map(kind => <tr key={kind} className="border-t border-[var(--line)]">
          <td className="px-5 py-2.5 capitalize">{kind}</td>
          {shown.map(stage => {
            const value = stage.byTypoKind[kind]?.['ndcg@10'] ?? 0;
            const kept = clean[stage.id] > 0 ? value / clean[stage.id] : 0;
            return <td key={stage.id} className="px-3 py-2.5 text-right tabular-nums">{fmt(value)} <span className="text-[11px] text-[var(--muted)]">({pct(kept)} kept)</span></td>;
          })}
        </tr>)}
      </tbody>
    </table>
  </div>;
}

function FullTable({ stages }: { stages: QualityStage[] }) {
  return <div className="overflow-x-auto">
    <table className="w-full min-w-[640px] border-collapse text-[13px]">
      <caption className="sr-only">All metrics for every stage over all test queries</caption>
      <thead><tr className="text-left text-[12px] text-[var(--muted)]">
        <th className="px-5 py-2.5 font-medium">Stage</th>
        {METRICS.map(metric => <th key={metric.key} className="px-3 py-2.5 text-right font-medium" title={metric.help}>{metric.name}<span className="block text-[11px] font-normal">{metric.label}</span></th>)}
        <th className="px-3 py-2.5 text-right font-medium">Typical time<span className="block text-[11px] font-normal">p50</span></th>
        <th className="px-5 py-2.5 text-right font-medium">Slowest 5%<span className="block text-[11px] font-normal">p95</span></th>
      </tr></thead>
      <tbody>{stages.map(stage => <tr key={stage.id} className={`border-t border-[var(--line)] ${stage.id === 'reranked' ? 'font-semibold' : ''}`}>
        <td className="px-5 py-2.5">{stage.label}</td>
        {METRICS.map(metric => <td key={metric.key} className="px-3 py-2.5 text-right tabular-nums">{fmt(stage.metrics.all[metric.key])}</td>)}
        <td className="px-3 py-2.5 text-right tabular-nums">{ms(stage.latencyMs.p50)}</td>
        <td className="px-5 py-2.5 text-right tabular-nums">{ms(stage.latencyMs.p95)}</td>
      </tr>)}</tbody>
    </table>
  </div>;
}

/** Three plain levels instead of five labels: a match, a close alternative, or not relevant. */
type Match = 'match' | 'close' | 'miss';
const matchOf = (grade: string): Match => (grade === 'Exact' ? 'match' : grade === 'Substitute' || grade === 'Complement' ? 'close' : 'miss');
const MATCH_TEXT: Record<Match, string> = { match: 'Exact match', close: 'Close alternative', miss: 'Not relevant' };

function MatchDot({ match }: { match: Match }) {
  const style = match === 'match' ? 'bg-[var(--accent)]' : match === 'close' ? 'border-2 border-[var(--accent)]' : 'bg-[var(--line)]';
  return <span aria-hidden="true" className={`block h-2.5 w-2.5 shrink-0 rounded-full ${style}`} />;
}

function ResultList({ title, results }: { title: string; results: QualityExample['keywordTop'] }) {
  return <div className="min-w-0">
    <p className="mb-2 text-[12px] font-medium text-[var(--muted)]">{title}</p>
    {results.length ? <ol className="space-y-2">{results.map((result, index) => {
      const match = matchOf(result.grade);
      return <li key={index} className="flex items-center gap-2.5 text-[13px]">
        <MatchDot match={match} />
        <span className={`min-w-0 truncate ${match === 'miss' ? 'text-[var(--muted)]' : ''}`} title={result.title}>{result.title}</span>
        <span className="sr-only">({MATCH_TEXT[match]})</span>
      </li>;
    })}</ol> : <p className="text-[13px] text-[var(--muted)]">No results</p>}
  </div>;
}

function Examples({ examples }: { examples: QualityExample[] }) {
  return <>
    <div className="border-b border-[var(--line)] px-5 py-3">
      <ul aria-label="Legend" className="flex flex-wrap gap-x-5 gap-y-2 text-[12px] text-[var(--muted)]">
        {(['match', 'close', 'miss'] as Match[]).map(match => <li key={match} className="flex items-center gap-2"><MatchDot match={match} />{MATCH_TEXT[match]}</li>)}
      </ul>
    </div>
    <ol className="divide-y divide-[var(--line)]">
      {examples.map(example => <li key={example.query} className="px-5 py-5">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <p className="min-w-0">
            <strong className="text-[14px]">“{example.query}”</strong>
            {example.kind !== 'clean' && <span className="ml-2 text-[12px] text-[var(--muted)]">{example.kind} typo</span>}
          </p>
          <p className="text-[12px] tabular-nums text-[var(--muted)]">
            NDCG {fmt(example.keywordNdcg)} → <strong className="text-[var(--ink)]">{fmt(example.rerankedNdcg)}</strong>
          </p>
        </div>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 sm:gap-8">
          <ResultList title="Keyword search" results={example.keywordTop} />
          <ResultList title="Our search" results={example.rerankedTop} />
        </div>
      </li>)}
    </ol>
  </>;
}

function LoadingState() {
  return <div className="space-y-6" aria-busy="true" aria-label="Loading the quality report">
    <Skeleton className="h-9 w-72" />
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[0, 1, 2, 3].map(index => <Skeleton key={index} className="h-[112px] rounded-2xl" />)}</div>
    <Skeleton className="h-80 rounded-2xl" />
  </div>;
}

const SECTIONS = [
  { id: 'overview', label: 'Overview' },
  { id: 'stages', label: 'Each stage' },
  { id: 'typos', label: 'Typos' },
  { id: 'speed', label: 'Speed' },
  { id: 'examples', label: 'Examples' },
  { id: 'details', label: 'Details' },
] as const;

/** Tabs that jump to each section and follow the reader while they scroll. */
function SectionNav() {
  const [active, setActive] = useState<string>(SECTIONS[0].id);
  const navRef = useRef<HTMLElement>(null);
  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      // At the very bottom the last sections can never reach the top, so pick the last one.
      const atBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
      // Otherwise the section being read is the last one whose top has passed under the tab bar.
      const passed = SECTIONS.filter(section => (document.getElementById(section.id)?.getBoundingClientRect().top ?? Infinity) <= 200);
      setActive(atBottom ? SECTIONS[SECTIONS.length - 1].id : (passed[passed.length - 1] ?? SECTIONS[0]).id);
    };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(update); };
    update();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      if (frame) cancelAnimationFrame(frame);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
    };
  }, []);
  // Keep the active tab visible when the tab row scrolls sideways on phones.
  useEffect(() => {
    navRef.current?.querySelector<HTMLElement>(`[data-section="${active}"]`)?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [active]);

  return <nav ref={navRef} aria-label="Report sections" className="z-[5] -mx-4 border-b border-[var(--line)] bg-[var(--paper)]/95 px-4 backdrop-blur sm:-mx-6 sm:px-6 lg:sticky lg:top-16 lg:-mx-10 lg:px-10">
    <div className="flex gap-1 overflow-x-auto [scrollbar-width:none]">
      {SECTIONS.map(section => <a key={section.id} href={`#${section.id}`} data-section={section.id} aria-current={active === section.id ? 'true' : undefined} onClick={() => setActive(section.id)}
        className={`shrink-0 border-b-2 px-3 py-3 text-[13px] font-medium transition-colors ${active === section.id ? 'border-[var(--accent)] text-[var(--ink)]' : 'border-transparent text-[var(--muted)] hover:text-[var(--ink)]'}`}>{section.label}</a>)}
    </div>
  </nav>;
}

/** A section that starts folded so the main story stays short. */
function Collapsible({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return <details className={`${card} group overflow-hidden`}>
    <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 [&::-webkit-details-marker]:hidden">
      <span className="min-w-0">
        <span className={`${heading} block text-base`}>{title}</span>
        <span className="mt-1 block text-[13px] text-[var(--muted)]">{description}</span>
      </span>
      <span aria-hidden="true" className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-[var(--line)] text-[var(--muted)] transition-transform group-open:rotate-90"><Icon name="arrow" size={14} /></span>
    </summary>
    <div className="border-t border-[var(--line)]">{children}</div>
  </details>;
}

/** Puts the reranker's cost next to what it buys, so the slow bar is not read as a flaw. */
function SpeedTradeoff({ hybrid, served }: { hybrid: QualityStage; served: QualityStage }) {
  const extra = Math.max(0, served.latencyMs.p50 - hybrid.latencyMs.p50);
  const gain = relative(served.metrics.all['ndcg@10'], hybrid.metrics.all['ndcg@10']);
  return <div className="mx-5 mb-5 rounded-xl bg-[var(--sage)] p-4 text-[13px] leading-relaxed">
    <p className="font-semibold">Why is the last step slower?</p>
    <p className="mt-1 text-[var(--muted)]">
      Finding candidates takes about <strong className="text-[var(--ink)]">{ms(hybrid.latencyMs.p50)}</strong>. The reranker then reads the
      query together with every candidate product and scores each pair, which is far more careful than the earlier steps. That adds about
      <strong className="text-[var(--ink)]"> {ms(extra)}</strong> on a small CPU, but raises overall quality from {fmt(hybrid.metrics.all['ndcg@10'])} to
      {' '}{fmt(served.metrics.all['ndcg@10'])} (<strong className="text-[var(--ink)]">{signed(gain)}</strong>) and puts the best matches first.
    </p>
  </div>;
}

export default function QualityReportView() {
  const { report, error, busy, load } = useQualityReport();
  const [metric, setMetric] = useState<MetricKey>('ndcg@10');
  const [segment, setSegment] = useState<Segment>('all');

  if (busy && !report) return <LoadingState />;
  if (error || !report) return <div role="alert" className={`${card} flex flex-col items-start gap-3 p-6`}>
    <strong className={`${heading} text-lg`}>The quality report is not available</strong>
    <p className="text-[13.5px] text-[var(--muted)]">{error}</p>
    <button type="button" onClick={() => void load()} className={ghostButton}><Icon name="refresh" size={14} />Try again</button>
  </div>;

  const stages = report.stages;
  const keyword = stages.find(stage => stage.id === 'keyword') ?? stages[0];
  const hybrid = stages.find(stage => stage.id === 'hybrid') ?? stages[stages.length - 2] ?? keyword;
  const served = stages.find(stage => stage.id === 'reranked') ?? stages[stages.length - 1];
  const metricInfo = METRICS.find(item => item.key === metric)!;
  const typoKept = (stage: QualityStage) => relative(stage.metrics.typo['ndcg@10'], stage.metrics.clean['ndcg@10']) + 1;
  const outOf100 = (value: number) => Math.round(value * 100);
  const sectionClass = 'scroll-mt-32 space-y-6';

  return <>
    <section className="flex flex-col gap-4">
      <div>
        <p className="text-[13px] text-[var(--muted)]">Offline evaluation · {report.split} split</p>
        <h1 className={`${heading} mt-1 text-[clamp(26px,3.4vw,34px)] leading-tight`}>How good is the search?</h1>
        <p className="mt-1.5 max-w-2xl text-[14px] text-[var(--muted)]">
          We ran {report.queryCount.toLocaleString()} real shopping searches, where people had already marked which products are a good match,
          and checked how often each version of our search puts those products at the top.
        </p>
      </div>
      <ul className="flex flex-wrap gap-2 text-[12px] text-[var(--muted)]">
        {[`${report.catalogProducts.toLocaleString()} products`, `${report.queryCount.toLocaleString()} test searches`, `Encoder: ${report.models.encoder}`, `Reranker: ${report.models.reranker}`]
          .map(item => <li key={item} className="rounded-full border border-[var(--line)] px-3 py-1">{item}</li>)}
      </ul>
      {report.partial && <p role="status" className="rounded-xl bg-[var(--sage)] px-4 py-2.5 text-[13px]">This report covers only part of the test split. Run the full evaluation before quoting these numbers.</p>}
    </section>

    <SectionNav />

    <section id="overview" aria-label="Summary" className={sectionClass}>
      <div className={`${card} p-5`}>
        <p className={`${heading} text-[clamp(18px,2.2vw,22px)] leading-snug`}>
          In <span className="text-[var(--accent)]">{outOf100(served.metrics.all['hit@5'])} of 100</span> searches, a good product shows up in the top 5,
          compared with {outOf100(keyword.metrics.all['hit@5'])} for plain keyword search.
        </p>
        <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-[var(--muted)]">
          Overall result quality is <strong className="text-[var(--ink)]">{signed(relative(served.metrics.all['ndcg@10'], keyword.metrics.all['ndcg@10']))}</strong> higher
          than keyword search. Typos barely hurt: our search keeps <strong className="text-[var(--ink)]">{pct(typoKept(served))}</strong> of its quality when a word is
          misspelled, while keyword search keeps {pct(typoKept(keyword))}.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Headline label="Overall quality" value={fmt(served.metrics.all['ndcg@10'])} note={`Keyword search: ${fmt(keyword.metrics.all['ndcg@10'])}`}
          info={`A 0 to 1 score for the whole top 10 (NDCG@10). ${METRICS[0].help}`} />
        <Headline label="Better than keyword search" value={signed(relative(served.metrics.all['ndcg@10'], keyword.metrics.all['ndcg@10']))} note="Gain in overall quality" />
        <Headline label="Good result in the top 5" value={pct(served.metrics.all['hit@5'])} note={`of searches (keyword: ${pct(keyword.metrics.all['hit@5'])})`}
          info="Hit@5: the share of searches where at least one product people marked as a good match is in the first five results." />
        <Headline label="Typical search time" value={ms(served.latencyMs.p50)} note={`Slowest 5%: ${ms(served.latencyMs.p95)}`}
          info={`Median time per search on ${report.environment.threads} CPU threads, like the production server. See Speed for why.`} />
      </div>
    </section>

    <section id="stages" aria-labelledby="ladder-title" className={`${card} scroll-mt-32`}>
      <PanelHeader id="ladder-title" title="Quality at each stage" description="Each step adds to the one before it. The last one is what the site serves." />
      <div className="flex flex-col gap-2 border-b border-[var(--line)] px-5 py-3 sm:flex-row sm:flex-wrap sm:items-center">
        <Segmented label="Measure" value={metric} options={METRICS.map(item => ({ key: item.key, label: item.name }))} onChange={setMetric} />
        <Segmented label="Searches" value={segment} options={SEGMENTS} onChange={setSegment} />
      </div>
      <p className="flex items-start gap-2 px-5 pt-4 text-[13px] text-[var(--muted)]">
        <Icon name="info" size={15} className="mt-0.5 shrink-0" />
        <span><strong className="font-semibold text-[var(--ink)]">{metricInfo.name}</strong> ({metricInfo.label}): {metricInfo.help}</span>
      </p>
      <div className="px-5 pt-4"><StageLadder stages={stages} metric={metric} segment={segment} /></div>
      <p className="border-t border-[var(--line)] px-5 py-3 text-[12px] text-[var(--muted)]">Percentages compare each stage with keyword search. Hover or focus a bar for details.</p>
    </section>

    <section id="typos" aria-label="Typos" className={sectionClass}>
      <div className={card}>
        <PanelHeader id="typo-title" title="Typed correctly vs. with a typo" description={`${metricInfo.name} when the search is typed correctly, and when it has one typing mistake.`} />
        <CleanVsTypo stages={stages} metric={metric} />
      </div>
      <div className={card}>
        <PanelHeader id="kinds-title" title="Which typos hurt most" description="Overall quality for each kind of typing mistake, and how much of the typed-correctly score each stage keeps." />
        <TypoKinds stages={stages} />
      </div>
    </section>

    <section id="speed" aria-labelledby="latency-title" className={`${card} scroll-mt-32`}>
      <PanelHeader id="latency-title" title="Time per search" description="Measured per search on CPU, like the production server." />
      <Latency stages={stages} />
      <SpeedTradeoff hybrid={hybrid} served={served} />
    </section>

    <section id="examples" aria-label="Examples" className={sectionClass}>
      {report.examples.wins.length > 0 && <div className={`${card} overflow-hidden`}>
        <PanelHeader id="wins-title" title="Where the pipeline helps most" description="Top three results from plain keyword search next to ours, marked using the dataset's human ratings." />
        <Examples examples={report.examples.wins} />
      </div>}
      {report.examples.misses.length > 0 && <div className={`${card} overflow-hidden`}>
        <PanelHeader id="misses-title" title="Still hard" description="Searches where our ranking scores lowest. They show what to improve next." />
        <Examples examples={report.examples.misses} />
      </div>}
    </section>

    <section id="details" aria-label="Details" className="scroll-mt-32 space-y-3">
      <Collapsible title="All numbers" description={`Every measure for every stage across all ${report.queryCount.toLocaleString()} searches.`}>
        <FullTable stages={stages} />
      </Collapsible>
    </section>
  </>;
}
