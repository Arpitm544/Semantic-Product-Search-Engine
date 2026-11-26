'use client';

import { ghostButton } from '@/components/dashboard/ui';
import type { Refinement, RefinementGroup } from '@/lib/guidedSearch';

export default function GuidedSearchFilters({ groups, selected, featureText, onFeatureText, onToggle, onClear }: {
  groups: RefinementGroup[];
  selected: Refinement[];
  featureText: string;
  onFeatureText: (text: string) => void;
  onToggle: (option: Refinement) => void;
  onClear: () => void;
}) {
  const hiddenSelections = selected.filter(option =>
    !groups.some(group => group.options.some(candidate => candidate.id === option.id))
  );

  return <section aria-labelledby="guided-search-title" className="my-4 rounded-xl border border-[var(--line)] bg-[var(--surface-fff)] p-4">
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <h3 id="guided-search-title" className="m-0 text-base font-semibold">Refine these results</h3>
      {(selected.length > 0 || featureText.trim()) && <button type="button" onClick={onClear}
        className="cursor-pointer border-0 bg-transparent px-1 py-1 text-xs font-semibold underline underline-offset-4">Clear refinements</button>}
    </div>
    <div className="mt-3 flex flex-col gap-1.5">
      <label htmlFor="guided-feature-text" className="text-xs font-semibold">Find a feature in these listings</label>
      <input id="guided-feature-text" type="search" value={featureText} maxLength={100}
        onChange={event => onFeatureText(event.target.value)} placeholder="Try waterproof, USB-C, or stainless steel"
        className="min-w-0 rounded-lg border border-[var(--line)] bg-[var(--paper)] px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)]" />
    </div>
    {hiddenSelections.length > 0 && <div className="mt-3 flex flex-wrap items-center gap-2" aria-label="Applied refinements">
      {hiddenSelections.map(option => <button key={option.id} type="button" onClick={() => onToggle(option)}
        aria-label={`Remove ${option.facet} refinement ${option.label}`}
        className={`${ghostButton} cursor-pointer border-[var(--accent)] bg-[var(--sage)]`}>{option.label} <span aria-hidden="true">×</span></button>)}
    </div>}
    {groups.length > 0 && <div className="mt-4 space-y-3 border-t border-[var(--line)] pt-3">
      {groups.map(({ facet, label, options }) => <fieldset key={facet} className="m-0 min-w-0 border-0 p-0">
        <legend className="mb-1 p-0 text-xs font-semibold text-[var(--muted)]">{label}</legend>
        <div className="flex flex-wrap items-center gap-2">
          {options.map(option => {
            const active = selected.some(item => item.id === option.id);
            return <button key={option.id} type="button" onClick={() => onToggle(option)} aria-pressed={active}
              className={`${ghostButton} cursor-pointer ${active ? 'border-[var(--accent)] bg-[var(--sage)]' : ''}`}>{option.label}</button>;
          })}
        </div>
      </fieldset>)}
    </div>}
  </section>;
}
