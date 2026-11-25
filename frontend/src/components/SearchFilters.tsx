'use client';

import { useEffect, useState } from 'react';
import { ResourceStatus } from '@/components/AccountControls';
import { useAccountResource, type Preferences } from '@/lib/account';

const inputClass = 'mt-2 w-full min-w-0 rounded-xl border border-[var(--line)] bg-[var(--surface-fff)] px-3 py-2.5 text-sm text-[var(--ink)] outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--sage)]';

export type PreferencesResource = ReturnType<typeof useAccountResource<Preferences>>;

export default function SearchFilters({
  resource,
  onApplied,
  onCleared,
}: {
  resource: PreferencesResource;
  onApplied: (filters: Preferences) => void;
  onCleared: () => void;
}) {
  const [form, setForm] = useState<Preferences | null>(null);
  const [categories, setCategories] = useState('');
  const [brands, setBrands] = useState('');

  useEffect(() => {
    if (!resource.data) return;
    setForm(resource.data);
    setCategories(resource.data.categories.join(', '));
    setBrands(resource.data.brands.join(', '));
  }, [resource.data]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!form) return;
    const tags = (value: string) => value.split(',').map(item => item.trim()).filter(Boolean);
    const filters = { ...form, applyByDefault: true, categories: tags(categories), brands: tags(brands) };
    const saved = await resource.mutate(() => resource.api<Preferences>('/api/preferences', {
      method: 'PUT',
      body: JSON.stringify(filters),
    }), 'Filters applied.');
    if (saved) onApplied(saved);
  }

  return <details id="filters" open className="group scroll-mt-24 rounded-2xl border border-[var(--line)] bg-[var(--surface-fff)] lg:sticky lg:top-24 lg:self-start">
    <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-base font-semibold text-[var(--ink)] [&::-webkit-details-marker]:hidden">
      <span>Filters</span><span aria-hidden="true" className="text-[var(--muted)] group-open:rotate-180">⌄</span>
    </summary>
    <div className="border-t border-[var(--line)] px-5 py-5">
      <ResourceStatus busy={resource.busy} error={resource.error} notice={resource.notice} retry={resource.reload} />
      {form && <form onSubmit={submit}>
        <fieldset disabled={resource.busy} className="m-0 min-w-0 space-y-5 border-0 p-0">
          <div>
            <h3 className="mb-3 text-sm font-semibold">Price range</h3>
            <label htmlFor="filter-currency" className="text-xs text-[var(--muted)]">Currency</label>
            <select id="filter-currency" className={inputClass} value={form.currency} onChange={event => setForm({ ...form, currency: event.target.value })}>
              {['INR', 'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'NZD', 'SGD', 'AED', 'CHF', 'JPY', 'CNY', 'HKD', 'SEK', 'NOK', 'DKK'].map(code => <option key={code}>{code}</option>)}
            </select>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <label className="min-w-0 text-xs text-[var(--muted)]">Min<input className={inputClass} type="number" min="0" max="1000000000000" step="0.01" placeholder="Any" value={form.minBudget ?? ''} onChange={event => setForm({ ...form, minBudget: event.target.value === '' ? null : Number(event.target.value) })} /></label>
              <label className="min-w-0 text-xs text-[var(--muted)]">Max<input className={inputClass} type="number" min={form.minBudget ?? 0} max="1000000000000" step="0.01" placeholder="Any" value={form.maxBudget ?? ''} onChange={event => setForm({ ...form, maxBudget: event.target.value === '' ? null : Number(event.target.value) })} /></label>
            </div>
          </div>
          <div className="border-t border-[var(--line)] pt-5">
            <label htmlFor="filter-categories" className="text-sm font-semibold">Categories</label>
            <input id="filter-categories" className={inputClass} value={categories} onChange={event => setCategories(event.target.value)} placeholder="Audio, Electronics" maxLength={2000} />
            <p className="mt-2 text-xs text-[var(--muted)]">Separate category names with commas.</p>
          </div>
          <div className="border-t border-[var(--line)] pt-5">
            <label htmlFor="filter-brands" className="text-sm font-semibold">Brands</label>
            <input id="filter-brands" className={inputClass} value={brands} onChange={event => setBrands(event.target.value)} placeholder="Sony, Bose" maxLength={2000} />
            <p className="mt-2 text-xs text-[var(--muted)]">Separate brand names with commas.</p>
          </div>
          <div className="border-t border-[var(--line)] pt-5">
            <h3 className="mb-3 text-sm font-semibold">Availability</h3>
            <label className="flex items-start gap-3 text-sm"><input type="checkbox" className="mt-1 accent-[var(--accent)]" checked={form.inStockOnly} onChange={event => setForm({ ...form, inStockOnly: event.target.checked })} />In stock only</label>
          </div>
          <button type="submit" className="w-full rounded-xl bg-[var(--accent)] px-4 py-3 text-sm font-semibold text-[var(--accent-ink)] hover:opacity-90">Apply filters</button>
          <button type="button" className="w-full text-sm font-medium text-[var(--muted)] underline underline-offset-4" onClick={async () => { const reset = await resource.mutate(() => resource.api('/api/preferences', { method: 'DELETE' }), 'Filters cleared.'); if (reset) onCleared(); }}>Clear all filters</button>
          <p className="text-xs leading-relaxed text-[var(--muted)]">Catalog results support brand and category filters. Shopping results support price filters. Filters use the selected currency without conversion.</p>
        </fieldset>
      </form>}
    </div>
  </details>;
}
