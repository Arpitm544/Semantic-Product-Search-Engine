import './landing.css';
import Hero from './components/Hero';
import Pipeline3D from './components/Pipeline3D';
import VectorSpace from './components/VectorSpace';
import ComparisonSection from './components/ComparisonSection';
import HybridFusionSection from './components/HybridFusionSection';
import PlaygroundSection from './components/PlaygroundSection';
import CTASection from './components/CTASection';

export const metadata = {
  title: 'Semantic Product Search | Vector & Hybrid AI Engine',
  description: 'An interactive walkthrough of how semantic product search works — from raw catalog to vector embeddings, FAISS indexing, and hybrid ranking.',
};

export default function LandingPage() {
  return (
    <div className="landing-layout">
      {/* Navigation */}
      <nav className="lp-nav">
        <div className="lp-logo">Semantic Search POC</div>
        <div className="lp-links">
          <a href="#pipeline">Pipeline</a>
          <a href="#vector-space">Vector Space</a>
          <a href="#playground">Playground</a>
        </div>
      </nav>

      <main>
        {/* 1. Hero with particle network */}
        <Hero />

        {/* 2. 3D Pipeline — main visual centerpiece */}
        <Pipeline3D />

        {/* 3. Interactive FAISS Vector Space */}
        <VectorSpace />

        {/* 4. Semantic vs BM25 comparison */}
        <ComparisonSection />

        {/* 5. Hybrid Fusion */}
        <HybridFusionSection />

        {/* 6. Live playground connected to real backend */}
        <PlaygroundSection />

        {/* 7. CTA */}
        <CTASection />
      </main>

      <footer className="lp-footer">
        <p>Built with Next.js · FastAPI · FAISS · Sentence Transformers · React Three Fiber</p>
      </footer>
    </div>
  );
}
