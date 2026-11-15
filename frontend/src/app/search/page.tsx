import ProductSearchPage from '@/components/ProductSearchPage';

type SearchParams = Promise<{ q?: string | string[]; source?: string | string[]; fuzzy?: string | string[]; preferences?: string | string[] }>;
export default async function SearchPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const query = typeof params.q === 'string' ? params.q.trim().slice(0, 512) : '';
  const source = params.source === 'serpapi' ? 'serpapi' : 'mongo';
  const fuzzy = params.fuzzy !== '0';
  return <ProductSearchPage key={`${source}:${fuzzy}:${params.preferences}:${query}`} initialQuery={query} initialSource={source} initialFuzzy={fuzzy} initialPreferences={params.preferences === '1'} />;
}
