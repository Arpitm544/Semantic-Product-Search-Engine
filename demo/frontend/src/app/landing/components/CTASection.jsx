'use client';
import Link from 'next/link';
import ScrollReveal from './ScrollReveal';

export default function CTASection() {
  return (
    <section className="lp-section cta-section">
      <div className="cta-bg-particles" />
      <div className="cta-content">
        <ScrollReveal>
          <h2 className="cta-title">Ready to build better search?</h2>
          <p className="cta-sub">Search beyond keywords. Understand intent.</p>
        </ScrollReveal>
        
        <ScrollReveal delay={0.2}>
          <Link href="/" className="cta-button-large">
            Try the Full Search Sandbox →
          </Link>
        </ScrollReveal>
      </div>
    </section>
  );
}
