"""Run the real search pipeline on labelled ESCI queries and save ranking features.

    .venv/bin/python scripts/ltr_features.py                # validation + test
    .venv/bin/python scripts/ltr_features.py --limit 20     # quick check

For every query this runs spelling, keyword + meaning retrieval and the
cross-encoder exactly as served (meaning search runs in memory over the same
embeddings, as in the quality report), then stores one feature row per
candidate with its ESCI grade (Exact 3, Substitute 2, Complement 1,
Irrelevant 0; unjudged 0). Results go to backend/indexes/ltr/ (git-ignored).
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np

from src.config import DATASET_DIR, INDEXES_DIR
from src.evaluation.cache_identity import ranking_cache_identity
from src.ranking.features import FEATURE_NAMES, candidate_features
from src.semantic.dataset import catalog_fingerprint, load_catalog, read_jsonl

OUTPUT_DIR = INDEXES_DIR / "ltr"


def search_features(engine, query):
    """The served pipeline up to the final ordering, returning features."""
    query = query.strip()
    corrected, _ = engine.spelling.correct(query)
    variations = engine.spelling.alternatives(query)
    candidate_ids, match_sources, signals = engine.find_candidates_detailed(variations, query)
    if not candidate_ids:
        return [], np.zeros((0, len(FEATURE_NAMES)), dtype="float32")
    ranking = engine.rank_candidates_detailed(corrected, candidate_ids)
    context = {"query": query, "corrected": corrected, "variations": variations}
    return candidate_features(context, ranking, signals, match_sources, engine.by_id)


def build_split(engine, rows, label):
    """Feature rows for every query in a split, with grades and grouping keys."""
    matrices, labels, query_index, ids = [], [], [], []
    queries = []
    start = time.time()
    for number, row in enumerate(rows):
        candidate_ids, matrix = search_features(engine, row["query"])
        grades = row["grades"]
        matrices.append(matrix)
        labels.extend(grades.get(product_id, 0) for product_id in candidate_ids)
        query_index.extend([number] * len(candidate_ids))
        ids.extend(candidate_ids)
        queries.append({"queryId": row["query_id"], "query": row["query"], "kind": row["kind"],
                        "family": row["query_family"], "grades": grades,
                        "relevant": row["relevant_doc_ids"], "candidates": len(candidate_ids)})
        if (number + 1) % 50 == 0 or number + 1 == len(rows):
            rate = (time.time() - start) / (number + 1)
            print(f"  {label}: {number + 1}/{len(rows)} queries ({rate:.2f}s each)", flush=True)
    return {"X": np.concatenate(matrices) if matrices else np.zeros((0, len(FEATURE_NAMES))),
            "y": np.asarray(labels, dtype="int32"), "query": np.asarray(query_index, dtype="int32"),
            "ids": np.asarray(ids), "queries": queries}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--splits", nargs="+", default=["validation", "test"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--threads", type=int, default=6)
    args = parser.parse_args()

    import torch
    from sentence_transformers import CrossEncoder, SentenceTransformer
    from scripts.evaluate_quality import load_product_vectors, model_path
    from src.evaluation.pipeline import ExactSemanticSearch
    from src.search.product_search import ProductSearch

    torch.set_num_threads(args.threads)
    data_dir = DATASET_DIR / "prepared"
    products = load_catalog(data_dir / "products.json")
    catalog_hash = catalog_fingerprint(products)
    encoder_path = model_path("SEMANTIC_MODEL_PATH", "models/colab-export/esci-minilm-20k")
    reranker_path = model_path("RERANKER_MODEL_PATH", "models/ms-marco-MiniLM-L6-v2")
    encoder = SentenceTransformer(str(encoder_path), local_files_only=True, device="cpu")
    reranker = CrossEncoder(str(reranker_path), local_files_only=True, device="cpu", max_length=256)
    vectors = load_product_vectors(encoder, products, catalog_hash, encoder_path)
    engine = ProductSearch(products, ExactSemanticSearch(products, encoder, vectors), reranker)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for split in args.splits:
        rows = read_jsonl(data_dir / f"{split}.jsonl")[:args.limit]
        print(f"Building {split} features for {len(rows)} queries...", flush=True)
        data = build_split(engine, rows, split)
        suffix = f"-limit{args.limit}" if args.limit else ""
        identity = ranking_cache_identity(products, rows, encoder_path, reranker_path)
        np.savez_compressed(OUTPUT_DIR / f"{split}{suffix}.npz", X=data["X"], y=data["y"], query=data["query"],
                            ids=data["ids"], ranking_identity=json.dumps(identity, sort_keys=True))
        (OUTPUT_DIR / f"{split}{suffix}.json").write_text(json.dumps({
            "catalogSha256": catalog_hash, "features": FEATURE_NAMES, "queries": data["queries"],
            "rankingIdentity": identity,
        }))
        print(f"  saved {len(data['y']):,} candidate rows ({int((data['y'] > 0).sum()):,} relevant)", flush=True)


if __name__ == "__main__":
    main()
