'use client';
import type { ReactNode } from 'react';
import DashboardShell from './dashboard/DashboardShell';

export const accountButton = 'rounded-full border border-[var(--line)] px-4 py-2 text-sm font-medium hover:bg-[var(--sage)] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2';
export const accountInput = 'w-full rounded-lg border border-[var(--line)] bg-[var(--paper)] p-3 text-sm text-[var(--ink)]';
export const accountPanel = 'rounded-2xl border border-[var(--line)] bg-[var(--surface-fff)] p-5';
export default function AccountShell({ title, description, children }: { title: string; description: string; children: ReactNode; active: string }) {
  return <DashboardShell>
    <section className="mx-auto max-w-6xl py-10"><h1 className="text-4xl font-semibold tracking-tight">{title}</h1><p className="mt-3 mb-8 max-w-3xl text-sm opacity-70">{description}</p>{children}</section>
  </DashboardShell>;
}
