"""Query-family bootstrap intervals and paired stage randomization tests."""

import numpy as np

from src.evaluation.metrics import METRIC_NAMES

BOOTSTRAP_SAMPLES = 5000
RANDOMIZATION_SAMPLES = 10000
CONFIDENCE_LEVEL = 0.95
ALPHA = 0.01
SEED = 42

# Semantic-only is a parallel baseline. Hybrid combines spelling and semantic retrieval.
COMPARISONS = (
    ("keyword", "spelling"),
    ("keyword", "semantic"),
    ("spelling", "hybrid"),
    ("semantic", "hybrid"),
    ("hybrid", "reranked"),
    ("keyword", "reranked"),
)


def intervals(samples):
    tail = (1 - CONFIDENCE_LEVEL) / 2
    return np.quantile(samples, [tail, 1 - tail], axis=0).T


def bootstrap(sums, counts, rng, times=None, families=None):
    """Sample whole families and preserve the query-weighted mean of each metric."""
    means, latency = [], []
    probabilities = np.full(len(counts), 1 / len(counts))
    for start in range(0, BOOTSTRAP_SAMPLES, 256):
        weights = rng.multinomial(len(counts), probabilities, size=min(256, BOOTSTRAP_SAMPLES - start))
        means.append((weights @ sums) / (weights @ counts)[:, None])
        if times is not None:
            for family_weights in weights:
                sampled = np.repeat(times, family_weights[families], axis=0)
                latency.append(np.vstack((np.quantile(sampled, [0.5, 0.95], axis=0), sampled.mean(axis=0))))
    return np.concatenate(means), np.asarray(latency)


def paired_p_values(differences, rng):
    """Two-sided test of the query-weighted mean difference, swapping stages by family."""
    observed = np.abs(differences.sum(axis=0))
    extreme = np.zeros_like(observed, dtype=int)
    for start in range(0, RANDOMIZATION_SAMPLES, 256):
        signs = 2 * rng.integers(0, 2, size=(min(256, RANDOMIZATION_SAMPLES - start), len(differences))) - 1
        permuted = np.abs(signs @ differences)
        ties = np.isclose(permuted, observed, rtol=1e-12, atol=1e-12)
        extreme += np.count_nonzero((permuted > observed) | ties, axis=0)
    return (extreme + 1) / (RANDOMIZATION_SAMPLES + 1)


def infer(per_query, latencies, stages):
    """Add uncertainty to the stage summaries and return segment-specific comparisons."""
    rng = np.random.default_rng(SEED)
    stage_ids = [stage["id"] for stage in stages]
    segments = ("all", "clean", "typo")
    kinds = sorted({row["kind"] for row in per_query if row["bucket"] == "typo"})
    tests = {segment: [] for segment in segments}
    available_tests = []
    for group in (*segments, *kinds):
        rows = [row for row in per_query if group in ("all", row["bucket"], row["kind"])]
        families_by_id = {family: index for index, family in enumerate(dict.fromkeys(row["family"] for row in rows))}
        families = np.array([families_by_id[row["family"]] for row in rows], dtype=int)
        counts = np.bincount(families)
        scores = np.array([[row["stages"][stage_id][metric]
                            for stage_id in stage_ids for metric in METRIC_NAMES] for row in rows])

        for stage in stages:
            summary = stage["metrics"][group] if group in segments else stage["byTypoKind"][group]
            summary["families"] = len(counts)
            summary["confidenceIntervals"] = None
            if group == "all":
                stage["latencyConfidenceIntervals"] = None
        if len(counts) < 2:
            continue

        sums = np.zeros((len(counts), scores.shape[1]))
        np.add.at(sums, families, scores)
        times = np.array([latencies[stage_id] for stage_id in stage_ids]).T if group == "all" else None
        samples, latency_samples = bootstrap(sums, counts, rng, times, families)
        for index, (stage, bounds) in enumerate(zip(stages, intervals(samples).reshape(len(stages), -1, 2))):
            summary = stage["metrics"][group] if group in segments else stage["byTypoKind"][group]
            summary["confidenceIntervals"] = dict(zip(METRIC_NAMES, bounds.tolist()))
            if times is not None:
                bounds = intervals(latency_samples[:, :, index])
                stage["latencyConfidenceIntervals"] = dict(zip(("p50", "p95", "mean"), bounds.tolist()))

        if group not in segments:
            continue
        for baseline, candidate in COMPARISONS:
            width = len(METRIC_NAMES)
            before, after = (stage_ids.index(stage_id) * width for stage_id in (baseline, candidate))
            baseline_columns, candidate_columns = slice(before, before + width), slice(after, after + width)
            differences = sums[:, candidate_columns] - sums[:, baseline_columns]
            deltas = differences.sum(axis=0) / len(rows)
            bounds = intervals(samples[:, candidate_columns] - samples[:, baseline_columns]).tolist()
            p_values = paired_p_values(differences, rng)
            metrics = {}
            for metric, delta, interval, p_value in zip(METRIC_NAMES, deltas, bounds, p_values):
                result = {"delta": float(delta), "confidenceInterval": interval, "pValue": float(p_value)}
                metrics[metric] = result
                available_tests.append(result)
            tests[group].append({"baseline": baseline, "candidate": candidate, "metrics": metrics})

    # Holm controls the family-wise error rate even when segments and metrics overlap.
    adjusted = 0.0
    for rank, result in enumerate(sorted(available_tests, key=lambda test: test["pValue"])):
        adjusted = min(1.0, max(adjusted, (len(available_tests) - rank) * result["pValue"]))
        result.update(adjustedPValue=adjusted, significant=adjusted < ALPHA)
    return {
        "confidenceLevel": CONFIDENCE_LEVEL,
        "alpha": ALPHA,
        "bootstrapSamples": BOOTSTRAP_SAMPLES,
        "randomizationSamples": RANDOMIZATION_SAMPLES,
        "seed": SEED,
        "comparisons": tests,
    }
