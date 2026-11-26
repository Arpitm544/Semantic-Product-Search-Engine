export type SearchSource = 'mongo' | 'serpapi' | 'shops';

export const SOURCE_LABELS: Record<SearchSource, string> = {
  mongo: 'Product catalog',
  serpapi: 'Google Shopping',
  shops: 'Online shops',
};

/** Where a saved or shown product came from; shop results name their shop. */
export function productSourceLabel(source: string, product: { merchant?: string }) {
  if (source === 'mongo') return SOURCE_LABELS.mongo;
  return product.merchant || SOURCE_LABELS[source as SearchSource] || 'Online shop';
}

export interface CatalogProduct {
  id: string;
  title: string;
  category: string;
  price: number;
  description: string;
  attributes: string[];
}

export interface SearchProduct {
  attributes?: string[];
  id?: string | number;
  title: string;
  category?: string;
  brand?: string;
  description?: string;
  price?: number | string | null;
  priceLabel?: string;
  currency?: string;
  imageUrl?: string;
  url?: string;
  merchant?: string;
  rating?: number | string | null;
  reviews?: number | string | null;
  stock?: number | string | null;
  inStock?: boolean | null;
  tags?: string[];
  provider?: string;
  matchSources?: string[];
  relevanceProbability?: number | null;
  explanation?: ResultExplanation;
}

/** Why a result ranked where it did: see backend/src/search/explanations.py. */
export interface ResultExplanation {
  candidateCount: number;
  matchedTerms: string[];
  keywordRank: number | null;
  semanticRank: number | null;
  semanticSimilarity: number | null;
  spellingMatch: boolean;
  providerRank: number | null;
  retrievalRank: number;
  rerankerRank: number;
  rerankerScore: number | null;
  blendedScore: number;
  weights: { retrieval: number; reranker: number };
  /** 'learned' when the LambdaMART model ordered the results (SEARCH_RANKER=learned). */
  ranker?: 'learned' | 'blend';
  /** The features that moved this product's learned score most; effect > 0 raised it. */
  learnedFactors?: { feature: string; label: string; effect: number }[];
}

export interface DashboardData {
  products: SearchProduct[];
  productCount: number;
  displayedProductCount: number;
  categories: string[];
  totalStock: number | null;
  sources?: { catalog?: string };
}

/** What the search understood from the query: see backend/api/query_understanding.py. */
export type QueryFilterType = 'price' | 'brand' | 'color';
export interface QueryFilterChip { type: 'brand' | 'color'; value: string; label: string }
export interface QueryFilters {
  searchText: string;
  /** available: the source has prices. applied: the shopper chose the price chip. */
  price: { label: string; text: string; available: boolean; applied: boolean } | null;
  active: QueryFilterChip[];
  suggestions: QueryFilterChip[];
}
/** The shopper's choices about smart filters, sent back with the next search. */
export interface SmartFilterChoice { skip: QueryFilterType[]; brand: string; color: string; price: boolean }
