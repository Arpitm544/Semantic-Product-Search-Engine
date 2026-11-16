'use client';
import { classes } from '@/lib/classes';

import type { CatalogProduct } from '@/lib/types';
import { useId } from 'react';

type ArtworkProduct = Pick<CatalogProduct, 'title'> & { id?: string | number };

/** Pick an illustration from the title. Catalog books are spotted by their
 * ISBN-style ASIN (ten digits, or nine and an X), since titles rarely say "book". */
export function artworkType(product: ArtworkProduct) {
  const title = product.title.toLowerCase();
  const asin = String(product.id ?? '').split(':').pop() ?? '';
  // An ISBN-style ASIN is the surest sign of a book ("Those Shoes" is a book, not shoes).
  if (/^[0-9]{9}[0-9x]$/i.test(asin)) return 'book';
  if (/headphone|headset/.test(title)) return 'headphones';
  if (/backpack/.test(title)) return 'backpack';
  if (/bottle|canteen/.test(title)) return 'bottle';
  if (/jacket|parka|raincoat/.test(title)) return 'jacket';
  if (/earbud/.test(title)) return 'earbuds';
  if (/laptop|keyboard|monitor|mouse|ssd/.test(title)) return 'computer';
  if (/shoe|boot|sandal|sneaker|slipper/.test(title)) return 'shoe';
  if (/watch|tracker/.test(title)) return 'watch';
  if (/chair|cushion/.test(title)) return 'chair';
  if (/espresso|coffee|blender|kettle/.test(title)) return 'coffee';
  if (/camera|binocular/.test(title)) return 'camera';
  if (/\b(book|novel|paperback|hardcover|edition)\b/.test(title)) return 'book';
  if (/iphone|phone|galaxy|charger|charging|usb|cable|screen protector|adapter|ipad|tablet/.test(title)) return 'phone';
  if (/shirt|dress|sleeve|costume|hoodie|sweater|pants|jeans|legging|socks|skirt|shorts|\bbra\b|underwear|pajama|blouse|\btee\b|swimsuit|bikini|\bcoat\b/.test(title)) return 'clothing';
  if (/hair|face|skin|cream|serum|shampoo|conditioner|lotion|makeup|lipstick|nail|perfume|mascara|eyeliner|moisturiz|soap|beard|razor/.test(title)) return 'beauty';
  if (/kitchen|\bcups?\b|\bmugs?\b|\bpans?\b|\bpots?\b|knife|knives|plate|bowl|utensil|cookware|spatula|tumbler|baking|stainless/.test(title)) return 'kitchen';
  if (/\btoys?\b|lego|puzzle|\bdolls?\b|\bgames?\b|\bkids?\b|\bbaby\b|party|plush|balloon|christmas/.test(title)) return 'toy';
  if (/\btools?\b|drill|screwdriver|wrench|plier|hammer|\bsaw\b|batter(y|ies)|garden|\bhose\b|replacement/.test(title)) return 'tool';
  if (/lamp|light|decor|pillow|curtain|\brugs?\b|storage|holder|candle|\bwall\b|frame|blanket|\bmats?\b|towel|sheet/.test(title)) return 'home';
  // Footwear named by activity ("Speedcross 4 Trail Running"); clothing is matched earlier.
  if (/\b(running|trail|hiking|walking|trainers?)\b/.test(title)) return 'shoe';
  return 'object';
}

type Tint = [light: string, mid: string, dark: string];
const DEFAULT_TINT: Tint = ['#f9faf7', '#a8b7ad', '#788986'];
const TINTS: [RegExp, Tint][] = [
  [/^black$/i, ['#8a918e', '#454d4b', '#262c2b']],
  [/^(white|ivory|cream|off-white)$/i, ['#ffffff', '#ecede7', '#c9cfc8']],
  [/^(silver|gr[ae]y|charcoal)$/i, ['#f3f5f3', '#b9c0be', '#7f8987']],
  [/^(blue|light blue|sky blue|teal)$/i, ['#e3edf8', '#7d9cc4', '#4f6f98']],
  [/^navy( blue)?$/i, ['#b8c4d8', '#4a5c80', '#2c3a57']],
  [/^(red|burgundy|wine)$/i, ['#f6dcd8', '#c06a62', '#8e3f39']],
  [/^(pink|rose|blush)$/i, ['#fbe9ee', '#dca2b2', '#b26f84']],
  [/^(green|olive|mint|sage)$/i, ['#e6efe2', '#8daa86', '#5c7a57']],
  [/^(brown|coffee|chocolate|tan|khaki|beige|camel)$/i, ['#f1e7dc', '#b39373', '#7c5e44']],
  [/^(gold|yellow|mustard)$/i, ['#faf1d6', '#d6b864', '#a38534']],
  [/^(purple|lavender|violet)$/i, ['#eee8f6', '#9d89bd', '#6c5a8d']],
  [/^(orange|coral|peach)$/i, ['#fbe7d8', '#dc9562', '#a9623a']],
];

/** Tint with the first recognised colour tag; without one, use the first
 * colour word in the title (e.g. "Running Shoe, Black/Black"). */
export function tintFor(colors?: string[], title?: string): Tint {
  const candidates = [...(colors ?? []), ...(title ?? '').split(/[^A-Za-z-]+/)];
  for (const color of candidates) {
    const match = TINTS.find(([pattern]) => pattern.test(color.trim()));
    if (match) return match[1];
  }
  return DEFAULT_TINT;
}

export default function ProductArtwork({ product, colors }: { product: ArtworkProduct; colors?: string[] }) {
  const type = artworkType(product);
  const id = useId().replaceAll(':', '');
  if (['headphones', 'backpack', 'bottle', 'jacket'].includes(type)) {
    return <div className={classes(`product-art product-art--${type}`)} role="img" aria-label={`Illustrative artwork for ${product.title}`} />;
  }
  const [light, mid, dark] = tintFor(colors, product.title);
  const gradient = `url(#material-${id})`;
  const line = '#687776';
  return (
    <div className={classes(`product-art product-art--vector product-art--${type}`)}>
      <svg viewBox="0 0 280 280" role="img" aria-label={`Illustrative artwork for ${product.title}`}>
        <defs><linearGradient id={`material-${id}`} x1="0" y1="0" x2="1" y2="1"><stop stopColor={light} /><stop offset=".5" stopColor={mid} /><stop offset="1" stopColor={dark} /></linearGradient></defs>
        <ellipse cx="140" cy="231" rx="76" ry="10" fill="#334b43" opacity=".09" />
        {type === 'computer' && <g stroke={line} strokeWidth="2"><rect x="55" y="61" width="170" height="128" rx="9" fill={gradient} /><rect x="64" y="70" width="152" height="105" rx="3" fill="#415b5b" /><path d="m65 159 57-68 36 42 47-51v80H65Z" fill="#a8bfc0" stroke="none" /><path d="M55 189 34 214q-2 10 10 10h192q12 0 10-10l-21-25Z" fill={gradient} /><path d="M37 215h206M115 211h50" stroke="#bec9c2" /></g>}
        {type === 'earbuds' && <g stroke={line} strokeWidth="2"><rect x="61" y="142" width="158" height="79" rx="30" fill={gradient} /><path d="M64 165h151" stroke="#a2b0a6" /><rect x="88" y="64" width="32" height="66" rx="15" fill={gradient} /><rect x="160" y="64" width="32" height="66" rx="15" fill={gradient} /><ellipse cx="100" cy="72" rx="15" ry="11" fill="#e8ede9" /><ellipse cx="180" cy="72" rx="15" ry="11" fill="#e8ede9" /><circle cx="140" cy="183" r="3" fill="#748a76" /></g>}
        {type === 'shoe' && <g fill="none" stroke={line} strokeWidth="2"><path d="M57 191q21-32 20-75l48 10 18 30 73 28q20 12 11 28H52q-9-12 5-21Z" fill={gradient} /><path d="m61 203 153 2q12 0 14-4l-1 17H51v-15Z" fill="#e8e9df" /><path d="m133 156-29 5m39 3-30 7m40 1-30 7M77 128l-7 53" /><path d="m157 187 32 8" stroke="#485953" strokeWidth="7" /></g>}
        {type === 'watch' && <g stroke={line} strokeWidth="2"><rect x="114" y="35" width="52" height="202" rx="15" fill="#8f9c8d" /><rect x="94" y="92" width="92" height="99" rx="25" fill={gradient} /><rect x="102" y="100" width="76" height="83" rx="18" fill="#334d49" /><circle cx="140" cy="141" r="25" fill="none" stroke="#c3d6bf" strokeWidth="3" /><path d="M140 123v19l11 11" stroke="#ebeee6" /><path d="M189 128v15" strokeWidth="5" /></g>}
        {type === 'chair' && <g fill="none" stroke={line} strokeWidth="3"><path d="M93 55q47-20 94 0v102H93Z" fill={gradient} /><path d="M101 66h78v80h-78Z" fill="#758a81" /><path d="M78 157h124v23H78Z" fill={gradient} /><path d="M73 125v45m134-45v45M140 181v48m-59 1 59-18 59 18M101 86h76M101 106h76M101 126h76" /><circle cx="81" cy="234" r="6" fill={line} /><circle cx="199" cy="234" r="6" fill={line} /><circle cx="140" cy="236" r="6" fill={line} /></g>}
        {type === 'coffee' && <g fill="none" stroke={line} strokeWidth="2"><rect x="79" y="57" width="114" height="168" rx="15" fill={gradient} /><rect x="90" y="76" width="92" height="31" rx="5" fill="#435d56" /><circle cx="111" cy="91" r="5" fill="#dee5db" /><circle cx="136" cy="91" r="5" fill="#dee5db" /><circle cx="161" cy="91" r="5" fill="#dee5db" /><path d="M136 110v29m-17 0h34" strokeWidth="6" /><path d="M111 157h53v36q-27 15-53 0Z" fill="#f1eee4" /><path d="M164 161h14q9 20-14 20M90 211h92" /><path d="M172 121h20v39" strokeWidth="5" /></g>}
        {type === 'camera' && <g stroke={line} strokeWidth="2"><rect x="60" y="92" width="161" height="104" rx="15" fill={gradient} /><path d="M78 92V78h44v14m65-1V81h18v10" fill="#a4b2a6" /><circle cx="139" cy="144" r="42" fill="#4c625d" /><circle cx="139" cy="144" r="30" fill="#7e9490" /><circle cx="139" cy="144" r="20" fill="#344e50" /><circle cx="131" cy="135" r="6" fill="#d6e8df" opacity=".6" /><rect x="188" y="105" width="18" height="9" rx="2" fill="#f3f5ee" /></g>}
        {type === 'book' && <g stroke={line} strokeWidth="2"><path d="M76 76h112q14 0 14 14v124q0 10-10 10H76Z" fill={gradient} /><path d="M92 76v148" stroke="#e8ede9" strokeWidth="3" /><path d="M76 76v148" /><rect x="108" y="104" width="72" height="13" rx="3" fill="#eef1ec" stroke="none" /><rect x="108" y="126" width="50" height="8" rx="3" fill="#eef1ec" stroke="none" /><path d="M64 224h148" /></g>}
        {type === 'phone' && <g stroke={line} strokeWidth="2"><rect x="94" y="40" width="92" height="190" rx="18" fill={gradient} /><rect x="103" y="58" width="74" height="150" rx="6" fill="#415b5b" /><rect x="128" y="47" width="24" height="5" rx="2.5" fill="#e8ede9" stroke="none" /><path d="M118 108h44M118 124h30" stroke="#a8bfc0" strokeWidth="4" strokeLinecap="round" /><path d="M140 230v12q0 14 18 14h42" fill="none" strokeWidth="4" /></g>}
        {type === 'clothing' && <g stroke={line} strokeWidth="2"><path d="M110 56 66 80l18 40 22-9v116h68V111l22 9 18-40-44-24q-30 22-60 0Z" fill={gradient} /><path d="M110 56q30 30 60 0" fill="none" /><path d="M106 150h68" stroke="#e8ede9" /></g>}
        {type === 'beauty' && <g stroke={line} strokeWidth="2"><rect x="82" y="100" width="58" height="126" rx="12" fill={gradient} /><path d="M100 100V78h22v22M111 78V62h30" fill="none" strokeWidth="5" strokeLinecap="round" /><rect x="94" y="140" width="34" height="40" rx="4" fill="#eef1ec" stroke="none" /><rect x="150" y="166" width="66" height="60" rx="12" fill={gradient} /><rect x="146" y="150" width="74" height="20" rx="6" fill="#d8e0d4" /></g>}
        {type === 'kitchen' && <g stroke={line} strokeWidth="2"><path d="M74 112q66-42 132 0" fill="#d8e0d4" /><circle cx="140" cy="86" r="8" fill="#d8e0d4" /><rect x="66" y="112" width="148" height="98" rx="16" fill={gradient} /><path d="M66 140H44M214 140h22" strokeWidth="7" strokeLinecap="round" /><path d="M82 168h116" stroke="#eef1ec" /></g>}
        {type === 'toy' && <g stroke={line} strokeWidth="2"><rect x="62" y="150" width="72" height="72" rx="10" fill={gradient} /><rect x="146" y="150" width="72" height="72" rx="10" fill="#d8e0d4" /><rect x="104" y="72" width="72" height="72" rx="10" fill={gradient} /><circle cx="98" cy="186" r="12" fill="#eef1ec" /><path d="m170 200 12-28 12 28Z" fill="#8fa596" /><path d="M128 108h24M140 96v24" stroke="#eef1ec" strokeWidth="6" strokeLinecap="round" /></g>}
        {type === 'tool' && <g stroke={line} strokeWidth="2"><path d="M190 58a38 38 0 0 0-50 48l-74 74a15 15 0 0 0 21 21l74-74a38 38 0 0 0 48-50l-22 22-20-5-5-20Z" fill={gradient} /><circle cx="78" cy="190" r="5" fill="#eef1ec" /></g>}
        {type === 'home' && <g stroke={line} strokeWidth="2"><path d="M102 64h76l30 78H72Z" fill={gradient} /><path d="M140 142v70" strokeWidth="6" /><ellipse cx="140" cy="216" rx="46" ry="10" fill="#d8e0d4" /><path d="M90 128h100" stroke="#eef1ec" /></g>}
        {type === 'object' && <g fill="none" stroke={line} strokeWidth="2"><path d="m76 83 64-28 64 28v115l-64 31-64-31Z" fill={gradient} /><path d="m76 83 64 29 64-29M140 112v117" /><path d="m102 72 65 29v30l-18 8v-30L84 80Z" fill="#d8e0d4" stroke="none" /><path d="m91 173 27 12m-27-1 16 7" /></g>}
      </svg>
    </div>
  );
}
