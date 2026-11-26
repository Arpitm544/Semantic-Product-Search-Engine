import { useMemo, useState } from 'react';
import { matchesListingText, suggestedRefinements, type Refinement } from '@/lib/guidedSearch';
import type { SearchProduct } from '@/lib/types';

export function useGuidedSearch(results: SearchProduct[], query: string) {
  const [selected, setSelected] = useState<Refinement[]>([]);
  const [featureText, setFeatureText] = useState('');
  const groups = useMemo(() => suggestedRefinements(results, query), [results, query]);
  const refined = selected.length > 0 || featureText.trim().length > 0;
  const visibleResults = refined
    ? results.filter(product => selected.every(option => option.matches(product)) && matchesListingText(product, featureText))
    : results;

  function clear() {
    setSelected([]);
    setFeatureText('');
  }

  function toggle(option: Refinement) {
    setSelected(current => {
      if (current.some(item => item.id === option.id)) return current.filter(item => item.id !== option.id);
      const other = option.facet === 'feature' ? current : current.filter(item => item.facet !== option.facet);
      return [...other, option];
    });
  }

  return { selected, featureText, setFeatureText, groups, refined, visibleResults, toggle, clear };
}
