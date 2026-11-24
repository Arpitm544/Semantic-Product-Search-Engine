/** Shape of backend/quality/quality_report.json, served by GET /api/quality. */

export type MetricKey = 'ndcg@10' | 'mrr@10' | 'recall@10' | 'hit@5';
export type Segment = 'all' | 'clean' | 'typo';

export type StageMetrics = { queries: number } & Record<MetricKey, number>;

export interface QualityStage {
  id: 'keyword' | 'spelling' | 'semantic' | 'hybrid' | 'reranked';
  label: string;
  description: string;
  metrics: Record<Segment, StageMetrics>;
  byTypoKind: Record<string, StageMetrics>;
  latencyMs: { p50: number; p95: number; mean: number };
}

export interface ExampleResult { title: string; grade: 'Exact' | 'Substitute' | 'Complement' | 'Irrelevant' | 'Unjudged' }

export interface QualityExample {
  query: string;
  kind: string;
  keywordNdcg: number;
  rerankedNdcg: number;
  keywordTop: ExampleResult[];
  rerankedTop: ExampleResult[];
}

export interface QualityReport {
  version: number;
  generatedAt: string;
  split: string;
  dataset: string;
  datasetUrl?: string | null;
  judgments: string;
  catalogProducts: number;
  queryCount: number;
  models: { encoder: string; reranker: string };
  environment: { device: string; threads: number; machine?: string; semanticBackend: string };
  commit?: string | null;
  partial?: boolean;
  stages: QualityStage[];
  examples: { wins: QualityExample[]; misses: QualityExample[] };
}

/** `name` is the plain-language label people see; `label` is the standard metric name. */
export const METRICS: { key: MetricKey; name: string; label: string; help: string }[] = [
  { key: 'ndcg@10', name: 'Overall quality', label: 'NDCG@10', help: 'Scores the whole top 10 from 0 to 1. Exact matches near the top score highest.' },
  { key: 'mrr@10', name: 'First good result', label: 'MRR@10', help: 'How high the first good product appears. 1.0 means it is always the first result.' },
  { key: 'recall@10', name: 'Found in top 10', label: 'Recall@10', help: 'Share of all the good products that make it into the top 10.' },
  { key: 'hit@5', name: 'Good result in top 5', label: 'Hit@5', help: 'Share of searches with at least one good product in the top 5.' },
];

export const SEGMENTS: { key: Segment; label: string }[] = [
  { key: 'all', label: 'All searches' },
  { key: 'clean', label: 'Typed correctly' },
  { key: 'typo', label: 'With a typo' },
];
