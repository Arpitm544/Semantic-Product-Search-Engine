"""Score every search stage on held-out ESCI queries and save the quality report.

Writes backend/quality/quality_report.json, which /api/quality serves and the
/quality page draws. Run from backend/ after the models are prepared:

    .venv/bin/python scripts/evaluate_quality.py            # full test split
    .venv/bin/python scripts/evaluate_quality.py --limit 50 # quick check

No MongoDB or Atlas access is needed: it reads the prepared catalog and runs
semantic retrieval in memory. Product embeddings are cached under
backend/indexes/quality/ and rebuilt when the catalog or encoder changes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import DATASET_DIR, INDEXES_DIR, PROJECT_ROOT
from src.evaluation.pipeline import (
    ExactSemanticSearch, build_engines, build_report, encode_products, evaluate,
)
from src.semantic.dataset import catalog_fingerprint, load_catalog, read_jsonl
from src.search.ranking import PipelineParams, configured_pipeline_params
from src.search.relevance import configured_reranker_path, load_reranker

REPORT_PATH = PROJECT_ROOT / "quality" / "quality_report.json"


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=DATASET_DIR / "prepared")
    parser.add_argument("--split", choices=("validation", "test"), default="test")
    parser.add_argument("--limit", type=int, default=None, help="Evaluate only the first N queries.")
    parser.add_argument("--threads", type=int, default=2,
                        help="Torch CPU threads; the production server uses 2.")
    parser.add_argument("--params", type=Path, default=None,
                        help="Optional JSON file of tuned PipelineParams.")
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    return parser.parse_args()


def model_path(variable, default):
    return (PROJECT_ROOT / os.environ.get(variable, default)).resolve()


def weights_signature(directory):
    """Identify a model by its weight files so cached vectors follow retraining."""
    digest = hashlib.sha256(str(directory).encode())
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix in {".safetensors", ".bin", ".json"}:
            stat = path.stat()
            digest.update(f"{path.relative_to(directory)}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    return digest.hexdigest()[:16]


def load_product_vectors(encoder, products, catalog_hash, encoder_path):
    """Reuse cached embeddings when catalog and encoder are unchanged."""
    import numpy as np

    key = f"{catalog_hash[:16]}-{weights_signature(encoder_path)}"
    cache = INDEXES_DIR / "quality" / f"product_vectors-{key}.npy"
    if cache.exists():
        vectors = np.load(cache)
        if vectors.shape[0] == len(products):
            print(f"Using cached product embeddings: {cache.name}", flush=True)
            return vectors
    print(f"Embedding {len(products):,} products (cached for next time)...", flush=True)
    vectors = encode_products(encoder, products)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache, vectors)
    return vectors


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def main():
    args = parse_arguments()
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(args.threads)
    products = load_catalog(args.data_dir / "products.json")
    manifest = json.loads((args.data_dir / "manifest.json").read_text())
    catalog_hash = catalog_fingerprint(products)
    if manifest["catalog_sha256"] != catalog_hash:
        sys.exit("The catalog changed since the evaluation split was prepared.")
    queries = read_jsonl(args.data_dir / f"{args.split}.jsonl")[:args.limit]
    if not queries:
        sys.exit("The evaluation split is empty.")

    encoder_path = model_path("SEMANTIC_MODEL_PATH", "models/colab-export/esci-minilm-20k")
    reranker_path = (PROJECT_ROOT / configured_reranker_path()).resolve()
    # Same loading options as api/ranking_service.py, so latency matches serving.
    encoder = SentenceTransformer(str(encoder_path), local_files_only=True, device="cpu")
    reranker = load_reranker(reranker_path)

    params = PipelineParams.load(args.params) if args.params else configured_pipeline_params()
    vectors = load_product_vectors(encoder, products, catalog_hash, encoder_path)
    semantic = ExactSemanticSearch(products, encoder, vectors, model_name=encoder_path.name)
    engine, keyword_engine = build_engines(products, semantic, reranker, params=params)

    def progress(done, total):
        if done == total or done % 50 == 0:
            print(f"  {done}/{total} queries", flush=True)

    print(f"Evaluating {len(queries)} {args.split} queries across 5 stages...", flush=True)
    per_query, latencies = evaluate(engine, keyword_engine, queries, progress)
    report = build_report(per_query, latencies, engine.by_id, {
        "split": args.split,
        "dataset": "Amazon ESCI (Shopping Queries Dataset), English",
        "datasetUrl": manifest.get("source_repository"),
        "judgments": "Exact 3 · Substitute 2 · Complement 1 · Irrelevant 0; unjudged results count as 0",
        "catalogProducts": len(products),
        "catalogSha256": catalog_hash,
        "models": {"encoder": encoder_path.name, "reranker": reranker_path.name},
        "environment": {
            "device": "cpu",
            "threads": args.threads,
            "machine": platform.machine(),
            "semanticBackend": "Exact in-memory cosine search (production uses Atlas Vector Search)",
        },
        "commit": git_commit(),
        "partial": args.limit is not None,
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")

    for stage in report["stages"]:
        overall = stage["metrics"]["all"]
        print(f"{stage['label']:24} NDCG@10={overall['ndcg@10']:.3f} MRR@10={overall['mrr@10']:.3f} "
              f"Recall@10={overall['recall@10']:.3f} p50={stage['latencyMs']['p50']:.0f}ms "
              f"p95={stage['latencyMs']['p95']:.0f}ms")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
