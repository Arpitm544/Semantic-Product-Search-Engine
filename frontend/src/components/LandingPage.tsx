'use client';
import { classes } from '@/lib/classes';

import type { CatalogProduct } from '@/lib/types';
import type { MouseEvent } from 'react';
import Image from 'next/image';
import { useEffect, useRef, useState } from 'react';
import Icon from './Icon';
import ProductArtwork from './ProductArtwork';
import HeadphoneStory from './HeadphoneStory';
import SearchComparison from './SearchComparison';
import AuthComingSoon from './AuthComingSoon';
import { priceLabel } from '@/lib/format';

const collections = [
  { label: 'All finds', id: 'all', ids: ['prod_3', 'prod_45', 'prod_12', 'prod_1'] },
  { label: 'For the outdoors', id: 'outdoors', ids: ['prod_45', 'prod_1', 'prod_9', 'prod_13'] },
  { label: 'For your focus', id: 'focus', ids: ['prod_3', 'prod_6', 'prod_10', 'prod_39'] },
  { label: 'For everyday', id: 'everyday', ids: ['prod_12', 'prod_11', 'prod_7', 'prod_4'] },
];
const inspirations = [
  { label: 'A quieter commute', collection: 'focus' },
  { label: 'Rainy-day adventures', collection: 'outdoors' },
  { label: 'A better everyday', collection: 'everyday' },
];

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
      <div className={"product-image-wrap relative aspect-[1/1.1] rounded-[9px] overflow-hidden [&:hover_.product-art]:[transform:scale(1.025)]"}>
        <ProductArtwork product={product} />
        <span className={"product-number absolute pointer-events-none left-[16px] top-[16px] [color:#7a8375] text-[9px] tracking-[1px] max-[780.01px]:text-[8px] max-[780.01px]:left-[12px] max-[780.01px]:top-[15px]"}>{String(index + 1).padStart(2, '0')}</span>
      </div>
      <div className={"product-info pt-[18px] pr-[0] pb-[10px] pl-[0] max-[780.01px]:pt-[14px]"}>
        <span className={"product-category block text-[8px] tracking-[.9px] uppercase [color:#66756c] mb-[8px] max-[430.01px]:text-[7px] max-[430.01px]:tracking-[.4px]"}>{product.category}</span>
        <div className={"product-title-row flex justify-between items-start gap-[10px] min-h-[39px] [&_h3]:text-left [&_h3]:text-[12px] [&_h3]:leading-[1.5] [&_h3]:font-medium [&_h3]:tracking-[-.1px] [&_h3]:[border:0] [&_h3]:[background:transparent] [&_h3]:pt-[0] [&_h3]:pr-[0] [&_h3]:pb-[0] [&_h3]:pl-[0] [&_>_span]:text-[11px] [&_>_span]:whitespace-nowrap [&_>_span]:leading-[1.65] max-[1100.01px]:flex-col max-[1100.01px]:gap-[5px] max-[780.01px]:min-h-[64px] max-[780.01px]:[&_h3]:text-[12px] max-[430.01px]:[&_h3]:text-[11px] max-[430.01px]:[&_>_span]:text-[10px]"}><h3>{product.title}</h3><span>{priceLabel(product.price)}</span></div>
        <div className={"product-bottom flex flex-wrap gap-[6px] justify-between mt-[8px] text-[9px] [color:#8d9386] leading-[1.5] max-[780.01px]:text-[8px]"}><span>{product.attributes?.slice(0, 2).join(' · ')}</span></div>
      </div>
    </article>
  );
}

export default function LandingPage({ catalog }: { catalog: CatalogProduct[] }) {
  const [collectionId, setCollectionId] = useState('all');
  const [mobileMenu, setMobileMenu] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const authTriggerRef = useRef<HTMLButtonElement | null>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileNavRef = useRef<HTMLElement>(null);
  const openAuthMessage = (event: MouseEvent<HTMLButtonElement>) => {
    authTriggerRef.current = event.currentTarget;
    setMobileMenu(false);
    setAuthOpen(true);
  };

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
      <main id="top">
        <section className={"hero relative min-h-[830px] h-[min(950px,_calc(100svh_-_24px))] mt-[12px] mr-[12px] mb-[12px] ml-[12px] rounded-[15px] overflow-hidden isolate [color:#fff] [background:#8ca3c7] [&_h1]:text-[clamp(68px,_6.7vw,_104px)] [&_h1]:leading-[.99] [&_h1]:tracking-[-5px] [&_h1]:mt-[22px] [&_h1]:mr-[0] [&_h1]:mb-[24px] [&_h1]:ml-[0] [&_h1]:[text-shadow:0_2px_14px_#273c6212] [&_h1_em]:[color:#f8efd9] min-[1500px]:max-h-[970px] max-[1100.01px]:min-h-[780px] max-[1100.01px]:[&_h1]:text-[82px] max-[780.01px]:min-h-[760px] max-[780.01px]:h-[850px] max-[780.01px]:max-h-[1000px] max-[780.01px]:mt-[8px] max-[780.01px]:mr-[8px] max-[780.01px]:mb-[8px] max-[780.01px]:ml-[8px] max-[780.01px]:rounded-[12px] max-[780.01px]:[&_h1]:text-[72px] max-[780.01px]:[&_h1]:tracking-[-3.9px] max-[780.01px]:[&_h1]:mt-[24px] max-[430.01px]:h-[780px] max-[430.01px]:min-h-[780px] max-[430.01px]:[&_h1]:text-[58px] max-[430.01px]:[&_h1]:leading-[1.04] max-[430.01px]:[&_h1]:tracking-[-3px]"} aria-labelledby="hero-title">
          <Image src="/images/discovery-landscape.png" alt="An original editorial scene of headphones, an outdoor jacket, and a water bottle in a misty alpine landscape" fill priority sizes="100vw" className={"hero-image object-cover object-[center_59%] z-[-3] max-[780.01px]:object-[35%_center] max-[430.01px]:object-[33%_center]"} />
          <div className={"hero-wash absolute [inset:0] z-[-2] [background:linear-gradient(180deg,_#203d653b,_#20344b15_47%,_transparent_61%,_#17252379_100%)]"} />
          <header className={"site-header flex justify-between items-center pt-[30px] pr-[40px] pb-[30px] pl-[40px] relative z-[4] max-[1100.01px]:pt-[25px] max-[1100.01px]:pr-[27px] max-[1100.01px]:pb-[25px] max-[1100.01px]:pl-[27px] max-[780.01px]:pt-[23px] max-[780.01px]:pr-[20px] max-[780.01px]:pb-[23px] max-[780.01px]:pl-[20px]"}>
            <Brand light />
            <nav className={"desktop-nav flex gap-[33px] ml-[52px] [&_a]:relative [&_a]:text-[12px] [&_a]:pt-[7px] [&_a]:pr-[0] [&_a]:pb-[7px] [&_a]:pl-[0] [&_a::after]:absolute [&_a::after]:[content:''] [&_a::after]:bottom-[0] [&_a::after]:left-[0] [&_a::after]:right-[0] [&_a::after]:h-[1px] [&_a::after]:[background:white] [&_a::after]:[transform:scaleX(0)] [&_a::after]:[transform-origin:left] [&_a::after]:[transition:transform_.2s] [&_a:hover::after]:[transform:scaleX(1)] max-[1100.01px]:gap-[23px] max-[1100.01px]:ml-[0] max-[780.01px]:hidden"} aria-label="Main navigation">
              <a href="#how-it-works">The experience</a>
              <a href="#discover" onClick={() => chooseCollection()}>The collection</a>
              <a href="#comparison">Compare approaches</a>
            </nav>
            <div className={"header-actions flex items-center gap-[12px]"}>
              <div className={"header-auth flex items-center gap-[13px] [&_.auth-login:hover]:[background:#ffffff15] max-[780.01px]:hidden"}><button className={"auth-login inline-flex items-center justify-center gap-[12px] min-h-[43px] pt-[11px] pr-[18px] pb-[11px] pl-[18px] rounded-[28px] text-[11px] [transition:background_.2s] [background:transparent] [border:1px_solid_transparent]"} aria-haspopup="dialog" onClick={openAuthMessage}>Log in</button><button className={"auth-signup inline-flex items-center justify-center gap-[12px] min-h-[43px] pt-[11px] pr-[18px] pb-[11px] pl-[18px] rounded-[28px] text-[11px] [transition:background_.2s] [background:#fbfaf0] [color:#37483e] [border:1px_solid_#fbfaf0] [&:hover]:[background:#e5ebdc] [&:hover]:[border-color:#e5ebdc]"} aria-haspopup="dialog" onClick={openAuthMessage}>Sign up <Icon name="diagonal" size={14} /></button></div>
              <button ref={menuButtonRef} className={"menu-button hidden max-[780.01px]:inline-flex max-[780.01px]:w-[35px] max-[780.01px]:h-[35px] icon-button items-center justify-center w-[38px] h-[38px] pt-[0] pr-[0] pb-[0] pl-[0] [border:1px_solid_#ffffff50] rounded-[50%] [background:transparent]"} aria-label={mobileMenu ? 'Close navigation' : 'Open navigation'} aria-expanded={mobileMenu} onClick={() => setMobileMenu(!mobileMenu)}><Icon name={mobileMenu ? 'close' : 'menu'} /></button>
            </div>
            {mobileMenu && <nav ref={mobileNavRef} className={"mobile-nav absolute right-[16px] left-[16px] top-[80px] flex flex-col gap-[5px] pt-[16px] pr-[16px] pb-[16px] pl-[16px] rounded-[10px] [background:var(--paper)] [color:var(--ink)] [box-shadow:0_10px_30px_#183b3529] [&_a]:pt-[12px] [&_a]:pr-[12px] [&_a]:pb-[12px] [&_a]:pl-[12px] [&_a]:text-[13px]"} aria-label="Mobile navigation"><a href="#how-it-works" onClick={() => setMobileMenu(false)}>The experience</a><a href="#discover" onClick={() => chooseCollection()}>The collection</a><a href="#comparison" onClick={() => setMobileMenu(false)}>Compare approaches</a><div className={"mobile-auth-actions flex items-center gap-[10px] mt-[9px] pt-[14px] pr-[10px] pb-[2px] pl-[10px] [border-top:1px_solid_var(--line)] [&_>_button]:[flex:1] [&_.auth-login]:[border-color:var(--line)] [&_.auth-signup]:[background:var(--ink)] [&_.auth-signup]:[color:var(--paper)] [&_.auth-signup]:[border-color:var(--ink)]"}><button className={"auth-login inline-flex items-center justify-center gap-[12px] min-h-[43px] pt-[11px] pr-[18px] pb-[11px] pl-[18px] rounded-[28px] text-[11px] [transition:background_.2s] [background:transparent] [border:1px_solid_transparent]"} aria-haspopup="dialog" onClick={openAuthMessage}>Log in</button><button className={"auth-signup inline-flex items-center justify-center gap-[12px] min-h-[43px] pt-[11px] pr-[18px] pb-[11px] pl-[18px] rounded-[28px] text-[11px] [transition:background_.2s] [background:#fbfaf0] [color:#37483e] [border:1px_solid_#fbfaf0] [&:hover]:[background:#e5ebdc] [&:hover]:[border-color:#e5ebdc]"} aria-haspopup="dialog" onClick={openAuthMessage}>Sign up <Icon name="diagonal" size={14} /></button></div></nav>}
          </header>
          <div className={"hero-content max-w-[860px] mt-[47px] mr-[auto] mb-[0] ml-[auto] text-center pt-[0] pr-[25px] pb-[0] pl-[25px] [animation:arrive_1s_ease_both] [&_>_p]:text-[14px] [&_>_p]:leading-[1.7] [&_>_p]:font-normal [&_>_p]:[color:#ffffffeb] min-[1500px]:mt-[58px] max-[1100.01px]:mt-[55px] max-[780.01px]:mt-[54px] max-[780.01px]:pl-[20px] max-[780.01px]:pr-[20px] max-[780.01px]:[&_>_p]:text-[13px] max-[430.01px]:mt-[48px] max-[430.01px]:pl-[16px] max-[430.01px]:pr-[16px]"}>
            <span className={"hero-eyebrow inline-flex items-center gap-[10px] text-[9px] leading-[1.6] tracking-[2.1px] max-[780.01px]:text-[8px] max-[780.01px]:tracking-[1.1px] max-[780.01px]:gap-[7px] max-[430.01px]:text-[7px] max-[430.01px]:tracking-[.8px]"}><span className={"tiny-star text-[14px] align-[middle]"}>✳</span> PRODUCT DISCOVERY, WITH A LITTLE MORE MEANING</span>
            <h1 id="hero-title">A little <em>meaning.</em><br />A better find.</h1>
            <p>You know what you’re looking for.<br className={"mobile-break hidden max-[430.01px]:[display:initial]"} /> You just don’t always know its name.</p>
            <div className={"hero-landing-actions flex flex-wrap items-center justify-center gap-[25px] mt-[30px] mr-[auto] mb-[20px] ml-[auto] max-[780.01px]:gap-[19px] max-[430.01px]:flex-col max-[430.01px]:gap-[9px] max-[430.01px]:mt-[24px] max-[430.01px]:mb-[17px]"}><a className={"hero-primary-cta inline-flex items-center justify-center gap-[25px] min-h-[53px] pt-[14px] pr-[25px] pb-[14px] pl-[25px] rounded-[35px] [background:#fbfaf4] [color:#37483e] text-[12px] [transition:background_.2s,_transform_.2s] [&:hover]:[background:#e5ebdc] [&:hover]:[transform:translateY(-2px)] max-[430.01px]:text-[11px] max-[430.01px]:min-h-[49px] max-[430.01px]:pl-[23px] max-[430.01px]:pr-[23px]"} href="/dashboard">Dashboard <Icon name="diagonal" size={18} /></a><a className={"hero-primary-cta inline-flex items-center justify-center gap-[25px] min-h-[53px] pt-[14px] pr-[25px] pb-[14px] pl-[25px] rounded-[35px] [background:#fbfaf4] [color:#37483e] text-[12px] [transition:background_.2s,_transform_.2s] [&:hover]:[background:#e5ebdc] [&:hover]:[transform:translateY(-2px)] max-[430.01px]:text-[11px] max-[430.01px]:min-h-[49px] max-[430.01px]:pl-[23px] max-[430.01px]:pr-[23px]"} href="#how-it-works">Follow the story <Icon name="arrow" size={20} /></a><a className={"hero-secondary-cta inline-flex items-center gap-[12px] pt-[12px] pr-[0] pb-[12px] pl-[0] [color:white] text-[11px] [border-bottom:1px_solid_#ffffff50] [&:hover]:[border-bottom-color:white] max-[430.01px]:pt-[8px] max-[430.01px]:pb-[8px] max-[430.01px]:text-[10px]"} href="#the-idea">Meet the idea <Icon name="diagonal" size={16} /></a></div>
            <div className={"query-presets flex justify-center items-center gap-[13px] text-[9px] [color:#ffffffdc] [&_>_span]:opacity-[.7] [&_a]:pt-[5px] [&_a]:pr-[0] [&_a]:pb-[5px] [&_a]:pl-[0] [&_a]:inline-flex [&_a]:items-center [&_a]:gap-[5px] [&_a]:[color:white] [&_a]:[border-top:0] [&_a]:[border-right:0] [&_a]:[border-left:0] [&_a]:[border-bottom:1px_solid_#ffffff40] [&_a]:[background:transparent] [&_a]:text-[9px] [&_a:hover]:[border-bottom-color:#fff] max-[780.01px]:flex-wrap max-[780.01px]:gap-[5px_12px] max-[780.01px]:[&_>_span]:basis-[100%] max-[780.01px]:[&_>_span]:mb-[2px] max-[430.01px]:gap-[5px_10px] max-[430.01px]:[&_a]:text-[8px] max-[430.01px]:[&_a]:gap-[3px]"}><span>A little inspiration:</span>{inspirations.map((item) => <a key={item.label} href="#discover" onClick={() => chooseCollection(item.collection)}>{item.label}<Icon name="diagonal" size={12} /></a>)}</div>
          </div>
          <div className={"hero-bottom absolute left-[40px] right-[40px] bottom-[43px] flex items-end justify-between [&_p]:mt-[8px] [&_p]:[font-family:var(--serif)] [&_p]:text-[24px] max-[1100.01px]:left-[27px] max-[1100.01px]:right-[27px] max-[780.01px]:left-[21px] max-[780.01px]:right-[21px] max-[780.01px]:bottom-[34px] max-[780.01px]:[&_p]:text-[21px] max-[430.01px]:[&_p]:text-[19px]"}><div><span className={"hero-bottom-label text-[8px] tracking-[1.5px] opacity-[.85] max-[780.01px]:text-[7px]"}>LESS SCROLLING. MORE FINDING.</span><p>Made for the way you think.</p></div><a href="#discover" className={"hero-scroll flex items-center gap-[16px] text-[8px] tracking-[1.2px] [&:hover_.scroll-circle]:[background:#ffffff24] max-[780.01px]:[&_>_span:first-child]:hidden"} aria-label="Explore product inspiration"><span>EXPLORE A LITTLE</span><span className={"scroll-circle flex items-center justify-center w-[45px] h-[45px] [border:1px_solid_#ffffff60] rounded-[50%] [transition:background_.2s]"}><Icon name="down" size={20} /></span></a></div>
          <span className={"hero-art-note absolute bottom-[13px] left-[50%] [transform:translateX(-50%)] text-[8px] tracking-[.6px] [color:#ffffff8c] whitespace-nowrap max-[780.01px]:bottom-[12px] max-[780.01px]:text-[7px]"}>An original scene. A world of possibilities.</span>
        </section>

        <div className={"discovery-strip mt-[0] mr-[52px] mb-[0] ml-[52px] flex items-center justify-between min-h-[88px] [border-bottom:1px_solid_var(--line)] text-[11px] [color:#79806f] [&_>_span]:flex [&_>_span]:items-center [&_>_span]:gap-[9px] [&_>_div]:flex [&_>_div]:items-center [&_>_div]:gap-[23px] [&_>_div]:text-[10px] [&_i]:w-[3px] [&_i]:h-[3px] [&_i]:[background:#abb09f] [&_i]:rounded-[50%] max-[1100.01px]:ml-[36px] max-[1100.01px]:mr-[36px] max-[780.01px]:ml-[22px] max-[780.01px]:mr-[22px] max-[780.01px]:min-h-[91px] max-[780.01px]:gap-[10px] max-[780.01px]:items-start max-[780.01px]:justify-center max-[780.01px]:flex-col max-[780.01px]:pt-[17px] max-[780.01px]:pb-[17px] max-[780.01px]:[&_>_span]:text-[10px] max-[780.01px]:[&_>_div]:w-[100%] max-[780.01px]:[&_>_div]:flex-wrap max-[780.01px]:[&_>_div]:text-[9px] max-[780.01px]:[&_>_div]:gap-[8px_15px]"}><span><span className={"tiny-star text-[14px] align-[middle]"}>✳</span> Good finds start with good intentions.</span><div><span>Everyday essentials</span><i /><span>Outdoor adventures</span><i /><span>A little more inspiration</span></div></div>

        <HeadphoneStory />

        <section className={"collection-section pt-[76px] pb-[80px] max-[780.01px]:pt-[56px] max-[780.01px]:pb-[60px] section-shell w-[min(1320px,_calc(100%_-_104px))] ml-[auto] mr-[auto] max-[1100.01px]:w-[calc(100%_-_72px)] max-[780.01px]:w-[calc(100%_-_44px)]"} id="discover" aria-labelledby="collection-title">
          <div className={"collection-heading flex items-end justify-between mb-[40px] gap-[30px] [&_h2]:text-[clamp(36px,_4vw,_53px)] [&_h2]:tracking-[-2px] [&_h2]:leading-[1.1] [&_h2]:mt-[14px] [&_>_p]:max-w-[260px] [&_>_p]:text-[12px] [&_>_p]:leading-[1.8] [&_>_p]:[color:#7a8077] [&_>_p]:pb-[5px] max-[780.01px]:items-start max-[780.01px]:flex-col max-[780.01px]:gap-[16px] max-[780.01px]:mb-[25px] max-[780.01px]:[&_h2]:text-[44px] max-[780.01px]:[&_>_p]:max-w-[380px] max-[780.01px]:[&_>_p]:text-[12px] max-[430.01px]:[&_h2]:text-[39px]"}><div><span className={"eyebrow block text-[10px] font-semibold tracking-[1.7px] leading-[1.6] [color:#737b6c] max-[430.01px]:text-[8px] max-[430.01px]:tracking-[1.2px]"}>THINGS FOR YOUR KIND OF EVERYDAY</span><h2 id="collection-title">A few good finds.</h2></div><p>For the small rituals, the big adventures, and everything in between.</p></div>
          <div className={"collection-toolbar flex items-center justify-between pb-[21px] [border-bottom:1px_solid_var(--line)] gap-[20px] max-[780.01px]:items-start max-[780.01px]:flex-col max-[780.01px]:gap-[8px]"}><div className={"collection-tabs flex gap-[6px] [&_button]:pt-[10px] [&_button]:pr-[16px] [&_button]:pb-[10px] [&_button]:pl-[16px] [&_button]:[border:1px_solid_transparent] [&_button]:rounded-[25px] [&_button]:[background:transparent] [&_button]:text-[11px] [&_button]:[color:#798273] [&_button]:whitespace-nowrap [&_button.active]:[color:var(--ink)] [&_button.active]:[border-color:#b1b6a9] [&_button.active]:[background:#f4f4ed] [&_button:hover]:[color:var(--ink)] [&_button:hover]:[background:#e9ecdf] max-[780.01px]:max-w-[100%] max-[780.01px]:overflow-x-auto max-[780.01px]:pb-[2px] max-[780.01px]:[&_button]:text-[10px] max-[780.01px]:[&_button]:pt-[9px] max-[780.01px]:[&_button]:pr-[13px] max-[780.01px]:[&_button]:pb-[9px] max-[780.01px]:[&_button]:pl-[13px]"} role="group" aria-label="Product inspiration collections">{collections.map((item) => <button key={item.id} className={classes(collectionId === item.id ? 'active' : '')} aria-pressed={collectionId === item.id} onClick={() => chooseCollection(item.id)}>{item.label}</button>)}</div></div>
          <div className={"results-meta flex items-center justify-between gap-[15px] pt-[20px] pr-[0] pb-[20px] pl-[0] text-[9px] [color:#8a9085] tracking-[.15px] [&_>_span:first-child]:flex [&_>_span:first-child]:items-center [&_>_span:first-child]:gap-[7px] max-[780.01px]:text-[8px] max-[780.01px]:flex-wrap max-[780.01px]:pt-[18px] max-[780.01px]:pb-[18px]"}><span>A glimpse of the possibilities</span><span className={"artwork-caption max-[430.01px]:hidden"}>Original illustrative product artwork</span></div>
          <div className={"product-grid grid grid-cols-[repeat(4,_minmax(0,_1fr))] gap-[23px] max-[1100.01px]:gap-[17px] max-[780.01px]:grid-cols-[repeat(2,_minmax(0,_1fr))] max-[780.01px]:gap-[26px_16px] max-[430.01px]:gap-[24px_12px]"}>{products.map((product, index) => <ProductPreview key={product.id} product={product} index={index} />)}</div>
          <div className={"collection-more pt-[34px] flex flex-col items-center gap-[15px] [&_>_span]:text-[9px] [&_>_span]:[color:#949888]"}><a className={"outline-button inline-flex items-center justify-center gap-[18px] min-h-[46px] pt-[12px] pr-[22px] pb-[12px] pl-[22px] rounded-[30px] text-[12px] [transition:background_.2s,_transform_.2s] [background:transparent] [border:1px_solid_#aab0a3] [&:hover]:[background:#e9ecdf] [&:hover]:[transform:translateY(-2px)]"} href="#how-it-works">Discover the idea behind it <Icon name="arrow" size={17} /></a></div>
        </section>

        <section className={"journey-section grid grid-cols-[1fr_1.2fr] min-h-[450px] mt-[0] mr-[12px] mb-[0] ml-[12px] rounded-[14px] overflow-hidden [background:#e8e9de] max-[780.01px]:grid-cols-[1fr] max-[780.01px]:ml-[8px] max-[780.01px]:mr-[8px] reveal [html[data-motion='ready']_&:not(.is-visible)]:[transform:translateY(14px)] [transition:opacity_.75s_ease,_transform_.75s_ease] motion-reduce:[html[data-motion='ready']_&:not(.is-visible)]:opacity-[1] motion-reduce:[html[data-motion='ready']_&:not(.is-visible)]:[transform:none]"} aria-labelledby="journey-title"><div className={"journey-heading pt-[65px] pr-[30px] pb-[65px] pl-[max(40px,_calc((100vw_-_1320px)_/_2_-_12px))] self-center relative z-[1] [&_h2]:text-[clamp(43px,_4.3vw,_66px)] [&_h2]:tracking-[-3px] [&_h2]:leading-[1.05] [&_h2]:mt-[22px] [&_h2]:mr-[0] [&_h2]:mb-[22px] [&_h2]:ml-[0] [&_h2_em]:[color:#7b8770] [&_p]:text-[12px] [&_p]:leading-[1.9] [&_p]:[color:#7b8572] [&_p]:mb-[28px] [&_.outline-button]:pl-[18px] [&_.outline-button]:pr-[18px] [&_.outline-button]:text-[10px] min-[1500px]:pl-[max(70px,_calc((100vw_-_1320px)_/_2_-_12px))] max-[1100.01px]:pl-[25px] max-[780.01px]:pt-[45px] max-[780.01px]:pr-[26px] max-[780.01px]:pb-[25px] max-[780.01px]:pl-[26px] max-[780.01px]:[&_h2]:text-[52px] max-[430.01px]:[&_h2]:text-[47px]"}><span className={"eyebrow block text-[10px] font-semibold tracking-[1.7px] leading-[1.6] [color:#737b6c] max-[430.01px]:text-[8px] max-[430.01px]:tracking-[1.2px]"}>FIND YOUR NEXT LITTLE ADVENTURE</span><h2 id="journey-title">For wherever<br /><em>life takes you.</em></h2><p>A rainy trail. A quiet commute. A space to create.<br />Start with the moment you’re shopping for.</p><a className={"outline-button inline-flex items-center justify-center gap-[18px] min-h-[46px] pt-[12px] pr-[22px] pb-[12px] pl-[22px] rounded-[30px] text-[12px] [transition:background_.2s,_transform_.2s] [background:transparent] [border:1px_solid_#aab0a3] [&:hover]:[background:#e9ecdf] [&:hover]:[transform:translateY(-2px)]"} href="#discover" onClick={() => chooseCollection('outdoors')}>Explore outdoor inspiration <Icon name="diagonal" size={17} /></a></div><div className={"journey-scene relative flex overflow-hidden [background:#e4e9df] max-[780.01px]:min-h-[350px] max-[430.01px]:min-h-[300px]"} aria-hidden="true"><div className={"journey-bottle absolute w-[43%] h-[72%] left-[-2%] bottom-[-4%] [transform:rotate(-13deg)] z-[1] [&_.product-art]:[mask-image:radial-gradient(ellipse_at_center,_#000_44%,_transparent_73%)] max-[780.01px]:w-[44%] max-[780.01px]:h-[102%] max-[780.01px]:bottom-[-23%]"}><div className={"product-art w-[100%] h-[100%] [background-image:url('/images/catalog-art.png')] [background-size:200%_200%] bg-no-repeat [transition:transform_.7s_cubic-bezier(.2,.65,.3,1)] [&_svg]:w-[92%] [&_svg]:h-[92%] product-art--bottle [background-position:0_100%] [&.product-art--bottle]:[&.product-art--bottle]:[background-size:200%_194%]"} /></div><div className={"journey-pack absolute w-[75%] h-[112%] top-[-3%] right-[-5%] [transform:rotate(10deg)] [&_.product-art]:[mask-image:radial-gradient(ellipse_at_center,_#000_45%,_transparent_78%)] max-[780.01px]:w-[74%] max-[780.01px]:h-[122%] max-[780.01px]:top-[-7%]"}><div className={"product-art w-[100%] h-[100%] [background-image:url('/images/catalog-art.png')] [background-size:200%_200%] bg-no-repeat [transition:transform_.7s_cubic-bezier(.2,.65,.3,1)] [&_svg]:w-[92%] [&_svg]:h-[92%] product-art--backpack [background-position:100%_0] [&.product-art--backpack]:[&.product-art--backpack]:[background-size:200%_206%]"} /></div><span className={"journey-tag flex gap-[7px] items-center absolute left-[6%] top-[17%] text-[10px] [color:#6e7e5e] pt-[12px] pr-[16px] pb-[12px] pl-[16px] [background:#f1f5e8] [border:1px_solid_#fff9] rounded-[25px] [transform:rotate(-9deg)] z-[2] max-[780.01px]:top-[12%] max-[780.01px]:text-[9px]"}><Icon name="leaf" size={14} /> A little further from ordinary.</span><span className={"journey-coordinate absolute bottom-[22px] right-[27px] text-[7px] tracking-[1px] [color:#8c9581]"}>DISCOVERY / EVERYDAY, REIMAGINED</span></div></section>

        <section className={"project-section pt-[95px] pb-[82px] max-[780.01px]:pt-[60px] max-[780.01px]:pb-[60px] section-shell w-[min(1320px,_calc(100%_-_104px))] ml-[auto] mr-[auto] max-[1100.01px]:w-[calc(100%_-_72px)] max-[780.01px]:w-[calc(100%_-_44px)] reveal [html[data-motion='ready']_&:not(.is-visible)]:[transform:translateY(14px)] [transition:opacity_.75s_ease,_transform_.75s_ease] motion-reduce:[html[data-motion='ready']_&:not(.is-visible)]:opacity-[1] motion-reduce:[html[data-motion='ready']_&:not(.is-visible)]:[transform:none]"} id="the-idea" aria-labelledby="project-title">
          <div className={"project-heading text-center max-w-[600px] mt-[0] mr-[auto] mb-[43px] ml-[auto] [&_h2]:text-[clamp(34px,_3.8vw,_52px)] [&_h2]:leading-[1.15] [&_h2]:tracking-[-2px] [&_h2]:mt-[18px] [&_h2]:mr-[0] [&_h2]:mb-[22px] [&_h2]:ml-[0] [&_h2_em]:[color:#7c8974] [&_p]:text-[11px] [&_p]:leading-[1.9] [&_p]:[color:#8a9080] [&_p]:max-w-[420px] [&_p]:mt-[0] [&_p]:mr-[auto] [&_p]:mb-[0] [&_p]:ml-[auto] max-[780.01px]:mb-[35px] max-[780.01px]:[&_h2]:text-[39px] max-[430.01px]:[&_h2]:text-[33px]"}><span className={"eyebrow block text-[10px] font-semibold tracking-[1.7px] leading-[1.6] [color:#737b6c] max-[430.01px]:text-[8px] max-[430.01px]:tracking-[1.2px]"}>THE IDEA BEHIND SEMANTIC</span><h2 id="project-title">Thoughtful by design.<br /><em>Personal by nature.</em></h2><p>An idea for more human product discovery. Because the best starting point is the life you want to live, and the little things that help you live it.</p></div>
          <div className={"engine-cards grid grid-cols-[repeat(3,_1fr)] gap-[35px] [&_article]:[border-top:1px_solid_#cdd3c1] [&_article]:pt-[22px] [&_h3]:[font-style:normal] [&_h3]:[font-weight:normal] [&_h3]:text-[25px] [&_h3]:leading-[normal] [&_h3]:[font-family:var(--serif)] [&_h3]:tracking-[-.8px] [&_h3]:mt-[22px] [&_h3]:mr-[0] [&_h3]:mb-[14px] [&_h3]:ml-[0] [&_p]:text-[11px] [&_p]:[color:#8b9081] [&_p]:leading-[1.9] [&_p]:max-w-[300px] [&_p]:min-h-[63px] max-[780.01px]:grid-cols-[1fr] max-[780.01px]:gap-[28px] max-[780.01px]:[&_h3]:text-[28px] max-[780.01px]:[&_h3]:mt-[17px] max-[780.01px]:[&_p]:max-w-[100%] max-[780.01px]:[&_p]:min-h-[unset]"}><article><span className={"engine-number text-[8px] tracking-[1.5px] [color:#9a9f8e]"}>01 / YOUR WORDS</span><h3>Make it your own.</h3><p>Start with a need, a feeling, or a small everyday wish. Your words give the experience its direction.</p><span className={"engine-pill inline-block mt-[24px] text-[8px] [color:#7f8d71] pt-[7px] pr-[11px] pb-[7px] pl-[11px] [border:1px_solid_#dce2d0] rounded-[15px] max-[780.01px]:mt-[15px]"}>Everyday moments</span></article><article><span className={"engine-number text-[8px] tracking-[1.5px] [color:#9a9f8e]"}>02 / YOUR WORLD</span><h3>A little more possibility.</h3><p>From a calmer workspace to a new outdoor adventure, there’s room to discover something unexpected.</p><span className={"engine-pill inline-block mt-[24px] text-[8px] [color:#7f8d71] pt-[7px] pr-[11px] pb-[7px] pl-[11px] [border:1px_solid_#dce2d0] rounded-[15px] max-[780.01px]:mt-[15px]"}>Fresh inspiration</span></article><article><span className={"engine-number text-[8px] tracking-[1.5px] [color:#9a9f8e]"}>03 / YOUR PACE</span><h3>Space to be curious.</h3><p>A calm, considered approach to exploring products. Less noise, more room for the things that matter.</p><span className={"engine-pill inline-block mt-[24px] text-[8px] [color:#7f8d71] pt-[7px] pr-[11px] pb-[7px] pl-[11px] [border:1px_solid_#dce2d0] rounded-[15px] max-[780.01px]:mt-[15px]"}>Thoughtful discovery</span></article></div>
          <div className={"project-note flex justify-between items-center gap-[15px] mt-[50px] pt-[23px] [border-top:1px_solid_var(--line)] text-[9px] [color:#8c9382] [&_>_span:first-child]:flex [&_>_span:first-child]:items-center [&_>_span:first-child]:gap-[8px] max-[780.01px]:mt-[30px] max-[780.01px]:flex-col max-[780.01px]:items-start max-[780.01px]:gap-[12px]"}><span>An independent product discovery concept.</span><span>Made with everyday curiosity.</span></div>
        </section>

        <SearchComparison />

        <footer className={"site-footer [background:#e5ebdc] pt-[62px] pr-[52px] pb-[25px] pl-[52px] mt-[0] mr-[12px] mb-[12px] ml-[12px] rounded-[14px] max-[1100.01px]:pl-[35px] max-[1100.01px]:pr-[35px] max-[780.01px]:mt-[0] max-[780.01px]:mr-[8px] max-[780.01px]:mb-[8px] max-[780.01px]:ml-[8px] max-[780.01px]:pt-[43px] max-[780.01px]:pr-[25px] max-[780.01px]:pb-[23px] max-[780.01px]:pl-[25px]"}><div className={"footer-main flex justify-between items-center pb-[48px] [&_h2]:text-[clamp(52px,_6vw,_83px)] [&_h2]:tracking-[-4px] [&_h2]:leading-[1.05] [&_h2]:mt-[22px] [&_h2_em]:[color:#849175] max-[780.01px]:pb-[35px] max-[780.01px]:gap-[15px] max-[780.01px]:[&_h2]:text-[59px] max-[780.01px]:[&_h2]:tracking-[-3px] max-[430.01px]:[&_h2]:text-[47px] max-[430.01px]:[&_h2]:tracking-[-2.5px] max-[430.01px]:[&_.eyebrow]:max-w-[190px]"}><div><span className={"eyebrow block text-[10px] font-semibold tracking-[1.7px] leading-[1.6] [color:#737b6c] max-[430.01px]:text-[8px] max-[430.01px]:tracking-[1.2px]"}>A LITTLE INSPIRATION STARTS HERE</span><h2>What’s your<br /><em>next good find?</em></h2></div><a className={"footer-cta inline-flex w-[91px] h-[91px] [border:1px_solid_#9eaf8f] rounded-[50%] items-center justify-center [transition:color_.2s,_background_.2s] [&:hover]:[background:#546d47] [&:hover]:[color:#fff] max-[780.01px]:w-[64px] max-[780.01px]:h-[64px] max-[780.01px]:shrink-[0] max-[780.01px]:[&_svg]:w-[25px] max-[780.01px]:[&_svg]:h-[25px] max-[430.01px]:w-[52px] max-[430.01px]:h-[52px]"} href="#discover" aria-label="Explore product inspiration"><Icon name="diagonal" size={34} /></a></div><div className={"footer-bottom flex justify-between items-center gap-[18px] [border-top:1px_solid_#c9d2bd] pt-[24px] [&_>_span]:text-[9px] [&_>_span]:[color:#7f8e70] [&_>_a:last-child]:flex [&_>_a:last-child]:items-center [&_>_a:last-child]:gap-[7px] [&_>_a:last-child]:text-[9px] [&_>_a:last-child]:[color:#7f8e70] max-[780.01px]:flex-wrap max-[780.01px]:gap-[22px] max-[780.01px]:[&_>_a:last-child]:basis-[100%]"}><Brand /><span>Semantic Product Search Engine</span><a href="#how-it-works">A little curiosity goes a long way. <Icon name="diagonal" size={14} /></a></div></footer>
      </main>
      <AuthComingSoon open={authOpen} onClose={() => setAuthOpen(false)} triggerRef={authTriggerRef} menuRef={menuButtonRef} />
    </>
  );
}
