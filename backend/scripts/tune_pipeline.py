"""Bayesian hyperparameter tuning of the search pipeline with Optuna.

1. Precomputes validation BM25/semantic top-K lists and cross-encoder scores once
   (4 CPU threads by default) and caches them under backend/indexes/tuning/.
2. Runs multi-objective Optuna (maximize validation NDCG@10, minimize estimated
   search latency) on the 1,000-query validation split.
3. Selects validation-only Pareto points (`best_balanced` and `best_quality`),
   then evaluates baseline vs tuned configs once on the untouched test split at
   --eval-threads 2 (matching production serving).
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import pickle
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.evaluate_quality import load_product_vectors, model_path, weights_signature
from src.config import DATASET_DIR, INDEXES_DIR, PROJECT_ROOT
from src.evaluation.inference import bootstrap, intervals, paired_p_values
from src.evaluation.metrics import METRIC_NAMES, mean_metrics, percentile
from src.evaluation.pipeline import ExactSemanticSearch, build_engines, evaluate, summarize
from src.evaluation.tuning import (
    LazyScoreStore,
    evaluate_cached,
    precompute_validation_data,
)
from src.search.ranking import PipelineParams
from src.search.relevance import configured_reranker_path, load_reranker
from src.semantic.dataset import catalog_fingerprint, load_catalog, read_jsonl

BASELINE_PARAMS = PipelineParams()
ANCHOR_BASELINE_TRIAL = {
    "bm25_k": 50,
    "semantic_k": 50,
    "hybrid_rrf_k": 60,
    "semantic_weight": 1.0,
    "variation_limit": 50,
    "variation_rrf_k": 60,
    "original_variation_weight": 1.0,
    "corrected_variation_weight": 1.0,
    "alt_variation_weight": 1.0,
    "rerank_k": 70,
    "blend_rrf_k": 60,
    "reranker_weight": 0.75,
}


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATASET_DIR / "prepared")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports/tuning")
    parser.add_argument("--cache-dir", type=Path, default=INDEXES_DIR / "tuning")
    parser.add_argument("--trials", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--precompute-threads", type=int, default=4)
    parser.add_argument("--eval-threads", type=int, default=2)
    parser.add_argument("--max-stage-k", type=int, default=100)
    parser.add_argument("--max-rerank-precompute", type=int, default=90)
    parser.add_argument("--val-limit", type=int, default=None)
    parser.add_argument("--test-limit", type=int, default=None)
    return parser.parse_args()


def validation_cache_key(catalog_hash, encoder_path, reranker_path, queries, max_stage_k, max_rerank_precompute):
    query_hash = sha256(json.dumps(queries, sort_keys=True).encode()).hexdigest()
    return (f"v2-{catalog_hash[:12]}-{weights_signature(encoder_path)}-{weights_signature(reranker_path)}-"
            f"{query_hash}-k{max_stage_k}-r{max_rerank_precompute}")


def load_or_build_validation_cache(
    cache_path,
    products,
    semantic,
    reranker,
    val_queries,
    max_stage_k,
    max_rerank_precompute,
):
    if cache_path.is_file():
        print(f"Loading validation cache: {cache_path.name}", flush=True)
        with cache_path.open("rb") as handle:
            data = pickle.load(handle)
        if len(data["queries"]) == len(val_queries):
            return data

    print(f"Precomputing validation cache for {len(val_queries)} queries...", flush=True)
    t0 = time.perf_counter()

    def progress(phase, done, total):
        print(f"  precompute [{phase}] {done}/{total}", flush=True)

    data = precompute_validation_data(
        products,
        semantic,
        reranker,
        val_queries,
        max_stage_k=max_stage_k,
        max_rerank_precompute=max_rerank_precompute,
        progress=progress,
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("wb") as handle:
        pickle.dump(data, handle)
    print(f"Validation cache built in {time.perf_counter() - t0:.1f}s", flush=True)
    return data


def calibrate_latency_model(products, semantic, reranker, val_queries, eval_threads):
    """Measure hybrid retrieval and linear per-candidate reranker latency at eval_threads."""
    import torch

    torch.set_num_threads(eval_threads)
    sample = val_queries[:30]
    engine, _ = build_engines(products, semantic, reranker)

    hybrid_times = []
    candidate_pools = []
    for row in sample:
        t0 = time.perf_counter()
        variations = engine.spelling.alternatives(row["query"])
        candidates, _ = engine.find_candidates(variations, row["query"])
        hybrid_times.append((time.perf_counter() - t0) * 1000)
        corrected, _ = engine.spelling.correct(row["query"])
        candidate_pools.append((corrected, candidates))

    xs, ys = [], []
    for k in (15, 30, 50, 70):
        for corrected, candidates in candidate_pools[:15]:
            subset = candidates[:k]
            if not subset:
                continue
            t0 = time.perf_counter()
            engine.rank_candidates(corrected, subset)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            xs.append(len(subset))
            ys.append(elapsed_ms)

    slope, intercept = np.polyfit(np.asarray(xs, dtype=float), np.asarray(ys, dtype=float), 1)
    warm_hybrid = hybrid_times[2:] if len(hybrid_times) > 4 else hybrid_times
    model = {
        "hybrid_mean_ms": float(np.mean(warm_hybrid)),
        "rerank_intercept_ms": float(max(0.0, intercept)),
        "rerank_per_candidate_ms": float(max(0.1, slope)),
    }
    print(
        f"Calibrated latency (@{eval_threads} threads): hybrid={model['hybrid_mean_ms']:.1f}ms, "
        f"rerank={model['rerank_intercept_ms']:.1f}ms + {model['rerank_per_candidate_ms']:.2f}ms/cand",
        flush=True,
    )
    return model


def params_from_trial(trial, max_stage_k):
    reranker_weight = trial.suggest_float("reranker_weight", 0.10, 0.95, step=0.05)
    return PipelineParams(
        bm25_k=trial.suggest_int("bm25_k", 15, max_stage_k, step=5),
        semantic_k=trial.suggest_int("semantic_k", 15, max_stage_k, step=5),
        hybrid_rrf_k=trial.suggest_int("hybrid_rrf_k", 5, 100, step=5),
        keyword_weight=1.0,
        semantic_weight=trial.suggest_float("semantic_weight", 0.25, 2.50, step=0.05),
        variation_limit=trial.suggest_int("variation_limit", 15, min(80, max_stage_k), step=5),
        variation_rrf_k=trial.suggest_int("variation_rrf_k", 5, 100, step=5),
        original_variation_weight=trial.suggest_float("original_variation_weight", 0.50, 2.00, step=0.05),
        corrected_variation_weight=trial.suggest_float("corrected_variation_weight", 0.20, 2.00, step=0.05),
        alt_variation_weight=trial.suggest_float("alt_variation_weight", 0.00, 1.50, step=0.05),
        rerank_k=trial.suggest_int("rerank_k", 15, 75, step=5),
        blend_rrf_k=trial.suggest_int("blend_rrf_k", 5, 100, step=5),
        retrieval_weight=round(1.0 - reranker_weight, 4),
        reranker_weight=round(reranker_weight, 4),
    )


def select_validation_winners(pareto_trials, baseline_ndcg):
    """Choose best_quality and best_balanced strictly from validation Pareto trials."""
    best_quality = max(pareto_trials, key=lambda t: t.values[0])

    qualifying = [t for t in pareto_trials if t.values[0] >= baseline_ndcg]
    pool = qualifying if qualifying else pareto_trials
    min_q = min(t.values[0] for t in pool)
    max_q = max(t.values[0] for t in pool)
    min_ms = min(t.values[1] for t in pool)
    max_ms = max(t.values[1] for t in pool)

    def knee_distance(trial):
        norm_q = (trial.values[0] - min_q) / (max_q - min_q) if max_q > min_q else 1.0
        norm_ms = (trial.values[1] - min_ms) / (max_ms - min_ms) if max_ms > min_ms else 0.0
        return ((1.0 - norm_q) ** 2 + norm_ms ** 2) ** 0.5

    best_balanced = min(pool, key=knee_distance)
    return best_balanced, best_quality


def compare_test_runs(baseline_rows, tuned_rows):
    """Family-clustered bootstrap CI & paired randomization test on reranked metrics."""
    rng = np.random.default_rng(42)
    families_by_id = {
        family: i for i, family in enumerate(dict.fromkeys(r["family"] for r in baseline_rows))
    }
    families = np.array([families_by_id[r["family"]] for r in baseline_rows], dtype=int)
    counts = np.bincount(families)
    if len(counts) < 2:
        return {}

    base_scores = np.array([[r["stages"]["reranked"][m] for m in METRIC_NAMES] for r in baseline_rows])
    tuned_scores = np.array([[r["stages"]["reranked"][m] for m in METRIC_NAMES] for r in tuned_rows])

    base_sums = np.zeros((len(counts), len(METRIC_NAMES)))
    tuned_sums = np.zeros((len(counts), len(METRIC_NAMES)))
    np.add.at(base_sums, families, base_scores)
    np.add.at(tuned_sums, families, tuned_scores)

    diffs = tuned_sums - base_sums
    difference_samples, _ = bootstrap(diffs, counts, rng)
    deltas = diffs.sum(axis=0) / len(baseline_rows)
    bounds = intervals(difference_samples).tolist()
    p_vals = paired_p_values(diffs, rng)
    return {
        metric: {"delta": float(delta), "confidenceInterval": ci, "pValue": float(p)}
        for metric, delta, ci, p in zip(METRIC_NAMES, deltas, bounds, p_vals)
    }


def evaluate_on_test(label, params, products, semantic, reranker, test_queries):
    engine, keyword_engine = build_engines(products, semantic, reranker, params=params)

    def progress(done, total):
        if done == total or done % 200 == 0:
            print(f"  [{label}] {done}/{total} test queries", flush=True)

    per_query, latencies = evaluate(engine, keyword_engine, test_queries, progress)
    stages = {stage["id"]: stage for stage in summarize(per_query, latencies)}
    return per_query, latencies, stages["reranked"], stages["hybrid"]


def save_pareto_plot(trials, pareto_trials, baseline_val, balanced_trial, quality_trial, output_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    xs = [t.values[1] for t in trials if t.values is not None]
    ys = [t.values[0] for t in trials if t.values is not None]
    ax.scatter(xs, ys, s=26, alpha=0.45, color="#64748b", label="Optuna trials (validation)")

    pareto_sorted = sorted(pareto_trials, key=lambda t: t.values[1])
    ax.plot(
        [t.values[1] for t in pareto_sorted],
        [t.values[0] for t in pareto_sorted],
        color="#2563eb",
        linewidth=2.0,
        marker="o",
        markersize=5,
        label="Pareto frontier",
    )
    ax.scatter(
        [baseline_val["estimated_search_ms"]],
        [baseline_val["reranked"]["ndcg@10"]],
        color="#dc2626",
        marker="X",
        s=110,
        zorder=5,
        label="Baseline (uncapped)",
    )
    ax.scatter(
        [balanced_trial.values[1]],
        [balanced_trial.values[0]],
        color="#16a34a",
        marker="*",
        s=180,
        zorder=6,
        label=f"Selected Balanced (rerank_k={balanced_trial.params['rerank_k']})",
    )
    ax.scatter(
        [quality_trial.values[1]],
        [quality_trial.values[0]],
        color="#9333ea",
        marker="D",
        s=75,
        zorder=6,
        label=f"Best Quality (rerank_k={quality_trial.params['rerank_k']})",
    )
    ax.set_title("Validation Split: Quality (NDCG@10) vs Estimated Search Latency", fontweight="bold")
    ax.set_xlabel("Estimated Mean Search Latency (ms @ 2 threads)")
    ax.set_ylabel("Validation NDCG@10")
    ax.grid(True, linestyle=":", alpha=0.55)
    ax.legend(frameon=True, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main():
    import optuna

    args = parse_arguments()
    import torch
    from sentence_transformers import SentenceTransformer

    products = load_catalog(args.data_dir / "products.json")
    manifest = json.loads((args.data_dir / "manifest.json").read_text())
    catalog_hash = catalog_fingerprint(products)
    if manifest["catalog_sha256"] != catalog_hash:
        sys.exit("Catalog hash mismatch.")

    val_queries = read_jsonl(args.data_dir / "validation.jsonl")[:args.val_limit]
    test_queries = read_jsonl(args.data_dir / "test.jsonl")[:args.test_limit]

    encoder_path = model_path("SEMANTIC_MODEL_PATH", "models/colab-export/esci-minilm-20k")
    reranker_path = (PROJECT_ROOT / configured_reranker_path()).resolve()

    torch.set_num_threads(args.precompute_threads)
    encoder = SentenceTransformer(str(encoder_path), local_files_only=True, device="cpu")
    reranker = load_reranker(reranker_path)
    vectors = load_product_vectors(encoder, products, catalog_hash, encoder_path)
    semantic = ExactSemanticSearch(products, encoder, vectors, model_name=encoder_path.name)

    cache_key = validation_cache_key(catalog_hash, encoder_path, reranker_path, val_queries,
                                     args.max_stage_k, args.max_rerank_precompute)
    cache_path = args.cache_dir / f"val_cache-{cache_key}.pkl"
    cache_data = load_or_build_validation_cache(
        cache_path,
        products,
        semantic,
        reranker,
        val_queries,
        args.max_stage_k,
        args.max_rerank_precompute,
    )

    latency_model = calibrate_latency_model(products, semantic, reranker, val_queries, args.eval_threads)

    by_id = {p["id"]: p for p in products}
    score_store = LazyScoreStore(by_id, reranker, cache_data["reranker_scores"])

    baseline_val = evaluate_cached(cache_data, score_store, BASELINE_PARAMS, latency_model)
    print(
        f"\nValidation Baseline: NDCG@10={baseline_val['reranked']['ndcg@10']:.4f} | "
        f"MRR@10={baseline_val['reranked']['mrr@10']:.4f} | "
        f"mean_cands={baseline_val['mean_rerank_candidates']:.1f} | "
        f"est_ms={baseline_val['estimated_search_ms']:.1f}ms",
        flush=True,
    )

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        directions=["maximize", "minimize"],
        sampler=optuna.samplers.TPESampler(seed=args.seed),
    )
    study.enqueue_trial(ANCHOR_BASELINE_TRIAL)
    study.enqueue_trial({**ANCHOR_BASELINE_TRIAL, "rerank_k": 30, "bm25_k": 35, "semantic_k": 35})
    study.enqueue_trial({**ANCHOR_BASELINE_TRIAL, "rerank_k": 50})

    def objective(trial):
        params = params_from_trial(trial, args.max_stage_k)
        summary = evaluate_cached(cache_data, score_store, params, latency_model)
        trial.set_user_attr("params", params.to_dict())
        trial.set_user_attr("mrr@10", summary["reranked"]["mrr@10"])
        trial.set_user_attr("recall@10", summary["reranked"]["recall@10"])
        trial.set_user_attr("mean_rerank_candidates", summary["mean_rerank_candidates"])
        return summary["reranked"]["ndcg@10"], summary["estimated_search_ms"]

    print(f"\nRunning Optuna ({args.trials} trials on {len(val_queries)} validation queries)...", flush=True)
    t_opt = time.perf_counter()
    study.optimize(objective, n_trials=args.trials, n_jobs=1)
    print(
        f"Optuna finished in {time.perf_counter() - t_opt:.1f}s "
        f"(on-demand rerank fills: {score_store.on_demand_predictions})",
        flush=True,
    )

    if score_store.on_demand_predictions > 0:
        with cache_path.open("wb") as handle:
            pickle.dump(cache_data, handle)

    pareto_trials = study.best_trials
    balanced_trial, quality_trial = select_validation_winners(
        pareto_trials, baseline_val["reranked"]["ndcg@10"],
    )
    balanced_params = PipelineParams.from_dict(balanced_trial.user_attrs["params"])
    quality_params = PipelineParams.from_dict(quality_trial.user_attrs["params"])

    print(
        f"Validation Best Balanced: NDCG@10={balanced_trial.values[0]:.4f} | "
        f"est_ms={balanced_trial.values[1]:.1f}ms | rerank_k={balanced_params.rerank_k}",
        flush=True,
    )
    print(
        f"Validation Best Quality : NDCG@10={quality_trial.values[0]:.4f} | "
        f"est_ms={quality_trial.values[1]:.1f}ms | rerank_k={quality_params.rerank_k}",
        flush=True,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "best_params_balanced.json").write_text(
        json.dumps(balanced_params.to_dict(), indent=2) + "\n",
    )
    (args.output_dir / "best_params_quality.json").write_text(
        json.dumps(quality_params.to_dict(), indent=2) + "\n",
    )
    save_pareto_plot(
        study.trials, pareto_trials, baseline_val, balanced_trial, quality_trial,
        args.output_dir / "tuning_pareto.png",
    )

    # Final evaluation on the untouched test split at --eval-threads (2).
    torch.set_num_threads(args.eval_threads)
    print(f"\nEvaluating on untouched test split ({len(test_queries)} queries, threads={args.eval_threads})...", flush=True)
    base_rows, _, base_reranked, base_hybrid = evaluate_on_test(
        "baseline", BASELINE_PARAMS, products, semantic, reranker, test_queries,
    )
    bal_rows, _, bal_reranked, bal_hybrid = evaluate_on_test(
        "best_balanced", balanced_params, products, semantic, reranker, test_queries,
    )
    if quality_params == balanced_params:
        qual_rows, qual_reranked, qual_hybrid = bal_rows, bal_reranked, bal_hybrid
    else:
        qual_rows, _, qual_reranked, qual_hybrid = evaluate_on_test(
            "best_quality", quality_params, products, semantic, reranker, test_queries,
        )

    report = {
        "validationCount": len(val_queries),
        "testCount": len(test_queries),
        "trials": args.trials,
        "seed": args.seed,
        "precomputeThreads": args.precompute_threads,
        "evalThreads": args.eval_threads,
        "models": {"encoder": encoder_path.name, "reranker": reranker_path.name},
        "latencyCalibration": latency_model,
        "validation": {
            "baseline": baseline_val,
            "bestBalanced": {
                "params": balanced_params.to_dict(),
                "ndcg@10": balanced_trial.values[0],
                "mrr@10": balanced_trial.user_attrs["mrr@10"],
                "recall@10": balanced_trial.user_attrs["recall@10"],
                "mean_rerank_candidates": balanced_trial.user_attrs["mean_rerank_candidates"],
                "estimated_search_ms": balanced_trial.values[1],
            },
            "bestQuality": {
                "params": quality_params.to_dict(),
                "ndcg@10": quality_trial.values[0],
                "mrr@10": quality_trial.user_attrs["mrr@10"],
                "recall@10": quality_trial.user_attrs["recall@10"],
                "mean_rerank_candidates": quality_trial.user_attrs["mean_rerank_candidates"],
                "estimated_search_ms": quality_trial.values[1],
            },
            "paretoFrontier": [
                {
                    "trial": t.number,
                    "ndcg@10": t.values[0],
                    "estimated_search_ms": t.values[1],
                    "mean_rerank_candidates": t.user_attrs["mean_rerank_candidates"],
                    "rerank_k": t.params["rerank_k"],
                }
                for t in sorted(pareto_trials, key=lambda tr: tr.values[1])
            ],
        },
        "test": {
            "baseline": {"hybrid": base_hybrid, "reranked": base_reranked, "params": BASELINE_PARAMS.to_dict()},
            "bestBalanced": {
                "hybrid": bal_hybrid,
                "reranked": bal_reranked,
                "params": balanced_params.to_dict(),
                "vsBaseline": compare_test_runs(base_rows, bal_rows),
            },
            "bestQuality": {
                "hybrid": qual_hybrid,
                "reranked": qual_reranked,
                "params": quality_params.to_dict(),
                "vsBaseline": compare_test_runs(base_rows, qual_rows),
            },
        },
    }
    report_path = args.output_dir / "tuning_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")

    print("\n=== Untouched Test Split Results ===")
    for name, st in (("baseline", base_reranked), ("best_balanced", bal_reranked), ("best_quality", qual_reranked)):
        m = st["metrics"]["all"]
        l = st["latencyMs"]
        print(
            f"{name:15} NDCG@10={m['ndcg@10']:.4f}  MRR@10={m['mrr@10']:.4f}  "
            f"Recall@10={m['recall@10']:.4f}  Hit@5={m['hit@5']:.4f}  "
            f"p50={l['p50']:.1f}ms  p95={l['p95']:.1f}ms  mean={l['mean']:.1f}ms"
        )
    print(f"\nSaved report: {report_path}")


if __name__ == "__main__":
    main()
