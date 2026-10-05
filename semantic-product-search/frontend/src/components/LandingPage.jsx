'use client';

import Image from 'next/image';
import { useEffect, useRef, useState } from 'react';
import Icon from './Icon';
import ProductArtwork from './ProductArtwork';
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
    <a className={`brand ${light ? 'brand--light' : ''}`} href="#top" aria-label="Semantic landing page home">
      <span className="brand-symbol" aria-hidden="true">✳</span>
      <span>semantic<span className="brand-period">.</span></span>
    </a>
  );
}

function ProductPreview({ product, index }) {
  return (
    <article className="product-card">
      <div className="product-image-wrap">
        <ProductArtwork product={product} />
        <span className="product-number">{String(index + 1).padStart(2, '0')}</span>
      </div>
      <div className="product-info">
        <span className="product-category">{product.category}</span>
        <div className="product-title-row"><h3>{product.title}</h3><span>{priceLabel(product.price)}</span></div>
        <div className="product-bottom"><span>{product.attributes?.slice(0, 2).join(' · ')}</span></div>
      </div>
    </article>
  );
}

export default function LandingPage({ catalog }) {
  const [collectionId, setCollectionId] = useState('all');
  const [mobileMenu, setMobileMenu] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const authTriggerRef = useRef(null);
  const menuButtonRef = useRef(null);
  const openAuthMessage = (event) => {
    authTriggerRef.current = event.currentTarget;
    setMobileMenu(false);
    setAuthOpen(true);
  };

  useEffect(() => {
    // After initial loading, honor a section link rather than an obsolete pixel
    // offset restored from an earlier version of the scroll-story layout.
    let frame = 0;
    let anchorId;
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
    document.documentElement.dataset.motion = 'ready';
    const observer = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }
    }), { threshold: 0.08 });
    document.querySelectorAll('.reveal').forEach((element) => observer.observe(element));
    return () => { observer.disconnect(); delete document.documentElement.dataset.motion; };
  }, []);

  const chooseCollection = (id = 'all') => { setCollectionId(id); setMobileMenu(false); };
  const collection = collections.find((item) => item.id === collectionId);
  const products = collection.ids.map((id) => catalog.find((product) => product.id === id)).filter(Boolean);

  return (
    <>
      <a className="skip-link" href="#discover">Skip to product inspiration</a>
      <main id="top">
        <section className="hero" aria-labelledby="hero-title">
          <Image src="/images/discovery-landscape.png" alt="An original editorial scene of headphones, an outdoor jacket, and a water bottle in a misty alpine landscape" fill priority sizes="100vw" className="hero-image" />
          <div className="hero-wash" />
          <header className="site-header">
            <Brand light />
            <nav className="desktop-nav" aria-label="Main navigation">
              <a href="#discover" onClick={() => chooseCollection()}>The collection</a>
              <a href="#the-idea">The idea</a>
            </nav>
            <div className="header-actions">
              <div className="header-auth"><button className="auth-login" aria-haspopup="dialog" onClick={openAuthMessage}>Log in</button><button className="auth-signup" aria-haspopup="dialog" onClick={openAuthMessage}>Sign up <Icon name="diagonal" size={14} /></button></div>
              <button ref={menuButtonRef} className="menu-button icon-button" aria-label={mobileMenu ? 'Close navigation' : 'Open navigation'} aria-expanded={mobileMenu} onClick={() => setMobileMenu(!mobileMenu)}><Icon name={mobileMenu ? 'close' : 'menu'} /></button>
            </div>
            {mobileMenu && <nav className="mobile-nav" aria-label="Mobile navigation"><a href="#discover" onClick={() => chooseCollection()}>The collection</a><a href="#the-idea" onClick={() => setMobileMenu(false)}>The idea</a><div className="mobile-auth-actions"><button className="auth-login" aria-haspopup="dialog" onClick={openAuthMessage}>Log in</button><button className="auth-signup" aria-haspopup="dialog" onClick={openAuthMessage}>Sign up <Icon name="diagonal" size={14} /></button></div></nav>}
          </header>
          <div className="hero-content">
            <span className="hero-eyebrow"><span className="tiny-star">✳</span> PRODUCT DISCOVERY, WITH A LITTLE MORE MEANING</span>
            <h1 id="hero-title">A little <em>meaning.</em><br />A better find.</h1>
            <p>You know what you’re looking for.<br className="mobile-break" /> You just don’t always know its name.</p>
            <div className="hero-landing-actions"><a className="hero-primary-cta" href="#discover">Explore the collection <Icon name="arrow" size={20} /></a><a className="hero-secondary-cta" href="#the-idea">Meet the idea <Icon name="diagonal" size={16} /></a></div>
            <div className="query-presets"><span>A little inspiration:</span>{inspirations.map((item) => <a key={item.label} href="#discover" onClick={() => chooseCollection(item.collection)}>{item.label}<Icon name="diagonal" size={12} /></a>)}</div>
          </div>
          <div className="hero-bottom"><div><span className="hero-bottom-label">LESS SCROLLING. MORE FINDING.</span><p>Made for the way you think.</p></div><a href="#discover" className="hero-scroll" aria-label="Explore product inspiration"><span>EXPLORE A LITTLE</span><span className="scroll-circle"><Icon name="down" size={20} /></span></a></div>
          <span className="hero-art-note">An original scene. A world of possibilities.</span>
        </section>

        <div className="discovery-strip"><span><span className="tiny-star">✳</span> Good finds start with good intentions.</span><div><span>Everyday essentials</span><i /><span>Outdoor adventures</span><i /><span>A little more inspiration</span></div></div>


        <section className="collection-section section-shell" id="discover" aria-labelledby="collection-title">
          <div className="collection-heading"><div><span className="eyebrow">THINGS FOR YOUR KIND OF EVERYDAY</span><h2 id="collection-title">A few good finds.</h2></div><p>For the small rituals, the big adventures, and everything in between.</p></div>
          <div className="collection-toolbar"><div className="collection-tabs" aria-label="Product inspiration collections">{collections.map((item) => <button key={item.id} className={collectionId === item.id ? 'active' : ''} aria-pressed={collectionId === item.id} onClick={() => chooseCollection(item.id)}>{item.label}</button>)}</div></div>
          <div className="results-meta"><span>A glimpse of the possibilities</span><span className="artwork-caption">Original illustrative product artwork</span></div>
          <div className="product-grid">{products.map((product, index) => <ProductPreview key={product.id} product={product} index={index} />)}</div>
          <div className="collection-more"><a className="outline-button" href="#the-idea">Discover the idea behind it <Icon name="arrow" size={17} /></a></div>
        </section>

        <section className="journey-section reveal" aria-labelledby="journey-title"><div className="journey-heading"><span className="eyebrow">FIND YOUR NEXT LITTLE ADVENTURE</span><h2 id="journey-title">For wherever<br /><em>life takes you.</em></h2><p>A rainy trail. A quiet commute. A space to create.<br />Start with the moment you’re shopping for.</p><a className="outline-button" href="#discover" onClick={() => chooseCollection('outdoors')}>Explore outdoor inspiration <Icon name="diagonal" size={17} /></a></div><div className="journey-scene" aria-hidden="true"><div className="journey-bottle"><div className="product-art product-art--bottle" /></div><div className="journey-pack"><div className="product-art product-art--backpack" /></div><span className="journey-tag"><Icon name="leaf" size={14} /> A little further from ordinary.</span><span className="journey-coordinate">DISCOVERY / EVERYDAY, REIMAGINED</span></div></section>

        <section className="project-section section-shell reveal" id="the-idea" aria-labelledby="project-title">
          <div className="project-heading"><span className="eyebrow">THE IDEA BEHIND SEMANTIC</span><h2 id="project-title">Thoughtful by design.<br /><em>Personal by nature.</em></h2><p>An idea for more human product discovery. Because the best starting point is the life you want to live, and the little things that help you live it.</p></div>
          <div className="engine-cards"><article><span className="engine-number">01 / YOUR WORDS</span><h3>Make it your own.</h3><p>Start with a need, a feeling, or a small everyday wish. Your words give the experience its direction.</p><span className="engine-pill">Everyday moments</span></article><article><span className="engine-number">02 / YOUR WORLD</span><h3>A little more possibility.</h3><p>From a calmer workspace to a new outdoor adventure, there’s room to discover something unexpected.</p><span className="engine-pill">Fresh inspiration</span></article><article><span className="engine-number">03 / YOUR PACE</span><h3>Space to be curious.</h3><p>A calm, considered approach to exploring products. Less noise, more room for the things that matter.</p><span className="engine-pill">Thoughtful discovery</span></article></div>
          <div className="project-note"><span>An independent product discovery concept.</span><span>Made with everyday curiosity.</span></div>
        </section>


        <footer className="site-footer"><div className="footer-main"><div><span className="eyebrow">A LITTLE INSPIRATION STARTS HERE</span><h2>What’s your<br /><em>next good find?</em></h2></div><a className="footer-cta" href="#discover" aria-label="Explore product inspiration"><Icon name="diagonal" size={34} /></a></div><div className="footer-bottom"><Brand /><span>Semantic Product Search Engine</span><a href="#the-idea">A little curiosity goes a long way. <Icon name="diagonal" size={14} /></a></div></footer>
      </main>
      <AuthComingSoon open={authOpen} onClose={() => setAuthOpen(false)} triggerRef={authTriggerRef} menuRef={menuButtonRef} />
    </>
  );
}
