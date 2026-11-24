import type { Metadata } from 'next';
import DashboardShell from '@/components/dashboard/DashboardShell';
import SystemHealthView from '@/components/system/SystemHealth';

export const metadata: Metadata = {
  title: 'System health — Semantic',
  description: 'Live request, search and error numbers for the running backend.',
};

export default function SystemHealthPage() {
  return <DashboardShell title="System health"><SystemHealthView /></DashboardShell>;
}
