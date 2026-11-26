'use client';
import ThemeToggle from '@/components/ThemeToggle';
import { classes } from '@/lib/classes';

import type { CatalogProduct } from '@/lib/types';
import Image from 'next/image';
import { useEffect, useRef, useState } from 'react';
import Icon from './Icon';
import ProductArtwork from './ProductArtwork';
import HeadphoneStory from './HeadphoneStory';
import { Show, SignInButton, SignUpButton, UserButton } from '@clerk/nextjs';
import { priceLabel } from '@/lib/format';
import { landingCollections as collections } from '@/lib/landingCollections';

const footerPhrases = [
  'Search by meaning',
  'Describe what you need',
  'Find relevant products',
  'Explore collections',
  'See why it matches',
];

function FooterStrip() {
  const [paused, setPaused] = useState(false);

  return (
    <div className="relative shrink-0 md:h-[clamp(100px,min(9.25vw,18svh),152px)]">
      <div className="footer-strip-rail grid border-y border-[var(--line)] bg-[var(--surface-topbar)] light:border-[#c4d2e3] light:bg-[#e5edf7] motion-safe:grid-cols-[minmax(0,1fr)_60px] md:absolute md:inset-x-[-2%] md:top-[clamp(22px,2.5vw,46px)] md:-rotate-2 md:pr-[3vw]">
        <div className="overflow-hidden motion-safe:[mask-image:linear-gradient(to_right,transparent,#000_22px,#000_calc(100%_-_22px),transparent)]">
          <div className="footer-strip-track" data-paused={paused}>
            {[false, true].map((duplicate) => (
              <ul
                key={String(duplicate)}
                aria-hidden={duplicate || undefined}
                className={`footer-strip-cycle ${duplicate ? 'hidden motion-safe:flex' : 'flex'} flex-wrap items-center justify-center gap-y-2 px-3 py-4 text-[11px] font-medium tracking-[.2em] text-[var(--footer-copy)] uppercase motion-safe:flex-nowrap motion-safe:px-0 md:py-5`}
              >
                {footerPhrases.map((phrase) => (
                  <li key={phrase} className="inline-flex shrink-0 items-center gap-3 whitespace-nowrap px-3 motion-safe:px-6">
                    <Icon name="sparkle" size={14} className="text-[var(--accent)]" />
                    {phrase}
                  </li>
                ))}
              </ul>
            ))}
          </div>
        </div>
        <button
          type="button"
          aria-label={paused ? 'Play footer text' : 'Pause footer text'}
          className="hidden size-11 items-center justify-center self-center justify-self-center rounded-full text-[var(--footer-copy)] hover:bg-[var(--sage)] hover:text-[var(--ink)] motion-safe:inline-flex"
          onClick={() => setPaused((current) => !current)}
        >
          <Icon name={paused ? 'play' : 'pause'} size={17} />
        </button>
      </div>
    </div>
  );
}

function Brand({ light = false }) {
  return (
    <a className={classes(`brand ${light ? 'brand--light' : ''}`)} href="#top" aria-label="Semantic landing page home">
      <span className={"brand-symbol text-[31px] [font-family:var(--sans)] font-normal leading-[1] max-[780.01px]:text-[27px]"} aria-hidden="true">✳</span>
      <span>semantic<span className={"brand-period ml-[1px]"}>.</span></span>
    </a>
  );
}

function ProductPreview({ product, index }: { product: CatalogProduct; index: number }) {
  return (
    <article className={"product-card min-w-[0] [animation:arrive_.5s_ease_both]"}>
      <div className={"product-image-wrap relative aspect-[1/1.1] rounded-[9px] overflow-hidden [&:hover_.product-art]:[transform:scale(1.025)] dark:ring-1 dark:ring-[var(--line)] dark:shadow-[0_12px_30px_#050d0926]"}>
        <ProductArtwork product={product} />
        <span className={"product-number absolute pointer-events-none left-[16px] top-[16px] [color:var(--text-7a8375)] text-[9px] tracking-[1px] max-[780.01px]:text-[8px] max-[780.01px]:left-[12px] max-[780.01px]:top-[15px]"}>{String(index + 1).padStart(2, '0')}</span>
      </div>
      <div className={"product-info pt-[18px] pr-[0] pb-[10px] pl-[0] max-[780.01px]:pt-[14px]"}>
        <span className={"product-category block text-[8px] tracking-[.9px] uppercase [color:var(--text-66756c)] mb-[8px] max-[430.01px]:text-[7px] max-[430.01px]:tracking-[.4px]"}>{product.category}</span>
        <div className={"product-title-row flex justify-between items-start gap-[10px] min-h-[39px] [&_h3]:text-left [&_h3]:text-[12px] [&_h3]:leading-[1.5] [&_h3]:font-medium [&_h3]:tracking-[-.1px] [&_h3]:[border:0] [&_h3]:[background:transparent] [&_h3]:pt-[0] [&_h3]:pr-[0] [&_h3]:pb-[0] [&_h3]:pl-[0] [&_>_span]:text-[11px] [&_>_span]:whitespace-nowrap [&_>_span]:leading-[1.65] max-[1100.01px]:flex-col max-[1100.01px]:gap-[5px] max-[780.01px]:min-h-[64px] max-[780.01px]:[&_h3]:text-[12px] max-[430.01px]:[&_h3]:text-[11px] max-[430.01px]:[&_>_span]:text-[10px]"}><h3>{product.title}</h3><span>{priceLabel(product.price)}</span></div>
        <div className={"product-bottom flex flex-wrap gap-[6px] justify-between mt-[8px] text-[9px] [color:var(--text-8d9386)] leading-[1.5] max-[780.01px]:text-[8px]"}><span>{product.attributes?.slice(0, 2).join(' · ')}</span></div>
      </div>
    </article>
  );
}

export default function LandingPage({
  catalog,
  exampleProduct,
}: {
  catalog: CatalogProduct[];
  exampleProduct?: CatalogProduct;
}) {
  const [collectionId, setCollectionId] = useState('all');
  const [mobileMenu, setMobileMenu] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileNavRef = useRef<HTMLElement>(null);

  useEffect(() => {
    // After initial loading, honor a section link rather than an obsolete pixel
    // offset restored from an earlier version of the scroll-story layout.
    let frame = 0;
    let anchorId: string;
    try { anchorId = decodeURIComponent(window.location.hash.slice(1)); } catch { return; }
    if (!anchorId || !document.getElementById(anchorId)) return;
    const alignAnchor = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        frame = requestAnimationFrame(() => {
          document.getElementById(anchorId)?.scrollIntoView({ behavior: 'instant', block: 'start' });
        });
      });
    };
    alignAnchor();
    if (document.readyState !== 'complete') window.addEventListener('load', alignAnchor, { once: true });
    return () => { cancelAnimationFrame(frame); window.removeEventListener('load', alignAnchor); };
  }, []);

  useEffect(() => {
    const desktopBreakpoint = window.matchMedia('(min-width: 781px)');
    const closeMobileMenu = (event: MediaQueryListEvent) => {
      if (event.matches) setMobileMenu(false);
    };
    desktopBreakpoint.addEventListener('change', closeMobileMenu);
    return () => desktopBreakpoint.removeEventListener('change', closeMobileMenu);
  }, []);

  useEffect(() => {
    if (!mobileMenu) return;

    mobileNavRef.current?.querySelector<HTMLElement>('a, button')?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMobileMenu(false);
        menuButtonRef.current?.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [mobileMenu]);

  useEffect(() => {
    document.documentElement.dataset.motion = 'ready';
    const observer = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }
    }), { threshold: 0.08 });
    document.querySelectorAll('.reveal').forEach((element) => observer.observe(element));
    return () => { observer.disconnect(); delete document.documentElement.dataset.motion; };
  }, []);

  const chooseCollection = (id = 'all') => { setCollectionId(id); setMobileMenu(false); };
  const collection = collections.find((item) => item.id === collectionId) ?? collections[0];
  const products = collection.ids.map((id) => catalog.find((product) => product.id === id)).filter((product): product is CatalogProduct => product !== undefined);

  return (
    <>
      <a className={"skip-link fixed left-[20px] top-[-80px] z-[100] [background:var(--paper)] pt-[15px] pr-[15px] pb-[15px] pl-[15px] rounded-[8px] [&:focus]:top-[15px]"} href="#discover">Skip to product inspiration</a>
      <main id="top" className="relative z-10 flow-root bg-[var(--paper)] pb-4 sm:pb-6">
        <section
          className="hero relative isolate m-3 min-h-[max(830px,min(950px,calc(100svh-24px)))] overflow-hidden rounded-[15px] bg-[var(--surface-8ca3c7)] text-white dark:[&_[data-theme-toggle]]:border-[#ffffff70] dark:[&_[data-theme-toggle]]:bg-[#0a1c2433] max-[1100px]:min-h-[780px] max-[780px]:m-2 max-[780px]:min-h-[850px] max-[780px]:rounded-xl max-[430px]:min-h-[780px]"
          aria-labelledby="hero-title"
        >
          <Image src="/images/discovery-landscape.webp" alt="An original editorial scene of headphones, an outdoor jacket, and a water bottle in a misty alpine landscape" fill priority sizes="100vw" className={"hero-image object-cover object-[center_59%] min-[600px]:origin-top min-[600px]:scale-[1.12] z-[-3] max-[780.01px]:object-[35%_center] max-[430.01px]:object-[33%_center]"} />
          <div className={"hero-wash absolute [inset:0] z-[-2] [background:linear-gradient(180deg,_var(--surface-203d653b),_#20344b15_42%,_#1a2c3a2e_56%,_#17252370_74%,_#172523a8_100%)] dark:[&.hero-wash]:[background:linear-gradient(180deg,#0b1b2b70,transparent_46%,color-mix(in_srgb,var(--paper)_50%,transparent)_70%,var(--paper)_120%)]"} />
          <header className={"site-header flex justify-between items-center pt-[30px] pr-[40px] pb-[30px] pl-[40px] relative z-[4] max-[1100.01px]:pt-[25px] max-[1100.01px]:pr-[27px] max-[1100.01px]:pb-[25px] max-[1100.01px]:pl-[27px] max-[780.01px]:pt-[23px] max-[780.01px]:pr-[20px] max-[780.01px]:pb-[23px] max-[780.01px]:pl-[20px]"}>
            <Brand light />
            <nav className={"desktop-nav flex gap-[33px] ml-[52px] [&_a]:relative [&_a]:text-[12px] [&_a]:pt-[7px] [&_a]:pr-[0] [&_a]:pb-[7px] [&_a]:pl-[0] [&_a::after]:absolute [&_a::after]:[content:''] [&_a::after]:bottom-[0] [&_a::after]:left-[0] [&_a::after]:right-[0] [&_a::after]:h-[1px] [&_a::after]:[background:white] [&_a::after]:[transform:scaleX(0)] [&_a::after]:[transform-origin:left] [&_a::after]:[transition:transform_.2s] [&_a:hover::after]:[transform:scaleX(1)] max-[1100.01px]:gap-[23px] max-[1100.01px]:ml-[0] max-[780.01px]:hidden"} aria-label="Main navigation">
              <a href="#how-it-works">The experience</a>
              <a href="#discover" onClick={() => chooseCollection()}>The collection</a>
              <a href="/quality">Search quality</a>
            </nav>
            <div className={"header-actions flex items-center gap-[12px]"}>
              <ThemeToggle />
              <div className={"header-auth flex items-center gap-[13px] [&_.auth-login:hover]:[background:var(--surface-ffffff15)] max-[780.01px]:hidden"}><Show when="signed-out"><SignInButton mode="modal" forceRedirectUrl="/dashboard" signUpForceRedirectUrl="/dashboard"><button className={"auth-login inline-flex items-center justify-center gap-[12px] min-h-[43px] pt-[11px] pr-[18px] pb-[11px] pl-[18px] rounded-[28px] text-[11px] [transition:background_.2s] [background:transparent] [border:1px_solid_transparent]"} aria-haspopup="dialog">Log in</button></SignInButton></Show><Show when="signed-out"><SignUpButton mode="modal" forceRedirectUrl="/dashboard" signInForceRedirectUrl="/dashboard"><button className={"auth-signup inline-flex items-center justify-center gap-[12px] min-h-[43px] pt-[11px] pr-[18px] pb-[11px] pl-[18px] rounded-[28px] text-[11px] [transition:background_.2s] [background:var(--surface-fff)] [color:var(--ink)] [border:1px_solid_var(--line)] [&:hover]:[background:var(--sage)] dark:[&.auth-signup]:[background:var(--accent)] dark:[&.auth-signup]:[color:var(--accent-ink)] dark:[&.auth-signup]:[border-color:transparent] dark:[&.auth-signup:hover]:[opacity:.9]"} aria-haspopup="dialog">Sign up <Icon name="diagonal" size={14} /></button></SignUpButton></Show><Show when="signed-in"><a href="/dashboard" className={"auth-dashboard inline-flex items-center justify-center gap-[12px] min-h-[43px] pt-[11px] pr-[18px] pb-[11px] pl-[18px] rounded-[28px] text-[11px] [transition:background_.2s] [background:var(--surface-fff)] [color:var(--ink)] [border:1px_solid_var(--line)] [&:hover]:[background:var(--sage)] dark:[&.auth-dashboard]:[background:var(--accent)] dark:[&.auth-dashboard]:[color:var(--accent-ink)] dark:[&.auth-dashboard]:[border-color:transparent] dark:[&.auth-dashboard:hover]:[opacity:.9]"}>Dashboard <Icon name="diagonal" size={14} /></a><UserButton /></Show></div>
              <button ref={menuButtonRef} className={"menu-button hidden max-[780.01px]:inline-flex max-[780.01px]:w-[35px] max-[780.01px]:h-[35px] icon-button items-center justify-center w-[38px] h-[38px] pt-[0] pr-[0] pb-[0] pl-[0] [border:1px_solid_var(--border-ffffff50)] rounded-[50%] [background:transparent] dark:[&.icon-button]:[border-color:#ffffff66] dark:[&.icon-button:hover]:[background:#ffffff15]"} aria-label={mobileMenu ? 'Close navigation' : 'Open navigation'} aria-expanded={mobileMenu} onClick={() => setMobileMenu(!mobileMenu)}><Icon name={mobileMenu ? 'close' : 'menu'} /></button>
            </div>
            {mobileMenu && <nav ref={mobileNavRef} className={"mobile-nav absolute right-[16px] left-[16px] top-[80px] flex flex-col gap-[5px] pt-[16px] pr-[16px] pb-[16px] pl-[16px] rounded-[10px] [background:var(--paper)] [color:var(--ink)] [box-shadow:0_10px_30px_var(--shadow-183b3529)] [&_a]:pt-[12px] [&_a]:pr-[12px] [&_a]:pb-[12px] [&_a]:pl-[12px] [&_a]:text-[13px]"} aria-label="Mobile navigation"><a href="#how-it-works" onClick={() => setMobileMenu(false)}>The experience</a><a href="#discover" onClick={() => chooseCollection()}>The collection</a><a href="/quality">Search quality</a><div className={"mobile-auth-actions flex items-center gap-[10px] mt-[9px] pt-[14px] pr-[10px] pb-[2px] pl-[10px] [border-top:1px_solid_var(--line)] [&_>_button]:[flex:1] [&_.auth-login]:[border-color:var(--line)] [&_.auth-signup]:[background:var(--ink)] [&_.auth-signup]:[color:var(--paper)] [&_.auth-signup]:[border-color:var(--ink)]"}><Show when="signed-out"><SignInButton mode="modal" forceRedirectUrl="/dashboard" signUpForceRedirectUrl="/dashboard"><button className={"auth-login inline-flex items-center justify-center gap-[12px] min-h-[43px] pt-[11px] pr-[18px] pb-[11px] pl-[18px] rounded-[28px] text-[11px] [transition:background_.2s] [background:transparent] [border:1px_solid_transparent]"} aria-haspopup="dialog">Log in</button></SignInButton></Show><Show when="signed-out"><SignUpButton mode="modal" forceRedirectUrl="/dashboard" signInForceRedirectUrl="/dashboard"><button className={"auth-signup inline-flex items-center justify-center gap-[12px] min-h-[43px] pt-[11px] pr-[18px] pb-[11px] pl-[18px] rounded-[28px] text-[11px] [transition:background_.2s] [background:var(--surface-fff)] [color:var(--ink)] [border:1px_solid_var(--line)] [&:hover]:[background:var(--sage)] dark:[&.auth-signup]:[background:var(--accent)] dark:[&.auth-signup]:[color:var(--accent-ink)] dark:[&.auth-signup]:[border-color:transparent] dark:[&.auth-signup:hover]:[opacity:.9]"} aria-haspopup="dialog">Sign up <Icon name="diagonal" size={14} /></button></SignUpButton></Show><Show when="signed-in"><a href="/dashboard" className={"auth-dashboard inline-flex items-center justify-center gap-[12px] min-h-[43px] pt-[11px] pr-[18px] pb-[11px] pl-[18px] rounded-[28px] text-[11px] [transition:background_.2s] [background:var(--surface-fff)] [color:var(--ink)] [border:1px_solid_var(--line)] [&:hover]:[background:var(--sage)] dark:[&.auth-dashboard]:[background:var(--accent)] dark:[&.auth-dashboard]:[color:var(--accent-ink)] dark:[&.auth-dashboard]:[border-color:transparent] dark:[&.auth-dashboard:hover]:[opacity:.9]"}>Dashboard <Icon name="diagonal" size={14} /></a><UserButton /></Show></div></nav>}
          </header>
          <div className="hero-content mx-auto mt-7 max-w-[950px] px-6 pb-16 text-center motion-safe:[animation:arrive_1s_ease_both] min-[1500px]:mt-11 max-[780px]:mt-12 max-[430px]:mt-8 max-[430px]:px-4">
            <h1
              id="hero-title"
              className="text-[clamp(60px,7.4vw,104px)] leading-[.99] tracking-[-.05em] [text-shadow:0_2px_18px_#17263770] max-[780px]:text-[clamp(32px,9.8vw,72px)]"
            >
              Find products<br />
              <em className="text-[var(--text-f8efd9)]">in your own words.</em>
            </h1>
            <p className="mx-auto mt-5 max-w-[36ch] text-[15px] leading-relaxed text-white [text-shadow:0_1px_12px_#0a141c]">
              Describe what you need, from a quieter commute to a rainy-day hike.
            </p>

            {exampleProduct && (
              <div className="mx-auto mt-5 max-w-[440px]">
                <p
                  id="landing-example-query"
                  className="mx-auto mb-3 w-fit rounded-full bg-[#0d1a24a6] px-4 py-2 text-sm text-white backdrop-blur-sm"
                >
                  “Headphones for a noisy commute”
                </p>
                {/* The native disclosure can open before React hydrates. */}
                <details className="group" suppressHydrationWarning>
                  <summary
                    aria-describedby="landing-example-query"
                    className="mx-auto flex min-h-12 w-fit cursor-pointer list-none items-center gap-3 rounded-full bg-[var(--accent)] px-6 py-3 text-sm font-medium text-[var(--accent-ink)] hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white [&::-webkit-details-marker]:hidden"
                  >
                    <span className="group-open:hidden">Show example result</span>
                    <span className="hidden group-open:inline">Hide example result</span>
                    <Icon name="down" size={16} className="group-open:rotate-180" />
                  </summary>
                  <article className="mt-3 flex gap-4 rounded-xl bg-[var(--surface-fff)] p-4 text-left text-[var(--ink)] shadow-lg max-[380px]:gap-3 max-[380px]:p-3">
                    <div className="h-16 w-16 shrink-0 overflow-hidden rounded-lg sm:h-20 sm:w-20">
                      <ProductArtwork product={exampleProduct} />
                    </div>
                    <div className="min-w-0">
                      <p className="mb-1 text-xs font-medium">Saved catalog example</p>
                      <h2 className="text-xl leading-tight">{exampleProduct.title}</h2>
                      <p className="mt-2 text-sm leading-relaxed">
                        <strong>Why it matches</strong> · Active noise cancellation helps cut background noise, and Bluetooth lets you listen wirelessly on the move.
                      </p>
                    </div>
                  </article>
                </details>
              </div>
            )}
          </div>
        </section>

        <div className={"discovery-strip mt-[0] mr-[52px] mb-[0] ml-[52px] flex items-center justify-between min-h-[88px] [border-bottom:1px_solid_var(--line)] text-[11px] [color:var(--muted)] [&_>_span]:flex [&_>_span]:items-center [&_>_span]:gap-[9px] [&_>_div]:flex [&_>_div]:items-center [&_>_div]:gap-[23px] [&_>_div]:text-[10px] [&_i]:w-[3px] [&_i]:h-[3px] [&_i]:[background:var(--surface-abb09f)] [&_i]:rounded-[50%] max-[1100.01px]:ml-[36px] max-[1100.01px]:mr-[36px] max-[780.01px]:ml-[22px] max-[780.01px]:mr-[22px] max-[780.01px]:min-h-[91px] max-[780.01px]:gap-[10px] max-[780.01px]:items-start max-[780.01px]:justify-center max-[780.01px]:flex-col max-[780.01px]:pt-[17px] max-[780.01px]:pb-[17px] max-[780.01px]:[&_>_span]:text-[10px] max-[780.01px]:[&_>_div]:w-[100%] max-[780.01px]:[&_>_div]:flex-wrap max-[780.01px]:[&_>_div]:text-[9px] max-[780.01px]:[&_>_div]:gap-[8px_15px]"}><span><span className={"tiny-star text-[14px] align-[middle]"}>✳</span> Good finds start with good intentions.</span><div><span>Everyday essentials</span><i /><span>Outdoor adventures</span><i /><span>A little more inspiration</span></div></div>

        <section className={"collection-section pt-[76px] pb-[80px] max-[780.01px]:pt-[56px] max-[780.01px]:pb-[60px] section-shell w-[min(1320px,_calc(100%_-_104px))] ml-[auto] mr-[auto] max-[1100.01px]:w-[calc(100%_-_72px)] max-[780.01px]:w-[calc(100%_-_44px)]"} id="discover" aria-labelledby="collection-title">
          <div className={"collection-heading flex items-end justify-between mb-[40px] gap-[30px] [&_h2]:text-[clamp(36px,_4vw,_53px)] [&_h2]:tracking-[-2px] [&_h2]:leading-[1.1] [&_h2]:mt-[14px] [&_>_p]:max-w-[260px] [&_>_p]:text-[12px] [&_>_p]:leading-[1.8] [&_>_p]:[color:var(--muted)] [&_>_p]:pb-[5px] max-[780.01px]:items-start max-[780.01px]:flex-col max-[780.01px]:gap-[16px] max-[780.01px]:mb-[25px] max-[780.01px]:[&_h2]:text-[44px] max-[780.01px]:[&_>_p]:max-w-[380px] max-[780.01px]:[&_>_p]:text-[12px] max-[430.01px]:[&_h2]:text-[39px]"}><div><span className={"eyebrow block text-[10px] font-semibold tracking-[1.7px] leading-[1.6] [color:var(--muted)] max-[430.01px]:text-[8px] max-[430.01px]:tracking-[1.2px]"}>THINGS FOR YOUR KIND OF EVERYDAY</span><h2 id="collection-title">A few good finds.</h2></div><p>For the small rituals, the big adventures, and everything in between.</p></div>
          <div className={"collection-toolbar flex items-center justify-between pb-[21px] [border-bottom:1px_solid_var(--line)] gap-[20px] max-[780.01px]:items-start max-[780.01px]:flex-col max-[780.01px]:gap-[8px]"}><div className={"collection-tabs flex gap-[6px] [&_button]:pt-[10px] [&_button]:pr-[16px] [&_button]:pb-[10px] [&_button]:pl-[16px] [&_button]:[border:1px_solid_transparent] [&_button]:rounded-[25px] [&_button]:[background:transparent] [&_button]:text-[11px] [&_button]:[color:var(--muted)] [&_button]:whitespace-nowrap [&_button.active]:[color:var(--ink)] [&_button.active]:[border-color:var(--line)] [&_button.active]:[background:var(--sage)] [&_button:hover]:[color:var(--ink)] [&_button:hover]:[background:var(--sage)] max-[780.01px]:max-w-[100%] max-[780.01px]:overflow-x-auto max-[780.01px]:pb-[2px] max-[780.01px]:[&_button]:text-[10px] max-[780.01px]:[&_button]:pt-[9px] max-[780.01px]:[&_button]:pr-[13px] max-[780.01px]:[&_button]:pb-[9px] max-[780.01px]:[&_button]:pl-[13px]"} role="group" aria-label="Product inspiration collections">{collections.map((item) => <button key={item.id} className={classes(collectionId === item.id ? 'active' : '')} aria-pressed={collectionId === item.id} onClick={() => chooseCollection(item.id)}>{item.label}</button>)}</div></div>
          <div className={"results-meta flex items-center justify-between gap-[15px] pt-[20px] pr-[0] pb-[20px] pl-[0] text-[9px] [color:var(--muted)] tracking-[.15px] [&_>_span:first-child]:flex [&_>_span:first-child]:items-center [&_>_span:first-child]:gap-[7px] max-[780.01px]:text-[8px] max-[780.01px]:flex-wrap max-[780.01px]:pt-[18px] max-[780.01px]:pb-[18px]"}><span>A glimpse of the possibilities</span><span className={"artwork-caption max-[430.01px]:hidden"}>Original illustrative product artwork</span></div>
          <div className={"product-grid grid grid-cols-[repeat(4,_minmax(0,_1fr))] gap-[23px] max-[1100.01px]:gap-[17px] max-[780.01px]:grid-cols-[repeat(2,_minmax(0,_1fr))] max-[780.01px]:gap-[26px_16px] max-[430.01px]:gap-[24px_12px]"}>{products.map((product, index) => <ProductPreview key={product.id} product={product} index={index} />)}</div>
          <div className={"collection-more pt-[34px] flex flex-col items-center gap-[15px] [&_>_span]:text-[9px] [&_>_span]:[color:var(--text-949888)]"}><a className={"outline-button inline-flex items-center justify-center gap-[18px] min-h-[46px] pt-[12px] pr-[22px] pb-[12px] pl-[22px] rounded-[30px] text-[12px] [transition:background_.2s,_transform_.2s] [background:transparent] [border:1px_solid_var(--line)] [&:hover]:[background:var(--sage)] [&:hover]:[transform:translateY(-2px)]"} href="#how-it-works">Discover the idea behind it <Icon name="arrow" size={17} /></a></div>
        </section>

        <HeadphoneStory />

        <section className={"journey-section grid grid-cols-[1fr_1.2fr] min-h-[450px] mt-[0] mr-[12px] mb-[0] ml-[12px] rounded-[14px] overflow-hidden border border-[var(--line)] bg-[var(--surface-fff)] max-[780.01px]:grid-cols-[1fr] max-[780.01px]:ml-[8px] max-[780.01px]:mr-[8px] reveal [html[data-motion='ready']_&:not(.is-visible)]:[transform:translateY(14px)] [transition:opacity_.75s_ease,_transform_.75s_ease] motion-reduce:[html[data-motion='ready']_&:not(.is-visible)]:opacity-[1] motion-reduce:[html[data-motion='ready']_&:not(.is-visible)]:[transform:none]"} aria-labelledby="journey-title"><div className={"journey-heading pt-[65px] pr-[30px] pb-[65px] pl-[max(40px,_calc((100vw_-_1320px)_/_2_-_12px))] self-center relative z-[1] [&_h2]:text-[clamp(43px,_4.3vw,_66px)] [&_h2]:tracking-[-3px] [&_h2]:leading-[1.05] [&_h2]:mt-[22px] [&_h2]:mr-[0] [&_h2]:mb-[22px] [&_h2]:ml-[0] [&_h2_em]:[color:var(--accent)] [&_p]:text-[12px] [&_p]:leading-[1.9] [&_p]:[color:var(--muted)] [&_p]:mb-[28px] [&_.outline-button]:pl-[18px] [&_.outline-button]:pr-[18px] [&_.outline-button]:text-[10px] min-[1500px]:pl-[max(70px,_calc((100vw_-_1320px)_/_2_-_12px))] max-[1100.01px]:pl-[25px] max-[780.01px]:pt-[45px] max-[780.01px]:pr-[26px] max-[780.01px]:pb-[25px] max-[780.01px]:pl-[26px] max-[780.01px]:[&_h2]:text-[52px] max-[430.01px]:[&_h2]:text-[47px]"}><span className={"eyebrow block text-[10px] font-semibold tracking-[1.7px] leading-[1.6] [color:var(--muted)] max-[430.01px]:text-[8px] max-[430.01px]:tracking-[1.2px]"}>FIND YOUR NEXT LITTLE ADVENTURE</span><h2 id="journey-title">For wherever<br /><em>life takes you.</em></h2><p>A rainy trail. A quiet commute. A space to create.<br />Start with the moment you’re shopping for.</p><a className={"outline-button inline-flex items-center justify-center gap-[18px] min-h-[46px] pt-[12px] pr-[22px] pb-[12px] pl-[22px] rounded-[30px] text-[12px] [transition:background_.2s,_transform_.2s] [background:transparent] [border:1px_solid_var(--line)] [&:hover]:[background:var(--sage)] [&:hover]:[transform:translateY(-2px)]"} href="#discover" onClick={() => chooseCollection('outdoors')}>Explore outdoor inspiration <Icon name="diagonal" size={17} /></a></div>
          <div className="journey-scene grid place-items-center bg-[var(--paper)] p-4 sm:p-6 lg:p-9" aria-hidden="true">
            <div className="grid w-full max-w-[660px] grid-cols-2 gap-3 sm:gap-4">
              <div className="aspect-square overflow-hidden rounded-xl ring-1 ring-inset ring-[var(--line)]">
                <div className={classes('product-art product-art--bottle')} />
              </div>
              <div className="aspect-square overflow-hidden rounded-xl ring-1 ring-inset ring-[var(--line)]">
                <div className={classes('product-art product-art--backpack')} />
              </div>
            </div>
          </div>
        </section>

      </main>

      <footer className="site-footer relative isolate flex flex-col overflow-hidden bg-[var(--surface-fff)] [--footer-copy:var(--muted)] light:bg-[var(--paper)] light:[--footer-copy:#435a74]">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10 [background:radial-gradient(ellipse_at_50%_50%,color-mix(in_srgb,var(--accent)_12%,transparent),transparent_68%),linear-gradient(var(--surface-fff),var(--paper))] light:[background:radial-gradient(ellipse_at_18%_78%,color-mix(in_srgb,var(--accent)_8%,transparent),transparent_55%),radial-gradient(ellipse_at_86%_32%,color-mix(in_srgb,var(--sage)_72%,transparent),transparent_54%),linear-gradient(180deg,var(--paper),#eaf1f9)]"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10 opacity-25 [mask-image:radial-gradient(ellipse_at_center,#000,transparent_76%)] [background-image:linear-gradient(to_right,var(--line)_1px,transparent_1px),linear-gradient(to_bottom,var(--line)_1px,transparent_1px)] [background-size:48px_48px] light:opacity-45"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 bottom-[-.24em] -z-10 select-none text-center text-[clamp(76px,23vw,390px)] leading-none font-semibold tracking-[-.08em] opacity-70 [font-family:var(--sans)] [color:color-mix(in_srgb,var(--line)_14%,transparent)] [-webkit-text-stroke:1px_var(--line)] light:opacity-55 light:[color:color-mix(in_srgb,var(--accent)_7%,transparent)] light:[-webkit-text-stroke-color:color-mix(in_srgb,var(--ink)_25%,var(--line))]"
        >
          Semantic
        </div>

        <FooterStrip />
        <div className="mx-auto my-auto w-full max-w-[760px] px-5 pt-[clamp(48px,min(7vw,8svh),100px)] pb-[clamp(38px,min(5vw,7svh),86px)] text-center sm:px-8">
          <h2 className="text-[clamp(40px,6.5vw,86px)] leading-[1.04] tracking-[-.055em]">
            <span className="font-medium [font-family:DM_Sans,Arial,sans-serif]">Find something</span><br />
            <em className="text-[var(--accent)] light:text-[#844a64]">that fits.</em>
          </h2>
          <p className="mx-auto mt-5 max-w-[36ch] text-sm leading-relaxed text-[var(--footer-copy)] sm:text-base">
            Start with what you need. See which products match.
          </p>
          <div className="mx-auto mt-8 grid max-w-[490px] gap-3 min-[480px]:grid-cols-2">
            <a
              href="/search"
              className="inline-flex min-h-13 items-center justify-between gap-4 rounded-full bg-[var(--accent)] px-6 py-3 text-left text-sm font-medium text-[var(--accent-ink)] transition-opacity hover:opacity-90"
            >
              Search products <Icon name="arrow" size={18} />
            </a>
            <a
              href="#discover"
              onClick={() => chooseCollection()}
              className="inline-flex min-h-13 items-center justify-between gap-4 rounded-full border border-[var(--line)] bg-[var(--surface-fff)] px-6 py-3 text-left text-sm font-medium transition-colors hover:bg-[var(--sage)] light:bg-white light:hover:bg-[var(--sage)]"
            >
              Browse collections <Icon name="arrow" size={18} />
            </a>
          </div>
          <nav aria-label="Footer navigation" className="mt-3 flex flex-wrap items-center justify-center gap-x-7 px-2 text-xs text-[var(--footer-copy)]">
            <a className="inline-flex min-h-11 items-center hover:text-[var(--accent)] hover:underline" href="#how-it-works">
              The headphone story
            </a>
            <a className="inline-flex min-h-11 items-center hover:text-[var(--accent)] hover:underline" href="/quality">
              Search quality
            </a>
          </nav>
        </div>

        <div className="mx-5 flex justify-end py-4 sm:mx-9">
          <a href="#top" className="inline-flex min-h-11 items-center gap-2 rounded-full border border-[var(--line)] px-4 text-xs text-[var(--footer-copy)] transition-colors hover:bg-[var(--sage)] hover:text-[var(--ink)] light:bg-white/75 light:hover:bg-[var(--sage)]">
            Back to top <Icon name="down" size={16} className="rotate-180" />
          </a>
        </div>
      </footer>
    </>
  );
}
