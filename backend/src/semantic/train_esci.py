"""Fine tune MiniLM on real ESCI pairs and their typo views with masked negatives."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import time

from src.config import DATASET_DIR, EMBEDDING_MODEL_NAME, PROJECT_ROOT
from src.semantic.dataset import grouped_batches, read_jsonl
from src.semantic.prepare_esci import normalize_query


def negative_mask(rows):
    """Other E/S/C matches and duplicate positives cannot become negatives."""
    document_ids = [row["product_id"] for row in rows] + [row["negative_id"] for row in rows]
    mask = []
    for index, row in enumerate(rows):
        protected = set(row["relevant_product_ids"]) | {row["product_id"]}
        if row["negative_id"] in protected:
            raise ValueError("A labeled relevant product was supplied as a hard negative.")
        mask.append([
            column == index or product_id not in protected
            for column, product_id in enumerate(document_ids)
        ])
    return mask


def contrastive_loss(query_vectors, positive_vectors, negative_vectors, rows):
    """Teach queries to favor the correct product over allowed negative products."""
    import torch
    import torch.nn.functional as functional

    query_vectors = functional.normalize(query_vectors, dim=-1)
    documents = functional.normalize(torch.cat((positive_vectors, negative_vectors)), dim=-1)
    logits = (query_vectors @ documents.T) * 20.0
    allowed = torch.tensor(negative_mask(rows), dtype=torch.bool, device=logits.device)
    logits = logits.masked_fill(~allowed, float("-inf"))
    return functional.cross_entropy(
        logits, torch.arange(len(rows), device=logits.device),
    )


def validate_training_rows(rows, manifest, held_rows):
    """Reject query leakage, incorrect labels, and unexpected row counts."""
    held = set(manifest["reserved_validation_families"]) | set(manifest["official_test_families"])
    held.update(normalize_query(row["query"]) for row in held_rows)
    for row in rows:
        if row["query_family"] in held or normalize_query(row["query"]) in held:
            raise ValueError("A training query overlaps a held-out query family.")
        if row["product_id"] not in row["relevant_product_ids"]:
            raise ValueError("An Exact positive is absent from its relevance labels.")
        if row["negative_id"] in row["relevant_product_ids"]:
            raise ValueError("A hard negative has a relevant label.")
    clean = sum(row["kind"] == "clean" for row in rows)
    if clean != manifest["clean_training_pairs"] or len(rows) != manifest["augmented_training_pairs"]:
        raise ValueError("Prepared row counts differ from the dataset manifest.")


def parse_arguments():
    """Read options supplied after the command name."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATASET_DIR / "prepared")
    parser.add_argument("--model", default=EMBEDDING_MODEL_NAME)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "models" / "esci-minilm-20k")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--checkpoint-every", type=int, default=250)
    parser.add_argument("--device", default=None)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser, parser.parse_args()


def train_batch(model, optimizer, scheduler, rows):
    """Encode one batch, calculate loss, and update the model weights."""
    import torch
    from sentence_transformers import InputExample
    from sentence_transformers.util import batch_to_device

    examples = [
        InputExample(texts=[row["query"], row["positive"], row["negative"]])
        for row in rows
    ]
    features, _ = model.smart_batching_collate(examples)
    features = [batch_to_device(feature, model.device) for feature in features]
    optimizer.zero_grad()
    query_vectors, positive_vectors, negative_vectors = [
        model(feature)["sentence_embedding"] for feature in features
    ]
    loss = contrastive_loss(query_vectors, positive_vectors, negative_vectors, rows)
    if not torch.isfinite(loss):
        raise RuntimeError("Training loss is not finite.")
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    optimizer.step()
    scheduler.step()
    return float(loss.detach().cpu())


def train_model(args, parser):
    """Validate the data, train or resume the model, then save weights and reports."""
    if min(args.epochs, args.batch_size, args.max_length, args.threads, args.checkpoint_every) < 1:
        parser.error("Epoch, batch, token, thread, and checkpoint counts must be positive.")
    if args.batch_size < 2 or args.learning_rate <= 0:
        parser.error("Use a batch size >= 2 and a positive learning rate.")
    output = args.output_dir.resolve()
    if (output / "modules.json").exists() and not args.resume:
        parser.error("A model already exists at the output. Choose another directory.")
    # 1. Validate the prepared data before loading a model.
    manifest_bytes = (args.data_dir / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    rows = read_jsonl(args.data_dir / "train.jsonl")
    held_rows = read_jsonl(args.data_dir / "validation.jsonl") + read_jsonl(args.data_dir / "test.jsonl")
    validate_training_rows(rows, manifest, held_rows)
    batches = [
        batch for epoch in range(args.epochs)
        for batch in grouped_batches(rows, args.batch_size, manifest["seed"] + epoch)
    ]
    total_steps = len(batches)
    if not total_steps:
        parser.error("No usable training batches.")
    config = {
        "dataset_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "base_model": args.model, "epochs": args.epochs, "batch_size": args.batch_size,
        "learning_rate": args.learning_rate, "max_length": args.max_length,
        "seed": manifest["seed"], "total_steps": total_steps,
    }

    import torch
    from sentence_transformers import SentenceTransformer

    # 2. Set up the model, optimizer, and learning-rate schedule.
    torch.set_num_threads(args.threads)
    torch.manual_seed(manifest["seed"])
    random.seed(manifest["seed"])
    model = SentenceTransformer(
        args.model, device=args.device, local_files_only=args.local_files_only,
    )
    model.max_seq_length = args.max_length
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    warmup = max(1, int(total_steps * 0.1))

    def schedule(step):
        if step < warmup:
            return (step + 1) / warmup
        return max(0.0, (total_steps - step) / max(1, total_steps - warmup))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, schedule)
    checkpoint_dir = output / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = checkpoint_dir / "latest.pt"
    step, loss_sum, trained_examples = 0, 0.0, 0
    # 3. Restore the saved state when resuming a previous run.
    if args.resume:
        state = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        if state["config"] != config:
            parser.error("Resume settings or the dataset differ from the saved checkpoint.")
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        scheduler.load_state_dict(state["scheduler"])
        torch.set_rng_state(state["torch_rng"])
        if model.device.type == "mps" and state.get("mps_rng") is not None:
            torch.mps.set_rng_state(state["mps_rng"])
        if model.device.type == "cuda" and state.get("cuda_rng") is not None:
            torch.cuda.set_rng_state_all(state["cuda_rng"])
        step, loss_sum = state["step"], state["loss_sum"]
        trained_examples = state["trained_examples"]
        print(f"Resuming from step {step}/{total_steps}", flush=True)

    started = time.monotonic()
    start_step = step

    def progress(status):
        elapsed = time.monotonic() - started
        completed = step - start_step
        remaining = (total_steps - step) * elapsed / completed if completed else None
        return {
            **config, "status": status, "step": step, "device": str(model.device),
            "trained_examples": trained_examples, "total_prepared_examples": len(rows),
            "elapsed_seconds_this_run": elapsed, "estimated_seconds_remaining": remaining,
            "mean_loss": loss_sum / step if step else None,
            "source_revision": manifest["source_revision"],
        }

    def save_checkpoint():
        state = {
            "config": config, "model": model.state_dict(), "optimizer": optimizer.state_dict(),
            "scheduler": scheduler.state_dict(), "step": step, "loss_sum": loss_sum,
            "trained_examples": trained_examples, "torch_rng": torch.get_rng_state(),
            "mps_rng": torch.mps.get_rng_state() if model.device.type == "mps" else None,
            "cuda_rng": torch.cuda.get_rng_state_all() if model.device.type == "cuda" else None,
        }
        temporary = checkpoint_path.with_suffix(".part")
        torch.save(state, temporary)
        temporary.replace(checkpoint_path)

    print(f"Training {len(rows):,} examples ({manifest['clean_training_pairs']:,} clean + typo views), "
          f"{total_steps} steps on {model.device}.", flush=True)
    # 4. Train each batch and save progress regularly.
    model.train()
    try:
        while step < total_steps:
            batch_rows = [rows[index] for index in batches[step]]
            loss_value = train_batch(model, optimizer, scheduler, batch_rows)
            step += 1
            loss_sum += loss_value
            trained_examples += len(batch_rows)
            if step == 1 or step % 25 == 0 or step == total_steps:
                status = progress("training")
                (output / "progress.json").write_text(json.dumps(status, indent=2) + "\n")
                eta = status["estimated_seconds_remaining"] or 0
                print(f"Step {step}/{total_steps}, loss {loss_value:.4f}, "
                      f"remaining approximately {eta / 60:.1f} minutes", flush=True)
            if step % args.checkpoint_every == 0 or step == total_steps:
                save_checkpoint()
            if step == total_steps // 2:
                model.save_pretrained(str(checkpoint_dir / "halfway"))
                (checkpoint_dir / "halfway" / "checkpoint_info.json").write_text(
                    json.dumps({"step": step, "config": config}, indent=2) + "\n",
                )
    except BaseException:
        save_checkpoint()
        (output / "progress.json").write_text(json.dumps(progress("interrupted"), indent=2) + "\n")
        print(f"Saved resumable checkpoint after step {step}.", flush=True)
        raise
    # 5. Save the finished model and its training report.
    model.eval()
    model.save_pretrained(str(output))
    report = {
        **progress("trained"), "clean_training_pairs": manifest["clean_training_pairs"],
        "training_query_families": manifest["training_query_families"],
        "training_source": manifest["source"], "loss": "masked contrastive with labeled Irrelevant hard negatives",
        "candidate_status": "evaluate on validation before selecting; test after selection",
        "unbatched_examples": len(rows) * args.epochs - trained_examples,
    }
    (output / "training_report.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "progress.json").write_text(json.dumps(progress("trained"), indent=2) + "\n")
    print(f"Saved fine tuned model at {output}", flush=True)


def main():
    parser, args = parse_arguments()
    train_model(args, parser)


if __name__ == "__main__":
    main()
