'use client';

import dynamic from 'next/dynamic';
import { useCallback, useEffect, useRef, useState } from 'react';
import Icon from './Icon';
import AirPodsArtwork from './AirPodsArtwork';

const HeadphoneScene = dynamic(() => import('./HeadphoneScene'), {
  ssr: false,
  loading: () => <div className="headphone-scene scene-fallback"><AirPodsArtwork /></div>,
});
const chapters = [
  {
    label: 'The product', eyebrow: '01 / THE LITTLE DETAILS',
    title: <>A quieter world.<br /><em>A closer look.</em></>,
    description: 'Meet AirPods Max. Sculpted aluminum ear cups, a knit mesh canopy, and active noise cancellation—a closer look at listening with fewer distractions.',
    tags: ['AirPods Max', 'Noise cancellation', 'Over-ear comfort'],
    note: 'Apple AirPods Max · original generation · illustrative product story',
  },
  {
    label: 'Your words', eyebrow: '02 / START WITH THE MOMENT',
    title: <>You have a need.<br /><em>Not a product name.</em></>,
    description: 'You might never type “noise-canceling headphones.” You might simply describe what you want your commute to feel like.',
    tags: ['“focus” → fewer distractions', '“commute” → on-the-go listening'],
    note: 'Your words describe the need. Product details describe a possible fit.',
  },
  {
    label: 'The connection', eyebrow: '03 / FIND THE SHARED MEANING',
    title: <>Different words.<br /><em>Nearby ideas.</em></>,
    description: 'Semantic search represents the query and product descriptions as vectors. Related meanings can sit near each other—even when their wording is different.',
    tags: ['Describe the need', 'Represent the meaning', 'Look for nearby products'],
    note: 'A simplified sketch of vector space. The positions here are illustrative.',
  },
  {
    label: 'A better fit', eyebrow: '04 / BRING IT BACK TO YOUR WORLD',
    title: <>From a little need<br /><em>to a possible fit.</em></>,
    description: 'Quiet for your focus. Wireless for your journey. Semantic retrieval connects your intention to relevant product details; it does not guarantee the perfect purchase.',
    tags: ['Focus ↔ noise cancellation', 'Commute ↔ wireless listening'],
    note: 'One illustrative match. Keep scrolling to compare the approaches.',
  },
];
const details = [
  { name: 'Quiet', text: 'Active noise cancellation helps reduce surrounding noise.' },
  { name: 'Freedom', text: 'Bluetooth listening makes a wired connection optional.' },
  { name: 'Comfort', text: 'A knit mesh canopy and fabric ear cushions frame the over-ear design.' },
];

function MeaningSketch() {
  return <div className="meaning-sketch" role="img" aria-label="Schematic connection from a commute query to related headphone ideas"><svg viewBox="0 0 420 250" aria-hidden="true"><g fill="none" stroke="#becbcb"><ellipse cx="216" cy="123" rx="150" ry="91" /><ellipse cx="216" cy="123" rx="103" ry="61" strokeDasharray="4 5" /><path d="m115 114 133-55m-133 55 170 29m-170-29 133 66" stroke="#b49e76" /></g>{Array.from({ length: 24 }, (_, i) => <circle key={i} cx={243 + Math.sin(i * 2.3) * 43} cy={92 + Math.cos(i * 1.5) * 48} r={i % 3 === 0 ? 4 : 2} fill="#92a9b5" />)}<circle cx="115" cy="114" r="7" fill="#bba073" /></svg><span className="sketch-query">your commute query</span><span className="sketch-match">quieter listening</span><span className="sketch-other">nearby product ideas</span></div>;
}

export default function HeadphoneStory() {
  const trackRef = useRef(null);
  const progressBarRef = useRef(null);
  const progressRef = useRef(0);
  const appearanceRef = useRef('silver');
  const rotationRef = useRef(0);
  const [activeChapter, setActiveChapter] = useState(0);
  // CSS selects the responsive layout before hydration, preserving hash anchors
  // and restored scroll positions while the 3D renderer loads.
  const [simple, setSimple] = useState(false);
  const [detail, setDetail] = useState(0);
  const [finish, setFinish] = useState('silver');
  const [sceneEnabled, setSceneEnabled] = useState(false);
  const useSimpleScene = useCallback(() => setSimple(true), []);

  useEffect(() => {
    const mobile = matchMedia('(max-width: 780px)');
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    const shortViewport = matchMedia('(max-height: 720px) and (min-width: 781px)');
    const updateMode = () => setSimple(mobile.matches || motion.matches || shortViewport.matches);
    updateMode(); mobile.addEventListener('change', updateMode); motion.addEventListener('change', updateMode); shortViewport.addEventListener('change', updateMode);
    return () => { mobile.removeEventListener('change', updateMode); motion.removeEventListener('change', updateMode); shortViewport.removeEventListener('change', updateMode); };
  }, []);

  useEffect(() => {
    if (simple || sceneEnabled || !trackRef.current) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { setSceneEnabled(true); observer.disconnect(); }
    }, { rootMargin: '300px' });
    observer.observe(trackRef.current);
    return () => observer.disconnect();
  }, [simple, sceneEnabled]);

  useEffect(() => {
    if (simple) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      const track = trackRef.current;
      if (!track) return;
      const bounds = track.getBoundingClientRect();
      const travel = Math.max(1, bounds.height - window.innerHeight);
      const progress = Math.max(0, Math.min(1, -bounds.top / travel));
      progressRef.current = progress;
      const nextChapter = Math.min(3, Math.floor(progress * 4));
      setActiveChapter((previous) => previous === nextChapter ? previous : nextChapter);
      if (progressBarRef.current) progressBarRef.current.style.transform = `scaleX(${progress})`;
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
    update(); window.addEventListener('scroll', schedule, { passive: true }); window.addEventListener('resize', schedule);
    return () => { cancelAnimationFrame(frame); window.removeEventListener('scroll', schedule); window.removeEventListener('resize', schedule); };
  }, [simple]);

  const goToChapter = (index) => {
    const track = trackRef.current;
    const start = track.getBoundingClientRect().top + window.scrollY;
    const distance = track.offsetHeight - window.innerHeight;
    window.scrollTo({ top: start + distance * (index * .25 + .08), behavior: 'smooth' });
  };
  const changeFinish = (value) => { setFinish(value); appearanceRef.current = value; };
  const chapter = chapters[activeChapter];

  return (
    <section className={`headphone-story ${simple ? 'is-simple' : ''}`} id="how-it-works" aria-labelledby="story-title">
      <div className="story-intro section-shell"><span className="eyebrow">ONE PRODUCT. A DIFFERENT WAY TO FIND IT.</span><h2 id="story-title">Let’s follow<br /><em>a little meaning.</em></h2><p>A headphone. A quiet commute. A look inside the idea of semantic search.</p><span className="story-demo-label"><span className="status-dot" /> A visual story · not a live search</span></div>
      <div className="story-track" ref={trackRef}>
        <div className="story-sticky" data-chapter={activeChapter}>
          <div className="story-topline"><span>THE ANATOMY OF A GOOD FIND</span><span>SCROLL TO FOLLOW THE STORY <Icon name="down" size={13} /></span></div>
          <nav className="story-chapters" aria-label="Headphone story chapters">{chapters.map((item, index) => <button key={item.label} onClick={() => goToChapter(index)} aria-current={activeChapter === index ? 'step' : undefined} className={activeChapter === index ? 'active' : ''}><span>0{index + 1}</span>{item.label}</button>)}</nav>
          <div className="story-layout">
            <div className="story-copy" key={activeChapter}><span className="eyebrow">{chapter.eyebrow}</span><h3>{chapter.title}</h3><p>{chapter.description}</p>{activeChapter === 1 && <blockquote>“Something to help me focus on my commute.”</blockquote>}<div className="story-tags">{chapter.tags.map((tag) => <span key={tag}>{tag}</span>)}</div><p className="story-note">{chapter.note}</p>{activeChapter === 3 && <a className="text-link" href="#comparison">See the difference <Icon name="arrow" size={18} /></a>}</div>
            <div className={`story-visual story-visual--${activeChapter}`}>
              {!simple && sceneEnabled ? <HeadphoneScene progressRef={progressRef} appearanceRef={appearanceRef} rotationRef={rotationRef} onUnavailable={useSimpleScene} /> : <div className="headphone-scene scene-fallback"><AirPodsArtwork /></div>}
              {activeChapter !== 2 && <div className="scene-turn-controls" role="group" aria-label="Rotate the illustrative headphones"><button aria-label="Rotate headphones left" onClick={() => { rotationRef.current -= .4; }}><Icon name="arrow" size={14} className="turn-left" /></button><button aria-label="Rotate headphones right" onClick={() => { rotationRef.current += .4; }}><Icon name="arrow" size={14} /></button></div>}
              <span className="scene-orbit orbit-a" /><span className="scene-orbit orbit-b" />
              {activeChapter === 0 && <div className="product-callout"><span>THE LITTLE DETAIL</span><strong>{details[detail].name}</strong><p>{details[detail].text}</p></div>}
              {activeChapter === 1 && <><span className="story-floating-tag float-focus">a little more focus</span><span className="story-floating-tag float-commute">a quieter commute</span></>}
              {activeChapter === 2 && <div className="map-annotations"><span className="map-label map-audio">Headphones & earbuds</span><span className="map-label map-outdoor">Outdoor ideas</span><span className="map-label map-home">Home comforts</span><span className="map-query">Your words</span><span className="map-note">SCHEMATIC VECTOR SPACE</span></div>}
              {activeChapter === 3 && <div className="match-ribbon"><Icon name="check" size={16} /><span>A possible fit for a quieter commute</span></div>}
              <div className="scene-toolbar"><span>{activeChapter === 2 ? 'Illustrative meaning map' : 'AirPods Max · interactive 3D'}</span>{activeChapter !== 2 && <div className="finish-control" role="group" aria-label="Illustrative model finish"><span>Color study</span><button aria-label="Silver color study" aria-pressed={finish === 'silver'} className={`finish-swatch silver ${finish === 'silver' ? 'active' : ''}`} onClick={() => changeFinish('silver')} /><button aria-label="Original green finish" aria-pressed={finish === 'sage'} className={`finish-swatch sage ${finish === 'sage' ? 'active' : ''}`} onClick={() => changeFinish('sage')} /></div>}</div>
              {activeChapter === 0 && <div className="detail-selector" role="group" aria-label="Explore headphone details">{details.map((item, index) => <button key={item.name} aria-pressed={detail === index} className={detail === index ? 'active' : ''} onClick={() => setDetail(index)}>{item.name}</button>)}</div>}
              <span className="scene-drag-note">{activeChapter === 2 ? 'Different descriptions. Related meanings.' : 'Drag or use the arrow controls to look around.'}</span>
            </div>
          </div>
          <div className="story-bottomline"><span>0{activeChapter + 1} / 04</span><span>{chapter.label}</span><a href="#comparison">Jump to comparison <Icon name="diagonal" size={13} /></a></div>
          <div className="story-progress"><div ref={progressBarRef} /></div>
        </div>
      </div>
      <div className="story-mobile section-shell">
        <div className="mobile-headphone-art"><AirPodsArtwork /><span>AirPods Max · product illustration</span></div>
        {chapters.map((item, index) => <article key={item.label} className="mobile-story-chapter" id={`story-mobile-${index}`}><span className="eyebrow">{item.eyebrow}</span><h3>{item.title}</h3><p>{item.description}</p>{index === 1 && <blockquote>“Something to help me focus on my commute.”</blockquote>}{index === 2 && <MeaningSketch />}<div className="story-tags">{item.tags.map((tag) => <span key={tag}>{tag}</span>)}</div><p className="story-note">{item.note}</p></article>)}
        <a className="outline-button" href="#comparison">Compare the approaches <Icon name="arrow" size={17} /></a>
      </div>
      <p className="story-asset-credit">3D model: <a href="https://sketchfab.com/3d-models/airpods-max-05181e126a6341668ca95f2d98324d30" target="_blank" rel="noreferrer">Airpods max by Mr.Philin</a> · <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0</a> · optimized textures &amp; silver color study. <a href="https://www.apple.com/newsroom/2020/12/apple-introduces-airpods-max-the-magic-of-airpods-in-a-stunning-over-ear-design/" target="_blank" rel="noreferrer">Product details</a></p>
    </section>
  );
}
