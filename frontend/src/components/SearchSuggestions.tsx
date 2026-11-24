'use client';
import { useEffect, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { API_BASE, useAuthenticatedFetch } from '@/lib/api';

export interface Suggestion { text: string; kind: 'recent' | 'brand' | 'catalog' }

const LIST_ID = 'search-suggestions';
const KIND_LABEL: Record<Suggestion['kind'], string> = { recent: 'Recent search', brand: 'Brand', catalog: 'Suggestion' };

function validSuggestion(value: unknown): value is Suggestion {
  if (!value || typeof value !== 'object') return false;
  const item = value as Partial<Suggestion>;
  return typeof item.text === 'string' && (item.kind === 'recent' || item.kind === 'brand' || item.kind === 'catalog');
}

/** Fetch suggestions shortly after typing stops. Failures just mean no suggestions. */
export function useSearchSuggestions(input: string, enabled: boolean) {
  const authenticatedFetch = useAuthenticatedFetch();
  const [items, setItems] = useState<Suggestion[]>([]);
  const [active, setActive] = useState(-1);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!enabled || input.trim().length < 2) { setItems([]); return; }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await authenticatedFetch(`${API_BASE}/api/suggest?${new URLSearchParams({ q: input })}`, { signal: controller.signal });
        if (!response.ok) return;
        const body = await response.json();
        if (Array.isArray(body?.suggestions)) {
          setItems(body.suggestions.filter(validSuggestion));
          setActive(-1);
        }
      } catch { /* suggestions are optional */ }
    }, 120);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [input, enabled, authenticatedFetch]);

  const visible = open && items.length > 0;

  /** Arrow keys move, Enter picks the highlighted suggestion, Escape closes. */
  function onKeyDown(event: KeyboardEvent<HTMLInputElement>, choose: (text: string) => void) {
    if (!visible) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      // -1 means the typed text itself; moving past either end wraps around through it.
      const last = items.length - 1;
      const down = event.key === 'ArrowDown';
      setActive(current => down ? (current >= last ? -1 : current + 1) : (current <= -1 ? last : current - 1));
    } else if (event.key === 'Enter' && active >= 0) {
      event.preventDefault();
      choose(items[active].text);
    } else if (event.key === 'Escape') {
      setOpen(false);
    }
  }

  const comboboxProps = {
    role: 'combobox' as const,
    'aria-expanded': visible,
    'aria-controls': LIST_ID,
    'aria-autocomplete': 'list' as const,
    'aria-activedescendant': visible && active >= 0 ? `${LIST_ID}-${active}` : undefined,
  };
  return { items, active, setActive, open: visible, setOpen, onKeyDown, comboboxProps };
}

/** The typed part stays plain and the completion is bold, so the new words stand out. */
function Highlighted({ text, typed }: { text: string; typed: string }) {
  const prefix = typed.trim().toLowerCase();
  if (prefix && text.toLowerCase().startsWith(prefix)) {
    return <span>{text.slice(0, prefix.length)}<strong className="font-semibold">{text.slice(prefix.length)}</strong></span>;
  }
  return <span>{text}</span>;
}

export function SuggestionList({ items, active, typed, onChoose, onHover }: {
  items: Suggestion[]; active: number; typed: string; onChoose: (text: string) => void; onHover: (index: number) => void;
}) {
  return <ul id={LIST_ID} role="listbox" aria-label="Search suggestions" className="absolute inset-x-0 top-full z-30 m-0 mt-2 list-none overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--surface-fff)] p-1 text-left shadow-lg">
    {items.map((item, index) => <li key={`${item.kind}:${item.text}`} id={`${LIST_ID}-${index}`} role="option" aria-selected={index === active}
      onMouseDown={event => { event.preventDefault(); onChoose(item.text); }} onMouseEnter={() => onHover(index)}
      className={`flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-[13px] text-[var(--ink)] ${index === active ? 'bg-[var(--sage)]' : ''}`}>
      <span aria-hidden="true" className="w-4 shrink-0 text-center text-[var(--muted)]">{item.kind === 'recent' ? '↺' : item.kind === 'brand' ? '◆' : '⌕'}</span>
      <span className="min-w-0 flex-1 truncate"><Highlighted text={item.text} typed={typed} /></span>
      {item.kind !== 'catalog' && <span className="shrink-0 text-[11px] text-[var(--muted)]">{KIND_LABEL[item.kind]}</span>}
    </li>)}
  </ul>;
}
