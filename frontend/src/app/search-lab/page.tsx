import type { Metadata } from 'next';
import DashboardShell from '@/components/dashboard/DashboardShell';
import SearchLab from '@/components/SearchLab';

export const metadata: Metadata = {
  title: 'Search Lab — Semantic',
  description: 'Run one query through keyword, semantic, and hybrid search and compare the rankings side by side.',
};

export default function SearchLabPage() {
  return <DashboardShell title="Search Lab"><SearchLab /></DashboardShell>;
}
