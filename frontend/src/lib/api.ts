import { useAuth } from '@clerk/nextjs';
import { useCallback } from 'react';

export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

export function useAuthenticatedFetch() {
  const { getToken } = useAuth();
  return useCallback(async (input: RequestInfo | URL, init?: RequestInit) => {
    const token = await getToken();
    if (!token) throw new Error('Your session has expired. Sign in again to continue.');
    const headers = new Headers(init?.headers);
    headers.set('Authorization', `Bearer ${token}`);
    const response = await fetch(input, { ...init, headers, cache: 'no-store' });
    if (response.status === 401) throw new Error('Your session has expired. Sign in again to continue.');
    return response;
  }, [getToken]);
}
