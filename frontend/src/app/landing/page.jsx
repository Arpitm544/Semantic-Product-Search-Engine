import './landing.css';
import Hero from './components/Hero';
import ProductDataSection from './components/ProductDataSection';
import EmbeddingSection from './components/EmbeddingSection';
import VectorSpace from './components/VectorSpace';
import ComparisonSection from './components/ComparisonSection';
import HybridFusionSection from './components/HybridFusionSection';
import PlaygroundSection from './components/PlaygroundSection';
import CTASection from './components/CTASection';

export const metadata = {
  title: 'Semantic Search Pipeline | Visualized',
  description: 'Interactive 3D visualization of how our semantic product search pipeline works.',
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

      {/* Main Content Sections */}
      <main>
        <Hero />
        <ProductDataSection />
        <EmbeddingSection />
        <VectorSpace />
        <ComparisonSection />
        <HybridFusionSection />
        <PlaygroundSection />
        <CTASection />
      </main>

      {/* Footer */}
      <footer className="lp-footer">
        <p>Built with Next.js, FastAPI, FAISS, and React Three Fiber.</p>
      </footer>
    </div>
  );
}
