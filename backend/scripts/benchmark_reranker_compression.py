"""Benchmark PyTorch FP32, ONNX FP32/INT8, and distilled rerankers; plot NDCG@10 vs p95 latency."""

import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.evaluate_quality import load_product_vectors, model_path
from src.config import DATASET_DIR, PROJECT_ROOT
from src.evaluation.metrics import mean_metrics, percentile, query_metrics
from src.evaluation.pipeline import ExactSemanticSearch, StageRunner, build_engines
from src.search.onnx_reranker import load_onnx_reranker
from src.search.relevance import load_reranker
from src.semantic.dataset import catalog_fingerprint, load_catalog, read_jsonl


def compute_pareto_frontier(points):
    """Return subset of points not dominated on (p95_ms lower, ndcg10 higher)."""
    ordered = sorted(points, key=lambda p: (p["search_p95_ms"], -p["ndcg@10"]))
    frontier = []
    best_ndcg = -1.0
    for point in ordered:
        if point["ndcg@10"] > best_ndcg:
            frontier.append(point)
            best_ndcg = point["ndcg@10"]
    return frontier


def pick_best_point(points, teacher_ndcg):
    """Pick the Pareto-optimal knee point balancing NDCG@10 retention and p95 speedup."""
    pareto = compute_pareto_frontier(points)
    candidates = [p for p in pareto if p["name"] != "hybrid (no reranker)"]
    if not candidates:
        return pareto[-1]
    min_lat = min(p["search_p95_ms"] for p in candidates)
    max_lat = max(p["search_p95_ms"] for p in candidates)
    min_q = min(p["ndcg@10"] for p in candidates)
    max_q = max(p["ndcg@10"] for p in candidates)

    def utopia_distance(point):
        norm_lat = (point["search_p95_ms"] - min_lat) / max(max_lat - min_lat, 1e-9)
        norm_q_loss = (max_q - point["ndcg@10"]) / max(max_q - min_q, 1e-9)
        # Slightly weight quality retention (1.2x) alongside latency reduction.
        return (norm_lat ** 2 + (1.2 * norm_q_loss) ** 2) ** 0.5

    # Prefer points retaining >= 97% of teacher NDCG@10 if available.
    retained = [p for p in candidates if p["ndcg@10"] >= 0.97 * teacher_ndcg]
    pool = retained if retained else candidates
    return min(pool, key=utopia_distance)


def benchmark_variant(name, family, runtime, size_mb, reranker, products, semantic, queries, warmup=3):
    engine, _ = build_engines(products, semantic, reranker)
    for row in queries[:warmup]:
        q = row["query"].strip()
        corrected, _ = engine.spelling.correct(q)
        variations = engine.spelling.alternatives(q)
        cands, _ = engine.find_candidates(variations, q)
        if cands:
            engine.rank_candidates(corrected, cands)

    rows_metrics = []
    hybrid_times, rerank_times, total_times = [], [], []
    for index, row in enumerate(queries, 1):
        q = row["query"].strip()
        t0 = time.perf_counter()
        corrected, _ = engine.spelling.correct(q)
        variations = engine.spelling.alternatives(q)
        candidates, _ = engine.find_candidates(variations, q)
        hybrid_ms = (time.perf_counter() - t0) * 1000

        if candidates:
            t1 = time.perf_counter()
            ranked, _ = engine.rank_candidates(corrected, candidates)
            rerank_ms = (time.perf_counter() - t1) * 1000
        else:
            ranked, rerank_ms = [], 0.0

        grades = row.get("grades") or {pid: 1 for pid in row["relevant_doc_ids"]}
        rows_metrics.append(query_metrics(ranked[:10], grades, row["relevant_doc_ids"]))
        hybrid_times.append(hybrid_ms)
        rerank_times.append(rerank_ms)
        total_times.append(hybrid_ms + rerank_ms)
        if index % 50 == 0 or index == len(queries):
            print(f"  [{name}] {index}/{len(queries)}", flush=True)

    summary = mean_metrics(rows_metrics)
    return {
        "name": name,
        "family": family,
        "runtime": runtime,
        "size_mb": round(size_mb, 2),
        "queries": len(queries),
        "ndcg@10": summary["ndcg@10"],
        "mrr@10": summary["mrr@10"],
        "recall@10": summary["recall@10"],
        "hit@5": summary["hit@5"],
        "hybrid_p50_ms": percentile(hybrid_times, 0.50),
        "hybrid_p95_ms": percentile(hybrid_times, 0.95),
        "rerank_p50_ms": percentile(rerank_times, 0.50),
        "rerank_p95_ms": percentile(rerank_times, 0.95),
        "search_p50_ms": percentile(total_times, 0.50),
        "search_p95_ms": percentile(total_times, 0.95),
        "search_mean_ms": sum(total_times) / len(total_times),
    }


def benchmark_hybrid_only(products, semantic, queries):
    engine, _ = build_engines(products, semantic, None)
    rows_metrics, hybrid_times = [], []
    for row in queries:
        q = row["query"].strip()
        t0 = time.perf_counter()
        variations = engine.spelling.alternatives(q)
        candidates, _ = engine.find_candidates(variations, q)
        hybrid_ms = (time.perf_counter() - t0) * 1000
        grades = row.get("grades") or {pid: 1 for pid in row["relevant_doc_ids"]}
        rows_metrics.append(query_metrics(candidates[:10], grades, row["relevant_doc_ids"]))
        hybrid_times.append(hybrid_ms)
    summary = mean_metrics(rows_metrics)
    return {
        "name": "hybrid (no reranker)",
        "family": "hybrid",
        "runtime": "retrieval-only",
        "size_mb": 0.0,
        "queries": len(queries),
        "ndcg@10": summary["ndcg@10"],
        "mrr@10": summary["mrr@10"],
        "recall@10": summary["recall@10"],
        "hit@5": summary["hit@5"],
        "hybrid_p50_ms": percentile(hybrid_times, 0.50),
        "hybrid_p95_ms": percentile(hybrid_times, 0.95),
        "rerank_p50_ms": 0.0,
        "rerank_p95_ms": 0.0,
        "search_p50_ms": percentile(hybrid_times, 0.50),
        "search_p95_ms": percentile(hybrid_times, 0.95),
        "search_mean_ms": sum(hybrid_times) / len(hybrid_times),
    }


def save_tradeoff_plot(results, pareto, best_point, output_path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 6.2), layout="constrained")

    runtime_styles = {
        "retrieval-only": ("x", "#6b7280", 90),
        "pytorch-fp32": ("o", "#2563eb", 95),
        "onnx-fp32": ("D", "#d97706", 85),
        "onnx-int8": ("s", "#059669", 95),
    }
    label_offsets = {
        "hybrid (no reranker)": (10, 4, "left"),
        "tinybert-l2 (pt-fp32)": (-8, 12, "right"),
        "tinybert-l2 (onnx-int8)": (10, -10, "left"),
        "tinybert-l2 (onnx-fp32)": (10, 4, "left"),
        "minilm-l2 (pt-fp32)": (10, 2, "left"),
        "minilm-l2 (onnx-int8)": (-8, 12, "right"),
        "minilm-l4 (pt-fp32)": (-10, -14, "right"),
        "minilm-l4 (onnx-int8)": (10, -8, "left"),
        "teacher-l6 (pt-fp32)": (10, 10, "left"),
        "teacher-l6 (onnx-int8)": (10, -6, "left"),
        "teacher-l6 (onnx-fp32)": (-10, -12, "right"),
    }

    # Left panel: Log-latency x-axis spreads 60ms..4100ms cleanly without crowding.
    ax1.set_xscale("log")
    for r in results:
        marker, color, size = runtime_styles.get(r["runtime"], ("o", "#333333", 80))
        is_best = r["name"] == best_point["name"]
        scatter_kwargs = {
            "marker": marker,
            "s": size * (1.8 if is_best else 1.0),
            "color": color,
            "zorder": 5 if is_best else 3,
        }
        if marker != "x":
            scatter_kwargs["edgecolor"] = "#111827" if is_best else "white"
            scatter_kwargs["linewidth"] = 2.0 if is_best else 0.8
        ax1.scatter(r["search_p95_ms"], r["ndcg@10"], **scatter_kwargs)

        dx, dy, ha = label_offsets.get(r["name"], (10, 4, "left"))
        label = r["name"] + (" ★" if is_best else "")
        ax1.annotate(
            label,
            (r["search_p95_ms"], r["ndcg@10"]),
            xytext=(dx, dy),
            textcoords="offset points",
            ha=ha,
            fontsize=8.3,
            fontweight="bold" if is_best else "normal",
            color="#111827",
            arrowprops={"arrowstyle": "-", "color": "#9ca3af", "lw": 0.7, "shrinkA": 0, "shrinkB": 4},
        )

    pareto_sorted = sorted(pareto, key=lambda p: p["search_p95_ms"])
    ax1.plot(
        [p["search_p95_ms"] for p in pareto_sorted],
        [p["ndcg@10"] for p in pareto_sorted],
        "--", color="#10b981", linewidth=1.6, alpha=0.85, label="Pareto frontier", zorder=2,
    )

    for rt, label in [
        ("pytorch-fp32", "PyTorch FP32"),
        ("onnx-fp32", "ONNX FP32"),
        ("onnx-int8", "ONNX INT8"),
        ("retrieval-only", "Hybrid only"),
    ]:
        m, c, _ = runtime_styles[rt]
        ax1.scatter([], [], marker=m, color=c, s=75, label=label)

    ticks = [60, 125, 250, 500, 1000, 2000, 4000]
    ax1.set_xticks(ticks)
    ax1.set_xticklabels([str(t) for t in ticks])
    ax1.set_xlim(45, 5600)
    ax1.set_ylim(0.504, 0.545)
    ax1.set_title("Quality vs. End-to-End Search Latency (p95, log scale)", fontsize=11.5, fontweight="bold")
    ax1.set_xlabel("End-to-End Search p95 Latency (ms, log scale)", fontsize=10.5)
    ax1.set_ylabel("NDCG@10", fontsize=10.5)
    ax1.grid(True, which="major", linestyle=":", alpha=0.55)
    ax1.legend(loc="lower right", fontsize=8.5)

    # Right panel: Reranker-only p95 vs Model Size & NDCG@10 bar comparison
    rerankers = [r for r in results if r["runtime"] != "retrieval-only"]
    rerankers_sorted = sorted(rerankers, key=lambda r: r["rerank_p95_ms"])
    y_pos = list(range(len(rerankers_sorted)))
    colors = [
        "#1d4ed8" if r["name"] == best_point["name"] else runtime_styles[r["runtime"]][1]
        for r in rerankers_sorted
    ]
    bars = ax2.barh(y_pos, [r["rerank_p95_ms"] for r in rerankers_sorted], color=colors, alpha=0.88)
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels([f"{r['name']} ({r['size_mb']:.0f}MB)" for r in rerankers_sorted], fontsize=8.5)
    for bar, r in zip(bars, rerankers_sorted):
        star = " ★" if r["name"] == best_point["name"] else ""
        ax2.text(
            bar.get_width() + 35, bar.get_y() + bar.get_height() / 2,
            f"{r['rerank_p95_ms']:.0f}ms · NDCG {r['ndcg@10']:.4f}{star}",
            va="center", fontsize=8.2,
            fontweight="bold" if r["name"] == best_point["name"] else "normal",
        )
    ax2.set_title("Reranker-Only p95 Latency & Quality", fontsize=11.5, fontweight="bold")
    ax2.set_xlabel("Reranker p95 Latency (ms)", fontsize=10.5)
    ax2.set_xlim(0, max(r["rerank_p95_ms"] for r in rerankers_sorted) * 1.42)
    ax2.grid(True, axis="x", linestyle=":", alpha=0.55)

    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATASET_DIR / "prepared")
    parser.add_argument("--distilled-dir", type=Path, default=PROJECT_ROOT / "models/distilled")
    parser.add_argument("--teacher", type=Path, default=PROJECT_ROOT / "models/esci-reranker")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports/compression")
    parser.add_argument("--limit", type=int, default=200, help="Number of test queries (0 for full split).")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--include-student-onnx-fp32", action="store_true")
    args = parser.parse_args()

    import torch

    torch.set_num_threads(args.threads)
    products = load_catalog(args.data_dir / "products.json")
    catalog_hash = catalog_fingerprint(products)
    queries = read_jsonl(args.data_dir / "test.jsonl")
    if args.limit > 0:
        queries = queries[:args.limit]

    encoder_path = model_path("SEMANTIC_MODEL_PATH", "models/colab-export/esci-minilm-20k")
    from sentence_transformers import SentenceTransformer

    encoder = SentenceTransformer(str(encoder_path), local_files_only=True, device="cpu")
    vectors = load_product_vectors(encoder, products, catalog_hash, encoder_path)
    semantic = ExactSemanticSearch(products, encoder, vectors, model_name=encoder_path.name)

    results = []
    print(f"Benchmarking on {len(queries)} ESCI test queries (threads={args.threads})...", flush=True)
    results.append(benchmark_hybrid_only(products, semantic, queries))

    variants = [
        ("teacher-l6 (pt-fp32)", "teacher-l6", "pytorch-fp32", args.teacher, "pytorch"),
        ("teacher-l6 (onnx-fp32)", "teacher-l6", "onnx-fp32", args.distilled_dir / "teacher-onnx", "model.onnx"),
        ("teacher-l6 (onnx-int8)", "teacher-l6", "onnx-int8", args.distilled_dir / "teacher-onnx", "model_int8.onnx"),
    ]
    for student_name in ("minilm-l4", "minilm-l2", "tinybert-l2"):
        sdir = args.distilled_dir / student_name
        if not sdir.is_dir():
            continue
        variants.append((f"{student_name} (pt-fp32)", student_name, "pytorch-fp32", sdir, "pytorch"))
        if (args.include_student_onnx_fp32 or student_name == "tinybert-l2") and (sdir / "model.onnx").is_file():
            variants.append((f"{student_name} (onnx-fp32)", student_name, "onnx-fp32", sdir, "model.onnx"))
        if (sdir / "model_int8.onnx").is_file():
            variants.append((f"{student_name} (onnx-int8)", student_name, "onnx-int8", sdir, "model_int8.onnx"))

    for label, family, runtime, model_dir, mode in variants:
        print(f"\nBenchmarking {label}...", flush=True)
        if mode == "pytorch":
            reranker = load_reranker(model_dir, device="cpu")
            size_mb = (model_dir / "model.safetensors").stat().st_size / 1e6
        else:
            reranker = load_onnx_reranker(model_dir, onnx_filename=mode, threads=args.threads)
            size_mb = (model_dir / mode).stat().st_size / 1e6
        res = benchmark_variant(label, family, runtime, size_mb, reranker, products, semantic, queries)
        results.append(res)
        print(f"  -> NDCG@10={res['ndcg@10']:.4f} | search p95={res['search_p95_ms']:.1f}ms "
              f"(rerank p95={res['rerank_p95_ms']:.1f}ms) | size={res['size_mb']:.1f}MB", flush=True)

    teacher_ndcg = next(r["ndcg@10"] for r in results if r["name"] == "teacher-l6 (pt-fp32)")
    pareto = compute_pareto_frontier(results)
    best_point = pick_best_point(results, teacher_ndcg)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "query_count": len(queries),
        "threads": args.threads,
        "results": results,
        "pareto_frontier": [p["name"] for p in pareto],
        "recommended_point": best_point,
    }
    report_path = args.output_dir / "compression_report.json"
    plot_path = args.output_dir / "quality_vs_latency.png"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    save_tradeoff_plot(results, pareto, best_point, plot_path)

    print("\n=== Summary ===")
    for r in results:
        mark = " <-- BEST" if r["name"] == best_point["name"] else (" [Pareto]" if r in pareto else "")
        print(f"{r['name']:26} NDCG@10={r['ndcg@10']:.4f}  search_p95={r['search_p95_ms']:7.1f}ms  "
              f"rerank_p95={r['rerank_p95_ms']:7.1f}ms  size={r['size_mb']:5.1f}MB{mark}")
    print(f"\nReport: {report_path}\nPlot:   {plot_path}")


if __name__ == "__main__":
    main()
