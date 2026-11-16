'use client';
import type { ReactNode } from 'react';

export type IconName = 'grid' | 'search' | 'box' | 'heart' | 'folder' | 'columns' | 'bell' | 'clock' | 'sliders' | 'arrow' | 'trash' | 'refresh' | 'tag';

const paths: Record<IconName, ReactNode> = {
  grid: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
  search: <><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 4 4" /></>,
  box: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="M3 8v9l9 5 9-5V8M12 13v9" /></>,
  heart: <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10Z" />,
  folder: <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />,
  columns: <><rect x="3" y="4" width="7" height="16" rx="1.5" /><rect x="14" y="4" width="7" height="16" rx="1.5" /></>,
  bell: <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" />,
  clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>,
  sliders: <path d="M4 7h10M18 7h2M4 17h4M12 17h8M16 5v4M10 15v4" />,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  trash: <path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3" />,
  refresh: <path d="M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6" />,
  tag: <><path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9-9-9Z" /><circle cx="8" cy="8" r="1.5" /></>,
};

export function Icon({ name, size = 18, className }: { name: IconName; size?: number; className?: string }) {
  return <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

export const card = 'rounded-2xl border border-[var(--line)] bg-[var(--surface-fff)]';
export const ghostButton = 'inline-flex items-center gap-1.5 rounded-full border border-[var(--line)] bg-transparent px-3 py-1.5 text-xs font-medium text-[var(--ink)] transition-colors hover:bg-[var(--sage)] disabled:cursor-not-allowed disabled:opacity-50';
export const primaryButton = 'inline-flex items-center justify-center gap-2 rounded-full border-0 bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-[var(--accent-ink)] transition-opacity hover:opacity-90 disabled:opacity-50';
export const heading = "[font-family:Manrope,sans-serif] font-bold tracking-[-0.02em] text-[var(--ink)]";

export function Skeleton({ className = '' }: { className?: string }) {
  return <span aria-hidden="true" className={`block animate-pulse rounded-md bg-[var(--sage)] ${className}`} />;
}

export function PanelHeader({ title, id, description, action }: { title: string; id?: string; description?: string; action?: ReactNode }) {
  return <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--line)] px-5 py-4">
    <div className="min-w-0">
      <h2 id={id} className={`${heading} text-base`}>{title}</h2>
      {description && <p className="mt-1 text-[13px] text-[var(--muted)]">{description}</p>}
    </div>
    {action}
  </div>;
}

export function EmptyState({ icon, title, body, href, cta }: { icon: IconName; title: string; body: string; href: string; cta: string }) {
  return <div className="flex flex-col items-center px-6 py-10 text-center">
    <span className="mb-3 grid h-11 w-11 place-items-center rounded-full bg-[var(--sage)] text-[var(--accent)]"><Icon name={icon} size={20} /></span>
    <p className="text-sm font-semibold">{title}</p>
    <p className="mt-1 max-w-xs text-[13px] text-[var(--muted)]">{body}</p>
    <a href={href} className="mt-4 inline-flex items-center gap-1 text-[13px] font-semibold text-[var(--accent)] hover:underline">{cta} <Icon name="arrow" size={14} /></a>
  </div>;
}

export function StatTile({ href, icon, label, value, loading, highlight }: { href: string; icon: IconName; label: string; value: number | undefined; loading: boolean; highlight?: boolean }) {
  return <a href={href} className={`${card} group flex flex-col gap-3 p-4 transition-colors hover:border-[var(--accent)] ${highlight ? 'ring-1 ring-[var(--accent)]' : ''}`}>
    <span className="flex items-center justify-between text-[var(--muted)]">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-[var(--sage)] text-[var(--accent)]"><Icon name={icon} size={16} /></span>
      <Icon name="arrow" size={14} className="opacity-0 transition-opacity group-hover:opacity-100" />
    </span>
    <span>
      {loading ? <Skeleton className="mb-1 h-7 w-12" /> : <strong className={`${heading} block text-2xl leading-none`}>{value ?? '—'}</strong>}
      <span className="mt-1.5 block text-[13px] text-[var(--muted)]">{label}</span>
    </span>
  </a>;
}

export interface Problem { label: string; message: string; retry: () => void }

/** Distinct messages without the repeated "Please try again." that each API adds. */
function details(problems: Problem[]) {
  const messages = problems.map(problem => problem.message.replace(/\s*Please try again\.?\s*$/i, '').trim()).filter(Boolean);
  return messages.filter((message, index) => messages.indexOf(message) === index).join(' ');
}

/** One banner for every section that failed, instead of a different alert per section. */
export function ProblemBanner({ problems, busy }: { problems: Problem[]; busy: boolean }) {
  if (!problems.length) return null;
  const unreachable = problems.every(problem => /reach|fetch|network|unavailable/i.test(problem.message));
  return <div role="alert" className="flex flex-wrap items-center gap-3 rounded-2xl border border-[#e6c9b8] bg-[#fbf1ea] px-4 py-3 text-sm text-[#7c4a33] dark:border-[#6b4636] dark:bg-[#2c1f19] dark:text-[#f0c9b4]">
    <span className="min-w-0 flex-1">
      <strong className="font-semibold">{problems.length > 1 ? 'Some sections could not load.' : `${problems[0].label} could not load.`}</strong>{' '}
      <span className="opacity-85">{unreachable && problems.length > 1 ? 'The server is not responding right now.' : details(problems)}</span>
    </span>
    <button type="button" disabled={busy} onClick={() => problems.forEach(problem => problem.retry())} className="inline-flex items-center gap-1.5 rounded-full border border-current bg-transparent px-3 py-1.5 text-xs font-semibold disabled:opacity-50">
      <Icon name="refresh" size={14} /> {busy ? 'Loading…' : 'Try again'}
    </button>
  </div>;
}
