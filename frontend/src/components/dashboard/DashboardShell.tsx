'use client';
import type { ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { UserButton } from '@clerk/nextjs';
import ThemeToggle from '@/components/ThemeToggle';
import { Icon, heading, type IconName } from './ui';

type NavItem = { href: string; label: string; icon: IconName; badge?: number };

export default function DashboardShell({ children, unreadAlerts, title = 'Overview' }: { children: ReactNode; unreadAlerts?: number; title?: string }) {
  const groups: { title: string; items: NavItem[] }[] = [
    { title: 'Discover', items: [
      { href: '/dashboard', label: 'Dashboard', icon: 'grid' },
      { href: '/search', label: 'Product search', icon: 'search' },
      { href: '/quality', label: 'Search quality', icon: 'chart' },
      { href: '/system', label: 'System health', icon: 'pulse' },
    ] },
    { title: 'Your library', items: [
      { href: '/saved', label: 'Saved', icon: 'heart' },
      { href: '/collections', label: 'Collections', icon: 'folder' },
      { href: '/comparisons', label: 'Comparisons', icon: 'columns' },
      { href: '/alerts', label: 'Price alerts', icon: 'bell', badge: unreadAlerts || undefined },
    ] },
  ];
  const all = groups.flatMap(group => group.items);

  return <div className="min-h-screen bg-[var(--paper)] text-[14px] text-[var(--ink)] [font-family:'DM_Sans',sans-serif] [&_ul]:m-0 [&_ul]:list-none [&_ul]:p-0 [&_button]:border-solid">
    {/* The app has no CSS reset, so lists and inputs are normalised here. */}
    <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r border-[var(--line)] bg-[var(--surface-fff)] px-3 py-5 lg:flex">
      <a href="/" className={`${heading} mb-7 flex items-center gap-2 px-3 text-xl`}><span className="text-[var(--accent)]">✳</span>semantic.</a>
      <nav aria-label="Dashboard navigation" className="flex flex-1 flex-col gap-6 overflow-y-auto">
        {groups.map(group => <div key={group.title}>
          <p className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">{group.title}</p>
          <ul className="space-y-0.5">{group.items.map(item => <li key={item.href}><NavLink item={item} /></li>)}</ul>
        </div>)}
      </nav>
      <a href="/search" className="mt-4 block rounded-xl bg-[var(--sage)] p-4 text-[13px]">
        <strong className="block font-semibold">Search by meaning</strong>
        <span className="mt-1 block text-[var(--muted)]">Describe what you need — “quiet headphones for travel” works.</span>
        <span className="mt-3 inline-flex items-center gap-1 font-semibold text-[var(--accent)]">Start searching <Icon name="arrow" size={14} /></span>
      </a>
    </aside>

    <div className="lg:pl-60">
      <header className="sticky top-0 z-10 border-b border-[var(--line)] bg-[var(--surface-topbar)] backdrop-blur">
        <div className="flex h-16 items-center justify-between gap-4 px-4 sm:px-6 lg:px-10">
          <a href="/" className={`${heading} flex items-center gap-2 text-lg lg:hidden`}><span className="text-[var(--accent)]">✳</span>semantic.</a>
          <p className="hidden text-[13px] text-[var(--muted)] lg:block">{title}</p>
          <div className="flex items-center gap-3">
            <a href="/alerts" aria-label={unreadAlerts ? `${unreadAlerts} unread price drops` : 'Price alerts'} className="relative grid h-9 w-9 place-items-center rounded-full border border-[var(--line)] hover:bg-[var(--sage)]">
              <Icon name="bell" size={17} />
              {!!unreadAlerts && <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-[var(--accent)] px-1 text-[10px] font-bold text-[var(--accent-ink)]">{unreadAlerts}</span>}
            </a>
            <ThemeToggle />
            <UserButton />
          </div>
        </div>
        <nav aria-label="Dashboard sections" className="flex gap-1.5 overflow-x-auto px-4 pb-3 sm:px-6 lg:hidden [scrollbar-width:none]">
          {all.map(item => <NavLink key={item.href} item={item} compact />)}
        </nav>
      </header>
      <main className="mx-auto max-w-6xl space-y-6 px-4 py-7 sm:px-6 lg:px-10 lg:py-9">{children}</main>
    </div>
  </div>;
}

function NavLink({ item, compact }: { item: NavItem; compact?: boolean }) {
  const active = usePathname() === item.href;
  if (compact) {
    return <a href={item.href} aria-current={active ? 'page' : undefined} className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-[13px] font-medium ${active ? 'border-[var(--accent)] bg-[var(--accent)] text-[var(--accent-ink)]' : 'border-[var(--line)] text-[var(--ink)]'}`}>
      <Icon name={item.icon} size={15} />{item.label}{item.badge ? <span className="text-[11px] font-bold">({item.badge})</span> : null}
    </a>;
  }
  return <a href={item.href} aria-current={active ? 'page' : undefined} className={`flex h-9 items-center gap-2.5 rounded-lg px-3 text-[13.5px] font-medium transition-colors ${active ? 'bg-[var(--sage)] font-semibold text-[var(--accent)]' : 'text-[var(--muted)] hover:bg-[var(--sage)] hover:text-[var(--ink)]'}`}>
    <Icon name={item.icon} size={17} /><span className="flex-1">{item.label}</span>
    {item.badge ? <span className="rounded-full bg-[var(--accent)] px-1.5 text-[11px] font-bold text-[var(--accent-ink)]">{item.badge}</span> : null}
  </a>;
}
