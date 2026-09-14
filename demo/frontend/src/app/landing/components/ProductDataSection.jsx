'use client';
import { motion } from 'framer-motion';
import ScrollReveal from './ScrollReveal';

const sampleProduct = {
  id: "prod_1",
  title: "ArcticShield Insulated Winter Parka",
  category: "Jackets & Outerwear",
  price: 4999,
  description: "Heavy-duty waterproof winter jacket with thermal fleece lining...",
  attributes: ["waterproof", "insulated", "fleece-lined", "winter"]
};

export default function ProductDataSection() {
  return (
    <section className="lp-section" id="pipeline">
      <ScrollReveal>
        <div className="section-badge">Step 1</div>
        <h2 className="section-title">Raw Product Catalog</h2>
        <p className="section-sub">Every product in the catalog is converted into a rich, searchable text representation.</p>
      </ScrollReveal>

      <div className="data-flow-grid">
        <ScrollReveal delay={0.2} direction="left">
          <div className="code-card">
            <div className="code-header">
              <span className="code-dot red" /><span className="code-dot yellow" /><span className="code-dot green" />
              <span className="code-filename">products.json</span>
            </div>
            <pre className="code-body">
{`{
  "id": "${sampleProduct.id}",
  "title": "${sampleProduct.title}",
  "category": "${sampleProduct.category}",
  "price": ${sampleProduct.price},
  "description": "Heavy-duty waterproof
    winter jacket...",
  "attributes": [
    "waterproof", "insulated",
    "fleece-lined", "winter"
  ]
}`}
            </pre>
          </div>
        </ScrollReveal>

        <ScrollReveal delay={0.4} direction="scale">
          <div className="flow-arrow-container">
            <div className="flow-arrow-line" />
            <div className="flow-arrow-label">Text Processing</div>
            <div className="flow-arrow-line" />
          </div>
        </ScrollReveal>

        <ScrollReveal delay={0.6} direction="right">
          <div className="code-card accent-card">
            <div className="code-header">
              <span className="code-dot red" /><span className="code-dot yellow" /><span className="code-dot green" />
              <span className="code-filename">Searchable Text</span>
            </div>
            <pre className="code-body highlight-text">
{`Title: ArcticShield Insulated
  Winter Parka
Category: Jackets & Outerwear
Description: Heavy-duty waterproof
  winter jacket with thermal
  fleece lining...
Attributes: waterproof, insulated,
  fleece-lined, winter`}
            </pre>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
