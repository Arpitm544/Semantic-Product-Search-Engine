import { PHASE_DEVELOPMENT_SERVER } from 'next/constants.js';

/** @param {string} phase @returns {import('next').NextConfig} */
export default function nextConfig(phase) {
  return {
    reactStrictMode: true,
    poweredByHeader: false,
    async headers() {
      return [{
        source: '/models/airpods-max-meshopt-v1.glb',
        headers: [{ key: 'Cache-Control', value: 'public, max-age=31536000, immutable' }],
      }];
    },
    // A production build must not overwrite a running dev server's chunks.
    distDir: phase === PHASE_DEVELOPMENT_SERVER ? '.next-dev' : '.next',
  };
}
