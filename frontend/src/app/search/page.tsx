'use client';
import { classes } from '@/lib/classes';

import { useEffect, useRef, useState } from 'react';
import type { SearchProduct } from '@/lib/types';
import type { FormEvent } from 'react';
import { API_BASE } from '@/lib/api';

const SOURCES = { mongo: 'MongoDB catalog', serpapi: 'Google Shopping · SerpApi' };

function money(product: SearchProduct) {
  if (product.priceLabel) return product.priceLabel;
  if (product.price == null || product.price === '' || !Number.isFinite(Number(product.price))) return 'Price unavailable';
  try {
    // SerpApi prices without a currency label must not be assigned a guessed currency.
    if (product.matchSources?.includes('google-shopping')) return new Intl.NumberFormat('en-IN').format(Number(product.price));
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: product.currency || 'USD' }).format(Number(product.price));
  } catch {
    return 'Price unavailable';
  }
}

function webUrl(value: string | undefined) {
  try {
    const url = new URL(value ?? '');
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}

function ProductImage({ product, index }: { product: SearchProduct; index: number }) {
  const [failed, setFailed] = useState(false);
  const url = webUrl(product.imageUrl);
  return (
    <div className={classes(`search-result-art art-${index % 5}`)}>
      {url && !failed
        ? <img src={url} alt={product.title} loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} />
        : <span aria-label="Product image unavailable">{product.title?.slice(0, 1) || 'P'}</span>}
    </div>
  );
}

export default function SearchPage() {
  const [input, setInput] = useState('');
  const [source, setSource] = useState<keyof typeof SOURCES>('mongo');
  const [searched, setSearched] = useState('');
  const [results, setResults] = useState<SearchProduct[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [warning, setWarning] = useState('');
  const [correctedQuery, setCorrectedQuery] = useState<string | null>(null);
  const pending = useRef<AbortController | null>(null);
  const shopping = source === 'serpapi';

  useEffect(() => () => pending.current?.abort(), []);

  function changeSource(value: keyof typeof SOURCES) {
    pending.current?.abort();
    pending.current = null;
    setSource(value);
    setSearched('');
    setResults([]);
    setTotal(0);
    setError('');
    setWarning('');
    setCorrectedQuery(null);
    setLoading(false);
  }

  async function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runSearch(input.trim());
  }

  async function runSearch(query: string, fuzzy = true) {
    if (!query) return;
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 45000);
    setSearched(query);
    setLoading(true);
    setResults([]);
    setTotal(0);
    setError('');
    setWarning('');
    setCorrectedQuery(null);
    try {
      const params = new URLSearchParams({ q: query, source, fuzzy: fuzzy ? '1' : '0' });
      const response = await fetch(`${API_BASE}/api/search?${params}`, { signal: controller.signal });
      let payload;
      try {
        payload = await response.json();
      } catch {
        throw new Error('Search returned an unreadable response. Please try again shortly.');
      }
      if (!response.ok) throw new Error(typeof payload?.error === 'string' ? payload.error : 'Search could not be completed. Please try again shortly.');
      if (!Array.isArray(payload?.results) || payload.results.some((product: unknown) => !product || typeof product !== 'object' || !('title' in product) || typeof product.title !== 'string')) {
        throw new Error('Search returned an invalid response. Please try again shortly.');
      }
      if (pending.current !== controller) return;
      setResults(payload.results);
      setTotal(Number.isFinite(payload.total) ? payload.total : payload.results.length);
      setCorrectedQuery(typeof payload.correctedQuery === 'string' ? payload.correctedQuery : null);
      setWarning(typeof payload.warning === 'string' ? payload.warning : '');
    } catch (reason) {
      if (pending.current !== controller) return;
      if (controller.signal.aborted && !timedOut) return;
      setError(timedOut ? 'Search took too long. Please try again.' : reason instanceof TypeError
        ? 'Cannot reach the search service. Make sure the backend is running and try again.'
        : (reason instanceof Error && reason.message || 'Search could not be completed.'));
    } finally {
      clearTimeout(timeout);
      if (pending.current === controller) {
        pending.current = null;
        setLoading(false);
      }
    }
  }

  return (
    <main className={"product-search-page min-h-[100vh] [background:#fafbf8] [color:#263127] [font-family:'DM_Sans',sans-serif]"}>
      <header className={"search-page-header h-[72px] [border-bottom:1px_solid_#e8ece6] [background:#fff] flex items-center justify-between pt-[0] pr-[max(6vw,24px)] pb-[0] pl-[max(6vw,24px)] max-[600.01px]:h-[60px]"}><a className={"search-page-brand [font-style:normal] font-extrabold text-[20px] leading-[normal] [font-family:Manrope,sans-serif] tracking-[-1px] [color:#263127] no-underline [&>span:first-child]:[color:#739b72] [&>span:first-child]:text-[24px] [&>span:first-child]:mr-[6px] [&>span:last-child]:[color:#7caa7c]"} href="/"><span>✳</span> semantic<span>.</span></a><a className={"back-dashboard text-[12px] font-semibold [color:#667665] no-underline [&_span]:ml-[6px]"} href="/dashboard">Back to dashboard <span>↗</span></a></header>
      <section className={"search-hero pt-[70px] pr-[24px] pb-[47px] pl-[24px] text-center max-w-[820px] mt-[auto] mr-[auto] mb-[auto] ml-[auto] [&_h1]:[font-style:normal] [&_h1]:font-bold [&_h1]:text-[clamp(40px,6vw,65px)] [&_h1]:leading-[1.04] [&_h1]:[font-family:Manrope,sans-serif] [&_h1]:tracking-[-3px] [&_h1]:mt-[15px] [&_h1]:mr-[0] [&_h1]:mb-[13px] [&_h1]:ml-[0] [&_h1]:[color:#29382e] [&_h1_em]:[color:#79937a] [&_h1_em]:font-medium [&>p]:text-[14px] [&>p]:[color:#838d82] [&>p]:mt-[0] [&>p]:mr-[0] [&>p]:mb-[27px] [&>p]:ml-[0] max-[600.01px]:pt-[52px] max-[600.01px]:pr-[18px] max-[600.01px]:pb-[35px] max-[600.01px]:pl-[18px] max-[600.01px]:[&_h1]:tracking-[-2px] max-[600.01px]:[&>p]:text-[12px] max-[600.01px]:[&>p]:leading-[1.5]"}>
        <span className={"search-page-eyebrow text-[10px] font-bold tracking-[1.3px] [color:#859482]"}>PRODUCT DISCOVERY</span>
        <h1>Find what you’re<br/><em>looking for.</em></h1>
        <p>Choose a source and search by product, brand, or detail.</p>
        <fieldset className={"search-source-picker [border:0] pt-[0] pr-[0] pb-[0] pl-[0] mt-[0] mr-[0] mb-[18px] ml-[0] flex justify-center gap-[10px] flex-wrap [&_legend]:mt-[0] [&_legend]:mr-[auto] [&_legend]:mb-[10px] [&_legend]:ml-[auto] [&_legend]:text-[11px] [&_legend]:[color:#667665] [&_label]:flex [&_label]:items-center [&_label]:gap-[7px] [&_label]:pt-[10px] [&_label]:pr-[13px] [&_label]:pb-[10px] [&_label]:pl-[13px] [&_label]:[border:1px_solid_#dce4d9] [&_label]:rounded-[8px] [&_label]:text-[12px] [&_label]:cursor-pointer [&_label]:[background:#fff] [&_label.is-selected]:[background:#edf3e9] [&_label.is-selected]:[border-color:#719375] [&_label.is-selected]:[color:#3e6747] [&_input]:[accent-color:#4f7857] [&_label:focus-within]:[outline:2px_solid_#4f7857] [&_label:focus-within]:[outline-offset:3px]"}>
          <legend>Search source</legend>
          {Object.entries(SOURCES).map(([value, label]) => <label key={value} className={classes(source === value ? 'is-selected' : '')}>
            <input type="radio" name="search-source" value={value} checked={source === value} onChange={() => changeSource(value as keyof typeof SOURCES)} />
            <span>{label}</span>
          </label>)}
        </fieldset>
        <form className={"real-search-form h-[62px] [background:#fff] [border:1px_solid_#dce4d9] rounded-[11px] flex items-center pt-[6px] pr-[7px] pb-[6px] pl-[17px] [box-shadow:0_10px_35px_#384a3610] [&_input]:h-[100%] [&_input]:min-w-[0] [&_input]:[flex:1] [&_input]:[border:0] [&_input]:[background:transparent] [&_input]:[color:#374237] [&_input]:[font-style:normal] [&_input]:[font-weight:normal] [&_input]:text-[13px] [&_input]:leading-[normal] [&_input]:[font-family:'DM_Sans',sans-serif] [&_input:focus-visible]:[outline:2px_solid_#4f7857] [&_input:focus-visible]:[outline-offset:3px] [&_input:focus-visible]:rounded-[2px] [&_input::placeholder]:[color:#a1aaa0] [&_button]:h-[46px] [&_button]:pt-[0] [&_button]:pr-[18px] [&_button]:pb-[0] [&_button]:pl-[18px] [&_button]:[border:0] [&_button]:rounded-[7px] [&_button]:[background:#4f7857] [&_button]:[color:white] [&_button]:[font-style:normal] [&_button]:font-semibold [&_button]:text-[12px] [&_button]:leading-[normal] [&_button]:[font-family:'DM_Sans',sans-serif] [&_button]:cursor-pointer [&_button:disabled]:[background:#aeb9ac] [&_button:disabled]:cursor-not-allowed [&_button_span]:text-[17px] [&_button_span]:ml-[10px] max-[600.01px]:h-[56px] max-[600.01px]:pl-[12px] max-[600.01px]:[&_button]:h-[42px] max-[600.01px]:[&_button]:pt-[0] max-[600.01px]:[&_button]:pr-[12px] max-[600.01px]:[&_button]:pb-[0] max-[600.01px]:[&_button]:pl-[12px] max-[600.01px]:[&_button]:text-[11px]"} onSubmit={submitSearch}>
          <span className={"search-glass text-[28px] [color:#879587] leading-[1] mr-[11px] [transform:rotate(-20deg)]"} aria-hidden="true">⌕</span>
          <input autoFocus maxLength={512} value={input} onChange={(event) => setInput(event.target.value)} placeholder="Try ‘wireless headphones’ or ‘mascara’" aria-label="Search products" />
          <button type="submit" disabled={!input.trim() || loading}>{loading ? 'Searching…' : 'Search'} <span>→</span></button>
        </form>
        <span className={"search-data-note block mt-[11px] text-[10px] [color:#a1a99f]"}>{shopping ? 'Google Shopping products ranked by our search engine. Prices and availability can change.' : 'Semantic catalog search with spelling suggestions. Images and prices may be unavailable.'}</span>
      </section>

      <section className={"search-results-section max-w-[990px] min-h-[290px] mt-[0] mr-[auto] mb-[0] ml-[auto] pt-[0] pr-[24px] pb-[50px] pl-[24px] max-[600.01px]:pl-[17px] max-[600.01px]:pr-[17px]"} aria-live="polite" aria-busy={loading}>
        {error && <div className={"search-error flex items-center justify-between gap-[12px] mt-[20px] mr-[0] mb-[20px] ml-[0] pt-[13px] pr-[13px] pb-[13px] pl-[13px] [border:1px_solid_#f0d5c8] rounded-[8px] [background:#fff9f5] [color:#945d45] text-[12px] [&_button]:shrink-[0] [&_button]:pt-[8px] [&_button]:pr-[10px] [&_button]:pb-[8px] [&_button]:pl-[10px] [&_button]:[background:#fff] [&_button]:[border:1px_solid_#dcbda9] [&_button]:rounded-[5px] [&_button]:[color:#804e36] [&_button]:cursor-pointer [&_button]:[font:inherit] max-[600.01px]:items-start max-[600.01px]:flex-col"} role="alert"><span>{error}</span><button type="button" onClick={() => runSearch(searched)}>Try again</button></div>}
        {loading && <div className={"search-state min-h-[190px] flex flex-col items-center justify-center gap-[9px] text-center [color:#677567] text-[13px] [&_small]:text-[11px] [&_small]:[color:#929c91]"}>Searching {SOURCES[source]}…</div>}
        {!loading && !error && !searched && <div className={"search-state min-h-[190px] flex flex-col items-center justify-center gap-[9px] text-center [color:#677567] text-[13px] [&_small]:text-[11px] [&_small]:[color:#929c91] search-empty-start [&>span]:w-[32px] [&>span]:h-[32px] [&>span]:rounded-[10px] [&>span]:[background:#edf3e9] [&>span]:[color:#759272] [&>span]:grid [&>span]:place-items-center [&>span]:mb-[4px] [&_strong]:text-[13px] [&_strong]:font-semibold"}><span>✳</span><strong>Start with a product or a need</strong><small>Enter a product, brand, or category to search {SOURCES[source]}.</small></div>}
        {!loading && !error && searched && <>
          <div className={"search-results-heading flex items-end justify-between pt-[20px] pr-[0] pb-[14px] pl-[0] [border-bottom:1px_solid_#e7ebe5] [&_h2]:[font-style:normal] [&_h2]:font-semibold [&_h2]:text-[22px] [&_h2]:leading-[normal] [&_h2]:[font-family:Manrope,sans-serif] [&_h2]:tracking-[-.6px] [&_h2]:mt-[5px] [&_h2]:mr-[0] [&_h2]:mb-[0] [&_h2]:ml-[0] [&_h2]:[color:#344035] [&>span]:text-[11px] [&>span]:[color:#8b958a] [&>span]:pb-[4px] max-[600.01px]:items-start max-[600.01px]:gap-[8px] max-[600.01px]:flex-col max-[600.01px]:[&_h2]:text-[19px]"}><div><span className={"search-page-eyebrow text-[10px] font-bold tracking-[1.3px] [color:#859482]"}>{SOURCES[source]} · RESULTS FOR</span><h2>“{searched}”</h2></div><span>{shopping ? `${results.length} products shown` : `${total} matching products`}</span></div>
          {warning && <div className={"search-ranking-warning mt-[15px] mr-[0] mb-[15px] ml-[0] pt-[12px] pr-[14px] pb-[12px] pl-[14px] [border:1px_solid_#e5d9b5] rounded-[8px] [background:#fffaf0] [color:#796338] text-[12px] leading-[1.5]"} role="status">{warning}</div>}
          {correctedQuery && <div className={"search-spelling-note flex items-center justify-between gap-[12px] mt-[15px] mr-[0] mb-[15px] ml-[0] pt-[12px] pr-[14px] pb-[12px] pl-[14px] [border:1px_solid_#dce4d9] rounded-[8px] [background:#edf3e9] [color:#455b48] text-[12px] leading-[1.5] [&_button]:[border:0] [&_button]:[background:transparent] [&_button]:[color:#4f7857] [&_button]:[font-style:normal] [&_button]:font-semibold [&_button]:text-[11px] [&_button]:leading-[normal] [&_button]:[font-family:'DM_Sans',sans-serif] [&_button]:underline [&_button]:cursor-pointer [&_button]:shrink-[0] [&_button:focus-visible]:[outline:2px_solid_#4f7857] [&_button:focus-visible]:[outline-offset:4px] max-[600.01px]:items-start max-[600.01px]:flex-col"}><span>Also searching for <strong>“{correctedQuery}”</strong>.</span><button type="button" onClick={() => runSearch(searched, false)}>Use original spelling</button></div>}
          {results.length ? <div className={"search-result-list grid"}>{results.map((product, index) => {
            const url = webUrl(product.url);
            return <article className={"search-result-card flex items-center gap-[18px] pt-[17px] pr-[4px] pb-[17px] pl-[4px] [border-bottom:1px_solid_#e9ede7] max-[600.01px]:gap-[11px] max-[600.01px]:pt-[14px] max-[600.01px]:pr-[0] max-[600.01px]:pb-[14px] max-[600.01px]:pl-[0] max-[600.01px]:flex-wrap"} key={product.id || index}>
              <ProductImage key={`${product.id}:${product.imageUrl}`} product={product} index={index} />
              <div className={"search-result-copy [&_h3_a]:[color:inherit] [&_h3_a]:no-underline [&_h3_a:hover]:underline [&_h3_a:focus-visible]:[outline:2px_solid_#4f7857] [&_h3_a:focus-visible]:[outline-offset:3px] min-w-[0] [flex:1] [&_h3]:[font-style:normal] [&_h3]:font-semibold [&_h3]:text-[14px] [&_h3]:leading-[normal] [&_h3]:[font-family:Manrope,sans-serif] [&_h3]:mt-[4px] [&_h3]:mr-[0] [&_h3]:mb-[4px] [&_h3]:ml-[0] [&_h3]:[color:#354136] [&_p]:text-[11px] [&_p]:leading-[1.5] [&_p]:[color:#828d81] [&_p]:mt-[0] [&_p]:mr-[0] [&_p]:mb-[0] [&_p]:ml-[0] [&_p]:max-w-[690px] [&_p]:[display:-webkit-box] [&_p]:[-webkit-line-clamp:2] [&_p]:[-webkit-box-orient:vertical] [&_p]:overflow-hidden max-[600.01px]:[&_h3]:text-[12px] max-[600.01px]:[&_p]:text-[10px] max-[600.01px]:basis-[calc(100%_-_70px)]"}>
                <span className={"search-result-category text-[9px] [color:#899587] uppercase tracking-[.55px]"}>{shopping ? product.merchant || 'Google Shopping' : [product.category, product.brand].filter(Boolean).join(' · ')}</span>
                <h3>{url ? <a href={url} target="_blank" rel="noopener noreferrer">{product.title} <span aria-hidden="true">↗</span></a> : product.title}</h3>
                {product.description && <p>{product.description}</p>}
                <div className={"search-result-meta flex items-center gap-[13px] mt-[7px] text-[10px] [color:#828d81] [&_strong]:text-[11px] [&_strong]:[color:#455b48] max-[600.01px]:gap-[8px] max-[600.01px]:text-[9px] max-[600.01px]:flex-wrap"}><strong>{money(product)}</strong>{product.rating != null && <span>★ {Number(product.rating).toFixed(1)}{product.reviews != null ? ` (${Number(product.reviews).toLocaleString()} reviews)` : ''}</span>}{product.stock != null && <span>{product.stock} in stock</span>}</div>
              </div>
              <span className={"relevance-score self-start mt-[3px] mr-[3px] mb-[0] ml-[0] rounded-[14px] pt-[5px] pr-[8px] pb-[5px] pl-[8px] [background:#f0f4ee] [color:#577658] text-[10px] font-bold whitespace-nowrap [&_small]:text-[8px] [&_small]:font-medium [&_small]:ml-[4px] [&_small]:[color:#82927f] max-[600.01px]:text-[9px] max-[600.01px]:pt-[4px] max-[600.01px]:pr-[6px] max-[600.01px]:pb-[4px] max-[600.01px]:pl-[6px] max-[600.01px]:ml-[66px] max-[600.01px]:[&_small]:hidden"}>{shopping ? product.matchSources?.includes('reranker') ? 'Engine ranked' : 'Google ranked' : product.matchSources?.includes('keyword') ? 'Product match' : product.matchSources?.includes('fuzzy') ? 'Spelling match' : 'Related match'}</span>
            </article>;
          })}</div> : <div className={"search-state min-h-[190px] flex flex-col items-center justify-center gap-[9px] text-center [color:#677567] text-[13px] [&_small]:text-[11px] [&_small]:[color:#929c91] search-no-results [&_strong]:text-[13px] [&_strong]:font-semibold"}><strong>No matching products found.</strong><small>Try a shorter query or choose another search source.</small></div>}
        </>}
      </section>
      <footer className={"search-page-footer pt-[19px] pr-[24px] pb-[19px] pl-[24px] text-center [border-top:1px_solid_#e8ece6] [color:#9aa398] text-[10px]"}>{shopping ? 'Products from Google Shopping · Open a product to check its latest offer' : 'MongoDB product catalog · Spelling suggestions available'}</footer>
    </main>
  );
}
