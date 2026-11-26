"""Where and why search fails: quality by query type and a failure taxonomy.

    .venv/bin/python scripts/error_analysis.py            # validation split
    .venv/bin/python scripts/error_analysis.py --run      # rerun the pipeline first

Analyses the ESCI **validation** split. The test split stays untouched for
final numbers: looking at its failures and then fixing them would make its
results optimistic.

Inputs: the served ranking of every candidate for each validation query.
By default this reuses rankings whose catalog, validation rows and model inputs
match the current run. With --run, or without a matching cache, it runs the
pipeline itself (about 30 minutes on CPU) and caches the result in
backend/indexes/errors/.

Outputs:
- backend/quality/error_analysis.json   every number and example
- docs/images/error-analysis/*.png      the figures used in docs/error-analysis.md
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
import re
import subprocess
import sys
from zipfile import BadZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np

from src.config import DATASET_DIR, INDEXES_DIR, PROJECT_ROOT
from src.evaluation.cache_identity import ranking_cache_identity
from src.evaluation.metrics import METRIC_NAMES, query_metrics
from src.keyword_search.bm25 import tokenize
from src.search.query_filters import ACCESSORY_WORDS, BrandIndex, normalize_brand, parse_color
from src.search.typos import STOP_WORDS

SEED = 7
BOOTSTRAP = 5_000
TOP = 5                       # a search "fails" when no Exact product is in the top 5
# The prepared ESCI files list only Exact products as "relevant" (Hit@5, MRR and
# Recall everywhere in this project count Exact matches only; NDCG uses all grades).
LTR_CACHE = INDEXES_DIR / "ltr" / "validation"
OWN_CACHE = INDEXES_DIR / "errors" / "validation.json"
REPORT_PATH = PROJECT_ROOT / "quality" / "error_analysis.json"
FIGURES = PROJECT_ROOT.parent / "docs" / "images" / "error-analysis"

NEGATION = re.compile(r"\b(without|no|not|non|except|excluding)\b")
SIZE_WORDS = {"inch", "inches", "in", "oz", "ounce", "ml", "l", "lb", "lbs", "pack", "pk", "count", "ct", "piece",
              "pieces", "pcs", "gb", "tb", "mm", "cm", "ft", "feet", "xl", "xxl", "xs", "small", "medium", "large",
              "size", "qt", "quart", "gallon", "watt", "w", "volt", "v", "mah", "pair", "set"}
AUDIENCE_WORDS = {"men", "mens", "man", "women", "womens", "woman", "womans", "kids", "kid", "boys", "boy",
                  "girls", "girl", "toddler", "toddlers", "baby", "babies", "unisex", "teen", "teens", "adult", "adults"}


# ------------------------------------------------------------------ inputs

def load_from_ltr_cache(prefix, meta):
    """Per-query served rankings from the learning-to-rank feature files."""
    # Read each array once: indexing an .npz file decompresses the array every time.
    with np.load(prefix.with_suffix(".npz")) as stored:
        if stored["ranking_identity"].item() != json.dumps(meta["rankingIdentity"], sort_keys=True):
            return None
        arrays = {name: stored[name] for name in ("X", "query", "ids")}
    names = list(meta["features"])
    column = {name: names.index(name) for name in ("keyword_rank", "semantic_rank", "semantic_similarity", "reranker_score")}
    rows = defaultdict(list)
    for index, number in enumerate(arrays["query"]):
        rows[int(number)].append(index)
    records = []
    for number, query in enumerate(meta["queries"]):
        indices = rows.get(number, [])          # stored in served (blend) order
        records.append({
            **{k: query[k] for k in ("query", "kind", "family", "grades", "relevant")},
            "ranked": [str(arrays["ids"][i]) for i in indices],
            "signals": {str(arrays["ids"][i]): {name: _clean(arrays["X"][i, c]) for name, c in column.items()}
                        for i in indices},
        })
    return records


def _clean(value):
    value = float(value)
    return None if np.isnan(value) or value >= 200 else value


def run_pipeline(rows, products, encoder_path, reranker_path):
    """Served ranking of every candidate, straight from ProductSearch.search()."""
    from scripts.evaluate_quality import load_product_vectors
    from sentence_transformers import CrossEncoder, SentenceTransformer
    import torch
    from src.evaluation.pipeline import ExactSemanticSearch
    from src.search.product_search import ProductSearch
    from src.semantic.dataset import catalog_fingerprint

    torch.set_num_threads(4)
    encoder = SentenceTransformer(str(encoder_path), local_files_only=True, device="cpu")
    reranker = CrossEncoder(str(reranker_path), local_files_only=True, device="cpu", max_length=256)
    vectors = load_product_vectors(encoder, products, catalog_fingerprint(products), encoder_path)
    engine = ProductSearch(products, ExactSemanticSearch(products, encoder, vectors), reranker)
    records = []
    for number, row in enumerate(rows, start=1):
        results = engine.search(row["query"], limit=1000)["results"]
        records.append({"query": row["query"], "kind": row["kind"], "family": row["query_family"],
                        "grades": row["grades"], "relevant": row["relevant_doc_ids"],
                        "ranked": [r["id"] for r in results],
                        "signals": {r["id"]: {"keyword_rank": r["explanation"]["keywordRank"],
                                              "semantic_rank": r["explanation"]["semanticRank"],
                                              "semantic_similarity": r["explanation"]["semanticSimilarity"],
                                              "reranker_score": r["explanation"]["rerankerScore"]} for r in results}})
        if number % 50 == 0:
            print(f"  {number}/{len(rows)} queries", flush=True)
    return records


# ------------------------------------------------------------------ query types

def content_words(text):
    return [w for w in tokenize(text) if w not in STOP_WORDS and len(w) > 1]


def query_tags(clean_query, kind, brands):
    """Every type a search belongs to. Tags come from the correctly typed query,
    so all typo variants of one query share them (apart from the typo kind)."""
    words = tokenize(clean_query)
    count = len(words)
    tags = [f"length:{'1-2' if count <= 2 else '3-4' if count <= 4 else '5-7' if count <= 7 else '8+'}",
            "clean" if kind == "clean" else f"typo:{kind}"]
    if NEGATION.search(clean_query.lower()):
        tags.append("negation")
    if any(w.isdigit() or re.match(r"^\d", w) for w in words) or set(words) & SIZE_WORDS:
        tags.append("number-or-size")
    if brands is not None and brands.find(clean_query)[0]:
        tags.append("brand")
    if set(words) & ACCESSORY_WORDS or re.search(r"\bfor\s+\w+", clean_query.lower()):
        tags.append("accessory-or-for")
    if parse_color(clean_query):
        tags.append("color")
    if set(words) & AUDIENCE_WORDS:
        tags.append("audience")
    return tags


# ------------------------------------------------------------------ failures

def product_text(product):
    return " ".join(str(product.get(f) or "") for f in ("title", "brand", "representation_text", "description"))


def negated_terms(query):
    """Words the shopper does not want: 'belt without buckle' -> {'buckle'}."""
    match = re.search(r"\b(?:without|no|not|non|except|excluding)\b\s+((?:\w+\s*){1,2})", query.lower())
    return set(content_words(match.group(1))) if match else set()


def numbers(text):
    return set(re.findall(r"\d+(?:\.\d+)?", text.lower()))


def head_word(query):
    """The product type, usually the last main word: 'red running shoes for men' -> 'shoes'.

    Words after 'for', 'with' or 'without' describe use or extras, and audience,
    size and number words are not product types."""
    main = re.split(r"\b(?:for|with|without|no|not|non)\b", query.lower())[0] or query.lower()
    words = [w for w in content_words(main)
             if not re.match(r"^\d", w) and w not in AUDIENCE_WORDS and w not in SIZE_WORDS]
    return words[-1] if words else None


def stem(word):
    return word[:-1] if word.endswith("s") and len(word) > 3 else word


def failure_cause(record, clean_query, by_id, brands):
    """Why a failed search failed. Retrieval misses never found a relevant product;
    ranking misses found one but put something else first."""
    relevant = set(record["relevant"])
    positions = [i for i, pid in enumerate(record["ranked"]) if pid in relevant]
    if not positions:
        return "retrieval-miss", None
    top = by_id.get(record["ranked"][0], {})
    top_words = {stem(w) for w in tokenize(product_text(top))}
    if negated_terms(clean_query) & {w for w in tokenize(product_text(top))}:
        return "ranking:negation-ignored", positions[0] + 1
    wanted = numbers(clean_query)
    if wanted and not wanted & numbers(product_text(top)):
        return "ranking:number-or-size", positions[0] + 1
    brand = brands.find(clean_query)[0] if brands is not None else None
    if brand and normalize_brand(top.get("brand")) and not normalize_brand(top.get("brand")).startswith(brand["value"]):
        return "ranking:wrong-brand", positions[0] + 1
    head = head_word(clean_query)
    if head and stem(head) not in top_words:
        return "ranking:wrong-product-type", positions[0] + 1
    top_grade = record["grades"].get(record["ranked"][0])
    if top_grade == 2:
        return "ranking:substitute-first", positions[0] + 1
    if top_grade is None:
        # ESCI judged only some products per query; this one may be fine.
        return "ranking:unjudged-first", positions[0] + 1
    return "ranking:other", positions[0] + 1


def top_label_status(record):
    """Were the top results actually judged wrong, or never judged at all?"""
    judged = [pid in record["grades"] for pid in record["ranked"][:TOP]]
    return "all judged" if all(judged) else "none judged" if not any(judged) else "some unjudged"


def position_bucket(position):
    return None if position is None else "6-10" if position <= 10 else "11-20" if position <= 20 else "21+"


# ------------------------------------------------------------------ statistics

def family_means(values, families):
    groups = defaultdict(list)
    for value, family in zip(values, families):
        groups[family].append(value)
    return np.array([np.mean(v) for v in groups.values()])


def bootstrap_mean(values, families, rng, rounds=BOOTSTRAP):
    """Mean with a 95% interval, resampling whole query families."""
    per_family = family_means(values, families)
    if len(per_family) < 2:
        return float(np.mean(values)), [float("nan"), float("nan")]
    samples = rng.choice(per_family, size=(rounds, len(per_family))).mean(axis=1)
    return float(np.mean(values)), [float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))]


def bootstrap_difference(inside, inside_families, outside, outside_families, rng, rounds=BOOTSTRAP):
    """Mean(inside) - mean(outside) with a 95% interval (families resampled per group)."""
    a, b = family_means(inside, inside_families), family_means(outside, outside_families)
    if len(a) < 2 or len(b) < 2:
        return float(np.mean(inside) - np.mean(outside)), [float("nan"), float("nan")]
    samples = (rng.choice(a, size=(rounds, len(a))).mean(axis=1) - rng.choice(b, size=(rounds, len(b))).mean(axis=1))
    return float(np.mean(inside) - np.mean(outside)), [float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))]


# ------------------------------------------------------------------ figures

def plot_quality_by_type(segments, overall, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = sorted(segments, key=lambda s: s["ndcg"])
    fig, ax = plt.subplots(figsize=(8, 0.38 * len(rows) + 1.2))
    y = np.arange(len(rows))
    colors = ["#c0392b" if s["significantlyWorse"] else "#2a78d6" if s["significantlyBetter"] else "#8a96a8" for s in rows]
    ax.barh(y, [s["ndcg"] for s in rows], color=colors, height=0.6)
    ax.errorbar([s["ndcg"] for s in rows], y, xerr=[[s["ndcg"] - s["interval95"][0] for s in rows],
                                                    [s["interval95"][1] - s["ndcg"] for s in rows]],
                fmt="none", ecolor="#29352e", elinewidth=1, capsize=2)
    ax.axvline(overall, color="#29352e", linestyle="--", linewidth=1)
    ax.set_yticks(y, [f"{s['tag']}  (n={s['queries']})" for s in rows], fontsize=8)
    ax.set_xlabel("NDCG@10 (95% CI over query families); dashed line = all searches")
    ax.set_title("Search quality by query type (ESCI validation)", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_similarity_gap(found, missed, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 3.4))
    bins = np.linspace(0, 1, 31)
    ax.hist(found, bins=bins, alpha=0.65, label=f"relevant product in top 5 (n={len(found)})", color="#2a78d6")
    ax.hist(missed, bins=bins, alpha=0.65, label=f"failed searches (n={len(missed)})", color="#eb6834")
    ax.set_xlabel("Cosine similarity: search vs. its closest relevant product")
    ax.set_ylabel("Searches")
    ax.set_title("Failed searches are farther from their products in meaning", fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# Broad product groups for colouring the map, matched on words anywhere in the
# title (titles usually end with a colour or size, so the last word is no help).
PRODUCT_GROUPS = (
    ("shoes", {"shoe", "shoes", "sneaker", "sneakers", "boot", "boots", "sandal", "sandals", "slipper", "slippers"}),
    ("clothing", {"shirt", "tshirt", "tee", "dress", "pants", "leggings", "shorts", "jacket", "hoodie", "sweater",
                  "socks", "bra", "underwear", "costume", "jeans", "skirt", "top"}),
    ("phone & tablet accessories", {"case", "cover", "protector", "iphone", "galaxy", "ipad"}),
    ("cables & chargers", {"cable", "charger", "adapter", "usb", "hdmi", "charging"}),
    ("bags", {"bag", "backpack", "tote", "wallet", "purse", "luggage"}),
    ("toys & games", {"toy", "toys", "lego", "puzzle", "game", "doll", "plush"}),
    ("kitchen", {"kitchen", "mug", "cup", "pan", "knife", "bottle", "container", "plate", "bowl"}),
    ("beauty & health", {"hair", "skin", "cream", "shampoo", "makeup", "nail", "vitamin", "supplement"}),
)


def product_group(title):
    words = set(tokenize(title))
    return next((name for name, keys in PRODUCT_GROUPS if words & keys), "other")


def plot_embedding_map(coordinates, types, highlight, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 6))
    palette = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#a0522d"]
    names = [name for name, _ in Counter(t for t in types if t != "other").most_common(len(palette))]
    for name, color in zip(names, palette):
        mask = np.array([t == name for t in types])
        ax.scatter(coordinates[mask, 0], coordinates[mask, 1], s=4, color=color, alpha=0.6, label=name)
    rest = np.array([t not in names for t in types])
    ax.scatter(coordinates[rest, 0], coordinates[rest, 1], s=3, color="#c8ccd2", alpha=0.4, label="other")
    ax.scatter(coordinates[highlight, 0], coordinates[highlight, 1], s=26, facecolors="none", edgecolors="#c0392b",
               linewidths=0.9, label="relevant product of a failed search")
    ax.set_xticks([]), ax.set_yticks([])
    ax.set_title("UMAP of product embeddings (meaning space), coloured by product group", fontsize=10)
    ax.legend(fontsize=7, markerscale=2.5, frameon=False, loc="lower left", ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ------------------------------------------------------------------ main

def read_matching_cache(path, identity):
    try:
        cached = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return cached if isinstance(cached, dict) and cached.get("rankingIdentity") == identity else None


def load_rankings(rows, products, encoder_path, reranker_path, *, force=False):
    identity = ranking_cache_identity(products, rows, encoder_path, reranker_path)
    if not force:
        cached = read_matching_cache(OWN_CACHE, identity)
        if cached is not None and isinstance(cached.get("records"), list):
            return cached["records"]
        meta = read_matching_cache(LTR_CACHE.with_suffix(".json"), identity)
        if meta is not None and LTR_CACHE.with_suffix(".npz").is_file():
            try:
                records = load_from_ltr_cache(LTR_CACHE, meta)
            except (OSError, ValueError, KeyError, BadZipFile):
                records = None
            if records is not None:
                print(f"Reusing rankings from {LTR_CACHE}.npz", flush=True)
                return records

    print(f"Running the baseline pipeline on {len(rows)} validation queries...", flush=True)
    records = run_pipeline(rows, products, encoder_path, reranker_path)
    OWN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", dir=OWN_CACHE.parent, delete=False) as output:
        temporary_path = Path(output.name)
        try:
            json.dump({"rankingIdentity": identity, "records": records}, output)
            output.close()
            temporary_path.replace(OWN_CACHE)
        finally:
            temporary_path.unlink(missing_ok=True)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="store_true", help="Rerun the served pipeline instead of reusing a cache.")
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args()
    rng = np.random.default_rng(SEED)

    from scripts.evaluate_quality import model_path
    from src.semantic.dataset import load_catalog, read_jsonl
    products = load_catalog(DATASET_DIR / "prepared" / "products.json")
    by_id = {p["id"]: p for p in products}
    rows = read_jsonl(DATASET_DIR / "prepared" / "validation.jsonl")
    clean_text = {row["query_family"]: row["clean_query"] for row in rows}

    encoder_path = model_path("SEMANTIC_MODEL_PATH", "models/colab-export/esci-minilm-20k")
    reranker_path = model_path("RERANKER_MODEL_PATH", "models/ms-marco-MiniLM-L6-v2")
    records = load_rankings(rows, products, encoder_path, reranker_path, force=args.run)

    brands = BrandIndex(products)
    for record in records:
        record["clean"] = clean_text.get(record["family"], record["query"])
        record["tags"] = query_tags(record["clean"], record["kind"], brands)
        record["metrics"] = query_metrics(record["ranked"][:10], record["grades"], record["relevant"])
        record["failed"] = not set(record["ranked"][:TOP]) & set(record["relevant"])
        # Lenient view: even a Substitute (a close alternative) in the top 5 counts.
        record["failedLenient"] = not any(record["grades"].get(pid, 0) >= 2 for pid in record["ranked"][:TOP])
    families = [r["family"] for r in records]
    ndcg = [r["metrics"]["ndcg@10"] for r in records]
    overall, overall_ci = bootstrap_mean(ndcg, families, rng)

    # 1. Quality by query type.
    segments = []
    for tag in sorted({t for r in records for t in r["tags"]}):
        inside = [r for r in records if tag in r["tags"]]
        outside = [r for r in records if tag not in r["tags"]]
        if len({r["family"] for r in inside}) < 5:
            continue
        mean, interval = bootstrap_mean([r["metrics"]["ndcg@10"] for r in inside], [r["family"] for r in inside], rng)
        diff, diff_ci = bootstrap_difference([r["metrics"]["ndcg@10"] for r in inside], [r["family"] for r in inside],
                                             [r["metrics"]["ndcg@10"] for r in outside], [r["family"] for r in outside], rng)
        segments.append({"tag": tag, "queries": len(inside), "families": len({r["family"] for r in inside}),
                         "ndcg": mean, "interval95": interval,
                         **{m: float(np.mean([r["metrics"][m] for r in inside])) for m in METRIC_NAMES if m != "ndcg@10"},
                         "failRate": float(np.mean([r["failed"] for r in inside])),
                         "differenceVsRest": diff, "differenceInterval95": diff_ci,
                         "significantlyWorse": bool(diff_ci[1] < 0), "significantlyBetter": bool(diff_ci[0] > 0)})

    # 2. Failure taxonomy.
    causes = Counter()
    positions = Counter()
    label_status = Counter()
    examples = defaultdict(list)
    for record in records:
        if not record["failed"]:
            continue
        cause, position = failure_cause(record, record["clean"], by_id, brands)
        record["cause"] = cause
        causes[cause] += 1
        if position is not None:
            positions[position_bucket(position)] += 1
            label_status[top_label_status(record)] += 1
        if len(examples[cause]) < 4 and record["kind"] == "clean":
            relevant = [pid for pid in record["ranked"] if pid in set(record["relevant"])]
            examples[cause].append({
                "query": record["query"],
                "topResult": by_id.get(record["ranked"][0], {}).get("title", "")[:120] if record["ranked"] else None,
                "bestRelevant": by_id.get(relevant[0], {}).get("title", "")[:120] if relevant else
                by_id.get(record["relevant"][0], {}).get("title", "")[:120],
                "bestRelevantPosition": position,
            })
    failed = [r for r in records if r["failed"]]
    in_candidates = [r for r in records if set(r["ranked"]) & set(r["relevant"])]

    # 3. Meaning gap: how close is each search to its closest relevant product?
    similarity = {"found": [], "missed": []}
    figures = {}
    if not args.no_figures:
        FIGURES.mkdir(parents=True, exist_ok=True)
        plot_quality_by_type(segments, overall, FIGURES / "quality-by-type.png")
        figures["qualityByType"] = "docs/images/error-analysis/quality-by-type.png"
        similarity, umap_note = meaning_figures(records, products, by_id)
        figures["similarityGap"] = "docs/images/error-analysis/similarity-gap.png"
        figures["embeddingMap"] = "docs/images/error-analysis/embedding-map.png"
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "split": "validation",
        "commit": _commit(),
        "definition": {"failure": f"no Exact product in the top {TOP} (the prepared files count only Exact as relevant)",
                       "lenientFailure": f"not even a Substitute (or Exact) in the top {TOP}",
                       "interval": f"95% bootstrap over query families, {BOOTSTRAP:,} resamples",
                       "tags": "from the correctly typed query, so typo variants share them"},
        "overall": {"queries": len(records), "families": len(set(families)), "ndcg": overall, "interval95": overall_ci,
                    "failRate": len(failed) / len(records),
                    "lenientFailRate": float(np.mean([r["failedLenient"] for r in records])),
                    "relevantInCandidates": len(in_candidates) / len(records)},
        "segments": sorted(segments, key=lambda s: s["ndcg"]),
        "failures": {"total": len(failed),
                     "causes": [{"cause": c, "count": n, "share": n / len(failed)} for c, n in causes.most_common()],
                     "rankingMissPositions": dict(positions),
                     "rankingMissTopLabels": dict(label_status),
                     "clean": Counter(r["cause"] for r in failed if r["kind"] == "clean"),
                     "typo": Counter(r["cause"] for r in failed if r["kind"] != "clean"),
                     "examples": examples},
        "meaningGap": {k: {"searches": len(v), "median": float(np.median(v)) if v else None} for k, v in similarity.items()},
        "figures": figures,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=list) + "\n")

    print(f"\nAll: NDCG@10 {overall:.3f} [{overall_ci[0]:.3f}, {overall_ci[1]:.3f}]; failures {len(failed)}/{len(records)}; "
          f"relevant product among candidates for {len(in_candidates) / len(records):.0%}")
    for s in report["segments"]:
        flag = "WORSE" if s["significantlyWorse"] else "better" if s["significantlyBetter"] else ""
        print(f"  {s['tag']:22} n={s['queries']:4} NDCG {s['ndcg']:.3f} [{s['interval95'][0]:.3f},{s['interval95'][1]:.3f}] "
              f"vs rest {s['differenceVsRest']:+.3f} [{s['differenceInterval95'][0]:+.3f},{s['differenceInterval95'][1]:+.3f}] {flag}")
    print("Failure causes: " + ", ".join(f"{c} {n}" for c, n in causes.most_common()))
    print(f"Lenient failure rate (no Exact or Substitute in top {TOP}): {report['overall']['lenientFailRate']:.1%}")
    print(f"Ranking misses by best Exact position: {dict(positions)}; top-{TOP} labels: {dict(label_status)}")
    if similarity.get("found"):
        print(f"Meaning gap (median cosine): found {np.median(similarity['found']):.3f}, failed {np.median(similarity['missed']):.3f}")
    print(f"Report: {REPORT_PATH}")


def meaning_figures(records, products, by_id):
    """Cosine between each search and its closest relevant product, plus a UMAP map."""
    from scripts.evaluate_quality import model_path
    from sentence_transformers import SentenceTransformer
    import glob

    vectors = np.load(sorted(glob.glob(str(INDEXES_DIR / "quality" / "product_vectors-*.npy")))[-1])
    index = {p["id"]: i for i, p in enumerate(products)}
    encoder = SentenceTransformer(str(model_path("SEMANTIC_MODEL_PATH", "models/colab-export/esci-minilm-20k")),
                                  local_files_only=True, device="cpu")
    queries = encoder.encode([r["query"] for r in records], normalize_embeddings=True, show_progress_bar=False)
    found, missed = [], []
    for record, vector in zip(records, queries):
        rows = [index[p] for p in record["relevant"] if p in index]
        if rows:
            (missed if record["failed"] else found).append(float((vectors[rows] @ vector).max()))
    plot_similarity_gap(found, missed, FIGURES / "similarity-gap.png")

    # UMAP on a sample: every relevant product of a validation query plus random others.
    import umap
    rng = np.random.default_rng(SEED)
    relevant = sorted({index[p] for r in records for p in r["relevant"] if p in index})
    others = rng.choice(len(products), size=min(4000, len(products)), replace=False)
    sample = np.array(sorted(set(relevant) | set(others.tolist())))
    coordinates = umap.UMAP(n_neighbors=20, min_dist=0.1, metric="cosine", random_state=SEED).fit_transform(vectors[sample])
    failed_targets = {index[p] for r in records if r["failed"] for p in r["relevant"] if p in index}
    types = [product_group(products[i].get("title", "")) for i in sample]
    highlight = np.array([i in failed_targets for i in sample])
    plot_embedding_map(coordinates, types, highlight, FIGURES / "embedding-map.png")
    return {"found": found, "missed": missed}, None


def _commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


if __name__ == "__main__":
    main()
