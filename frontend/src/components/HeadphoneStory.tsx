'use client';
import { classes } from '@/lib/classes';

import dynamic from 'next/dynamic';
import { useEffect, useRef, useState } from 'react';
import Icon from './Icon';
import HeadphonePoster from './HeadphonePoster';

const HeadphoneScene = dynamic(() => import('./HeadphoneScene'), {
  ssr: false,
  loading: () => <div className={"headphone-scene absolute z-[1] [&.is-ready::after]:[content:''] [&.is-ready::after]:absolute [&.is-ready::after]:bottom-[8%] [&.is-ready::after]:left-[24%] [&.is-ready::after]:w-[52%] [&.is-ready::after]:h-[4%] [&.is-ready::after]:rounded-[50%] [&.is-ready::after]:[background:var(--surface-647b7021)] [&.is-ready::after]:[filter:blur(12px)] [&.is-ready::after]:pointer-events-none [&.is-ready::after]:z-[-1] scene-fallback absolute [inset:0] rounded-[15px] overflow-hidden"}><HeadphonePoster loading /></div>,
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
  return <div className={"meaning-sketch relative [background:var(--surface-e5edeb)] rounded-[12px] mt-[24px] aspect-[1.65] overflow-hidden [&_svg]:w-[100%] [&_svg]:h-[100%] [&_>_span]:absolute [&_>_span]:text-[8px] [&_>_span]:[background:var(--surface-f9faf3da)] [&_>_span]:rounded-[15px] [&_>_span]:pt-[7px] [&_>_span]:pr-[9px] [&_>_span]:pb-[7px] [&_>_span]:pl-[9px] [&_>_span]:[color:var(--text-4e625a)]"} role="group" aria-label="Schematic connection from a commute query to related headphone ideas"><svg viewBox="0 0 420 250" aria-hidden="true"><g fill="none" stroke="#becbcb"><ellipse cx="216" cy="123" rx="150" ry="91" /><ellipse cx="216" cy="123" rx="103" ry="61" strokeDasharray="4 5" /><path d="m115 114 133-55m-133 55 170 29m-170-29 133 66" stroke="#b49e76" /></g>{Array.from({ length: 24 }, (_, i) => <circle key={i} cx={243 + Math.sin(i * 2.3) * 43} cy={92 + Math.cos(i * 1.5) * 48} r={i % 3 === 0 ? 4 : 2} fill="#92a9b5" />)}<circle cx="115" cy="114" r="7" fill="#bba073" /></svg><span className={"sketch-query left-[5%] top-[32%] [color:var(--text-644f31)]!"}>your commute query</span><span className={"sketch-match right-[9%] top-[13%]"}>quieter listening</span><span className={"sketch-other right-[13%] bottom-[15%]"}>nearby product ideas</span></div>;
}

export default function HeadphoneStory() {
  const trackRef = useRef<HTMLDivElement>(null);
  const progressBarRef = useRef<HTMLDivElement>(null);
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

  const goToChapter = (index: number) => {
    const track = trackRef.current;
    if (!track) return;
    const start = track.getBoundingClientRect().top + window.scrollY;
    const distance = track.offsetHeight - window.innerHeight;
    window.scrollTo({ top: start + distance * (index * .25 + .08), behavior: 'smooth' });
  };
  const changeFinish = (value: string) => { setFinish(value); appearanceRef.current = value; };
  const chapter = chapters[activeChapter];

  return (
    <section className={classes(`headphone-story ${simple ? 'is-simple' : ''}`)} id="how-it-works" aria-labelledby="story-title">
      <div className={"story-intro text-center mb-[46px] [&_h2]:text-[clamp(43px,_4.8vw,_66px)] [&_h2]:tracking-[-3px] [&_h2]:leading-[1.1] [&_h2]:mt-[17px] [&_h2]:mr-[0] [&_h2]:mb-[23px] [&_h2]:ml-[0] [&_h2_em]:[color:var(--text-50666a)] [&_>_p]:[color:var(--text-53615b)] [&_>_p]:text-[13px] [&_>_p]:leading-[1.8] max-[780.01px]:mb-[32px] max-[780.01px]:[&_h2]:text-[47px] max-[780.01px]:[&_>_p]:max-w-[290px] max-[780.01px]:[&_>_p]:ml-[auto] max-[780.01px]:[&_>_p]:mr-[auto] max-[780.01px]:[&_>_p]:text-[12px] section-shell w-[min(1320px,_calc(100%_-_104px))] ml-[auto] mr-[auto] max-[1100.01px]:w-[calc(100%_-_72px)] max-[780.01px]:w-[calc(100%_-_44px)]"}><span className={"eyebrow block text-[10px] font-semibold tracking-[1.7px] leading-[1.6] [color:var(--text-737b6c)] max-[430.01px]:text-[8px] max-[430.01px]:tracking-[1.2px]"}>ONE PRODUCT. A DIFFERENT WAY TO FIND IT.</span><h2 id="story-title">Let’s follow<br /><em>a little meaning.</em></h2><p>A headphone. A quiet commute. A look inside the idea of semantic search.</p><span className={"story-demo-label inline-flex items-center gap-[8px] mt-[22px] text-[10px] [color:var(--text-53615b)]"}><span className={"status-dot inline-block w-[5px] h-[5px] shrink-[0] rounded-[50%] [background:var(--surface-99a293)] [&.is-online]:[background:var(--surface-6b9763)] [&.is-online]:[box-shadow:0_0_0_3px_var(--shadow-6b976314)]"} /> A visual story · not a live search</span></div>
      <div className={"story-track h-[430svh] relative"} ref={trackRef}>
        <div className={"story-sticky sticky top-[0] h-[100svh] pt-[29px] pr-[40px] pb-[23px] pl-[40px] mt-[0] mr-[12px] mb-[0] ml-[12px] rounded-[17px] [background:var(--surface-eff1ed)] flex flex-col overflow-hidden max-[1100.01px]:pt-[25px] max-[1100.01px]:pr-[25px] max-[1100.01px]:pb-[20px] max-[1100.01px]:pl-[25px] dark:[&.story-sticky]:[background:linear-gradient(145deg,#1c2a22,#141f19)] dark:ring-1 dark:ring-[#c9ddb51a]"} data-chapter={activeChapter}>
          <div className={"story-topline flex items-center justify-between gap-[20px] [color:var(--text-53615b)] text-[8px] tracking-[1.4px] pb-[20px] [&_>_span:last-child]:flex [&_>_span:last-child]:items-center [&_>_span:last-child]:gap-[8px]"}><span>THE ANATOMY OF A GOOD FIND</span><span>SCROLL TO FOLLOW THE STORY <Icon name="down" size={13} /></span></div>
          <nav className={"story-chapters flex gap-[34px] [border-top:1px_solid_var(--border-d7ded5)] pt-[16px] [&_button]:flex [&_button]:items-center [&_button]:gap-[10px] [&_button]:[border:0] [&_button]:[background:transparent] [&_button]:pt-[8px] [&_button]:pr-[0] [&_button]:pb-[8px] [&_button]:pl-[0] [&_button]:[color:var(--text-53615b)] [&_button]:text-[11px] [&_button]:[transition:color_.2s] [&_button_>_span]:text-[8px] [&_button_>_span]:[border:1px_solid_var(--border-d1d8ce)] [&_button_>_span]:rounded-[50%] [&_button_>_span]:w-[23px] [&_button_>_span]:h-[23px] [&_button_>_span]:inline-flex [&_button_>_span]:items-center [&_button_>_span]:justify-center [&_button.active]:[color:var(--text-344b4e)] [&_button.active_>_span]:[border-color:var(--text-8caaac)] [&_button.active_>_span]:[background:var(--surface-e0e9e5)] max-[1100.01px]:gap-[22px]"} aria-label="Headphone story chapters">{chapters.map((item, index) => <button key={item.label} onClick={() => goToChapter(index)} aria-current={activeChapter === index ? 'step' : undefined} className={classes(activeChapter === index ? 'active' : '')}><span>0{index + 1}</span>{item.label}</button>)}</nav>
          <div className={"story-layout grid grid-cols-[.85fr_1.15fr] gap-[40px] [flex:1] min-h-[0] pt-[18px] pr-[0] pb-[18px] pl-[0] max-[1100.01px]:gap-[25px] max-[1100.01px]:grid-cols-[.9fr_1.1fr]"}>
            <div className={"story-copy self-center max-w-[470px] [animation:arrive_.55s_ease_both] pt-[15px] pr-[0] pb-[15px] pl-[0] [&_.eyebrow]:[color:var(--text-53615b)] [&_h3]:[font-family:var(--serif)] [&_h3]:font-normal [&_h3]:text-[clamp(40px,_4.3vw,_63px)] [&_h3]:leading-[1.07] [&_h3]:tracking-[-2.6px] [&_h3]:mt-[20px] [&_h3]:mr-[0] [&_h3]:mb-[25px] [&_h3]:ml-[0] [&_h3_em]:[color:var(--text-50666a)] [&_>_p]:text-[13px] [&_>_p]:[color:var(--text-4f5e56)] [&_>_p]:leading-[1.9] [&_>_p]:max-w-[375px] [&_blockquote]:mt-[26px] [&_blockquote]:mr-[0] [&_blockquote]:mb-[0] [&_blockquote]:ml-[0] [&_blockquote]:pt-[18px] [&_blockquote]:pr-[22px] [&_blockquote]:pb-[18px] [&_blockquote]:pl-[22px] [&_blockquote]:[background:var(--surface-f8f9f4)] [&_blockquote]:[border:1px_solid_var(--border-d7e0d5)] [&_blockquote]:rounded-[10px] [&_blockquote]:[font-style:italic] [&_blockquote]:[font-weight:normal] [&_blockquote]:text-[23px] [&_blockquote]:leading-[1.4] [&_blockquote]:[font-family:var(--serif)] [&_blockquote]:tracking-[-.5px] [&_blockquote]:[color:var(--text-465b59)] [&_p.story-note]:[color:var(--text-536159)] [&_p.story-note]:text-[9px] [&_p.story-note]:mt-[22px] [&_p.story-note]:leading-[1.8] [&_.text-link]:mt-[26px] [&_.text-link]:text-[12px] max-[1100.01px]:[&_h3]:text-[44px] max-[1100.01px]:[&_>_p]:text-[12px]"} key={activeChapter}><span className={"eyebrow block text-[10px] font-semibold tracking-[1.7px] leading-[1.6] [color:var(--text-737b6c)] max-[430.01px]:text-[8px] max-[430.01px]:tracking-[1.2px]"}>{chapter.eyebrow}</span><h3>{chapter.title}</h3><p>{chapter.description}</p>{activeChapter === 1 && <blockquote>“Something to help me focus on my commute.”</blockquote>}<div className={"story-tags flex flex-wrap gap-[7px] mt-[24px] [&_>_span]:text-[9px] [&_>_span]:[color:var(--text-4f6255)] [&_>_span]:[background:var(--surface-e6ece2)] [&_>_span]:pt-[8px] [&_>_span]:pr-[11px] [&_>_span]:pb-[8px] [&_>_span]:pl-[11px] [&_>_span]:[border:1px_solid_var(--border-dbe2d4)] [&_>_span]:rounded-[25px] [&_>_span]:leading-[1.5]"}>{chapter.tags.map((tag) => <span key={tag}>{tag}</span>)}</div><p className={"story-note"}>{chapter.note}</p>{activeChapter === 3 && <a className={"text-link inline-flex items-center gap-[22px] text-[13px] pb-[9px] [border-bottom:1px_solid_var(--ink)]"} href="#comparison">See the difference <Icon name="arrow" size={18} /></a>}</div>
            <div className={classes(`story-visual story-visual--${activeChapter}`)}>
              {!simple && sceneEnabled ? <HeadphoneScene progressRef={progressRef} appearanceRef={appearanceRef} rotationRef={rotationRef} /> : <div className={"headphone-scene absolute z-[1] [&.is-ready::after]:[content:''] [&.is-ready::after]:absolute [&.is-ready::after]:bottom-[8%] [&.is-ready::after]:left-[24%] [&.is-ready::after]:w-[52%] [&.is-ready::after]:h-[4%] [&.is-ready::after]:rounded-[50%] [&.is-ready::after]:[background:var(--surface-647b7021)] [&.is-ready::after]:[filter:blur(12px)] [&.is-ready::after]:pointer-events-none [&.is-ready::after]:z-[-1] scene-fallback absolute [inset:0] rounded-[15px] overflow-hidden"}><HeadphonePoster loading={!simple} /></div>}
              {activeChapter !== 2 && <div className={"scene-turn-controls absolute z-[2] top-[24px] left-[20px] flex gap-[6px] [&_button]:w-[30px] [&_button]:h-[30px] [&_button]:pt-[0] [&_button]:pr-[0] [&_button]:pb-[0] [&_button]:pl-[0] [&_button]:inline-flex [&_button]:items-center [&_button]:justify-center [&_button]:[background:var(--surface-f9fbf2c9)] [&_button]:[border:1px_solid_var(--border-ffffffbf)] [&_button]:rounded-[50%] [&_button]:[color:var(--text-53615b)] [&_button:hover]:[background:var(--surface-fff)] [&_.turn-left]:[transform:rotate(180deg)]"} role="group" aria-label="Rotate the illustrative headphones"><button aria-label="Rotate headphones left" onClick={() => { rotationRef.current -= .4; }}><Icon name="arrow" size={14} className={"turn-left"} /></button><button aria-label="Rotate headphones right" onClick={() => { rotationRef.current += .4; }}><Icon name="arrow" size={14} /></button></div>}
              <span className={"scene-orbit absolute w-[75%] h-[75%] top-[5%] left-[12.5%] [border:1px_solid_var(--border-9eb5b921)] rounded-[50%] pointer-events-none [&.orbit-b]:w-[57%] [&.orbit-b]:h-[57%] [&.orbit-b]:top-[13%] [&.orbit-b]:left-[21.5%] [&.orbit-b]:[border-style:dashed] orbit-a"} /><span className={"scene-orbit absolute w-[75%] h-[75%] top-[5%] left-[12.5%] [border:1px_solid_var(--border-9eb5b921)] rounded-[50%] pointer-events-none [&.orbit-b]:w-[57%] [&.orbit-b]:h-[57%] [&.orbit-b]:top-[13%] [&.orbit-b]:left-[21.5%] [&.orbit-b]:[border-style:dashed] orbit-b"} />
              {activeChapter === 0 && <div className={"product-callout absolute z-[2] top-[25px] right-[21px] w-[164px] pt-[15px] pr-[15px] pb-[15px] pl-[15px] [background:var(--surface-fafbf6d6)] [border:1px_solid_var(--border-ffffffc9)] rounded-[10px] [backdrop-filter:blur(9px)] pointer-events-none [&_>_span]:block [&_>_span]:[color:var(--text-53615b)] [&_>_span]:text-[7px] [&_>_span]:tracking-[1px] [&_strong]:block [&_strong]:[font-style:normal] [&_strong]:[font-weight:normal] [&_strong]:text-[25px] [&_strong]:leading-[normal] [&_strong]:[font-family:var(--serif)] [&_strong]:mt-[8px] [&_strong]:[color:var(--text-4c6253)] [&_p]:text-[9px] [&_p]:leading-[1.8] [&_p]:mt-[8px] [&_p]:[color:var(--text-53604e)] max-[1100.01px]:w-[145px] max-[1100.01px]:right-[13px] max-[1100.01px]:pt-[12px] max-[1100.01px]:pr-[12px] max-[1100.01px]:pb-[12px] max-[1100.01px]:pl-[12px] dark:[&.product-callout]:[background:#17271ce6] dark:[&.product-callout]:[border-color:#a5c49733] dark:shadow-[0_12px_30px_#050d0940]"}><span>THE LITTLE DETAIL</span><strong>{details[detail].name}</strong><p>{details[detail].text}</p></div>}
              {activeChapter === 1 && <><span className={"story-floating-tag absolute pt-[12px] pr-[16px] pb-[12px] pl-[16px] rounded-[24px] [background:var(--surface-fafbf5e6)] [border:1px_solid_var(--border-fff)] z-[2] [color:var(--text-526357)] [font-style:italic] [font-weight:normal] text-[16px] leading-[normal] [font-family:var(--serif)] pointer-events-none float-focus top-[23%] left-[5%] [transform:rotate(-7deg)]"}>a little more focus</span><span className={"story-floating-tag absolute pt-[12px] pr-[16px] pb-[12px] pl-[16px] rounded-[24px] [background:var(--surface-fafbf5e6)] [border:1px_solid_var(--border-fff)] z-[2] [color:var(--text-526357)] [font-style:italic] [font-weight:normal] text-[16px] leading-[normal] [font-family:var(--serif)] pointer-events-none float-commute bottom-[29%] right-[6%] [transform:rotate(5deg)]"}>a quieter commute</span></>}
              {activeChapter === 2 && <div className={"map-annotations absolute [inset:0] z-[2] pointer-events-none"}><span className={"map-label absolute [background:var(--surface-f7f9f1e6)] [border:1px_solid_var(--border-ffffffa6)] pt-[9px] pr-[12px] pb-[9px] pl-[12px] rounded-[20px] text-[10px] [color:var(--text-4e625f)] map-audio top-[30%] right-[4%]"}>Headphones & earbuds</span><span className={"map-label absolute [background:var(--surface-f7f9f1e6)] [border:1px_solid_var(--border-ffffffa6)] pt-[9px] pr-[12px] pb-[9px] pl-[12px] rounded-[20px] text-[10px] [color:var(--text-4e625f)] map-outdoor bottom-[30%] left-[6%] [color:var(--text-5c4f70)]"}>Outdoor ideas</span><span className={"map-label absolute [background:var(--surface-f7f9f1e6)] [border:1px_solid_var(--border-ffffffa6)] pt-[9px] pr-[12px] pb-[9px] pl-[12px] rounded-[20px] text-[10px] [color:var(--text-4e625f)] map-home bottom-[19%] right-[13%] [color:var(--text-4e6049)]"}>Home comforts</span><span className={"map-query absolute [background:var(--surface-f7f9f1e6)] [border:1px_solid_var(--border-ffffffa6)] pt-[9px] pr-[12px] pb-[9px] pl-[12px] rounded-[20px] text-[10px] [color:var(--text-695637)] top-[17%] left-[34%]"}>Your words</span><span className={"map-note absolute top-[26px] left-[22px] text-[7px] tracking-[1.6px] [color:var(--text-52645f)]"}>SCHEMATIC VECTOR SPACE</span></div>}
              {activeChapter === 3 && <div className={"match-ribbon absolute bottom-[128px] left-[50%] [transform:translateX(-50%)] [border:1px_solid_var(--border-ffffffc2)] [background:var(--surface-f5f9eef0)] rounded-[25px] pt-[11px] pr-[17px] pb-[11px] pl-[17px] flex gap-[8px] items-center text-[10px] [color:var(--text-4b6043)] z-[2] whitespace-nowrap"}><Icon name="check" size={16} /><span>A possible fit for a quieter commute</span></div>}
              <div className={"scene-toolbar flex justify-between items-center gap-[12px] absolute bottom-[81px] left-[20px] right-[20px] z-[2] [color:var(--text-53615b)] text-[8px] max-[1100.01px]:left-[13px] max-[1100.01px]:right-[13px] max-[1100.01px]:text-[7px]"}><span>{activeChapter === 2 ? 'Illustrative meaning map' : 'AirPods Max · interactive 3D'}</span>{activeChapter !== 2 && <div className={"finish-control inline-flex gap-[8px] items-center [&_>_span]:text-[8px] [&_>_span]:mr-[3px] max-[1100.01px]:[&_>_span]:hidden"} role="group" aria-label="Illustrative model finish"><span>Color study</span><button aria-label="Silver color study" aria-pressed={finish === 'silver'} className={classes(`finish-swatch silver ${finish === 'silver' ? 'active' : ''}`)} onClick={() => changeFinish('silver')} /><button aria-label="Original green finish" aria-pressed={finish === 'sage'} className={classes(`finish-swatch sage ${finish === 'sage' ? 'active' : ''}`)} onClick={() => changeFinish('sage')} /></div>}</div>
              {activeChapter === 0 && <div className={"detail-selector absolute bottom-[38px] left-[50%] [transform:translateX(-50%)] flex pt-[4px] pr-[4px] pb-[4px] pl-[4px] [background:var(--surface-edf3e9b3)] [border:1px_solid_var(--border-ffffffb0)] rounded-[25px] z-[2] whitespace-nowrap [&_button]:[border:0] [&_button]:[background:transparent] [&_button]:pt-[8px] [&_button]:pr-[16px] [&_button]:pb-[8px] [&_button]:pl-[16px] [&_button]:rounded-[20px] [&_button]:[color:var(--text-53604e)] [&_button]:text-[9px] [&_button.active]:[background:var(--surface-f9faf5)] [&_button.active]:[color:var(--text-506d5f)]"} role="group" aria-label="Explore headphone details">{details.map((item, index) => <button key={item.name} aria-pressed={detail === index} className={classes(detail === index ? 'active' : '')} onClick={() => setDetail(index)}>{item.name}</button>)}</div>}
              <span className={"scene-drag-note absolute bottom-[16px] left-[0] right-[0] text-center [color:var(--text-53615b)] text-[8px]"}>{activeChapter === 2 ? 'Different descriptions. Related meanings.' : 'Drag or use the arrow controls to look around.'}</span>
            </div>
          </div>
          <div className={"story-bottomline flex justify-between items-center gap-[20px] [color:var(--text-53604e)] text-[9px] pt-[8px] pr-[0] pb-[0] pl-[0] [&_>_span:first-child]:[font-variant-numeric:tabular-nums] [&_>_a]:inline-flex [&_>_a]:items-center [&_>_a]:gap-[7px] [&_>_a]:text-[9px]"}><span>0{activeChapter + 1} / 04</span><span>{chapter.label}</span><a href="#comparison">Jump to comparison <Icon name="diagonal" size={13} /></a></div>
          <div className={"story-progress h-[2px] [background:var(--surface-dbe2d6)] absolute bottom-[0] left-[0] right-[0] [&_>_div]:[background:var(--surface-8da3a1)] [&_>_div]:h-[100%] [&_>_div]:[transform:scaleX(0)] [&_>_div]:[transform-origin:left]"}><div ref={progressBarRef} /></div>
        </div>
      </div>
      <div className={"story-mobile hidden [&_>_.outline-button]:flex [&_>_.outline-button]:w-[max-content] [&_>_.outline-button]:mt-[20px] [&_>_.outline-button]:mr-[auto] [&_>_.outline-button]:mb-[45px] [&_>_.outline-button]:ml-[auto] section-shell w-[min(1320px,_calc(100%_-_104px))] ml-[auto] mr-[auto] max-[1100.01px]:w-[calc(100%_-_72px)] max-[780.01px]:w-[calc(100%_-_44px)]"}>
        <div className={"mobile-headphone-art h-[380px] max-w-[600px] mt-[0] mr-[auto] mb-[40px] ml-[auto] rounded-[14px] overflow-hidden relative [&_>_span]:absolute [&_>_span]:left-[12px] [&_>_span]:bottom-[12px] [&_>_span]:text-[8px] [&_>_span]:[color:var(--text-53615b)] [&_>_span]:[background:var(--surface-f4f5e9b3)] [&_>_span]:pt-[7px] [&_>_span]:pr-[10px] [&_>_span]:pb-[7px] [&_>_span]:pl-[10px] [&_>_span]:rounded-[15px] max-[780.01px]:h-[320px]"}><HeadphonePoster /><span>AirPods Max · 3D model preview</span></div>
        {chapters.map((item, index) => <article key={item.label} className={"mobile-story-chapter [&_h3]:[font-family:var(--serif)] [&_h3]:font-normal [&_h3]:text-[40px] [&_h3]:leading-[1.07] [&_h3]:tracking-[-2.6px] [&_h3]:mt-[20px] [&_h3]:mr-[0] [&_h3]:mb-[25px] [&_h3]:ml-[0] [&_h3_em]:[color:var(--text-50666a)] [&_blockquote]:mt-[26px] [&_blockquote]:mr-[0] [&_blockquote]:mb-[0] [&_blockquote]:ml-[0] [&_blockquote]:pt-[18px] [&_blockquote]:pr-[22px] [&_blockquote]:pb-[18px] [&_blockquote]:pl-[22px] [&_blockquote]:[background:var(--surface-f8f9f4)] [&_blockquote]:[border:1px_solid_var(--border-d7e0d5)] [&_blockquote]:rounded-[10px] [&_blockquote]:[font-style:italic] [&_blockquote]:[font-weight:normal] [&_blockquote]:text-[23px] [&_blockquote]:leading-[1.4] [&_blockquote]:[font-family:var(--serif)] [&_blockquote]:tracking-[-.5px] [&_blockquote]:[color:var(--text-465b59)] [&_p.story-note]:[color:var(--text-536159)] [&_p.story-note]:text-[9px] [&_p.story-note]:mt-[22px] [&_p.story-note]:leading-[1.8] [border-top:1px_solid_var(--border-d8e0d4)] pt-[35px] pr-[0] pb-[35px] pl-[0] max-w-[700px] ml-[auto] mr-[auto] [scroll-margin-top:30px] [&_>_p]:text-[13px] [&_>_p]:leading-[1.85] [&_>_p]:[color:var(--text-4f5e56)] max-[780.01px]:[&_h3]:text-[39px]"} id={`story-mobile-${index}`}><span className={"eyebrow block text-[10px] font-semibold tracking-[1.7px] leading-[1.6] [color:var(--text-737b6c)] max-[430.01px]:text-[8px] max-[430.01px]:tracking-[1.2px]"}>{item.eyebrow}</span><h3>{item.title}</h3><p>{item.description}</p>{index === 1 && <blockquote>“Something to help me focus on my commute.”</blockquote>}{index === 2 && <MeaningSketch />}<div className={"story-tags flex flex-wrap gap-[7px] mt-[24px] [&_>_span]:text-[9px] [&_>_span]:[color:var(--text-4f6255)] [&_>_span]:[background:var(--surface-e6ece2)] [&_>_span]:pt-[8px] [&_>_span]:pr-[11px] [&_>_span]:pb-[8px] [&_>_span]:pl-[11px] [&_>_span]:[border:1px_solid_var(--border-dbe2d4)] [&_>_span]:rounded-[25px] [&_>_span]:leading-[1.5]"}>{item.tags.map((tag) => <span key={tag}>{tag}</span>)}</div><p className={"story-note"}>{item.note}</p></article>)}
        <a className={"outline-button inline-flex items-center justify-center gap-[18px] min-h-[46px] pt-[12px] pr-[22px] pb-[12px] pl-[22px] rounded-[30px] text-[12px] [transition:background_.2s,_transform_.2s] [background:transparent] [border:1px_solid_var(--border-aab0a3)] [&:hover]:[background:var(--surface-e9ecdf)] [&:hover]:[transform:translateY(-2px)]"} href="#comparison">Compare the approaches <Icon name="arrow" size={17} /></a>
      </div>
      <p className={"story-asset-credit mt-[24px] mr-[auto] mb-[0] ml-[auto] pt-[0] pr-[24px] pb-[0] pl-[24px] max-w-[1000px] text-center text-[9px] leading-[1.8] [color:var(--text-53615b)] [&_a]:underline [&_a]:underline-offset-[3px]"}>3D model: <a href="https://sketchfab.com/3d-models/airpods-max-05181e126a6341668ca95f2d98324d30" target="_blank" rel="noreferrer">Airpods max by Mr.Philin</a> · <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0</a> · optimized textures &amp; silver color study. <a href="https://www.apple.com/newsroom/2020/12/apple-introduces-airpods-max-the-magic-of-airpods-in-a-stunning-over-ear-design/" target="_blank" rel="noreferrer">Product details</a></p>
    </section>
  );
}
