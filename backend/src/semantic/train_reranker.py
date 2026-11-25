"""Fine-tune MS MARCO on ESCI, fit Platt scaling, and evaluate on unseen queries."""

import argparse
from collections import defaultdict
from dataclasses import asdict
import json
from pathlib import Path
import random

from src.evaluation.metrics import ndcg_at_k
from src.search.relevance import CALIBRATION_FILE, MAX_LENGTH, PlattScaling, RELEVANCE_THRESHOLD, weights_sha256
from src.semantic.dataset import read_jsonl

BASE_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"
BASE_REVISION = "ce0834f22110de6d9222af7a7a03628121708969"
TRAIN_TARGETS = (0.0, 0.65, 0.85, 1.0)


def load_splits(data):
    splits = {name: read_jsonl(data / f"{name}.jsonl") for name in ("train", "calibration", "test")}
    used_families = set()
    for name, rows in splits.items():
        families = {row["family"] for row in rows}
        if families & used_families or {row["grade"] for row in rows} != {0, 1, 2, 3}:
            raise ValueError(f"{name} needs disjoint query families and all four ESCI grades.")
        used_families.update(families)
    return splits


def train(model, rows, args):
    import torch
    from transformers import get_linear_schedule_with_warmup

    rng = random.Random(args.seed)
    rng.shuffle(rows)
    # Group similar lengths to avoid padding short products to the longest input.
    rows.sort(key=lambda row: min(len(row["query"]) + len(row["text"]), MAX_LENGTH * 4))
    batches = [rows[start:start + args.batch_size] for start in range(0, len(rows), args.batch_size)]
    rng.shuffle(batches)
    optimizer = torch.optim.AdamW(model.model.parameters(), lr=2e-5)
    steps = len(batches)
    scheduler = get_linear_schedule_with_warmup(optimizer, steps // 10, steps)
    mixed_precision = model.device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=mixed_precision)
    model.train()
    for step, batch in enumerate(batches, 1):
        tokens = model.tokenizer([row["query"] for row in batch], [row["text"] for row in batch],
                                 padding=True, truncation=True, max_length=MAX_LENGTH,
                                 pad_to_multiple_of=32,
                                 return_tensors="pt").to(model.device)
        targets = torch.tensor([TRAIN_TARGETS[row["grade"]] for row in batch], device=model.device)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast("cuda", enabled=mixed_precision):
            logits = model.model(**tokens).logits.flatten()
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, targets)
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.model.parameters(), 1.0)
        previous_scale = scaler.get_scale()
        scaler.step(optimizer)
        scaler.update()
        if scaler.get_scale() >= previous_scale:
            scheduler.step()
        if step == 1 or step % 50 == 0 or step == steps:
            print(f"Training step {step}/{steps} · loss {loss.item():.4f}", flush=True)


def predict(model, rows, batch_size):
    import numpy as np

    scores = np.asarray(model.predict([(row["query"], row["text"]) for row in rows],
                                      batch_size=batch_size, show_progress_bar=True), dtype=float)
    if scores.shape != (len(rows),) or not np.isfinite(scores).all():
        raise ValueError("Expected one finite raw logit per pair.")
    return scores


def fit_platt(logits, rows):
    from sklearn.linear_model import LogisticRegression

    fitted = LogisticRegression(C=1e6).fit(logits.reshape(-1, 1), [row["grade"] > 0 for row in rows])
    return PlattScaling(float(fitted.coef_[0, 0]), float(fitted.intercept_[0]))


def ranking_quality(rows, logits):
    groups = defaultdict(list)
    for row, score in zip(rows, logits):
        groups[row["family"]].append((float(score), row["product_id"], row["grade"]))
    return sum(ndcg_at_k([pid for _, pid, _ in sorted(group, key=lambda entry: (-entry[0], entry[1]))],
                         {pid: grade for _, pid, grade in group}) for group in groups.values()) / len(groups)


def calibration_quality(labels, probabilities):
    import numpy as np
    from sklearn.metrics import brier_score_loss, log_loss

    bins = []
    bin_ids = np.minimum((probabilities * 10).astype(int), 9)
    for index in range(10):
        mask = bin_ids == index
        if mask.any():
            bins.append({"bin": index, "count": int(mask.sum()), "mean_probability": float(probabilities[mask].mean()),
                         "observed_relevance": float(labels[mask].mean())})
    return {"brier": float(brier_score_loss(labels, probabilities)), "log_loss": float(log_loss(labels, probabilities)),
            "ece": sum(b["count"] * abs(b["mean_probability"] - b["observed_relevance"]) for b in bins) / len(labels),
            "bins": bins}


def save_diagram(report, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, (curve, support) = plt.subplots(2, 1, figsize=(7.2, 7.4), sharex=True, layout="constrained",
                                             gridspec_kw={"height_ratios": [3, 1]})
    curve.plot([0, 1], [0, 1], "--", color="#777777", label="Perfect calibration")
    for key, name, color, offset in (
        ("uncalibrated", "Fine-tuned sigmoid", "#92613c", -0.019),
        ("platt", "Fine-tuned + Platt", "#235c80", 0.019),
    ):
        metrics = report[key]
        bins = metrics["bins"]
        curve.plot([b["mean_probability"] for b in bins], [b["observed_relevance"] for b in bins],
                   "o-", color=color, label=f"{name} (Brier {metrics['brier']:.3f})")
        support.bar([(b["bin"] + 0.5) / 10 + offset for b in bins], [b["count"] for b in bins],
                    width=0.037, color=color)
    curve.axvline(RELEVANCE_THRESHOLD, color="#909090", linestyle=":", label="20% close-match threshold")
    curve.set(title="Reliability on held-out ESCI test pairs", ylabel="Observed relevant fraction", ylim=(0, 1))
    curve.legend(loc="lower right")
    support.set(xlabel="Predicted probability of relevance", ylabel="Pairs", xlim=(0, 1),
                xticks=[i / 10 for i in range(11)])
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(args):
    import numpy as np
    from scipy.special import expit
    from sentence_transformers import CrossEncoder
    import torch

    splits = load_splits(args.data)
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("Choose an empty output directory for this run.")
    torch.set_num_threads(2)
    torch.manual_seed(args.seed)
    model = CrossEncoder(args.base_model, revision=BASE_REVISION if args.base_model == BASE_MODEL else None,
                         device=args.device, max_length=MAX_LENGTH, activation_fn=torch.nn.Identity())
    test = splits["test"]
    baseline = ranking_quality(test, predict(model, test, args.batch_size))
    train(model, splits["train"], args)
    calibration_rows = splits["calibration"]
    scaling = fit_platt(predict(model, calibration_rows, args.batch_size), calibration_rows)
    logits = predict(model, test, args.batch_size)
    actual = np.asarray([row["grade"] > 0 for row in test], dtype=int)
    calibrated = np.asarray([scaling.probability(score) for score in logits])
    close = calibrated >= RELEVANCE_THRESHOLD
    best_by_query = {}
    for row, probability in zip(test, calibrated):
        family = row["family"]
        best_by_query[family] = max(float(probability), best_by_query.get(family, 0))
    manifest = json.loads((args.data / "manifest.json").read_text())
    report = {
        "dataset": manifest, "base_model": args.base_model, "base_revision": BASE_REVISION if args.base_model == BASE_MODEL else None,
        "training_targets_by_grade": TRAIN_TARGETS, "seed": args.seed, "test_pairs": len(test),
        "base_ndcg_at_10": baseline, "fine_tuned_ndcg_at_10": ranking_quality(test, logits),
        "uncalibrated": calibration_quality(actual, expit(logits)), "platt": calibration_quality(actual, calibrated),
        "close_match": {"threshold": RELEVANCE_THRESHOLD, "pairs_below": int((~close).sum()),
                        "relevant_pairs_below": int(actual[~close].sum()),
                        "queries_all_below": sum(score < RELEVANCE_THRESHOLD for score in best_by_query.values())},
    }
    reports = args.output / "reports"
    reports.mkdir(parents=True)
    save_diagram(report, reports / "reliability.png")
    (reports / "calibration_report.json").write_text(json.dumps(report, indent=2) + "\n")
    destination = args.output / "esci-reranker"
    model.save_pretrained(str(destination), safe_serialization=True)
    metadata = {"method": "platt", "version": 1, **asdict(scaling), "max_length": MAX_LENGTH,
                "relevant_labels": ["E", "S", "C"], "weights_sha256": weights_sha256(destination)}
    (destination / CALIBRATION_FILE).write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Test nDCG@10 {baseline:.4f} → {report['fine_tuned_ndcg_at_10']:.4f}; "
          f"Brier {report['uncalibrated']['brier']:.4f} → {report['platt']['brier']:.4f}", flush=True)
    print(f"Model and reliability report saved to {args.output}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--base-model", default=BASE_MODEL)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("Batch size must be positive.")
    run(args)
