'use client';
import type { QueryFilterChip, QueryFilters } from '@/lib/types';

const chip = 'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--focus-ring)]';
const appliedChip = `${chip} border-[var(--accent)] bg-[var(--sage)] text-[var(--ink)] hover:opacity-80`;
const suggestedChip = `${chip} border-[var(--line)] text-[var(--ink)] hover:border-[var(--accent)] hover:bg-[var(--sage)]`;
const label = 'text-xs font-semibold text-[var(--muted)]';

type Price = NonNullable<QueryFilters['price']>;

function ActiveChip({ item, onRemove }: { item: QueryFilterChip; onRemove: (item: QueryFilterChip) => void }) {
  return <button type="button" className={appliedChip} onClick={() => onRemove(item)} aria-label={`Remove ${item.type} filter ${item.label}`}>
    <span className="text-[var(--muted)]">{item.type === 'brand' ? 'Brand' : 'Color'}:</span> {item.label} <span aria-hidden="true">×</span>
  </button>;
}

/** A price found in the search, offered but never applied on its own. */
function PriceSuggestion({ price, onPrice, onSearchShops }: { price: Price; onPrice: (price: boolean) => void; onSearchShops: () => void }) {
  if (price.available) {
    return <button type="button" className={suggestedChip} onClick={() => onPrice(true)} aria-label={`Show only products ${price.label.toLowerCase()}`}>
      <span aria-hidden="true">+</span> {price.label}
    </button>;
  }
  // Catalog products have no prices, so the price can only apply to shop results.
  return <span className="inline-flex flex-wrap items-center gap-2 text-xs text-[var(--muted)]">
    <span className={`${chip} border-dashed border-[var(--line)]`} title="Catalog products have no prices">{price.label}</span>
    <button type="button" className="font-semibold text-[var(--accent)] underline underline-offset-2" onClick={onSearchShops}>Filter by price in online shops</button>
  </span>;
}

function SuggestionRow({ filters, onPrice, onNarrow, onSearchShops }: {
  filters: QueryFilters; onPrice: (price: boolean) => void; onNarrow: (item: QueryFilterChip) => void; onSearchShops: () => void;
}) {
  const price = filters.price && !filters.price.applied ? filters.price : null;
  if (!price && !filters.suggestions.length) return null;
  return <div className="flex flex-wrap items-center gap-2" aria-label="Ways to narrow your results">
    <span className={label}>Narrow to</span>
    {price && <PriceSuggestion price={price} onPrice={onPrice} onSearchShops={onSearchShops} />}
    {filters.suggestions.map(item => <button key={item.type} type="button" className={suggestedChip} onClick={() => onNarrow(item)} aria-label={`Show only ${item.type} ${item.label}`}>
      <span aria-hidden="true">+</span> {item.label} only
    </button>)}
  </div>;
}

/** True when the search understood anything worth showing. */
function hasChips({ price, active, suggestions }: QueryFilters) {
  return Boolean(price) || active.length + suggestions.length > 0;
}

/** Shows what the search understood from the query. Nothing is filtered until the shopper picks a chip. */
export default function QueryFilterChips({ filters, onPrice, onRemove, onNarrow, onSearchShops }: {
  filters: QueryFilters;
  onPrice: (price: boolean) => void;
  onRemove: (item: QueryFilterChip) => void;
  onNarrow: (item: QueryFilterChip) => void;
  onSearchShops: () => void;
}) {
  if (!hasChips(filters)) return null;
  const appliedPrice = filters.price?.applied ? filters.price : null;
  const filtered = Boolean(appliedPrice) || filters.active.length > 0;
  return <div className="mt-4 flex flex-col gap-2.5 rounded-xl border border-[var(--line)] bg-[var(--surface-fff)] px-4 py-3">
    {filtered && <div className="flex flex-wrap items-center gap-2" aria-label="Filters you chose">
      <span className={label}>Filtered by</span>
      {appliedPrice && <button type="button" className={appliedChip} onClick={() => onPrice(false)} aria-label={`Remove price filter ${appliedPrice.label}`}>
        {appliedPrice.label} <span aria-hidden="true">×</span>
      </button>}
      {filters.active.map(item => <ActiveChip key={item.type} item={item} onRemove={onRemove} />)}
    </div>}
    <SuggestionRow filters={filters} onPrice={onPrice} onNarrow={onNarrow} onSearchShops={onSearchShops} />
  </div>;
}
