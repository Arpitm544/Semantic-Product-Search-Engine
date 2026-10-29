'use client';
import { useAuth } from '@clerk/nextjs';
import { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE, useAuthenticatedFetch } from './api';
import type { SearchProduct } from './types';

export interface SavedItem { id: string; identity: string; source: 'mongo' | 'serpapi'; product: SearchProduct; savedAt: string }
export interface ProductCollection { id: string; name: string; productIds: string[]; updatedAt: string; items?: SavedItem[] }
export interface Comparison { id: string; name: string; updatedAt: string; products: { savedId: string; source: string; product: SearchProduct }[] }
export interface Preferences { defaultSource: 'mongo' | 'serpapi'; applyByDefault: boolean; currency: string; minBudget: number | null; maxBudget: number | null; categories: string[]; brands: string[]; inStockOnly: boolean }
export type Page<T> = { items: T[]; hasMore: boolean };
export function useAccountApi() {
  const request = useAuthenticatedFetch();
  return useCallback(async <T,>(path: string, options?: RequestInit): Promise<T> => {
    const response = await request(`${API_BASE}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options?.headers } });
    const body = await response.json();
    if (!response.ok) {
      const message = typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? body.detail[0]?.msg : body.error;
      throw new Error(message || 'Your request could not be completed. Please try again.');
    }
    return body;
  }, [request]);
}
export function useAccountResource<T>(path: string) {
  const api = useAccountApi();
  const { userId, isLoaded } = useAuth();
  const ownerRef = useRef(userId);
  ownerRef.current = userId;
  const [data, setData] = useState<T | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const version = useRef(0);
  const reload = useCallback(async () => {
    const current = ++version.current;
    setBusy(true); setError('');
    try { const result = await api<T>(path); if (current === version.current) setData(result); }
    catch (reason) { if (current === version.current) setError(accountError(reason)); }
    finally { if (current === version.current) setBusy(false); }
  }, [api, path]);
  useEffect(() => { setData(null); setNotice(''); setError(''); if (isLoaded && userId) void reload(); else setBusy(!isLoaded); return () => { version.current++; }; }, [reload, isLoaded, userId]);
  const mutate = useAccountMutation({ busy, setBusy, setError, setNotice, ownerRef, userId, reload });
  return { data, setData, busy, error, setError, notice, reload, mutate, api };
}
function accountError(reason: unknown) {
  return reason instanceof Error ? reason.message : 'Please try again.';
}
function useAccountMutation({ busy, setBusy, setError, setNotice, ownerRef, userId, reload }: {
  busy: boolean; setBusy: (value: boolean) => void; setError: (value: string) => void; setNotice: (value: string) => void;
  ownerRef: { current: string | null | undefined }; userId: string | null | undefined; reload: () => Promise<void>;
}) {
  async function mutate<R>(task: () => Promise<R>, message = 'Changes saved.'): Promise<R | undefined> {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { const result = await task(); if (ownerRef.current !== userId) return; setNotice(message); await reload(); return result; }
    catch (reason) { if (ownerRef.current === userId) setError(accountError(reason)); }
    finally { if (ownerRef.current === userId) setBusy(false); }
  }
  return mutate;
}
export function safeProductUrl(value?: string) {
  try { const url = new URL(value || ''); return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : undefined; } catch { return undefined; }
}
export function productPrice(product: SearchProduct) {
  return product.priceLabel || (product.price != null ? `${product.currency || ''} ${product.price}`.trim() : 'Unavailable');
}
