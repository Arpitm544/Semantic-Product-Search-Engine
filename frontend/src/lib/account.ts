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
      throw new Error(accountResponseMessage(body) || 'Your request could not be completed. Please try again.');
    }
    return body;
  }, [request]);
}
function accountResponseMessage(body: { detail?: string | { msg?: string }[]; error?: string }) {
  if (typeof body.detail === 'string') return body.detail;
  if (Array.isArray(body.detail)) return body.detail[0]?.msg;
  return body.error;
}

type ResourceState<T> = {
  api: ReturnType<typeof useAccountApi>; path: string; version: React.RefObject<number>;
  setBusy: React.Dispatch<React.SetStateAction<boolean>>;
  setError: React.Dispatch<React.SetStateAction<string>>;
  setData: React.Dispatch<React.SetStateAction<T | null>>;
  setNotice: React.Dispatch<React.SetStateAction<string>>;
  ownerRef: React.RefObject<ReturnType<typeof useAuth>['userId']>;
  userId: ReturnType<typeof useAuth>['userId']; busy: boolean;
};
function useResourceReload<T>({ api, path, version, setBusy, setError, setData }: ResourceState<T>) {
  const reload = useCallback(async () => {
    const current = ++version.current;
    setBusy(true); setError('');
    try { const result = await api<T>(path); if (current === version.current) setData(result); }
    catch (reason) { if (current === version.current) setError(accountError(reason)); }
    finally { if (current === version.current) setBusy(false); }
  }, [api, path]);
  return reload;
}
function useResourceMutation<T>({ busy, setBusy, setError, setNotice, ownerRef, userId }: ResourceState<T>, reload: () => Promise<void>) {
  async function mutate<R>(task: () => Promise<R>, message = 'Changes saved.'): Promise<R | undefined> {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { const result = await task(); if (ownerRef.current !== userId) return; setNotice(message); await reload(); return result; }
    catch (reason) { if (ownerRef.current === userId) setError(accountError(reason)); }
    finally { if (ownerRef.current === userId) setBusy(false); }
  }
  return mutate;
}
export function accountError(reason: unknown, fallback = 'Please try again.') {
  return reason instanceof Error ? reason.message : fallback;
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
  const state = { api, path, version, setBusy, setError, setData, setNotice, ownerRef, userId, busy };
  const reload = useResourceReload(state);
  const mutate = useResourceMutation(state, reload);
  useEffect(() => { setData(null); setNotice(''); setError(''); if (isLoaded && userId) void reload(); else setBusy(!isLoaded); return () => { version.current++; }; }, [reload, isLoaded, userId]);
  return { data, setData, busy, error, setError, notice, reload, mutate, api };
}
function publicHttpUrl(url: URL) {
  if (!['http:', 'https:'].includes(url.protocol)) return undefined;
  if (url.username) return undefined;
  if (url.password) return undefined;
  return url.href;
}

export function safeProductUrl(value = '') {
  try { return publicHttpUrl(new URL(value)); } catch { return undefined; }
}

export function productPrice(product: SearchProduct, unavailable = 'Unavailable') {
  return product.priceLabel || (product.price != null ? `${product.currency || ''} ${product.price}`.trim() : unavailable);
}
