import Icon from './Icon';
import { STORY_QUERY } from '@/lib/story';

export default function StorySearchDemo({ typedCount = STORY_QUERY.length, onReveal }) {
  const complete = typedCount >= STORY_QUERY.length;
  return <div className={`story-search-demo ${complete ? 'is-complete' : ''}`}>
    <div className="demo-search-brand"><span aria-hidden="true">✳</span> semantic.</div>
    <span className="demo-search-eyebrow">A GOOD FIND STARTS WITH YOUR WORDS</span>
    <h4>A little search.<br /><em>A world of possibility.</em></h4>
    <div className="demo-search-bar" role="group" aria-label="Scripted example search">
      <Icon name="search" size={19} />
      <span className="demo-search-text" aria-hidden="true">{typedCount ? STORY_QUERY.slice(0, typedCount) : <span className="demo-search-placeholder">What are you looking for?</span>}<i className="demo-search-cursor" /></span>
      <span className="sr-only">{STORY_QUERY}</span>
    </div>
    <div className="demo-search-signals" aria-hidden={!complete}><span>Apple <small>brand</small></span><span>Headphones <small>product</small></span><span>Quieter commute <small>your need</small></span></div>
    {onReveal ? <button className="demo-search-submit" onClick={onReveal}>Find my headphones <Icon name="arrow" size={17} /></button> : <a className="demo-search-submit" href="#story-mobile-1">Meet the headphones <Icon name="arrow" size={17} /></a>}
    <p className="demo-search-caption">{onReveal ? 'Scroll to write the query, then reveal the product.' : 'An example query. Follow its meaning below.'}<br /><span>Scripted demo · no live search</span></p>
  </div>;
}
