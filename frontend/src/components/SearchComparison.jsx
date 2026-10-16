'use client';

import { useState } from 'react';
import Icon from './Icon';
import Image from 'next/image';

const approaches = [
  { id: 'keyword', number: '01', title: 'The words you type.', name: 'Keyword', label: 'LOOK FOR WORD OVERLAP', text: 'Checks product text for the terms in your query. A clear product name is helpful; an everyday need may use different words.', tags: ['focus', 'commute'], outcome: 'The product wording may not overlap.', note: 'Useful for exact terms, product names, and model numbers.' },
  { id: 'semantic', number: '02', title: 'The need you mean.', name: 'Semantic', label: 'LOOK FOR RELATED MEANING', text: 'Connects the idea of fewer distractions and listening on the move to relevant product descriptions.', tags: ['fewer distractions', 'portable listening'], outcome: 'Noise-canceling headphones are a possible fit.', note: 'Useful for describing needs in your own words.' },
  { id: 'hybrid', number: '03', title: 'Room for both.', name: 'Hybrid', label: 'BLEND THE TWO SIGNALS', text: 'Combines related meaning with word overlap. Any exact details in the query can contribute alongside semantic relevance.', tags: ['related meaning', 'exact details'], outcome: 'A balance of context and word-level detail.', note: 'The balance depends on the query and chosen weights.' },
];

export default function SearchComparison() {
  const [selected, setSelected] = useState('semantic');
  return (
    <section className="comparison-section" id="comparison" aria-labelledby="comparison-title">
      <div className="comparison-inner section-shell">
        <div className="comparison-heading"><div><span className="eyebrow">THE SAME NEED. THREE WAYS TO LOOK.</span><h2 id="comparison-title">A little difference.<br /><em>A different discovery.</em></h2></div><p>Words are one starting point.<br />Meaning opens another.</p></div>
        <div className="comparison-query"><span className="comparison-query-label"><Icon name="search" size={18} /> ONE EXAMPLE QUERY</span><blockquote>“Something to help me focus on my commute.”</blockquote><span className="comparison-demo">Illustrative comparison · no live ranking</span></div>
        <div className="comparison-switch" role="group" aria-label="Highlight a search approach">{approaches.map((item) => <button key={item.id} aria-pressed={selected === item.id} onClick={() => setSelected(item.id)}>{item.name}<span>0{Number(item.number)}</span></button>)}</div>
        <div className="comparison-grid">{approaches.map((item) => <article key={item.id} className={`approach-card ${selected === item.id ? 'is-selected' : ''}`}><div className="approach-top"><span>{item.number} / {item.name.toUpperCase()}</span>{selected === item.id && <Icon name="sparkle" size={18} />}</div><h3>{item.title}</h3><span className="approach-label">{item.label}</span><p>{item.text}</p><div className="comparison-tags">{item.tags.map((tag) => <span key={tag}>{tag}</span>)}</div><div className="approach-outcome">{item.id === 'keyword' ? <div className="keyword-visual" aria-hidden="true"><span>focus</span><i /><span>commute</span><i /><span>product text?</span></div> : <div className="comparison-product"><Image src="/images/airpods-max-render.jpg" alt="AirPods Max rendered from the same 3D model as the product story" width={72} height={75} className="comparison-airpods-image" /><div><span>ILLUSTRATIVE CANDIDATE</span><strong>AirPods Max</strong><small>Noise-canceling · wireless</small></div></div>}<p>{item.outcome}</p></div><footer>{item.note}</footer></article>)}</div>
        <div className="comparison-footnote"><span><Icon name="sparkle" size={14} /> A visual explanation of search approaches.</span><span>This is a scripted example, not a benchmark or measured result.</span></div>
      </div>
    </section>
  );
}
