export interface CatalogProduct {
  id: string;
  title: string;
  category: string;
  price: number;
  description: string;
  attributes: string[];
}

export interface SearchProduct {
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
