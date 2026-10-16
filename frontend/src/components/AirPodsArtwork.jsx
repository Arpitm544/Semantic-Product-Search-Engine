import { useId } from 'react';

// A lightweight original illustration for loading, reduced motion, and mobile.
export default function AirPodsArtwork() {
  const id = useId().replaceAll(':', '');
  return <svg className="airpods-artwork" viewBox="0 0 500 500" role="img" aria-label="Illustration of AirPods Max with a mesh headband and rounded aluminum ear cups">
    <defs>
      <linearGradient id={`${id}-metal`} x1="0" x2="1" y1="0" y2=".3"><stop stopColor="#a4b1ad" /><stop offset=".35" stopColor="#e6ebe7" /><stop offset=".68" stopColor="#c8d3cc" /><stop offset="1" stopColor="#849a8c" /></linearGradient>
      <linearGradient id={`${id}-pad`}><stop stopColor="#63746a" /><stop offset=".45" stopColor="#b7c3b7" /><stop offset="1" stopColor="#6c8071" /></linearGradient>
      <pattern id={`${id}-knit`} width="4" height="4" patternUnits="userSpaceOnUse"><path d="M0 0h4v4" fill="none" stroke="#9aa99b" strokeWidth=".8" /></pattern>
      <filter id={`${id}-shadow`}><feGaussianBlur stdDeviation="9" /></filter>
    </defs>
    <ellipse cx="250" cy="433" rx="117" ry="14" fill="#698779" opacity=".13" filter={`url(#${id}-shadow)`} />
    <g transform="rotate(-10 250 250)">
      <path d="M130 242v-72C130 70 370 70 370 170v72" fill="none" stroke="#899b8d" strokeWidth="17" />
      <path d="M144 164c6-62 206-62 212 0v28c-54-47-158-47-212 0Z" fill={`url(#${id}-knit)`} stroke="#a9b8a8" strokeWidth="5" />
      <path d="M130 200v56m240-56v56" stroke={`url(#${id}-metal)`} strokeWidth="12" strokeLinecap="round" />
      <g transform="rotate(7 150 320)"><rect x="102" y="244" width="90" height="160" rx="40" fill={`url(#${id}-pad)`} /><rect x="89" y="248" width="89" height="150" rx="35" fill={`url(#${id}-metal)`} stroke="#a4b4a8" /><path d="M98 278v94" stroke="#edf1ec" strokeWidth="2" opacity=".65" /></g>
      <g transform="rotate(-7 350 320)"><rect x="302" y="244" width="90" height="160" rx="40" fill={`url(#${id}-pad)`} /><rect x="320" y="248" width="91" height="150" rx="35" fill={`url(#${id}-metal)`} stroke="#a4b4a8" /><path d="M403 278v94" stroke="#edf1ec" strokeWidth="2" opacity=".65" /><rect x="356" y="237" width="19" height="10" rx="4" fill="#9dac9f" /><rect x="389" y="245" width="13" height="4" rx="2" fill="#84988c" /><path d="M360 394h14" stroke="#778d7e" strokeWidth="3" strokeLinecap="round" /></g>
    </g>
  </svg>;
}
