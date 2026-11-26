'use client';

import { useRef, useState, type ReactNode } from 'react';
import type { SearchProduct } from '@/lib/types';

const LIMIT = 3;
const buttonClass = 'cursor-pointer rounded-full border border-[var(--line)] px-3 py-2 text-xs font-semibold hover:bg-[var(--sage)] disabled:cursor-default disabled:opacity-50';

type Entry<Product> = { key: string; product: Product; source?: string };
type ComparisonRow<Product> = { label: string; value: (product: Product, source?: string) => ReactNode };

export function comparisonKey(product: SearchProduct, source?: string) {
  return JSON.stringify([source, product.id ?? product.url ?? [product.title, product.merchant]]);
}

export function useProductComparison<Product extends SearchProduct>() {
  const [items, setItems] = useState<Entry<Product>[]>([]);

  function toggle(product: Product, source?: string) {
    const key = comparisonKey(product, source);
    setItems(current => {
      if (current.some(item => item.key === key)) return current.filter(item => item.key !== key);
      if (current.length >= LIMIT) return current;
      return [...current, { key, product, source }];
    });
  }

  return { items, toggle, clear: () => setItems([]) };
}

export function CompareProductButton({ title, selected, count, onToggle }: {
  title: string;
  selected: boolean;
  count: number;
  onToggle: () => void;
}) {
  return <button
    type="button"
    className={`${buttonClass} whitespace-nowrap ${selected ? 'bg-[var(--sage)] text-[var(--ink)]' : ''}`}
    aria-label={`Compare ${title}`}
    aria-pressed={selected}
    disabled={!selected && count >= LIMIT}
    onClick={onToggle}
  >{selected ? '✓ Added' : '+ Compare'}</button>;
}

export function ProductComparison<Product extends SearchProduct>({ items, rows, onRemove, onClear }: {
  items: Entry<Product>[];
  rows: ComparisonRow<Product>[];
  onRemove: (product: Product, source?: string) => void;
  onClear: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const count = items.length;
  const message = count === 0 ? 'Choose two or three products to compare.' : `${count} of ${LIMIT} selected`;

  return <section aria-label="Product comparison" className="my-4 rounded-xl border border-[var(--line)] bg-[var(--surface-fff)] px-4 py-3">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="m-0 text-xs text-[var(--muted)]" role="status">{message}</p>
      <div className="flex flex-wrap items-center gap-3">
        {count > 0 && <button type="button" onClick={onClear} className="cursor-pointer border-0 bg-transparent px-1 py-2 text-xs underline underline-offset-4">Clear selection</button>}
        <button type="button" onClick={() => dialog.current?.showModal()} disabled={count < 2} className="cursor-pointer rounded-full border-0 bg-[var(--accent)] px-4 py-2 text-xs font-semibold text-[var(--accent-ink)] disabled:cursor-default disabled:opacity-50">Compare{count > 0 ? ` (${count})` : ''}</button>
      </div>
    </div>
    {count > 0 && <ul className="mt-2 flex flex-wrap gap-2">
      {items.map(({ key, product, source }) => <li key={key} className="min-w-0 max-w-full">
        <button type="button" onClick={() => onRemove(product, source)} aria-label={`Remove ${product.title} from comparison`} title={product.title} className={`${buttonClass} flex max-w-full items-center gap-2`}>
          <span className="truncate">{product.title}</span><span aria-hidden="true">×</span>
        </button>
      </li>)}
    </ul>}
    <dialog ref={dialog} aria-labelledby="product-comparison-title" className="m-auto max-h-[85dvh] w-[calc(100%_-_2rem)] max-w-4xl overflow-auto rounded-2xl border border-[var(--line)] bg-[var(--surface-fff)] p-4 text-[var(--ink)] shadow-xl backdrop:bg-black/60 sm:p-6">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 id="product-comparison-title" className="m-0 text-xl font-semibold">Compare products</h2>
        <form method="dialog" className="m-0"><button className={buttonClass}>Close</button></form>
      </div>
      <p className="mb-2 mt-0 text-xs text-[var(--muted)] sm:hidden">Swipe or scroll to see all products.</p>
      <ComparisonTable items={items} rows={rows} />
    </dialog>
  </section>;
}


function ComparisonTable<Product extends SearchProduct>({ items, rows }: {
  items: Entry<Product>[];
  rows: ComparisonRow<Product>[];
}) {
  return <div className="overflow-x-auto rounded-xl border border-[var(--line)] focus-visible:outline-2" tabIndex={0} role="region" aria-label="Side-by-side comparison table">
    <table className="w-full table-fixed border-collapse text-left text-sm">
      <thead className="bg-[var(--sage)]">
        <tr>
          <th scope="col" className="sticky left-0 w-24 bg-[var(--sage)] px-3 py-3 sm:w-36">Details</th>
          {items.map(({ key, product }) => <th key={key} scope="col" className="w-36 break-words px-3 py-3 align-top sm:w-auto">{product.title}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.map(row => <tr key={row.label} className="border-t border-[var(--line)]">
          <th scope="row" className="sticky left-0 bg-[var(--surface-fff)] px-3 py-3 align-top font-medium">{row.label}</th>
          {items.map(({ key, product, source }) => <td key={key} className="break-words px-3 py-3 align-top">{row.value(product, source) ?? 'Unavailable'}</td>)}
        </tr>)}
      </tbody>
    </table>
  </div>;
}
