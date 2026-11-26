"""Train a LambdaMART ranker on ESCI features and test it against the current blend.

    .venv/bin/python scripts/ltr_features.py   # first: build the feature files
    .venv/bin/python scripts/train_ltr.py

Protocol (no test data is used for any choice):
- Training data: the ESCI validation split (200 query families, each as one
  clean query and four typo variants). Its products are fully in the catalog,
  and the meaning encoder was not trained on these families.
- Model selection: 5-fold cross-validation grouped by query family, so typo
  variants of the same query never sit on both sides of a fold.
- Final check: the untouched test split (200 other families, 992 queries),
  with 95% bootstrap intervals over families and a paired randomization test
  against the served 25% retrieval / 75% cross-encoder blend.

Writes backend/ranking/ltr_model.json (served without LightGBM, see
src/ranking/learned.py) and backend/ranking/ltr_report.json.
"""
from collections import defaultdict
from datetime import datetime, timezone
import itertools
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np

from src.config import INDEXES_DIR, PROJECT_ROOT
from src.evaluation.metrics import METRIC_NAMES, query_metrics
from src.ranking.features import FEATURE_LABELS, FEATURE_NAMES

FEATURE_DIR = INDEXES_DIR / "ltr"
OUTPUT_DIR = PROJECT_ROOT / "ranking"
SEED = 13
LABEL_GAIN = [0, 1, 3, 7]          # 2^grade - 1, the same gains our NDCG uses
BOOTSTRAP = 10_000
PERMUTATIONS = 10_000
GRID = {"num_leaves": [7, 15, 31], "min_child_samples": [10, 40]}
BASE_PARAMS = {"objective": "lambdarank", "learning_rate": 0.05, "n_estimators": 1000,
               "colsample_bytree": 0.8, "reg_lambda": 1.0, "label_gain": LABEL_GAIN,
               "lambdarank_truncation_level": 20, "random_state": SEED, "verbose": -1}
# The careful check (cross-encoder) and the blend built on it: dropped in the ablation.
RERANKER_FEATURES = ("blend_rank", "reranker_rank", "reranker_score", "reranker_gap", "reranker_z")


# ------------------------------------------------------------------ data

class Split:
    """Feature rows of one split, grouped by query."""

    def __init__(self, name):
        arrays = np.load(FEATURE_DIR / f"{name}.npz", allow_pickle=True)
        meta = json.loads((FEATURE_DIR / f"{name}.json").read_text())
        if tuple(meta["features"]) != FEATURE_NAMES:
            raise SystemExit(f"{name} features are outdated; run scripts/ltr_features.py again.")
        self.X, self.y, self.query, self.ids = arrays["X"], arrays["y"], arrays["query"], arrays["ids"]
        self.queries = meta["queries"]
        self.rows = defaultdict(list)                 # query number -> row indices (in blend order)
        for row, number in enumerate(self.query):
            self.rows[int(number)].append(row)
        self.families = [q["family"] for q in self.queries]

    def subset(self, numbers):
        """Rows, labels and LightGBM group sizes for some queries (with candidates)."""
        numbers = [n for n in numbers if self.rows.get(n)]
        rows = [row for n in numbers for row in self.rows[n]]
        return self.X[rows], self.y[rows], [len(self.rows[n]) for n in numbers], numbers


def columns(names):
    return [FEATURE_NAMES.index(name) for name in names]


# ------------------------------------------------------------------ scoring

def ranked_metrics(split, numbers, scores_for):
    """Per-query metrics when each query's candidates are sorted by `scores_for`."""
    results = []
    for number in numbers:
        rows = split.rows.get(number, [])
        meta = split.queries[number]
        if rows:
            scores = scores_for(rows)
            order = sorted(range(len(rows)), key=lambda i: (-scores[i], i))
            ids = [str(split.ids[rows[i]]) for i in order]
        else:
            ids = []
        results.append(query_metrics(ids[:10], meta["grades"], meta["relevant"]))
    return results


def blend_scores(split):
    position = FEATURE_NAMES.index("blend_rank")
    return lambda rows: -split.X[rows, position]


def model_scores(split, model, feature_columns):
    return lambda rows: model.booster_.predict(split.X[rows][:, feature_columns])


def mean(results, metric="ndcg@10"):
    return float(np.mean([r[metric] for r in results])) if results else 0.0


def summary(results, split, numbers):
    """All metrics overall and for clean / typo queries."""
    def group(keep):
        chosen = [r for r, n in zip(results, numbers) if keep(split.queries[n]["kind"])]
        return {"queries": len(chosen), **{m: mean(chosen, m) for m in METRIC_NAMES}}
    return {"all": group(lambda kind: True), "clean": group(lambda kind: kind == "clean"),
            "typo": group(lambda kind: kind != "clean")}


# ------------------------------------------------------------------ training

def fit(split, numbers, params, feature_columns, eval_numbers=None):
    import lightgbm

    X, y, groups, _ = split.subset(numbers)
    model = lightgbm.LGBMRanker(**params)
    kwargs = {}
    if eval_numbers is not None:
        eX, ey, egroups, _ = split.subset(eval_numbers)
        kwargs = {"eval_set": [(eX[:, feature_columns], ey)], "eval_group": [egroups], "eval_at": [10],
                  "callbacks": [lightgbm.early_stopping(50, verbose=False)]}
    model.fit(X[:, feature_columns], y, group=groups, feature_name=[FEATURE_NAMES[c] for c in feature_columns], **kwargs)
    return model


def cross_validate(split, params, feature_columns, folds=5):
    """Mean held-out NDCG@10 over family-grouped folds, and the best tree counts."""
    from sklearn.model_selection import GroupKFold

    numbers = np.arange(len(split.queries))
    held_out, iterations = [], []
    for train_idx, test_idx in GroupKFold(n_splits=folds).split(numbers, groups=split.families):
        model = fit(split, train_idx.tolist(), params, feature_columns, eval_numbers=test_idx.tolist())
        iterations.append(model.best_iteration_ or params["n_estimators"])
        held_out += ranked_metrics(split, test_idx.tolist(), model_scores(split, model, feature_columns))
    return mean(held_out), int(np.mean(iterations)), held_out


# ------------------------------------------------------------------ significance

def family_differences(split, numbers, base, new, metric="ndcg@10"):
    """Mean per-family difference: typo variants of one query are not independent."""
    by_family = defaultdict(list)
    for result_base, result_new, number in zip(base, new, numbers):
        by_family[split.queries[number]["family"]].append(result_new[metric] - result_base[metric])
    return np.array([np.mean(values) for values in by_family.values()])


def bootstrap_interval(values, rng, rounds=BOOTSTRAP):
    samples = rng.choice(values, size=(rounds, len(values)), replace=True).mean(axis=1)
    return [float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))]


def randomization_p_value(differences, rng, rounds=PERMUTATIONS):
    """Paired test: randomly swap which system each family's result came from."""
    observed = abs(differences.mean())
    signs = rng.choice([-1.0, 1.0], size=(rounds, len(differences)))
    flipped = np.abs((signs * differences).mean(axis=1))
    return float((np.sum(flipped >= observed) + 1) / (rounds + 1))


def compare(split, numbers, base, new, rng):
    report = {}
    for metric in ("ndcg@10", "mrr@10", "hit@5"):
        diffs = family_differences(split, numbers, base, new, metric)
        report[metric] = {"difference": float(diffs.mean()), "interval95": bootstrap_interval(diffs, rng),
                          "pValue": randomization_p_value(diffs, rng)}
    report["families"] = int(len(family_differences(split, numbers, base, new)))
    return report


# ------------------------------------------------------------------ explanation

def shap_importance(model, X):
    """Mean SHAP contribution of each feature on test candidates."""
    contributions = model.booster_.predict(X, pred_contrib=True)[:, :-1]
    order = np.argsort(-np.abs(contributions).mean(axis=0))

    def direction(i):
        """Correlation between a feature's value and its contribution: + means higher helps."""
        known = np.isfinite(X[:, i])
        if known.sum() < 3 or np.std(X[known, i]) == 0 or np.std(contributions[known, i]) == 0:
            return 0.0
        return float(np.corrcoef(X[known, i], contributions[known, i])[0, 1])

    return [{"feature": FEATURE_NAMES[i], "label": FEATURE_LABELS[FEATURE_NAMES[i]],
             "meanAbsolute": float(np.abs(contributions[:, i]).mean()), "direction": direction(i)}
            for i in order]


# ------------------------------------------------------------------ main

def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suffix", default="", help='Feature file suffix, e.g. "-limit30" for a quick check.')
    args = parser.parse_args()
    output_dir = OUTPUT_DIR if not args.suffix else FEATURE_DIR / f"trial{args.suffix}"

    rng = np.random.default_rng(SEED)
    train, test = Split(f"validation{args.suffix}"), Split(f"test{args.suffix}")
    all_columns = list(range(len(FEATURE_NAMES)))
    print(f"Training queries: {len(train.queries)} ({len(set(train.families))} families); "
          f"test queries: {len(test.queries)} ({len(set(test.families))} families)", flush=True)

    # 1. Model selection by cross-validation on the training split only.
    train_numbers = list(range(len(train.queries)))
    cv_baseline = mean(ranked_metrics(train, train_numbers, blend_scores(train)))
    grid = []
    for leaves, min_child in itertools.product(GRID["num_leaves"], GRID["min_child_samples"]):
        params = {**BASE_PARAMS, "num_leaves": leaves, "min_child_samples": min_child}
        score, trees, _ = cross_validate(train, params, all_columns)
        grid.append({"numLeaves": leaves, "minChildSamples": min_child, "cvNdcg10": score, "trees": trees})
        print(f"  CV num_leaves={leaves:2} min_child_samples={min_child:2}: NDCG@10 {score:.4f} ({trees} trees)", flush=True)
    best = max(grid, key=lambda row: row["cvNdcg10"])
    params = {**BASE_PARAMS, "num_leaves": best["numLeaves"], "min_child_samples": best["minChildSamples"],
              "n_estimators": max(20, best["trees"])}
    print(f"  CV baseline (current blend): NDCG@10 {cv_baseline:.4f}", flush=True)

    # 2. Final models on all training queries.
    model = fit(train, train_numbers, params, all_columns)
    no_reranker = [c for c in all_columns if FEATURE_NAMES[c] not in RERANKER_FEATURES]
    ablation = fit(train, train_numbers, params, no_reranker)

    # 3. One look at the untouched test split.
    test_numbers = list(range(len(test.queries)))
    base = ranked_metrics(test, test_numbers, blend_scores(test))
    learned = ranked_metrics(test, test_numbers, model_scores(test, model, all_columns))
    without = ranked_metrics(test, test_numbers, model_scores(test, ablation, no_reranker))
    comparison = compare(test, test_numbers, base, learned, rng)
    ablation_comparison = compare(test, test_numbers, base, without, rng)

    # 4. Explanation and serving cost.
    X_test, _, groups, _ = test.subset(test_numbers)
    importance = shap_importance(model, X_test)
    start = time.perf_counter()
    for size in groups[:200]:
        model.booster_.predict(X_test[:size])
    per_query_ms = (time.perf_counter() - start) * 1000 / min(200, len(groups))

    output_dir.mkdir(parents=True, exist_ok=True)
    dump = model.booster_.dump_model()
    # The server scores with our own tree evaluator; it must agree with LightGBM exactly.
    from src.ranking.learned import TreeModel
    served = TreeModel(dump).predict(X_test[:2000])
    agreement = float(np.abs(served - model.booster_.predict(X_test[:2000])).max())
    if agreement > 1e-6:
        raise SystemExit(f"Served scores differ from LightGBM by {agreement}")
    (output_dir / "ltr_model.json").write_text(json.dumps(dump))
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol": {
            "training": "ESCI validation split: 200 query families x (1 clean + 4 typo variants)",
            "selection": "5-fold cross-validation grouped by query family",
            "test": "ESCI test split, untouched until the final evaluation",
            "significance": f"{BOOTSTRAP:,} family bootstrap resamples; {PERMUTATIONS:,}-round paired randomization test",
            "labels": "Exact 3, Substitute 2, Complement 1, Irrelevant 0; unjudged candidates 0",
        },
        "features": [{"name": n, "label": FEATURE_LABELS[n]} for n in FEATURE_NAMES],
        "candidates": {"trainingRows": int(len(train.y)), "testRows": int(len(test.y))},
        "crossValidation": {"baselineNdcg10": cv_baseline, "grid": grid, "chosen": best},
        "params": {k: v for k, v in params.items() if k not in ("verbose",)},
        "test": {
            "blend": summary(base, test, test_numbers),
            "learned": summary(learned, test, test_numbers),
            "learnedWithoutReranker": summary(without, test, test_numbers),
            "learnedVsBlend": comparison,
            "withoutRerankerVsBlend": ablation_comparison,
        },
        "shap": importance,
        "scoringMsPerQuery": per_query_ms,
        "servedScoreMaxDifference": agreement,
    }
    (output_dir / "ltr_report.json").write_text(json.dumps(report, indent=2) + "\n")

    t = report["test"]
    print(f"\nTest NDCG@10: blend {t['blend']['all']['ndcg@10']:.4f} | learned {t['learned']['all']['ndcg@10']:.4f} | "
          f"learned without careful check {t['learnedWithoutReranker']['all']['ndcg@10']:.4f}")
    c = comparison["ndcg@10"]
    print(f"Learned - blend: {c['difference']:+.4f} (95% CI {c['interval95'][0]:+.4f} to {c['interval95'][1]:+.4f}), p = {c['pValue']:.4f}")
    print("Top features (mean |SHAP|): " + ", ".join(f"{row['feature']} {row['meanAbsolute']:.3f}" for row in importance[:6]))
    print(f"Scoring cost: {per_query_ms:.2f} ms per query (LightGBM). Served evaluator matches within {agreement:.1e}.")
    print(f"Wrote {output_dir / 'ltr_model.json'} and ltr_report.json")


if __name__ == "__main__":
    main()
