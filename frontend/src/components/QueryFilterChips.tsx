'use client';
import type { QueryFilterChip, QueryFilters } from '@/lib/types';

const chip = 'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--focus-ring)]';
const appliedChip = `${chip} border-[var(--accent)] bg-[var(--sage)] text-[var(--ink)] hover:opacity-80`;
const label = 'text-xs font-semibold text-[var(--muted)]';

type Price = NonNullable<QueryFilters['price']>;

function PriceChip({ price, onRemove, onSearchShops }: { price: Price; onRemove: () => void; onSearchShops: () => void }) {
  if (price.applied) {
    return <button type="button" className={appliedChip} onClick={onRemove} aria-label={`Remove price filter ${price.label}`}>
      {price.label} <span aria-hidden="true">×</span>
    </button>;
  }
  // Catalog products have no prices, so the price can only apply to shop results.
  return <span className="inline-flex flex-wrap items-center gap-2 text-xs text-[var(--muted)]">
    <span className={`${chip} border-dashed border-[var(--line)]`} title="Catalog products have no prices">{price.label} · not applied</span>
    <button type="button" className="font-semibold text-[var(--accent)] underline underline-offset-2" onClick={onSearchShops}>Filter by price in online shops</button>
  </span>;
}

function ActiveChip({ item, onRemove }: { item: QueryFilterChip; onRemove: (item: QueryFilterChip) => void }) {
  return <button type="button" className={appliedChip} onClick={() => onRemove(item)} aria-label={`Remove ${item.type} filter ${item.label}`}>
    <span className="text-[var(--muted)]">{item.type === 'brand' ? 'Brand' : 'Color'}:</span> {item.label} <span aria-hidden="true">×</span>
  </button>;
}

function SuggestionRow({ suggestions, onNarrow }: { suggestions: QueryFilterChip[]; onNarrow: (item: QueryFilterChip) => void }) {
  if (!suggestions.length) return null;
  return <div className="flex flex-wrap items-center gap-2" aria-label="Ways to narrow your results">
    <span className={label}>Narrow to</span>
    {suggestions.map(item => <button key={item.type} type="button" className={`${chip} border-[var(--line)] text-[var(--ink)] hover:border-[var(--accent)] hover:bg-[var(--sage)]`} onClick={() => onNarrow(item)} aria-label={`Show only ${item.type} ${item.label}`}>
      <span aria-hidden="true">+</span> {item.label} only
    </button>)}
  </div>;
}

/** True when the search understood anything worth showing. */
function hasChips({ price, active, suggestions }: QueryFilters) {
  return Boolean(price) || active.length + suggestions.length > 0;
}

/** Shows what the search understood from the query and lets the shopper adjust it. */
export default function QueryFilterChips({ filters, onRemovePrice, onRemove, onNarrow, onSearchShops }: {
  filters: QueryFilters;
  onRemovePrice: () => void;
  onRemove: (item: QueryFilterChip) => void;
  onNarrow: (item: QueryFilterChip) => void;
  onSearchShops: () => void;
}) {
  if (!hasChips(filters)) return null;
  const { price, active, suggestions } = filters;
  const filtered = Boolean(price) || active.length > 0;
  return <div className="mt-4 flex flex-col gap-2.5 rounded-xl border border-[var(--line)] bg-[var(--surface-fff)] px-4 py-3">
    {filtered && <div className="flex flex-wrap items-center gap-2" aria-label="Filters from your search">
      <span className={label}>Filtered by</span>
      {price && <PriceChip price={price} onRemove={onRemovePrice} onSearchShops={onSearchShops} />}
      {active.map(item => <ActiveChip key={item.type} item={item} onRemove={onRemove} />)}
    </div>}
    <SuggestionRow suggestions={suggestions} onNarrow={onNarrow} />
  </div>;
}
