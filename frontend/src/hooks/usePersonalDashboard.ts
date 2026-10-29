'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useUser } from '@clerk/nextjs';
import { API_BASE, useAuthenticatedFetch } from '@/lib/api';
import type { SearchProduct } from '@/lib/types';

export interface HistoryEntry {
  id: string; query: string; source: 'mongo' | 'serpapi'; fuzzy: boolean;
  resultCount: number; searchedAt: string;
}
export interface PersonalData {
  searchCount: number; savedCount: number; recentSearches: HistoryEntry[];
  hasMoreSearches: boolean;
  savedProducts: { id: string; product: SearchProduct; source: string; savedAt: string }[];
}
function errorMessage(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}

function appendHistory(old: PersonalData | null, result: { hasMore: boolean; items: HistoryEntry[] }) {
  if (!old) return old;
  const existing = new Set(old.recentSearches.map(entry => entry.id));
  return { ...old, hasMoreSearches: result.hasMore,
    recentSearches: [...old.recentSearches, ...result.items.filter(entry => !existing.has(entry.id))] };
}

type DashboardRequest = ReturnType<typeof useAuthenticatedFetch>;

async function fetchDashboard(request: DashboardRequest): Promise<PersonalData> {
  const response = await request(`${API_BASE}/api/personal-dashboard`);
  if (!response.ok) throw new Error('Could not load your personal dashboard. Please try again.');
  return response.json();
}

async function fetchHistoryPage(request: DashboardRequest, offset: number) {
  const response = await request(`${API_BASE}/api/search-history?offset=${offset}&limit=6`);
  if (!response.ok) throw new Error('Could not load more searches. Please try again.');
  return response.json();
}

async function deleteHistory(request: DashboardRequest, id?: string) {
  const response = await request(`${API_BASE}/api/search-history${id ? `/${encodeURIComponent(id)}` : ''}`, { method: 'DELETE' });
  if (!response.ok) throw new Error('Could not delete search history. Please try again.');
}

function deletionNotice(id?: string) {
  return id ? 'Search removed from your history.' : 'Your search history has been cleared.';
}

function useDashboardState() {
  const [data, setData] = useState<PersonalData | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  const [mutation, setMutation] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [notice, setNotice] = useState('');
  const version = useRef(0);
  return { data, setData, error, setError, busy, setBusy, mutation, setMutation, confirmClear, setConfirmClear, notice, setNotice, version };
}

type DashboardState = ReturnType<typeof useDashboardState>;

async function loadDashboard(state: DashboardState, request: DashboardRequest) {
  const { version, setBusy, setError, setData } = state;
  const current = ++version.current;
  setBusy(true); setError('');
  try {
    const result = await fetchDashboard(request);
    if (current === version.current) setData(result);
  } catch (reason) {
    if (current === version.current) setError(errorMessage(reason, 'Could not load your dashboard.'));
  } finally { if (current === version.current) setBusy(false); }
}

async function mutateHistory(state: DashboardState, request: DashboardRequest, load: () => Promise<void>, id?: string) {
  const { mutation, busy, setMutation, setError, setNotice, setConfirmClear } = state;
  if (mutation || busy) return;
  setMutation(id || 'clear'); setError(''); setNotice('');
  try {
    await deleteHistory(request, id);
    setConfirmClear(false);
    setNotice(deletionNotice(id));
    await load();
  } catch (reason) { setError(errorMessage(reason, 'Please try again.')); }
  finally { setMutation(null); }
}

async function loadHistoryPage(state: DashboardState, request: DashboardRequest) {
  const { data, mutation, busy, version, setBusy, setError, setData } = state;
  if (!data) return;
  if (mutation) return;
  if (busy) return;
  setBusy(true); setError('');
  const current = version.current;
  try {
    const result = await fetchHistoryPage(request, data.recentSearches.length);
    if (current === version.current) setData(old => appendHistory(old, result));
  } catch (reason) { if (current === version.current) setError(errorMessage(reason, 'Please try again.')); }
  finally { if (current === version.current) setBusy(false); }
}

export function usePersonalDashboard() {
  const request = useAuthenticatedFetch();
  const { user } = useUser();
  const state = useDashboardState();
  const { version, setData, setNotice, setConfirmClear } = state;
  const userId = user?.id;
  // Loading uses only stable state setters and the version ref.
  const load = useCallback(() => loadDashboard(state, request), [request]);
  useEffect(() => {
    setData(null); setNotice(''); setConfirmClear(false);
    if (userId) void load();
    return () => { version.current++; };
  }, [load, userId]);
  return { ...state, user, load,
    mutate: (id?: string) => mutateHistory(state, request, load, id),
    loadMore: () => loadHistoryPage(state, request),
  };
}
