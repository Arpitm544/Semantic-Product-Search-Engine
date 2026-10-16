"""Train a candidate MiniLM retriever on clean and misspelled product queries."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import random

from src.config import EMBEDDING_MODEL_NAME, PROJECT_ROOT, PROCESSED_DATA_PATH
from src.semantic.prepare_training import (
    TRAINING_DIR, catalog_fingerprint, load_catalog, read_jsonl,
)


def grouped_batches(rows, batch_size, seed):
    """One category per batch to reduce false negatives among similar products."""
    if batch_size < 2:
        raise ValueError("Contrastive learning requires a batch size of at least two.")
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        groups[row["negative_group"]].append(index)
    if len(groups) < 2:
        raise ValueError("Training requires at least two negative groups/categories.")
    rng = random.Random(seed)
    for indices in groups.values():
        rng.shuffle(indices)
    batches = []
    while True:
        active = [group for group, indices in groups.items() if indices]
        if len(active) < 2:
            break
        rng.shuffle(active)
        # Prioritize large groups so one category is less likely to be left alone.
        active.sort(key=lambda group: len(groups[group]), reverse=True)
        batches.append([groups[group].pop() for group in active[:batch_size]])
    return batches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=TRAINING_DIR)
    parser.add_argument("--catalog", type=Path, default=PROCESSED_DATA_PATH)
    parser.add_argument("--model", default=EMBEDDING_MODEL_NAME)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "models" / "typo-minilm-candidate")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-steps", type=int, default=None, help="Optional short experiment.")
    parser.add_argument("--device", default=None, help="cpu, cuda, or mps; auto-detected by default.")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()
    if args.epochs < 1 or args.learning_rate <= 0 or args.threads < 1:
        parser.error("epochs, learning rate, and threads must be positive.")
    if args.max_steps is not None and args.max_steps < 1:
        parser.error("max-steps must be positive.")
    if (args.output_dir / "modules.json").exists():
        parser.error("The output already contains a model. Choose a new output directory.")

    products = load_catalog(args.catalog)
    manifest = json.loads((args.data_dir / "manifest.json").read_text())
    if manifest["catalog_sha256"] != catalog_fingerprint(products):
        parser.error("The catalog changed; prepare the training data again.")
    rows = read_jsonl(args.data_dir / "train.jsonl")
    train_ids = {row["product_id"] for row in rows}
    held_ids = set(manifest["product_ids"]["validation"] + manifest["product_ids"]["test"]
                   + manifest["reserved_eval_product_ids"])
    if train_ids & held_ids:
        parser.error("Training data contains held-out products.")
    held_queries = {
        row["query"].lower() for split in ("validation", "test")
        for row in read_jsonl(args.data_dir / f"{split}.jsonl")
    }
    if any(row["query"].lower() in held_queries for row in rows):
        parser.error("Training data contains a held-out query.")
    epoch_batches = [grouped_batches(rows, args.batch_size, manifest["seed"] + epoch)
                     for epoch in range(args.epochs)]
    total_steps = sum(len(batches) for batches in epoch_batches)
    if args.max_steps is not None:
        total_steps = min(total_steps, args.max_steps)
    if not total_steps:
        parser.error("No usable contrastive batches.")

    import torch
    from sentence_transformers import InputExample, SentenceTransformer, losses
    from sentence_transformers.util import batch_to_device
    from torch.utils.data import DataLoader

    torch.set_num_threads(args.threads)
    torch.manual_seed(manifest["seed"])
    model = SentenceTransformer(
        args.model, device=args.device, local_files_only=args.local_files_only,
    )
    model.max_seq_length = 128
    examples = [InputExample(texts=[row["query"], row["positive"]]) for row in rows]
    loss_fn = losses.MultipleNegativesRankingLoss(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    warmup_steps = max(1, int(total_steps * 0.1))

    def schedule(step):
        if step < warmup_steps:
            return (step + 1) / warmup_steps
        return max(0.0, (total_steps - step) / max(1, total_steps - warmup_steps))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, schedule)
    step = 0
    losses_seen = []
    print(f"Training on {len(rows)} starter pairs for {total_steps} steps on {model.device}.", flush=True)
    for epoch, batches in enumerate(epoch_batches):
        loader = DataLoader(examples, batch_sampler=batches, collate_fn=model.smart_batching_collate)
        model.train()
        for features, labels in loader:
            optimizer.zero_grad()
            features = [batch_to_device(feature, model.device) for feature in features]
            labels = labels.to(model.device)
            loss = loss_fn(features, labels)
            if not torch.isfinite(loss):
                raise RuntimeError("Non-finite loss; no model was saved.")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            step += 1
            losses_seen.append(loss.item())
            if step == 1 or step % 10 == 0 or step == total_steps:
                print(f"Epoch {epoch + 1}, step {step}/{total_steps}, loss {loss.item():.4f}", flush=True)
            if step >= total_steps:
                break
        if step >= total_steps:
            break
    model.eval()
    output = args.output_dir.resolve()
    model.save_pretrained(str(output))
    training_report = {
        "base_model": args.model, "steps": step, "epochs_requested": args.epochs,
        "pairs": len(rows), "device": str(model.device), "seed": manifest["seed"],
        "learning_rate": args.learning_rate, "batch_size": args.batch_size,
        "mean_training_loss": sum(losses_seen) / len(losses_seen),
        "catalog_sha256": manifest["catalog_sha256"],
        "training_source": manifest["source"],
        "status": "candidate; evaluate before configuring the API to use it",
        "examples_not_batched": [
            len(rows) - sum(len(batch) for batch in batches) for batches in epoch_batches
        ],
    }
    (output / "training_report.json").write_text(json.dumps(training_report, indent=2) + "\n")
    # Separate artifacts prevent overwriting the original model's index.
    from src.semantic.vector_search import SemanticVectorSearch

    engine = SemanticVectorSearch(str(output))
    engine._model = model
    engine.fit(products)
    engine.save(output / "faiss_index.bin", output / "faiss_id_map.pkl")
    print(f"Saved candidate model and rebuilt FAISS index at {output}", flush=True)
    print("Run evaluate_typos before activating this model.", flush=True)


if __name__ == "__main__":
    main()
