'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useUser } from '@clerk/nextjs';
import { API_BASE, applyIfCurrent, readJsonResponse, requireResponseOk, useAuthenticatedFetch } from './api';
import { accountError } from './account';
import type { SearchProduct } from './types';

export interface HistoryEntry {
  id: string; query: string; source: 'mongo' | 'serpapi'; fuzzy: boolean;
  resultCount: number; searchedAt: string; usePreferences?: boolean;
}
export interface PersonalData {
  searchCount: number; savedCount: number; recentSearches: HistoryEntry[];
  hasMoreSearches: boolean;
  savedProducts: { id: string; product: SearchProduct; source: string; savedAt: string }[];
}
function historyDeletion(id?: string) {
  if (!id) return { mutation: 'clear', path: '', notice: 'Your search history has been cleared.' };
  return { mutation: id, path: `/${encodeURIComponent(id)}`, notice: 'Search removed from your history.' };
}

function appendHistory(old: PersonalData | null, result: { hasMore: boolean; items: HistoryEntry[] }) {
  if (!old) return old;
  const ids = new Set(old.recentSearches.map(item => item.id));
  return { ...old, hasMoreSearches: result.hasMore, recentSearches: [...old.recentSearches, ...result.items.filter(entry => !ids.has(entry.id))] };
}

export function usePersonalDashboard() {
  const request = useAuthenticatedFetch();
  const { user } = useUser();
  const [data, setData] = useState<PersonalData | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  const [mutation, setMutation] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [notice, setNotice] = useState('');
  const version = useRef(0);
  const userId = user?.id;
  const blocked = Boolean(mutation) || busy;
  const load = useCallback(async () => {
    const current = ++version.current;
    setBusy(true); setError('');
    try {
      const response = await request(`${API_BASE}/api/personal-dashboard`);
      const result = await readJsonResponse<PersonalData>(response, 'Could not load your personal dashboard. Please try again.');
      applyIfCurrent(version, current, () => setData(result));
    } catch (reason) {
      applyIfCurrent(version, current, () => setError(accountError(reason, 'Could not load your dashboard.')));
    } finally { applyIfCurrent(version, current, () => setBusy(false)); }
  }, [request]);
  useEffect(() => {
    setData(null); setNotice(''); setConfirmClear(false);
    if (userId) void load();
    return () => { version.current++; };
  }, [load, userId]);

  async function mutate(id?: string) {
    if (blocked) return;
    const change = historyDeletion(id);
    setMutation(change.mutation); setError(''); setNotice('');
    try {
      const response = await request(`${API_BASE}/api/search-history${change.path}`, { method: 'DELETE' });
      requireResponseOk(response, 'Could not delete search history. Please try again.');
      setConfirmClear(false);
      setNotice(change.notice);
      await load();
    } catch (reason) { setError(accountError(reason)); }
    finally { setMutation(null); }
  }
  async function loadMore() {
    if (!data) return;
    if (blocked) return;
    setBusy(true); setError('');
    const current = version.current;
    try {
      const response = await request(`${API_BASE}/api/search-history?offset=${data.recentSearches.length}&limit=6`);
      const result = await readJsonResponse<{ hasMore: boolean; items: HistoryEntry[] }>(response, 'Could not load more searches. Please try again.');
      applyIfCurrent(version, current, () => setData(old => appendHistory(old, result)));
    } catch (reason) { applyIfCurrent(version, current, () => setError(accountError(reason))); }
    finally { applyIfCurrent(version, current, () => setBusy(false)); }
  }
  return { user, data, error, busy, blocked, mutation, confirmClear, setConfirmClear, notice, load, mutate, loadMore };
}

