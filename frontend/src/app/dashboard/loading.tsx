import DashboardShell from '@/components/dashboard/DashboardShell';
import { Skeleton } from '@/components/dashboard/ui';

export default function DashboardLoading() {
  return <DashboardShell>
    <div role="status" aria-label="Loading your dashboard" className="space-y-6">
      <span className="sr-only">Loading your dashboard…</span>
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div className="space-y-3"><Skeleton className="h-3 w-32" /><Skeleton className="h-9 w-64 max-w-full" /><Skeleton className="h-4 w-80 max-w-full" /></div>
        <Skeleton className="h-11 w-full rounded-full sm:w-80" />
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, index) => <div key={index} className="space-y-4 rounded-2xl border border-[var(--line)] bg-[var(--surface-fff)] p-4">
          <Skeleton className="h-8 w-8" /><Skeleton className="h-7 w-12" /><Skeleton className="h-3 w-24 max-w-full" />
        </div>)}
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
        <div className="rounded-2xl border border-[var(--line)] bg-[var(--surface-fff)] p-5">
          <Skeleton className="mb-5 h-5 w-40" />
          {Array.from({ length: 3 }, (_, index) => <div key={index} className="flex items-center gap-4 border-t border-[var(--line)] py-4">
            <Skeleton className="h-11 w-11 shrink-0" /><div className="flex-1 space-y-2"><Skeleton className="h-4 w-2/3" /><Skeleton className="h-3 w-1/2" /></div>
          </div>)}
        </div>
        <div className="space-y-6">
          {Array.from({ length: 2 }, (_, index) => <div key={index} className="rounded-2xl border border-[var(--line)] bg-[var(--surface-fff)] p-5">
            <Skeleton className="mb-6 h-5 w-36" /><Skeleton className="mb-3 h-4 w-3/4" /><Skeleton className="h-4 w-1/2" />
          </div>)}
        </div>
      </div>
    </div>
  </DashboardShell>;
}
