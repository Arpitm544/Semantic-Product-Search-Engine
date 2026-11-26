export const methods = [
  { id: 'keyword', label: 'Keyword', description: 'BM25 word matching' },
  { id: 'semantic', label: 'Semantic', description: 'Vector similarity' },
  { id: 'hybrid', label: 'Hybrid', description: 'Weighted rank fusion' },
] as const;

export type Method = typeof methods[number]['id'];
export type RankedProduct = { id: string; title: string };
export type LabReport = {
  query: string;
  limit: number;
  rankings: Record<Method, RankedProduct[]>;
};

function isProductList(value: unknown): boolean {
  return Array.isArray(value) && value.every(product =>
    typeof product?.id === 'string' && typeof product.title === 'string');
}

function isLabReport(value: unknown): value is LabReport {
  if (!value || typeof value !== 'object') return false;
  const { query, limit, rankings } = value as Partial<LabReport>;
  return typeof query === 'string' && typeof limit === 'number' &&
    methods.every(({ id }) => isProductList(rankings?.[id]));
}

function searchServiceError(response: Response, body: { error?: string; detail?: string } | null) {
  if (response.status === 404) return 'Search Lab is unavailable on the connected search service.';
  return body?.error || body?.detail || 'The search comparison could not be completed.';
}

export async function readRankings(response: Response): Promise<LabReport> {
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(searchServiceError(response, body));
  if (isLabReport(body)) return body;
  throw new Error('The search service returned invalid rankings.');
}

export function comparisonError(reason: unknown, timedOut: boolean) {
  if (timedOut) return 'The search comparison took too long. Try again.';
  if (reason instanceof TypeError) return 'The search service could not be reached. Check that the backend is running.';
  return reason instanceof Error ? reason.message : 'The search comparison could not be completed.';
}
