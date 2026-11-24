import type { Metadata } from 'next';
import DashboardShell from '@/components/dashboard/DashboardShell';
import QualityReportView from '@/components/quality/QualityReport';

export const metadata: Metadata = {
  title: 'Search quality — Semantic',
  description: 'NDCG, MRR, recall and latency for each stage of the semantic product search pipeline, measured on Amazon ESCI test queries.',
};

// Public on purpose: the report holds aggregate scores over a public dataset and no user data.
export default function QualityPage() {
  return <DashboardShell title="Search quality"><QualityReportView /></DashboardShell>;
}
