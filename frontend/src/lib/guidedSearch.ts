import type { SearchProduct } from '@/lib/types';
import { budgetGroup } from '@/lib/guidedSearchBudget';

type Facet = 'brand' | 'category' | 'color' | 'seller' | 'budget' | 'feature';

export type Refinement = {
  id: string;
  facet: Facet;
  label: string;
  matches: (product: SearchProduct) => boolean;
};

export type RefinementGroup = { facet: Facet; label: string; options: Refinement[] };

function text(value: unknown) {
  return typeof value === 'string' ? value.trim() : '';
}

function list(value: unknown) {
  return Array.isArray(value) ? value.map(text).filter(Boolean) : [];
}

function normalize(value: string) {
  return value.normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
}

export function listedCategory(product: SearchProduct) {
  const value = text(product.category);
  return ['amazon-esci', 'uncategorized', 'unknown', 'other'].includes(value.toLowerCase()) ? '' : value;
}

export function listedColors(product: SearchProduct) {
  return list(product.tags);
}

function listedDetails(product: SearchProduct) {
  const bullets = text(product.representation_text).match(/(?:^| \| )\[Features\] (.*?)(?= \| \[(?:Brand|Title|Details|Color)\] |$)/i)?.[1];
  return [...list(product.attributes), ...(bullets ? [bullets] : [])];
}

const featurePatterns = [
  /\bnoise[- ]cancel(?:l?ing|l?ation)\b/gi,
  /\b(?:water|weather)[- ]?(?:proof|resistant)\b/gi,
  /\b(?:usb[- ]?c|wi[- ]?fi\s*[67]|bluetooth|wireless|rechargeable|insulated|foldable|dishwasher[- ]safe|gluten[- ]free|unscented|refillable)\b/gi,
  /\b(?:stainless steel|genuine leather|solid wood|tempered glass|memory foam|machine washable)\b/gi,
  /\b\d+(?:\.\d+)?(?:\s*(?:-|–|to)\s*\d+(?:\.\d+)?)?(?:[- ]*)(?:hours?|hrs?|gb|tb|mah|watts?|volts?|inches|inch|cm|mm|fl\.?\s*oz|oz|ml|liters?|litres?|gallons?)\b/gi,
  /\b(?:size|pack of)\s+\d+(?:\.\d+)?\b/gi,
];

export function listedFeatures(product: SearchProduct) {
  const details = [product.title, ...listedDetails(product)].join(' ');
  const structured = list(product.attributes).filter(value => /^[\p{L}][\p{L} /-]{1,28}:\s*\S/u.test(value));
  const mentions = featurePatterns.flatMap(pattern =>
    [...details.matchAll(pattern)].map(match => match[0].toLowerCase().replace(/\s+/g, ' '))
  );
  return [...new Set([...structured, ...mentions])];
}

export function matchesListingText(product: SearchProduct, input: string) {
  const terms = normalize(input).split(' ').filter(Boolean);
  if (!terms.length) return true;
  const words = new Set(normalize([
    product.title, text(product.description), text(product.brand), listedCategory(product),
    ...listedColors(product), ...listedDetails(product),
  ].join(' ')).split(' '));
  return terms.every(term => words.has(term));
}

function countValues(
  products: SearchProduct[], values: (product: SearchProduct) => string[], include: (key: string) => boolean,
) {
  const entries = new Map<string, { label: string; count: number }>();
  for (const product of products) {
    const unique = new Map(values(product)
      .filter(value => value.length <= 70)
      .map(value => [normalize(value), value]));
    for (const [key, value] of unique) {
      if (!key || !include(key)) continue;
      const existing = entries.get(key);
      entries.set(key, { label: existing?.label ?? value, count: (existing?.count ?? 0) + 1 });
    }
  }
  return entries;
}

function categoricalGroup(
  products: SearchProduct[], facet: Facet, label: string,
  values: (product: SearchProduct) => string[],
  include: (key: string) => boolean = () => true,
): RefinementGroup {
  const entries = countValues(products, values, include);
  const options = [...entries]
    .filter(([, option]) => option.count < products.length && (facet !== 'feature' || option.count >= 2))
    .sort(([, a], [, b]) => b.count - a.count || a.label.localeCompare(b.label))
    .slice(0, facet === 'feature' ? 5 : 4)
    .map(([key, option]) => ({
      id: `${facet}:${key}`, facet, label: option.label,
      matches: (product: SearchProduct) => values(product).some(value => normalize(value) === key),
    }));
  return { facet, label, options };
}

export function suggestedRefinements(products: SearchProduct[], query: string) {
  const queryWords = new Set(normalize(query).split(' '));
  return [
    budgetGroup(products),
    categoricalGroup(products, 'brand', 'Brand', product => [text(product.brand)]),
    categoricalGroup(products, 'feature', 'Features mentioned', listedFeatures,
      key => key.split(' ').some(word => !queryWords.has(word))),
    categoricalGroup(products, 'color', 'Color', listedColors),
    categoricalGroup(products, 'category', 'Category', product => [listedCategory(product)]),
    categoricalGroup(products, 'seller', 'Seller', product => [text(product.merchant)]),
  ].filter(group => group.options.length > 0);
}
