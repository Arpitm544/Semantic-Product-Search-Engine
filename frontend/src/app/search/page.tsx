import ProductSearchPage from '@/components/ProductSearchPage';
import { SOURCE_LABELS, type SearchSource } from '@/lib/types';

type SearchParams = Promise<{ q?: string | string[]; source?: string | string[]; fuzzy?: string | string[]; preferences?: string | string[] }>;
export default async function SearchPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const query = typeof params.q === 'string' ? params.q.trim().slice(0, 512) : '';
  const hasExplicitSource = typeof params.source === 'string' && params.source in SOURCE_LABELS;
  const source: SearchSource = hasExplicitSource ? params.source as SearchSource : 'mongo';
  const fuzzy = params.fuzzy !== '0';
  const hasExplicitPreferences = params.preferences === '1' || params.preferences === '0';
  return (
    <ProductSearchPage
      key={`${source}:${fuzzy}:${params.preferences}:${query}`}
      initialQuery={query}
      initialSource={source}
      initialFuzzy={fuzzy}
      initialPreferences={params.preferences === '1'}
      hasExplicitSource={hasExplicitSource}
      hasExplicitPreferences={hasExplicitPreferences}
    />
  );
}
