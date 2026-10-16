"""Compare keyword, fuzzy, semantic, and hybrid retrieval on held-out queries."""

import argparse
from collections import defaultdict
import json
from pathlib import Path

from src.keyword_search.bm25 import fit_bm25, search_bm25
from src.config import DATASET_DIR, EMBEDDING_MODEL_NAME, PROJECT_ROOT
from src.search.hybrid import HybridSearch
from src.semantic.dataset import (
    catalog_fingerprint, load_catalog, read_jsonl,
)


def retrieval_metrics(retrieved_ids, relevant_ids, k=5):
    """Measure relevant matches in the top five and the first match in the top ten."""
    relevant = set(relevant_ids)
    hits = len(set(retrieved_ids[:k]) & relevant)
    first = next((rank for rank, product_id in enumerate(retrieved_ids[:10], 1)
                  if product_id in relevant), None)
    return {
        "recall@5": hits / len(relevant) if relevant else 0.0,
        "hit_rate@5": float(hits > 0),
        "mrr@10": 1 / first if first else 0.0,
    }


class CachedSemantic:
    """Reuse query vectors when comparing semantic-only with hybrid ranking."""
    def __init__(self, engine):
        self.engine = engine
        self.cache = {}

    def search(self, query, top_k):
        if query not in self.cache or len(self.cache[query]) < min(top_k, len(self.engine.products)):
            self.cache[query] = self.engine.search(
                query, min(len(self.engine.products), max(50, top_k)),
            )
        return self.cache[query][:top_k]

    def prime(self, queries):
        """Batch query inference and retain only the candidates fusion needs."""
        import numpy as np

        texts = list(dict.fromkeys(queries))
        vectors = self.engine.model.encode(texts, batch_size=32, show_progress_bar=False)
        vectors = self.engine._normalize_embeddings(np.asarray(vectors))
        scores, indices = self.engine.index.search(vectors, min(50, len(self.engine.products)))
        for text, row_scores, row_indices in zip(texts, scores, indices):
            self.cache[text] = [
                (self.engine.products[int(index)], float(score))
                for index, score in zip(row_indices, row_scores) if index >= 0
            ]


def evaluate_systems(systems, queries):
    """Run each search method and summarize scores for clean and typo queries."""
    summary = {}
    details = []
    for name, search in systems.items():
        groups = defaultdict(list)
        for query in queries:
            ids = search(query["query"])
            metrics = retrieval_metrics(ids, query["relevant_doc_ids"])
            bucket = "clean" if query["kind"] == "clean" else "typo"
            groups["all"].append(metrics)
            groups[bucket].append(metrics)
            groups[f"source:{query['source']}:{bucket}"].append(metrics)
            details.append({
                "system": name, "query_id": query["query_id"], "query": query["query"],
                "retrieved_ids": ids[:10], **metrics,
            })
        summary[name] = {
            group: {"queries": len(values), **{
                metric: sum(value[metric] for value in values) / len(values)
                for metric in ("recall@5", "hit_rate@5", "mrr@10")
            }} for group, values in groups.items()
        }
    return summary, details


def parse_arguments():
    """Read options supplied after the command name."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATASET_DIR / "prepared")
    parser.add_argument("--catalog", type=Path, default=DATASET_DIR / "prepared" / "products.json")
    parser.add_argument("--split", choices=("validation", "test"), default="validation")
    parser.add_argument("--base-model", default=EMBEDDING_MODEL_NAME)
    parser.add_argument("--model", type=Path, default=None, help="Candidate model directory.")
    parser.add_argument("--lexical-only", action="store_true")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--device", default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser, parser.parse_args()


def load_evaluation_index(engine, products, model_ref, catalog_hash, data_dir, name):
    """Reuse product vectors only when both the catalog and model match."""
    from src.semantic.vector_search import SemanticVectorSearch

    model = engine.model
    model_directory = Path(model_ref)
    signature = {
        "catalog_sha256": catalog_hash,
        "model_ref": str(model_ref),
        "max_seq_length": model.max_seq_length,
        "base_revision": getattr(model[0].auto_model.config, "_commit_hash", None),
        "local_weights": {
            str(path.relative_to(model_directory)): [path.stat().st_size, path.stat().st_mtime_ns]
            for pattern in ("*.safetensors", "*.bin", "modules.json", "config.json")
            for path in model_directory.rglob(pattern)
        } if model_directory.is_dir() else {},
    }
    cache = data_dir / "evaluation_indexes" / name
    cache_manifest = cache / "signature.json"
    index_path, map_path = cache / "faiss_index.bin", cache / "faiss_id_map.pkl"
    if (cache_manifest.exists() and index_path.exists() and map_path.exists()
            and json.loads(cache_manifest.read_text()) == signature):
        engine = SemanticVectorSearch.load(index_path, map_path)
        engine._model = model
        print(f"Using cached {name} product embeddings.", flush=True)
    else:
        engine.fit(products)
        engine.save(index_path, map_path)
        cache_manifest.write_text(json.dumps(signature, indent=2) + "\n")
    return engine


def evaluate_models(args, parser):
    """Load evaluation data, compare search methods, and save their scores."""
    products = load_catalog(args.catalog)
    manifest = json.loads((args.data_dir / "manifest.json").read_text())
    if manifest["catalog_sha256"] != catalog_fingerprint(products):
        parser.error("The catalog changed; prepare the training data again.")
    queries = read_jsonl(args.data_dir / f"{args.split}.jsonl")
    if not queries:
        parser.error("The evaluation split is empty.")
    lexical = fit_bm25(products)
    fuzzy = HybridSearch(products, lexical=lexical)
    systems = {
        "bm25": lambda query: [p["id"] for p, _ in search_bm25(lexical, query, 10)],
        "bm25+fuzzy": lambda query: [p["id"] for p in fuzzy.search(query, 10)["results"]],
    }
    if not args.lexical_only:
        import torch
        from src.semantic.vector_search import SemanticVectorSearch

        torch.set_num_threads(2)
        for name, model_ref in (("base", args.base_model), ("fine-tuned", args.model)):
            if model_ref is None:
                continue
            print(f"Preparing {name} search index...", flush=True)
            engine = SemanticVectorSearch(
                str(model_ref), local_files_only=args.local_files_only, device=args.device,
            )
            engine = load_evaluation_index(
                engine, products, model_ref, manifest["catalog_sha256"], args.data_dir, name,
            )
            cached = CachedSemantic(engine)
            expanded_queries = [row["query"] for row in queries]
            expanded_queries.extend(fuzzy.spelling.correct(row["query"])[0] for row in queries)
            cached.prime(expanded_queries)
            hybrid = HybridSearch(products, cached, lexical=lexical)
            hybrid.spelling = fuzzy.spelling
            systems[f"{name}-semantic"] = (
                lambda query, retriever=cached: [p["id"] for p, _ in retriever.search(query, 10)]
            )
            systems[f"{name}-hybrid"] = (
                lambda query, retriever=hybrid: [p["id"] for p in retriever.search(query, 10)["results"]]
            )
    summary, details = evaluate_systems(systems, queries)
    output = args.output or PROJECT_ROOT / "reports" / f"typo_{args.split}_metrics.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "split": args.split, "catalog_sha256": manifest["catalog_sha256"],
        "data_note": manifest["source"], "candidate_model": str(args.model) if args.model else None,
        "metrics": summary, "per_query": details,
    }, indent=2) + "\n")
    for name, metrics in summary.items():
        for bucket in ("clean", "typo"):
            if bucket in metrics:
                value = metrics[bucket]
                print(f"{name:20} {bucket:5} Recall@5={value['recall@5']:.3f} "
                      f"Hit@5={value['hit_rate@5']:.3f} MRR@10={value['mrr@10']:.3f}")
    print(f"Report: {output}")


def main():
    parser, args = parse_arguments()
    evaluate_models(args, parser)


if __name__ == "__main__":
    main()
