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
  provider?: string;
  matchSources?: string[];
}

export interface DashboardData {
  products: SearchProduct[];
  productCount: number;
  displayedProductCount: number;
  categories: string[];
  totalStock: number | null;
  sources?: { catalog?: string };
}
