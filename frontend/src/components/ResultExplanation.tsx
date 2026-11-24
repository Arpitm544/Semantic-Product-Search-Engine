'use client';
import type { ReactNode } from 'react';
import type { ResultExplanation as Explanation } from '@/lib/types';

const pct = (value: number) => `${Math.round(value * 100)}%`;

function Row({ label, children }: { label: string; children: ReactNode }) {
  return <div className="grid grid-cols-[minmax(0,1fr)] gap-1 py-2 sm:grid-cols-[120px_minmax(0,1fr)] sm:gap-3">
    <dt className="text-[11px] font-semibold text-[var(--muted)]">{label}</dt>
    <dd className="m-0 min-w-0 text-[12px] leading-relaxed text-[var(--ink)]">{children}</dd>
  </div>;
}

function MatchedWords({ terms }: { terms: string[] }) {
  if (!terms.length) return <>No exact word match. It was found by meaning.</>;
  return <span className="flex flex-wrap gap-1.5">
    {terms.map(term => <span key={term} className="rounded-full bg-[var(--sage)] px-2 py-0.5 text-[11px] font-medium">{term}</span>)}
  </span>;
}

/** One line per way the product was found, in plain words. */
function foundBy(explanation: Explanation) {
  const lines: string[] = [];
  if (explanation.providerRank != null) lines.push(`The shop listed it #${explanation.providerRank}.`);
  if (explanation.keywordRank != null) lines.push(`Keyword search ranked it #${explanation.keywordRank}.`);
  if (explanation.semanticRank != null) {
    // Cosine similarity of the two embeddings: 1 means the same meaning. It is not a percentage.
    const similarity = explanation.semanticSimilarity != null ? ` (similarity ${explanation.semanticSimilarity.toFixed(2)} out of 1)` : '';
    lines.push(`Meaning search ranked it #${explanation.semanticRank}${similarity}.`);
  }
  if (explanation.spellingMatch) lines.push('It also matched a spelling correction of your search.');
  return lines;
}

/** "Why this result?": the numbers the search used, in the shopper's words. */
export default function ResultExplanation({ explanation, position }: { explanation: Explanation; position: number }) {
  const { weights } = explanation;
  return <details className="group mt-2 max-w-[690px] text-[12px]">
    <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-[11px] font-semibold text-[var(--accent)] hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--focus-ring)] [&::-webkit-details-marker]:hidden">
      Why this result? <span aria-hidden="true" className="transition-transform group-open:rotate-90">›</span>
    </summary>
    <dl className="mt-2 divide-y divide-[var(--line)] rounded-xl border border-[var(--line)] bg-[var(--surface-fff)] px-4 py-1">
      <Row label="Your words">
        <MatchedWords terms={explanation.matchedTerms} />
      </Row>
      <Row label="How it was found">
        {foundBy(explanation).map(line => <span key={line} className="block">{line}</span>)}
      </Row>
      <Row label="Careful check">
        A second model read your search together with this product and ranked it <strong>#{explanation.rerankerRank}</strong> of {explanation.candidateCount} candidates.
      </Row>
      <Row label={`Why #${position}`}>
        Candidates are ordered {pct(weights.retrieval)} by how they were found (#{explanation.retrievalRank}) and {pct(weights.reranker)} by the careful check (#{explanation.rerankerRank}).
        <span className="mt-1.5 flex h-1.5 overflow-hidden rounded-full" aria-hidden="true">
          <span className="bg-[var(--accent)] opacity-40" style={{ width: pct(weights.retrieval) }} />
          <span className="bg-[var(--accent)]" style={{ width: pct(weights.reranker) }} />
        </span>
      </Row>
    </dl>
  </details>;
}
