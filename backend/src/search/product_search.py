"""Find product candidates, score query/product pairs, then return ranked matches."""
from collections import Counter, defaultdict
from functools import lru_cache
import re
from threading import Lock
from src.keyword_search.bm25 import fit_bm25
from src.search.hybrid import HybridSearch
from src.search.typos import CatalogSpelling, STOP_WORDS, edit_distance


def brand_title(product):
    """Build keyword-search text using the product brand and title."""
    match = re.search(r'\[Brand\]\s*([^|]+)', product.get('representation_text', ''))
    brand = match.group(1).strip() if match else product.get('brand', '')
    return f"{brand} {product.get('title', '')}"


class FrequencySpelling(CatalogSpelling):
    def __init__(self, frequency):
        super().__init__(frequency)
        self.frequency = frequency

    @lru_cache(maxsize=8192)
    def suggestion(self, word):
        word = word.lower()
        if (word in self.vocabulary or word in STOP_WORDS or not word.isascii()
                or not word.isalpha() or not 4 <= len(word) <= 40):
            return None
        edits = 1 if len(word) < 8 else 2
        candidates = []
        for length in range(len(word)-edits, len(word)+edits+1):
            for candidate in self.by_length.get(length, []):
                distance = edit_distance(word, candidate)
                if distance <= edits and 1-distance/max(len(word), length) >= .8:
                    candidates.append((distance, candidate))
        if not candidates:
            return None
        distance = min(d for d, _ in candidates)
        closest = sorted((c for d, c in candidates if d == distance),
                         key=lambda c: (-self.frequency[c], c))
        if len(closest) > 1:
            first, second = (self.frequency[c] for c in closest[:2])
            if first < 5 or first < 3*max(1, second):
                return None
        return closest[0], distance

    def alternatives(self, query, maximum=5):
        corrected, _ = self.correct(query)
        variants = list(dict.fromkeys([query, corrected]))
        for match in re.finditer(r'\b[a-zA-Z]+\b', query):
            word = match.group().lower()
            if word in STOP_WORDS or not 4 <= len(word) <= 40 or self.frequency[word] >= 5:
                continue
            candidates = []
            for length in range(len(word)-1, len(word)+2):
                for candidate in self.by_length.get(length, []):
                    frequency = self.frequency[candidate]
                    if (candidate != word and frequency >= 5
                            and edit_distance(word, candidate) == 1
                            and 1-1/max(len(word), len(candidate)) >= .8):
                        candidates.append((frequency, candidate))
            candidates.sort(key=lambda item: (-item[0], item[1]))
            for _, candidate in candidates[:2]:
                variant = query[:match.start()]+candidate+query[match.end():]
                if variant not in variants:
                    variants.append(variant)
                if len(variants) >= maximum:
                    return variants
        return variants


class ProductSearch:
    def __init__(self, products, semantic, reranker):
        self.products = products
        self.by_id = {p['id']: p for p in products}
        self.semantic = semantic
        self.reranker = reranker
        self.lock = Lock()
        frequency = Counter()
        for product in products:
            text = brand_title(product)
            frequency.update(set(re.findall(r'\b[a-z]+\b', text.lower())))
        lexical = fit_bm25(products)
        lexical['products'] = products
        self.hybrid = HybridSearch(products, semantic, lexical=lexical)
        self.spelling = FrequencySpelling(frequency)
        self.hybrid.spelling = self.spelling

    def search(self, query, limit=20, fuzzy=True):
        query = query.strip()
        corrected, corrections = self.spelling.correct(query) if fuzzy else (query, [])
        variants = self.spelling.alternatives(query) if fuzzy else [query]
        payload = dict(query=query, correctedQuery=corrected if corrections else None,
                       corrections=corrections, queryAlternatives=variants,
                       searchMode='expanded-hybrid-reranked', semanticModel=getattr(self.semantic, 'model_name', None),
                       total=0, results=[])
        if not query or limit <= 0:
            return payload
        with self.lock:
            candidate_ids, sources = self.find_candidates(variants, query)
            if not candidate_ids:
                return payload
            final, blended = self.rank_candidates(corrected, candidate_ids)
            payload['total'] = len(final)
            payload['results'] = [{**self.by_id[pid], 'score': blended[pid],
                                   'matchSources': sorted(sources[pid]) + ['reranker']}
                                  for pid in final[:limit]]
        return payload

    def find_candidates(self, variants, query):
        """Combine keyword and semantic matches from each query variation."""
        retrieval = defaultdict(float)
        sources = defaultdict(set)
        for variant in variants:
            result = self.hybrid.search(variant, 50, fuzzy=False)
            for rank, product in enumerate(result['results'], 1):
                retrieval[product['id']] += 1/(60+rank)
                sources[product['id']].update(product['matchSources'])
                if variant != query:
                    sources[product['id']].add('fuzzy')
        ids = sorted(retrieval, key=lambda pid: (-retrieval[pid], pid))
        return ids, sources

    def rank_candidates(self, corrected, ids):
        """Blend model ranking (75%) with retrieval ranking (25%)."""
        retrieval_ranks = {pid: rank for rank, pid in enumerate(ids, 1)}
        pairs = [(corrected, self.by_id[pid].get('representation_text')
                  or self.by_id[pid].get('title', '')) for pid in ids]
        scores = self.reranker.predict(pairs, batch_size=32, show_progress_bar=False)
        reranked = sorted(range(len(ids)), key=lambda i: (-float(scores[i]), retrieval_ranks[ids[i]]))
        reranker_ranks = {ids[i]: rank for rank, i in enumerate(reranked, 1)}
        blended = {pid: .25/(60+retrieval_ranks[pid])+.75/(60+reranker_ranks[pid]) for pid in ids}
        final = sorted(ids, key=lambda pid: (-blended[pid], retrieval_ranks[pid]))

        return final, blended
