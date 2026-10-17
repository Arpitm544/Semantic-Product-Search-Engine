'use client';

import { useEffect, useState } from 'react';

export default function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const sync = () => setDark(document.documentElement.dataset.theme === 'dark');
    const restore = (event: StorageEvent) => {
      if (event.key !== 'semantic-theme') return;
      document.documentElement.dataset.theme = event.newValue === 'dark' ? 'dark' : 'light';
      sync();
    };
    sync();
    window.addEventListener('semantic-theme-change', sync);
    window.addEventListener('storage', restore);
    return () => {
      window.removeEventListener('semantic-theme-change', sync);
      window.removeEventListener('storage', restore);
    };
  }, []);

  function toggle() {
    const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('semantic-theme', theme); } catch { /* Theme still works when storage is unavailable. */ }
    window.dispatchEvent(new Event('semantic-theme-change'));
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-pressed={dark}
      title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-current bg-transparent text-inherit opacity-90 hover:opacity-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4"
    >
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {dark ? <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" /></> : <path d="M20.8 13A9 9 0 0 1 11 3.2 9 9 0 1 0 20.8 13Z" />}
      </svg>
    </button>
  );
}
