'use client';

import { useEffect, useId, useRef, useState, type MouseEvent, type Ref } from 'react';
import { card, ghostButton, heading } from '@/components/dashboard/ui';
import { methods, type LabReport, type Method, type RankedProduct } from '@/lib/searchLab';

const relevanceLabels = ['Exact match', 'Substitute', 'Complement', 'Irrelevant'] as const;
type RelevanceLabel = typeof relevanceLabels[number];

function judgmentKey(userId: string, query: string, productId: string) {
  return `semantic-search-lab-judgment-v1:${JSON.stringify([userId, query, productId])}`;
}

function loadJudgments(userId: string, report: LabReport) {
  const judgments = new Map<string, RelevanceLabel>();
  const ids = new Set(Object.values(report.rankings).flatMap(products => products.map(product => product.id)));
  try {
    for (const id of ids) {
      const saved = localStorage.getItem(judgmentKey(userId, report.query, id));
      const label = relevanceLabels.find(value => value === saved);
      if (label) judgments.set(id, label);
    }
  } catch {
    // Feedback still works in memory when browser storage is unavailable.
  }
  return judgments;
}

function byRank(products: RankedProduct[]) {
  return new Map(products.map((product, index) => [product.id, index + 1]));
}

function movement(rank: number, baseline: number | undefined, method: string, limit: number) {
  if (baseline === undefined) return `Outside ${method} top ${limit}`;
  const difference = baseline - rank;
  if (difference === 0) return `Same as ${method}`;
  return `${difference > 0 ? 'Up' : 'Down'} ${Math.abs(difference)} vs ${method}`;
}

type Positions = Record<Method, Map<string, number>>;

function ProductFeedback({ selected, positions, limit, judgment, storageUnavailable, feedbackPanel, onJudgment }: {
  selected: RankedProduct;
  positions: Positions;
  limit: number;
  judgment: RelevanceLabel | undefined;
  storageUnavailable: boolean;
  feedbackPanel: Ref<HTMLDivElement>;
  onJudgment: (label: RelevanceLabel | null) => void;
}) {
  const judgmentGroup = useId();
  return <div ref={feedbackPanel} tabIndex={-1} role="region" aria-label="Selected product" className="mb-4 rounded-xl border border-[var(--line)] bg-[var(--sage)] p-4 focus-visible:outline-2">
    <div aria-live="polite" aria-atomic="true">
      <p className="m-0 line-clamp-2 break-words text-sm font-semibold sm:line-clamp-none">{selected.title}</p>
      <dl className="mb-0 mt-2 flex flex-wrap gap-x-5 gap-y-1">
        {methods.map(({ id, label }) => {
          const rank = positions[id].get(selected.id);
          return <div key={id} className="flex gap-1.5 text-xs">
            <dt className="font-semibold">{label}</dt>
            <dd className="m-0">{rank === undefined ? `Outside top ${limit}` : `#${rank}`}</dd>
      </div>;
            })}
          </dl>
        </div>
        <fieldset className="m-0 mt-3 min-w-0 border-0 p-0">
          <legend className="mb-1.5 p-0 text-xs font-semibold">Relevance to this query</legend>
          <div className="flex flex-wrap items-center gap-2">
            {relevanceLabels.map(label => <label key={label} className={`${ghostButton} cursor-pointer has-[:checked]:border-[var(--accent)] has-[:checked]:bg-[var(--surface-fff)]`}>
              <input type="radio" name={judgmentGroup} checked={judgment === label}
                onChange={() => onJudgment(label)} className="m-0 accent-[var(--accent)]" />
              {label}
            </label>)}
            {judgment && <button type="button" onClick={() => onJudgment(null)} className="cursor-pointer border-0 bg-transparent px-1 py-1.5 text-xs underline underline-offset-4">Clear judgment</button>}
          </div>
        </fieldset>
        <p role="status" className={storageUnavailable ? 'mb-0 mt-2 text-xs' : 'sr-only'}>
          {storageUnavailable ? 'Browser storage is unavailable. This judgment is temporary.' : judgment ?? 'No judgment selected.'}
        </p>
      </div>;
}

function RankRow({ product, rank, selected, judgment, comparison, onSelect }: {
  product: RankedProduct;
  rank: number;
  selected: boolean;
  judgment: RelevanceLabel | undefined;
  comparison?: string[];
  onSelect: (product: RankedProduct, event: MouseEvent<HTMLButtonElement>) => void;
}) {
  return <li>
    <button type="button" aria-pressed={selected} onClick={event => onSelect(product, event)}
      className={`flex w-full cursor-pointer items-start gap-2 border-0 p-3 text-left text-[var(--ink)] hover:bg-[var(--sage)] focus-visible:outline-2 focus-visible:-outline-offset-2 ${selected ? 'bg-[var(--sage)]' : 'bg-transparent'}`}>
      <span className="min-w-6 shrink-0 text-xs font-semibold tabular-nums text-[var(--accent)]">#{rank}</span>
      <span className="min-w-0 break-words text-xs leading-relaxed">
        <span className="block font-semibold">{product.title}</span>
        {judgment && <span className="mt-1 inline-flex rounded-full border border-[var(--line)] bg-[var(--surface-fff)] px-2 py-0.5 text-[11px] font-semibold text-[var(--accent)]">{judgment}</span>}
        {comparison && <span className="mt-1.5 block space-y-0.5 text-[11px] text-[var(--muted)]">
          {comparison.map(change => <span key={change} className="block">{change}</span>)}
        </span>}
      </span>
    </button>
  </li>;
}

function RankingColumn({ method, products, selectedId, judgments, positions, limit, onSelect }: {
  method: typeof methods[number];
  products: RankedProduct[];
  selectedId?: string;
  judgments: Map<string, RelevanceLabel>;
  positions: Positions;
  limit: number;
  onSelect: (product: RankedProduct, event: MouseEvent<HTMLButtonElement>) => void;
}) {
  const { id, label, description } = method;
  const hybrid = id === 'hybrid';
  return <section aria-label={`${label} ranking`} className={`${card} min-w-0 overflow-hidden`}>
    <div className={`border-b border-[var(--line)] p-4 ${hybrid ? 'bg-[var(--sage)]' : ''}`}>
      <h3 className={`${heading} m-0 text-base`}>{label}</h3>
      <p className="mb-0 mt-1 text-xs text-[var(--muted)]">{description}</p>
    </div>
    {products.length ? <ol role="list" className="m-0 list-none divide-y divide-[var(--line)] p-0">
      {products.map((product, index) => <RankRow key={product.id} product={product} rank={index + 1}
        selected={selectedId === product.id} judgment={judgments.get(product.id)} onSelect={onSelect}
        comparison={hybrid ? [
          movement(index + 1, positions.keyword.get(product.id), 'keyword', limit),
          movement(index + 1, positions.semantic.get(product.id), 'semantic', limit),
        ] : undefined} />)}
    </ol> : <p className="p-4 text-sm text-[var(--muted)]">No results for this method.</p>}
  </section>;
}

export default function SearchLabResults({ report, userId }: { report: LabReport; userId: string }) {
  const [selected, setSelected] = useState<RankedProduct | null>(null);
  const [judgments, setJudgments] = useState(() => loadJudgments(userId, report));
  const [storageUnavailable, setStorageUnavailable] = useState(false);
  const feedbackPanel = useRef<HTMLDivElement>(null);
  const focusFeedback = useRef(false);
  const { query, limit, rankings } = report;
  const positions = {
    keyword: byRank(rankings.keyword),
    semantic: byRank(rankings.semantic),
    hybrid: byRank(rankings.hybrid),
  };

  useEffect(() => {
    if (selected && focusFeedback.current) {
      feedbackPanel.current?.focus({ preventScroll: true });
      focusFeedback.current = false;
    }
  }, [selected]);

  function setJudgment(productId: string, label: RelevanceLabel | null) {
    const key = judgmentKey(userId, query, productId);
    try {
      if (label) localStorage.setItem(key, label);
      else localStorage.removeItem(key);
      setStorageUnavailable(false);
    } catch {
      setStorageUnavailable(true);
    }
    setJudgments(current => {
      const next = new Map(current);
      if (label) next.set(productId, label);
      else next.delete(productId);
      return next;
    });
  }

  function selectProduct(product: RankedProduct, event: MouseEvent<HTMLButtonElement>) {
    const alreadySelected = selected?.id === product.id;
    focusFeedback.current = !alreadySelected && event.detail === 0;
    setSelected(alreadySelected ? null : product);
  }

  function updateSelectedJudgment(productId: string, label: RelevanceLabel | null) {
    setJudgment(productId, label);
    if (label === null) feedbackPanel.current?.focus({ preventScroll: true });
  }

  return <section aria-labelledby="lab-results-title" className="min-w-0">
    <h2 id="lab-results-title" className={`${heading} m-0 break-words text-xl`}>Rankings for “{query}”</h2>
    <p className="mb-4 mt-1 text-sm text-[var(--muted)]">Up to {limit} results per method. Select a product to trace its ranks and mark its relevance.</p>

    <div className="sticky top-28 z-[1] lg:top-16">
      {selected && <ProductFeedback selected={selected} positions={positions} limit={limit}
        judgment={judgments.get(selected.id)} storageUnavailable={storageUnavailable}
        feedbackPanel={feedbackPanel} onJudgment={label => updateSelectedJudgment(selected.id, label)} />}
    </div>

    <p className="mb-2 mt-0 text-xs text-[var(--muted)] md:hidden">Swipe or scroll to see all three rankings.</p>
    <div className="overflow-x-auto rounded-2xl focus-visible:outline-2" tabIndex={0} role="region" aria-label="Side-by-side search rankings">
      <div className="grid min-w-[660px] grid-cols-3 items-start gap-3 pb-2">
        {methods.map(method => <RankingColumn key={method.id} method={method}
          products={rankings[method.id]} selectedId={selected?.id} judgments={judgments}
          positions={positions} limit={limit} onSelect={selectProduct} />)}
      </div>
    </div>
  </section>;
}
