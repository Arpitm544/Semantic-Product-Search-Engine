'use client';
import type { ReactNode } from 'react';
import { UserButton } from '@clerk/nextjs';
import ThemeToggle from './ThemeToggle';

export const accountButton = 'rounded-full border border-[var(--line)] px-4 py-2 text-sm font-medium hover:bg-[var(--sage)] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2';
export const accountInput = 'w-full rounded-lg border border-[var(--line)] bg-[var(--paper)] p-3 text-sm text-[var(--ink)]';
export const accountPanel = 'rounded-2xl border border-[var(--line)] bg-[var(--surface-fff)] p-5';
const links = [['/dashboard', 'Dashboard'], ['/saved', 'Saved'], ['/collections', 'Collections'], ['/preferences', 'Preferences'], ['/comparisons', 'Comparisons'], ['/alerts', 'Price alerts'], ['/search', 'Search']];
export default function AccountShell({ title, description, children, active }: { title: string; description: string; children: ReactNode; active: string }) {
  return <main className="min-h-screen bg-[var(--paper)] px-4 py-6 text-[var(--ink)] sm:px-6">
    <header className="mx-auto max-w-6xl border-b border-[var(--line)] pb-5"><div className="mb-5 flex items-center justify-between gap-4"><a href="/" className="text-xl font-bold">✳ semantic.</a><div className="flex items-center gap-4"><ThemeToggle /><UserButton /></div></div>
      <nav aria-label="Your account" className="flex flex-wrap gap-x-5 gap-y-3 text-sm">{links.map(([href, label]) => <a key={href} href={href} aria-current={active === href ? 'page' : undefined} className={active === href ? 'font-bold underline underline-offset-4' : 'opacity-70 hover:opacity-100'}>{label}</a>)}</nav>
    </header>
    <section className="mx-auto max-w-6xl py-10"><h1 className="text-4xl font-semibold tracking-tight">{title}</h1><p className="mt-3 mb-8 max-w-3xl text-sm opacity-70">{description}</p>{children}</section>
  </main>;
}
