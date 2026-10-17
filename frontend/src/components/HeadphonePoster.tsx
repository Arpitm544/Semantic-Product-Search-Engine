'use client';

import Image from 'next/image';
import { useState } from 'react';

type HeadphonePosterProps = {
  loading?: boolean;
  failed?: boolean;
  onRetry?: () => void;
};

/** A still of the GLB model, with a text fallback if the image also fails. */
export default function HeadphonePoster({ loading = false, failed = false, onRetry }: HeadphonePosterProps) {
  const [imageFailed, setImageFailed] = useState(false);

  return (
    <div className="absolute inset-0 overflow-hidden rounded-[15px] bg-[var(--surface-edf2ef)]" aria-busy={loading}>
      {imageFailed ? (
        <div className="flex h-full flex-col items-center justify-center gap-3 px-6 pb-16 text-center text-[var(--surface-53615b)]">
          <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
            <path d="M4 14v-3a8 8 0 0 1 16 0v3M4 13H3v7h4v-7H4Zm16 0h1v7h-4v-7h3Z" />
          </svg>
          <strong className="text-lg font-medium">AirPods Max</strong>
          <p className="text-xs">Product preview unavailable</p>
        </div>
      ) : (
        <Image
          src="/images/airpods-max-render.jpg"
          alt="AirPods Max rendered from the product story’s 3D model"
          fill
          sizes="(max-width: 780px) 100vw, 600px"
          className="object-contain"
          onError={() => setImageFailed(true)}
        />
      )}
      {(loading || failed) && (
        <div className={`absolute inset-x-3 bottom-4 z-10 flex flex-wrap items-center justify-center gap-3 rounded-xl bg-[var(--surface-fafbf6ed)] px-3 py-2 text-center text-[11px] text-[var(--surface-53615b)] ${loading ? 'motion-reduce:hidden' : ''}`}>
          <span role="status" aria-live="polite" className="inline-flex items-center gap-2">
            {loading && <span className="h-3 w-3 rounded-full border border-[var(--surface-8caa9b)] border-t-transparent motion-safe:animate-spin" aria-hidden="true" />}
            {loading ? 'Loading 3D view…' : imageFailed ? '3D view unavailable.' : '3D view unavailable. Showing product preview.'}
          </span>
          {failed && onRetry && (
            <button type="button" onClick={onRetry} className="rounded-full border border-[var(--surface-aab8ab)] bg-[var(--surface-fff)] px-3 py-1.5 text-[11px] text-[var(--surface-37483e)] hover:bg-[var(--surface-e5ebdc)] focus-visible:outline-2">
              Retry 3D
            </button>
          )}
        </div>
      )}
    </div>
  );
}
