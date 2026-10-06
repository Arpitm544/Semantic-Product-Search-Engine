'use client';

import { useId } from 'react';

export function artworkType(product) {
  const title = product.title.toLowerCase();
  if (/headphone|headset/.test(title)) return 'headphones';
  if (/backpack/.test(title)) return 'backpack';
  if (/bottle|canteen/.test(title)) return 'bottle';
  if (/jacket|parka|raincoat/.test(title)) return 'jacket';
  if (/earbud/.test(title)) return 'earbuds';
  if (/laptop|keyboard|monitor|mouse|ssd/.test(title)) return 'computer';
  if (/shoe|boot|sandal/.test(title)) return 'shoe';
  if (/watch|tracker/.test(title)) return 'watch';
  if (/chair|cushion/.test(title)) return 'chair';
  if (/espresso|coffee|blender|kettle/.test(title)) return 'coffee';
  if (/camera|binocular/.test(title)) return 'camera';
  return 'object';
}

export default function ProductArtwork({ product }) {
  const type = artworkType(product);
  const id = useId().replaceAll(':', '');
  if (['headphones', 'backpack', 'bottle', 'jacket'].includes(type)) {
    return <div className={`product-art product-art--${type}`} role="img" aria-label={`Illustrative ${type} artwork`} />;
  }
  const gradient = `url(#material-${id})`;
  const line = '#687776';
  return (
    <div className={`product-art product-art--vector product-art--${type}`}>
      <svg viewBox="0 0 280 280" role="img" aria-label={`Illustrative artwork for ${product.title}`}>
        <defs><linearGradient id={`material-${id}`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#f9faf7" /><stop offset=".5" stopColor="#a8b7ad" /><stop offset="1" stopColor="#788986" /></linearGradient></defs>
        <ellipse cx="140" cy="231" rx="76" ry="10" fill="#334b43" opacity=".09" />
        {type === 'computer' && <g stroke={line} strokeWidth="2"><rect x="55" y="61" width="170" height="128" rx="9" fill={gradient} /><rect x="64" y="70" width="152" height="105" rx="3" fill="#415b5b" /><path d="m65 159 57-68 36 42 47-51v80H65Z" fill="#a8bfc0" stroke="none" /><path d="M55 189 34 214q-2 10 10 10h192q12 0 10-10l-21-25Z" fill={gradient} /><path d="M37 215h206M115 211h50" stroke="#bec9c2" /></g>}
        {type === 'earbuds' && <g stroke={line} strokeWidth="2"><rect x="61" y="142" width="158" height="79" rx="30" fill={gradient} /><path d="M64 165h151" stroke="#a2b0a6" /><rect x="88" y="64" width="32" height="66" rx="15" fill={gradient} /><rect x="160" y="64" width="32" height="66" rx="15" fill={gradient} /><ellipse cx="100" cy="72" rx="15" ry="11" fill="#e8ede9" /><ellipse cx="180" cy="72" rx="15" ry="11" fill="#e8ede9" /><circle cx="140" cy="183" r="3" fill="#748a76" /></g>}
        {type === 'shoe' && <g stroke={line} strokeWidth="2"><path d="M57 191q21-32 20-75l48 10 18 30 73 28q20 12 11 28H52q-9-12 5-21Z" fill={gradient} /><path d="m61 203 153 2q12 0 14-4l-1 17H51v-15Z" fill="#e8e9df" /><path d="m133 156-29 5m39 3-30 7m40 1-30 7M77 128l-7 53" /><path d="m157 187 32 8" stroke="#485953" strokeWidth="7" /></g>}
        {type === 'watch' && <g stroke={line} strokeWidth="2"><rect x="114" y="35" width="52" height="202" rx="15" fill="#8f9c8d" /><rect x="94" y="92" width="92" height="99" rx="25" fill={gradient} /><rect x="102" y="100" width="76" height="83" rx="18" fill="#334d49" /><circle cx="140" cy="141" r="25" fill="none" stroke="#c3d6bf" strokeWidth="3" /><path d="M140 123v19l11 11" stroke="#ebeee6" /><path d="M189 128v15" strokeWidth="5" /></g>}
        {type === 'chair' && <g stroke={line} strokeWidth="3"><path d="M93 55q47-20 94 0v102H93Z" fill={gradient} /><path d="M101 66h78v80h-78Z" fill="#758a81" /><path d="M78 157h124v23H78Z" fill={gradient} /><path d="M73 125v45m134-45v45M140 181v48m-59 1 59-18 59 18M101 86h76M101 106h76M101 126h76" /><circle cx="81" cy="234" r="6" fill={line} /><circle cx="199" cy="234" r="6" fill={line} /><circle cx="140" cy="236" r="6" fill={line} /></g>}
        {type === 'coffee' && <g stroke={line} strokeWidth="2"><rect x="79" y="57" width="114" height="168" rx="15" fill={gradient} /><rect x="90" y="76" width="92" height="31" rx="5" fill="#435d56" /><circle cx="111" cy="91" r="5" fill="#dee5db" /><circle cx="136" cy="91" r="5" fill="#dee5db" /><circle cx="161" cy="91" r="5" fill="#dee5db" /><path d="M136 110v29m-17 0h34" strokeWidth="6" /><path d="M111 157h53v36q-27 15-53 0Z" fill="#f1eee4" /><path d="M164 161h14q9 20-14 20M90 211h92" /><path d="M172 121h20v39" strokeWidth="5" /></g>}
        {type === 'camera' && <g stroke={line} strokeWidth="2"><rect x="60" y="92" width="161" height="104" rx="15" fill={gradient} /><path d="M78 92V78h44v14m65-1V81h18v10" fill="#a4b2a6" /><circle cx="139" cy="144" r="42" fill="#4c625d" /><circle cx="139" cy="144" r="30" fill="#7e9490" /><circle cx="139" cy="144" r="20" fill="#344e50" /><circle cx="131" cy="135" r="6" fill="#d6e8df" opacity=".6" /><rect x="188" y="105" width="18" height="9" rx="2" fill="#f3f5ee" /></g>}
        {type === 'object' && <g stroke={line} strokeWidth="2"><path d="m76 83 64-28 64 28v115l-64 31-64-31Z" fill={gradient} /><path d="m76 83 64 29 64-29M140 112v117" /><path d="m102 72 65 29v30l-18 8v-30L84 80Z" fill="#d8e0d4" stroke="none" /><path d="m91 173 27 12m-27-1 16 7" /></g>}
      </svg>
    </div>
  );
}
